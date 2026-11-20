//! Rust implementation of g711xz call recording codec with PyO3 bindings
//! 
//! Matches the exact Python API and test vectors including the 0x7F zero-code rule for mu-law.

use pyo3::prelude::*;
use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::types::PyBytes;
use lzma_turbo::{XzReader, encode_xz, LzmaEncProps};
use lzma_turbo::xz::stream::CheckType;
use byteorder::{LittleEndian, ReadBytesExt, WriteBytesExt};
use std::io::{Read, Cursor};
use thiserror::Error;

const MAGIC: &[u8; 4] = b"CRG7";
const VERSION: u8 = 1;
const CHANNELS: u8 = 2;
const RATE: u32 = 8000;
const HEADER_SIZE: usize = 16;

/// Errors that can occur during g711xz operations
#[derive(Error, Debug)]
pub enum G711xzError {
    #[error("not a valid xz stream: {0}")]
    InvalidXz(String),
    
    #[error("payload is longer than {0} bytes, not a call recording")]
    LongPayload(u64),

    #[error("payload is {0} bytes, shorter than the header")]
    ShortPayload(usize),
    
    #[error("bad magic {0:?}, not a .g711.xz file")]
    BadMagic([u8; 4]),
    
    #[error("unknown format version {0}, this reader knows {1}")]
    UnknownVersion(u8, u8),
    
    #[error("unknown law {0:?}")]
    UnknownLaw(u8),
    
    #[error("channels is {0}, expected {1}")]
    WrongChannels(u8, u8),
    
    #[error("reserved byte is {0}, expected 0")]
    ReservedSet(u8),
    
    #[error("sample rate is {0}, expected {1}")]
    WrongRate(u32, u32),
    
    #[error("damaged: {0} code bytes for {1} frames, expected {2}")]
    DamagedBody(usize, u32, usize),
    
    #[error("PCM is not pure G.711 (mu-law or A-law on both channels), refusing to encode")]
    RefusedEncode,
    
    #[error("not a readable WAV file: {0}")]
    BadWav(String),
    
    #[error("WAV is {0} ch, {1}-bit, {2} Hz; expected 2 ch, 16-bit, 8000 Hz")]
    WrongWavFormat(u16, u16, u32),
    
    #[error(transparent)]
    Io(#[from] std::io::Error),
}

// Raised when the PCM is not pure G.711. A subclass of ValueError, like the
// RefusedError of the Python package, which re-raises it as its own class.
create_exception!(_rust, RefusedError, PyValueError);

impl From<G711xzError> for PyErr {
    fn from(err: G711xzError) -> PyErr {
        match err {
            G711xzError::RefusedEncode => RefusedError::new_err(err.to_string()),
            G711xzError::BadWav(_) | G711xzError::WrongWavFormat(_, _, _) => PyValueError::new_err(err.to_string()),
            _ => PyValueError::new_err(err.to_string()),
        }
    }
}

/// Expansion tables for a given law
#[derive(Clone, Copy)]
struct ExpansionTables {
    low: [u8; 256],
    high: [u8; 256],
}

/// Compression table for a given law
struct CompressionTable {
    table: [u16; 65536],
}

impl ExpansionTables {
    fn new(law: u8) -> Self {
        let mut low = [0u8; 256];
        let mut high = [0u8; 256];
        
        for code in 0u8..=255 {
            let sample = if law == b'u' {
                expand_ulaw(code)
            } else {
                expand_alaw(code)
            } as u16;
            
            low[code as usize] = (sample & 0xFF) as u8;
            high[code as usize] = (sample >> 8) as u8;
        }
        
        Self { low, high }
    }
}

impl CompressionTable {
    fn new(law: u8) -> Self {
        let mut table = [256u16; 65536];
        
        for code in 0u8..=255 {
            let sample = if law == b'u' {
                expand_ulaw(code)
            } else {
                expand_alaw(code)
            } as u16;
            
            let idx = sample as usize;
            if table[idx] == 256 {
                table[idx] = code as u16;
            }
        }
        
        Self { table }
    }
    
    fn encode(&self, sample: u16) -> Result<u8, G711xzError> {
        let code = self.table[sample as usize];
        if code == 256 {
            Err(G711xzError::RefusedEncode)
        } else {
            Ok(code as u8)
        }
    }
}

/// Expand mu-law code to 16-bit signed sample
fn expand_ulaw(code: u8) -> i16 {
    let value = (!code & 0xFF) as i16;
    let magnitude = ((((value & 0x0F) << 3) + 0x84) << ((value >> 4) & 0x07)) - 0x84;
    if value & 0x80 != 0 { -magnitude } else { magnitude }
}

/// Expand A-law code to 16-bit signed sample
fn expand_alaw(code: u8) -> i16 {
    let value = code ^ 0x55;
    let exponent = (value >> 4) & 0x07;
    let mantissa = value & 0x0F;
    
    let magnitude = if exponent == 0 {
        ((mantissa << 4) + 8) as i16
    } else {
        // Use u16 for the intermediate calculation to avoid overflow
        let mantissa_u16 = mantissa as u16;
        let magnitude_u16 = ((mantissa_u16 << 4) + 0x108) << (exponent - 1);
        magnitude_u16 as i16
    };
    
    if value & 0x80 != 0 { magnitude } else { -magnitude }
}

/// Decode g711xz data
fn decode_internal(data: &[u8], max_payload: u64) -> Result<(u8, u32, Vec<u8>), G711xzError> {
    // Decompress xz
    let payload = decompress(data, max_payload)?;
    
    // Parse header
    let (law, frames) = parse_header(&payload)?;
    
    // Get expansion tables
    let tables = ExpansionTables::new(law);
    
    // Decode body
    let body = &payload[HEADER_SIZE..];
    let frames_usize = frames as usize;
    let mut pcm = vec![0u8; frames_usize * 4];

    for i in 0..frames_usize {
        // Left channel code
        let left_code = body[i] as usize;
        pcm[i * 4] = tables.low[left_code];
        pcm[i * 4 + 1] = tables.high[left_code];
        
        // Right channel code
        let right_code = body[frames_usize + i] as usize;
        pcm[i * 4 + 2] = tables.low[right_code];
        pcm[i * 4 + 3] = tables.high[right_code];
    }
    
    Ok((law, frames, pcm))
}

/// Encode PCM to g711xz data
fn encode_internal(pcm: &[u8]) -> Result<Vec<u8>, G711xzError> {
    let frames = pcm.len() / 4;
    
    // Convert to u16 samples
    let mut samples = Vec::with_capacity(frames * 2);
    for chunk in pcm[..frames * 4].chunks_exact(4) {
        let left = u16::from_le_bytes([chunk[0], chunk[1]]);
        let right = u16::from_le_bytes([chunk[2], chunk[3]]);
        samples.push(left);
        samples.push(right);
    }
    
    // Split into left/right planes
    let left: Vec<u16> = samples.iter().step_by(2).copied().collect();
    let right: Vec<u16> = samples.iter().skip(1).step_by(2).copied().collect();
    
    // Try mu-law first, then A-law
    for law in [b'u', b'a'] {
        let table = CompressionTable::new(law);
        
        let mut left_codes = Vec::with_capacity(left.len());
        let mut right_codes = Vec::with_capacity(right.len());
        
        let mut ok = true;
        for &s in &left {
            match table.encode(s) {
                Ok(code) => left_codes.push(code),
                Err(_) => { ok = false; break; }
            }
        }
        if !ok { continue; }
        
        for &s in &right {
            match table.encode(s) {
                Ok(code) => right_codes.push(code),
                Err(_) => { ok = false; break; }
            }
        }
        if !ok { continue; }
        
        // Build header
        let mut header = Vec::with_capacity(HEADER_SIZE);
        header.extend_from_slice(MAGIC);
        header.push(VERSION);
        header.push(law);
        header.push(CHANNELS);
        header.push(0); // reserved
        header.write_u32::<LittleEndian>(RATE)?;
        header.write_u32::<LittleEndian>(frames as u32)?;
        
        // Combine header + planes
        let mut payload = Vec::with_capacity(HEADER_SIZE + left_codes.len() + right_codes.len());
        payload.extend_from_slice(&header);
        payload.extend_from_slice(&left_codes);
        payload.extend_from_slice(&right_codes);

        // xz preset 6 with the dictionary cut to the size of the codes, as the
        // format asks: max(4096, min(8 MiB, frames * 2))
        let dictionary = (frames * 2).clamp(4096, 8 << 20) as u32;
        let props = LzmaEncProps::xz_preset(6, false)
            .map_err(|e| G711xzError::InvalidXz(e.to_string()))?
            .with_dict_size(dictionary);
        return encode_xz(&payload, &props, CheckType::Crc64, 0)
            .map_err(|e| G711xzError::InvalidXz(e.to_string()));
    }
    
    Err(G711xzError::RefusedEncode)
}

/// Decompress xz data, refusing a payload longer than `max_payload` bytes so a
/// small file cannot expand without bound
fn decompress(data: &[u8], max_payload: u64) -> Result<Vec<u8>, G711xzError> {
    let reader = XzReader::new(Cursor::new(data));
    let mut payload = Vec::new();
    reader
        .take(max_payload.saturating_add(1))
        .read_to_end(&mut payload)
        .map_err(|e| G711xzError::InvalidXz(e.to_string()))?;
    if payload.len() as u64 > max_payload {
        return Err(G711xzError::LongPayload(max_payload));
    }
    Ok(payload)
}

/// Parse and validate header
fn parse_header(payload: &[u8]) -> Result<(u8, u32), G711xzError> {
    if payload.len() < HEADER_SIZE {
        return Err(G711xzError::ShortPayload(payload.len()));
    }
    
    let mut cursor = Cursor::new(payload);
    
    let mut magic = [0u8; 4];
    cursor.read_exact(&mut magic)?;
    if magic != *MAGIC {
        return Err(G711xzError::BadMagic(magic));
    }
    
    let version = cursor.read_u8()?;
    if version != VERSION {
        return Err(G711xzError::UnknownVersion(version, VERSION));
    }
    
    let law = cursor.read_u8()?;
    if law != b'u' && law != b'a' {
        return Err(G711xzError::UnknownLaw(law));
    }
    
    let channels = cursor.read_u8()?;
    if channels != CHANNELS {
        return Err(G711xzError::WrongChannels(channels, CHANNELS));
    }
    
    let reserved = cursor.read_u8()?;
    if reserved != 0 {
        return Err(G711xzError::ReservedSet(reserved));
    }
    
    let rate = cursor.read_u32::<LittleEndian>()?;
    if rate != RATE {
        return Err(G711xzError::WrongRate(rate, RATE));
    }
    
    let frames = cursor.read_u32::<LittleEndian>()?;
    let body_len = payload.len() - HEADER_SIZE;
    let expected = frames as usize * CHANNELS as usize;
    if body_len != expected {
        return Err(G711xzError::DamagedBody(body_len, frames, expected));
    }
    
    Ok((law, frames))
}

/// Python bindings
#[pyfunction]
fn decode<'py>(
    py: Python<'py>,
    data: &[u8],
    max_payload: u64,
) -> PyResult<(u8, u32, Bound<'py, PyBytes>)> {
    let (law, frames, pcm) = decode_internal(data, max_payload)?;
    Ok((law, frames, PyBytes::new_bound(py, &pcm)))
}

#[pyfunction]
fn encode<'py>(py: Python<'py>, pcm: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    let data = encode_internal(pcm)?;
    Ok(PyBytes::new_bound(py, &data))
}

#[pyfunction]
fn expand_ulaw_py(code: u8) -> i16 {
    expand_ulaw(code)
}

#[pyfunction]
fn expand_alaw_py(code: u8) -> i16 {
    expand_alaw(code)
}

#[pyfunction]
fn expand_ulaw_vec(codes: &[u8]) -> Vec<i16> {
    codes.iter().map(|&c| expand_ulaw(c)).collect()
}

#[pyfunction]
fn expand_alaw_vec(codes: &[u8]) -> Vec<i16> {
    codes.iter().map(|&c| expand_alaw(c)).collect()
}

/// Python module definition
#[pymodule]
fn _rust(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(decode, m)?)?;
    m.add_function(wrap_pyfunction!(encode, m)?)?;
    m.add_function(wrap_pyfunction!(expand_ulaw_py, m)?)?;
    m.add_function(wrap_pyfunction!(expand_alaw_py, m)?)?;
    m.add_function(wrap_pyfunction!(expand_ulaw_vec, m)?)?;
    m.add_function(wrap_pyfunction!(expand_alaw_vec, m)?)?;
    
    // Add constants
    m.add("MAGIC", b"CRG7".as_slice())?;
    m.add("VERSION", 1)?;
    m.add("CHANNELS", 2)?;
    m.add("RATE", 8000)?;
    m.add("SUFFIX", ".g711.xz")?;
    m.add("EXIT_BAD_INPUT", 2)?;
    m.add("EXIT_REFUSED", 3)?;
    
    // Add exception classes
    m.add("FormatError", _py.get_type_bound::<PyValueError>())?;
    m.add("RefusedError", _py.get_type_bound::<RefusedError>())?;
    
    // Create EXPAND dict for Python - the Python tests use g711xz.EXPAND[b'u'] and g711xz.EXPAND[b'a'] as functions
    let expand_dict = pyo3::types::PyDict::new_bound(_py);
    expand_dict.set_item("u", m.getattr("expand_ulaw_py")?)?;
    expand_dict.set_item("a", m.getattr("expand_alaw_py")?)?;
    m.add("EXPAND", expand_dict)?;
    
    // Add HEADER struct format - the tests use g711xz.HEADER.pack()
    // Python: HEADER = struct.Struct("<4sBcBBII")
    // We can expose this as a format string for Python's struct module
    m.add("HEADER_FORMAT", "<4sBcBBII")?;
    
    Ok(())
}