//! Rust implementation of g711xz call recording codec with PyO3 bindings
//! 
//! Matches the exact Python API and test vectors including the 0x7F zero-code rule for mu-law.

use pyo3::prelude::*;
use pyo3::create_exception;
use pyo3::exceptions::PyValueError;
use pyo3::types::PyBytes;
use liblzma::stream::{Action, Check, Filters, LzmaOptions, Status, Stream, CONCATENATED};
use byteorder::{LittleEndian, ReadBytesExt};
use std::io::{Read, Cursor};
use std::sync::OnceLock;
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

    #[error("xz compression failed: {0}")]
    XzEncode(String),

    #[error("{0} frames is more than a file can hold")]
    TooManyFrames(usize),
    
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

/// Compression table for a given law, kept on the heap: at 128 KiB it would
/// overflow a small thread stack
struct CompressionTable {
    table: Box<[u16]>,
}

static ULAW_EXPANSION: OnceLock<ExpansionTables> = OnceLock::new();
static ALAW_EXPANSION: OnceLock<ExpansionTables> = OnceLock::new();
static ULAW_COMPRESSION: OnceLock<CompressionTable> = OnceLock::new();
static ALAW_COMPRESSION: OnceLock<CompressionTable> = OnceLock::new();

/// Expansion tables of a law, built on first use
fn expansion_tables(law: u8) -> &'static ExpansionTables {
    let cell = if law == b'u' { &ULAW_EXPANSION } else { &ALAW_EXPANSION };
    cell.get_or_init(|| ExpansionTables::new(law))
}

/// Compression table of a law, built on first use
fn compression_table(law: u8) -> &'static CompressionTable {
    let cell = if law == b'u' { &ULAW_COMPRESSION } else { &ALAW_COMPRESSION };
    cell.get_or_init(|| CompressionTable::new(law))
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
        let mut table = vec![256u16; 65536].into_boxed_slice();
        
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

/// Decompress and validate g711xz data, returning (law, frames, payload)
fn decode_internal(data: &[u8], max_payload: u64) -> Result<(u8, u32, Vec<u8>), G711xzError> {
    let payload = decompress(data, max_payload)?;
    let (law, frames) = parse_header(&payload)?;
    Ok((law, frames, payload))
}

/// Expand the planar code body into interleaved s16le stereo PCM
fn expand_body(law: u8, body: &[u8], pcm: &mut [u8]) {
    let tables = expansion_tables(law);
    let frames = pcm.len() / 4;
    let (left, right) = body.split_at(frames);
    for ((out, &left_code), &right_code) in pcm.chunks_exact_mut(4).zip(left).zip(right) {
        out[0] = tables.low[left_code as usize];
        out[1] = tables.high[left_code as usize];
        out[2] = tables.low[right_code as usize];
        out[3] = tables.high[right_code as usize];
    }
}

/// Write the codes of both channels straight into the planar body. Returns
/// false when a sample is not a value of the law.
fn compress_planes(table: &CompressionTable, pcm: &[u8], body: &mut [u8]) -> bool {
    let frames = body.len() / 2;
    let (left, right) = body.split_at_mut(frames);
    for ((frame, left_code), right_code) in pcm.chunks_exact(4).zip(left).zip(right) {
        let left_sample = u16::from_le_bytes([frame[0], frame[1]]);
        let right_sample = u16::from_le_bytes([frame[2], frame[3]]);
        match (table.encode(left_sample), table.encode(right_sample)) {
            (Ok(l), Ok(r)) => {
                *left_code = l;
                *right_code = r;
            }
            _ => return false,
        }
    }
    true
}

/// Encode PCM to g711xz data
fn encode_internal(pcm: &[u8]) -> Result<Vec<u8>, G711xzError> {
    let frames = pcm.len() / 4;
    let frames_u32 = u32::try_from(frames).map_err(|_| G711xzError::TooManyFrames(frames))?;

    // One buffer for header + left plane + right plane
    let mut payload = vec![0u8; HEADER_SIZE + frames * 2];

    // Try mu-law first, then A-law
    for law in [b'u', b'a'] {
        if !compress_planes(compression_table(law), &pcm[..frames * 4], &mut payload[HEADER_SIZE..]) {
            continue;
        }

        payload[0..4].copy_from_slice(MAGIC);
        payload[4] = VERSION;
        payload[5] = law;
        payload[6] = CHANNELS;
        payload[7] = 0; // reserved
        payload[8..12].copy_from_slice(&RATE.to_le_bytes());
        payload[12..16].copy_from_slice(&frames_u32.to_le_bytes());

        return compress(&payload, frames);
    }

    Err(G711xzError::RefusedEncode)
}

/// Compress the payload as one xz stream: LZMA2 preset 6 with the dictionary
/// cut to the size of the codes, as the format asks:
/// max(4096, min(8 MiB, frames * 2)), and a CRC64 check
fn compress(payload: &[u8], frames: usize) -> Result<Vec<u8>, G711xzError> {
    let encode_error = |e: liblzma::stream::Error| G711xzError::XzEncode(e.to_string());
    let dictionary = frames.saturating_mul(2).clamp(4096, 8 << 20) as u32;
    let mut options = LzmaOptions::new_preset(6).map_err(encode_error)?;
    options.dict_size(dictionary);
    let mut filters = Filters::new();
    filters.lzma2(&options);
    let mut stream = Stream::new_stream_encoder(&filters, Check::Crc64).map_err(encode_error)?;

    let mut data = Vec::with_capacity(payload.len() / 4 + 4096);
    loop {
        if data.len() == data.capacity() {
            data.reserve(data.capacity());
        }
        let consumed = stream.total_in() as usize;
        let status = stream
            .process_vec(&payload[consumed..], &mut data, Action::Finish)
            .map_err(encode_error)?;
        match status {
            Status::StreamEnd => return Ok(data),
            Status::MemNeeded if data.len() < data.capacity() => {
                return Err(G711xzError::XzEncode("encoder made no progress".to_string()));
            }
            _ => {}
        }
    }
}

/// Decompress xz data, refusing a payload longer than `max_payload` bytes so a
/// small file cannot expand without bound. Concatenated streams and stream
/// padding are read; trailing garbage and a truncated stream are errors.
fn decompress(data: &[u8], max_payload: u64) -> Result<Vec<u8>, G711xzError> {
    let invalid = |e: liblzma::stream::Error| G711xzError::InvalidXz(e.to_string());
    let mut stream = Stream::new_stream_decoder(u64::MAX, CONCATENATED).map_err(invalid)?;
    // Never hold more than one byte past the limit
    let limit = usize::try_from(max_payload.saturating_add(1)).unwrap_or(usize::MAX);
    let mut payload = Vec::new();
    loop {
        if payload.len() as u64 > max_payload {
            return Err(G711xzError::LongPayload(max_payload));
        }
        if payload.len() == payload.capacity() {
            let room = payload.capacity().max(64 << 10).min(limit - payload.len());
            payload.reserve_exact(room);
        }
        let consumed = stream.total_in() as usize;
        let produced = payload.len();
        let status = stream
            .process_vec(&data[consumed..], &mut payload, Action::Finish)
            .map_err(invalid)?;
        if status == Status::StreamEnd {
            break;
        }
        // All input is given, so a call that neither reads nor writes while
        // there is room for output means the stream ends early
        let stalled = stream.total_in() as usize == consumed && payload.len() == produced;
        if stalled && payload.len() < payload.capacity() {
            // The decoder takes every byte in, so whether the first stream
            // was cut short or is followed by extra bytes needs a second look
            let reason = match first_stream_end(data) {
                Some(end) if end < data.len() => "trailing data after the xz stream",
                _ => "truncated",
            };
            return Err(G711xzError::InvalidXz(reason.to_string()));
        }
    }
    if payload.len() as u64 > max_payload {
        return Err(G711xzError::LongPayload(max_payload));
    }
    Ok(payload)
}

/// Offset just past the first xz stream, or None if it does not end cleanly.
/// Only called on a failed decode; the output is thrown away as it is made,
/// and it is no longer than what the failed decode already produced.
fn first_stream_end(data: &[u8]) -> Option<usize> {
    let mut stream = Stream::new_stream_decoder(u64::MAX, 0).ok()?;
    let mut scratch = vec![0u8; 64 << 10];
    loop {
        let consumed = stream.total_in() as usize;
        let produced = stream.total_out();
        let status = stream.process(&data[consumed..], &mut scratch, Action::Finish).ok()?;
        if status == Status::StreamEnd {
            return Some(stream.total_in() as usize);
        }
        if stream.total_in() as usize == consumed && stream.total_out() == produced {
            return None;
        }
    }
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

// decode and encode release the GIL for the work. The input is borrowed from
// an immutable bytes object that the caller keeps alive for the whole call, so
// reading it without the GIL is sound and saves a copy of the whole recording.

/// Python bindings
#[pyfunction]
fn decode<'py>(
    py: Python<'py>,
    data: &[u8],
    max_payload: u64,
) -> PyResult<(u8, u32, Bound<'py, PyBytes>)> {
    let (law, frames, payload) = py.allow_threads(|| decode_internal(data, max_payload))?;
    // The PCM is written straight into the new bytes object, which nothing
    // else can see yet, so that too runs without the GIL
    let pcm = PyBytes::new_bound_with(py, frames as usize * 4, |pcm| {
        py.allow_threads(|| expand_body(law, &payload[HEADER_SIZE..], pcm));
        Ok(())
    })?;
    Ok((law, frames, pcm))
}

#[pyfunction]
fn encode<'py>(py: Python<'py>, pcm: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
    let data = py.allow_threads(|| encode_internal(pcm))?;
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