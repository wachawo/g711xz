#!/usr/bin/env python3
"""Read, decode and encode `.g711.xz` call recordings.

A `.g711.xz` file is one xz stream holding a 16-byte header and the 8-bit
G.711 codes of a stereo 8 kHz call, left plane (caller) then right plane
(callee). Decoding gives back the recorder's 16-bit PCM bit for bit.

Usage:
    g711xz info      FILE.g711.xz [...]
    g711xz decode    FILE.g711.xz [OUT.wav]
    g711xz encode    FILE.wav     [OUT.g711.xz] [--vox]
    g711xz transcode FILE.g711.xz {u,a} OUT.g711.xz

VOX (beta) is asked for only when writing. `encode --vox` writes a VOX file:
speech is kept bit for bit and long stretches of even line noise are replaced
by a short piece of the same noise repeated. Such a file is marked in its
header and is not an exact copy of the recording. Reading needs no switch: the
header says what a file is, and `info`, `decode` and `transcode` read both
kinds. In Python the switch is the keyword `vox=True` of `encode`.

Exit codes: 0 ok, 2 bad or damaged input, 3 encode refused (the PCM is not
pure G.711, so a lossless file cannot be made).

Standard library only; NumPy and the Rust extension are optional accelerators.
"""

from __future__ import annotations

import argparse
import array
import functools
import io
import lzma
import math
import operator
import os
import struct
import sys
import wave
from collections.abc import Iterable, Iterator
from typing import Any, BinaryIO, Callable, Literal, Union, overload

# Optional NumPy acceleration
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None  # type: ignore[assignment]

# Optional Rust acceleration
try:
    import g711xz._rust as _rust  # type: ignore[import-untyped]

    HAS_RUST = True
except ImportError:
    HAS_RUST = False
    _rust = None  # type: ignore[assignment, unused-ignore]

HEADER = struct.Struct("<4sBcBBII")
MAGIC = b"CRG7"
VERSION = 1
CHANNELS = 2
RATE = 8000
SUFFIX = ".g711.xz"
# Recommended name for a VOX file; the header, not the name, says what a file is
VOX_SUFFIX = ".vox.g711.xz"
# A reader refuses anything longer than a day of audio, so a small xz file
# cannot expand without bound.
MAX_FRAMES = 24 * 3600 * RATE
MAX_PAYLOAD = HEADER.size + MAX_FRAMES * CHANNELS
READ_SIZE = 65536
PIECE_SIZE = 1 << 20

EXIT_BAD_INPUT = 2
EXIT_REFUSED = 3

# Header byte 7: how the codes relate to the recording
MODE_LOSSLESS = 0
# Beta: speech bit for bit, long stretches of even line noise replaced
MODE_VOX = 1
MODE_NAMES = {MODE_LOSSLESS: "lossless", MODE_VOX: "vox"}
# Appended to a result line of the command line tool
MODE_NOTES = {MODE_LOSSLESS: "", MODE_VOX: ", vox (not an exact copy)"}

# VOX (beta) defaults. Parameters of the encoder, not of the format.
# Samples per VOX frame: 20 ms
VOX_FRAME = 160
# A frame is active when its level is above this, dBFS
VOX_THRESHOLD_DB = -45.0
# Kept before and after every active frame, ms
VOX_HANGOVER_MS = 800
# Only quiet runs at least this long are replaced, ms
VOX_MIN_QUIET_MS = 1000
# A replaced run repeats its own first piece of this length, ms
VOX_FILL_MS = 250
# A run whose median level is at or below this is left alone, dBFS
VOX_FLOOR_DB = -70.0
# A run with a frame this far above its median level is left alone, dB
VOX_PEAK_DB = 6.0

Law = Literal[b"u", b"a"]


class FormatError(ValueError):
    """The input is not a valid `.g711.xz` version 1 file or WAV."""


class RefusedError(ValueError):
    """The PCM is not on the G.711 lattice of a single law."""


def expand_ulaw(code: int) -> int:
    value = ~code & 0xFF
    magnitude = ((((value & 0x0F) << 3) + 0x84) << ((value >> 4) & 0x07)) - 0x84
    return -magnitude if value & 0x80 else magnitude


def expand_alaw(code: int) -> int:
    value = code ^ 0x55
    exponent = (value >> 4) & 0x07
    mantissa = value & 0x0F
    if exponent == 0:
        magnitude = (mantissa << 4) + 8
    else:
        magnitude = ((mantissa << 4) + 0x108) << (exponent - 1)
    return magnitude if value & 0x80 else -magnitude


EXPAND: dict[Law, Callable[[int], int]] = {b"u": expand_ulaw, b"a": expand_alaw}
LAW_NAMES: dict[Law, str] = {b"u": "mu-law (PCMU)", b"a": "A-law (PCMA)"}
# Mu-law is tried first when encoding.
LAW_ORDER: tuple[Law, Law] = (b"u", b"a")

# Public API
__all__ = [
    "FormatError",
    "RefusedError",
    "Law",
    "expand_ulaw",
    "expand_alaw",
    "expansion_tables",
    "compression_table",
    "translation_table",
    "transcode_codes",
    "transcode_law",
    "unpack_header",
    "parse_header",
    "read_payload",
    "decompress",
    "pack_file",
    "read_mode",
    "frame_levels",
    "vox_runs",
    "vox_pcm",
    "decode_stream",
    "encode_stream",
    "decode",
    "encode",
    "read_wav",
    "write_wav",
    "replace_suffix",
    "command_info",
    "command_decode",
    "command_encode",
    "command_transcode",
    "build_parser",
    "main",
    "MAGIC",
    "VERSION",
    "CHANNELS",
    "RATE",
    "SUFFIX",
    "VOX_SUFFIX",
    "MAX_FRAMES",
    "MAX_PAYLOAD",
    "EXIT_BAD_INPUT",
    "EXIT_REFUSED",
    "MODE_LOSSLESS",
    "MODE_VOX",
    "MODE_NAMES",
    "VOX_FRAME",
    "VOX_THRESHOLD_DB",
    "VOX_HANGOVER_MS",
    "VOX_MIN_QUIET_MS",
    "VOX_FILL_MS",
    "VOX_FLOOR_DB",
    "VOX_PEAK_DB",
    "HAS_NUMPY",
    "HAS_RUST",
]


def expansion_tables(law: Law) -> tuple[bytes, bytes]:
    """Return (low, high) byte translation tables: code -> s16le bytes."""
    samples = [EXPAND[law](code) & 0xFFFF for code in range(256)]
    low = bytes(sample & 0xFF for sample in samples)
    high = bytes(sample >> 8 for sample in samples)
    return low, high


def compression_table(law: Law) -> list[int]:
    """Return a list indexed by the unsigned 16-bit sample giving its code.

    Samples with no code map to 256, which `bytes()` rejects. When two codes
    expand to the same sample (mu-law 0x7F and 0xFF both give 0), the lower
    code is kept, as the recorder does.
    """
    table = [256] * 65536
    for code in range(256):
        index = EXPAND[law](code) & 0xFFFF
        if table[index] == 256:
            table[index] = code
    return table


# NumPy lookup tables (created lazily on first use)
_NUMPY_EXPAND_TABLES: dict[Law, np.ndarray] = {}  # law -> uint16[256]
_NUMPY_COMPRESS_TABLES: dict[Law, np.ndarray] = {}  # law -> uint16[65536]


def _get_numpy_expand_table(law: Law) -> np.ndarray:
    """Get or create uint16 expansion lookup table for a law."""
    if law not in _NUMPY_EXPAND_TABLES:
        samples = np.fromiter(
            (EXPAND[law](code) & 0xFFFF for code in range(256)),
            dtype=np.uint16,
            count=256,
        )
        _NUMPY_EXPAND_TABLES[law] = samples
    return _NUMPY_EXPAND_TABLES[law]


def _get_numpy_compress_table(law: Law) -> np.ndarray:
    """Get or create uint16 compression lookup table for a law."""
    if law not in _NUMPY_COMPRESS_TABLES:
        table = np.full(65536, 256, dtype=np.uint16)
        for code in range(256):
            index = EXPAND[law](code) & 0xFFFF
            if table[index] == 256:
                table[index] = code
        _NUMPY_COMPRESS_TABLES[law] = table
    return _NUMPY_COMPRESS_TABLES[law]


@functools.cache
def translation_table(from_law: Law, to_law: Law) -> bytes:
    """Return a 256-byte table: code in from_law -> nearest code in to_law.

    The two laws have different sample values, so this is lossy: a code maps
    to the code of the closest sample of the target law, the lower code on a
    tie.
    """
    targets = [EXPAND[to_law](code) for code in range(256)]
    table = bytearray(256)
    for code in range(256):
        sample = EXPAND[from_law](code)
        distances = [abs(target - sample) for target in targets]
        table[code] = distances.index(min(distances))
    return bytes(table)


def transcode_codes(codes: bytes, from_law: Law, to_law: Law) -> bytes:
    """Convert raw G.711 code bytes from one law to the other.

    Lossy unless the laws are equal: the result is what expanding to PCM and
    compressing in the target law would give, not the same PCM.
    """
    if from_law == to_law:
        return codes
    table = translation_table(from_law, to_law)
    return codes.translate(table)


def transcode_law(data: bytes, target_law: Law) -> bytes:
    """Convert a `.g711.xz` file to the other law.

    Lossy: the result is a valid file, but it decodes to the nearest samples
    of the target law, not to the PCM of the input. A file that is already in
    the target law is returned unchanged.

    The mode is carried over: a VOX (beta) file gives a VOX file.

    Raises:
        FormatError: if input is not a valid .g711.xz file.
    """
    if target_law not in EXPAND:
        raise FormatError(f"unknown target law {target_law!r}")
    payload = decompress(data)
    law, frames = parse_header(payload)
    if law == target_law:
        return data
    planes = transcode_codes(payload[HEADER.size :], law, target_law)
    return pack_file(target_law, frames, planes, payload[7])


def unpack_header(payload: bytes | bytearray) -> tuple[Law, int]:
    """Validate the 16 header bytes of a payload and return (law, frames).

    Both modes are read; the mode is header byte 7, see `read_mode`.
    """
    if len(payload) < HEADER.size:
        raise FormatError(f"payload is {len(payload)} bytes, shorter than the header")
    magic, version, law, channels, mode, rate, frames = HEADER.unpack_from(payload)
    if magic != MAGIC:
        raise FormatError(f"bad magic {magic!r}, not a .g711.xz file")
    if version != VERSION:
        raise FormatError(f"unknown format version {version}, this reader knows {VERSION}")
    if law not in EXPAND:
        raise FormatError(f"unknown law {law!r}")
    if channels != CHANNELS:
        raise FormatError(f"channels is {channels}, expected {CHANNELS}")
    if mode not in MODE_NAMES:
        raise FormatError(f"unknown mode {mode}, this reader knows 0 (lossless) and 1 (vox)")
    if rate != RATE:
        raise FormatError(f"sample rate is {rate}, expected {RATE}")
    if frames > MAX_FRAMES:
        raise FormatError(f"{frames} frames is more than the {MAX_FRAMES} a file may hold")
    return law, frames


def parse_header(payload: bytes | bytearray) -> tuple[Law, int]:
    """Validate the decompressed payload and return (law, frames).

    Both modes are read; the mode is header byte 7, see `read_mode`.
    """
    law, frames = unpack_header(payload)
    body = len(payload) - HEADER.size
    if body != frames * CHANNELS:
        raise FormatError(
            f"damaged: {body} code bytes for {frames} frames, expected {frames * CHANNELS}"
        )
    return law, frames


def read_payload(file_obj: BinaryIO) -> Iterator[bytes]:
    """Yield the decompressed payload of an xz stream piece by piece.

    Raises FormatError for a bad or truncated stream and for a payload longer
    than MAX_PAYLOAD, so a small file cannot expand without bound.
    """
    decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    total = 0
    while not decompressor.eof:
        chunk = file_obj.read(READ_SIZE)
        if not chunk:
            raise FormatError("not a valid xz stream: truncated")
        while True:
            try:
                piece = decompressor.decompress(chunk, max_length=PIECE_SIZE)
            except lzma.LZMAError as error:
                raise FormatError(f"not a valid xz stream: {error}") from error
            total += len(piece)
            if total > MAX_PAYLOAD:
                raise FormatError(
                    f"payload is longer than {MAX_PAYLOAD} bytes, not a call recording"
                )
            if piece:
                yield piece
            if decompressor.eof or decompressor.needs_input:
                break
            chunk = b""


def decompress(data: bytes) -> bytes:
    """Return the payload of an xz stream, see `read_payload` for the limits."""
    return b"".join(read_payload(io.BytesIO(data)))


def read_mode(input_: BytesOrFile) -> int:
    """Return the mode of a `.g711.xz` file: MODE_LOSSLESS or MODE_VOX (beta).

    Accepts what `decode` accepts: the bytes of a file, a file path or a
    binary file object. Only the header is decompressed, so damage after it
    is not found here. Raises FormatError for a bad file.
    """
    if isinstance(input_, (str, os.PathLike)):
        with open(str(input_), "rb") as source:
            return read_mode(source)
    if isinstance(input_, (bytes, bytearray, memoryview)):
        return read_mode(io.BytesIO(input_))
    if not hasattr(input_, "read"):
        raise TypeError(f"Unsupported input type: {type(input_)}")
    decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    header = b""
    chunk = b""
    # Between two xz streams, where zero padding may stand. The Rust backend
    # reads xz streams that follow each other as one, so a header that does
    # not fit into the first stream goes on in the next.
    between = False
    while len(header) < HEADER.size:
        if decompressor.eof:
            chunk = decompressor.unused_data
            decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
            between = True
        if between:
            chunk = chunk.lstrip(b"\0")
        if not chunk:
            chunk = input_.read(READ_SIZE)
            if chunk:
                continue
            if between:
                break
            raise FormatError("not a valid xz stream: truncated")
        try:
            header += decompressor.decompress(chunk, max_length=HEADER.size - len(header))
        except lzma.LZMAError as error:
            raise FormatError(f"not a valid xz stream: {error}") from error
        chunk = b""
        between = False
    unpack_header(header)
    return header[7]


def pack_file(law: Law, frames: int, planes: bytes, mode: int = MODE_LOSSLESS) -> bytes:
    """Compress the header and the two code planes into a `.g711.xz` file.

    `mode` is header byte 7: MODE_LOSSLESS, or MODE_VOX for a beta VOX file.
    """
    if mode not in MODE_NAMES:
        raise FormatError(f"unknown mode {mode}")
    header = HEADER.pack(MAGIC, VERSION, law, CHANNELS, mode, RATE, frames)
    dictionary = max(4096, min(8 << 20, frames * 2))
    filters = [{"id": lzma.FILTER_LZMA2, "preset": 6, "dict_size": dictionary}]
    return lzma.compress(
        header + planes, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, filters=filters
    )


DecodeFrame = tuple[Law, int, int, int]


def decode_stream(file_obj: BinaryIO) -> Iterator[DecodeFrame]:
    """Decode a `.g711.xz` file object frame by frame.

    Args:
        file_obj: A file-like object opened in binary mode (seek not required).
                  Both modes are read; `read_mode` tells a VOX (beta) file,
                  which is not an exact copy of the recording.

    Yields:
        Tuples of (law, frame_idx, left_sample, right_sample), the samples as
        signed 16-bit values.

    The file is decompressed incrementally and the PCM is never built, so the
    memory used is the two code planes (2 bytes per frame). The layout is
    planar: the first frame comes out only after the whole left plane was read.

    Raises FormatError when the file is damaged. Damage after the header (a
    truncated stream, a wrong body length) is found at the end, after the
    frames that could be read were yielded.
    """
    buffer = bytearray()
    law: Law | None = None
    frames = 0
    samples: list[int] = []
    emitted = 0
    for piece in read_payload(file_obj):
        buffer += piece
        if law is None:
            if len(buffer) < HEADER.size:
                continue
            law, frames = unpack_header(buffer)
            samples = [EXPAND[law](code) for code in range(256)]
        right_start = HEADER.size + frames
        ready = min(frames, len(buffer) - right_start)
        while emitted < ready:
            left_code = buffer[HEADER.size + emitted]
            right_code = buffer[right_start + emitted]
            yield law, emitted, samples[left_code], samples[right_code]
            emitted += 1
    parse_header(buffer)


def encode_stream(
    pcm_chunks: Iterable[bytes],
    total_frames: int | None = None,
    *,
    vox: bool = False,
    **vox_options: Any,
) -> Iterator[bytes]:
    """Encode chunks of interleaved s16le stereo 8 kHz PCM to `.g711.xz` chunks.

    Args:
        pcm_chunks: An iterable of bytes. Chunks may be cut anywhere, also in
                    the middle of a frame; trailing bytes short of a whole
                    frame are ignored.
        total_frames: Optional expected number of frames. FormatError is raised
                      when the input holds a different number.
        vox, vox_options: As in `encode`.

    Yields:
        Pieces of one valid `.g711.xz` file.

    The law in the header depends on every sample and the layout is planar, so
    nothing can be written before the input ends: the input is collected first
    and the file is yielded after that. Raises RefusedError like `encode`.
    """
    pcm = b"".join(pcm_chunks)
    if total_frames is not None and len(pcm) // 4 != total_frames:
        raise FormatError(f"expected {total_frames} frames, got {len(pcm) // 4}")
    data = _encode_bytes(pcm, vox, **vox_options)
    for start in range(0, len(data), READ_SIZE):
        yield data[start : start + READ_SIZE]


def _decode_bytes(data: bytes) -> tuple[Law, int, bytes]:
    """Decode `.g711.xz` bytes to (law, frames, interleaved s16le stereo PCM)."""
    # Rust backend (fastest)
    if HAS_RUST:
        try:
            law_int, frames, pcm_rust = _rust.decode(data, MAX_PAYLOAD)
        except ValueError as error:
            raise FormatError(str(error)) from error
        rust_law: Law = b"a" if law_int == ord("a") else b"u"
        return rust_law, frames, bytes(pcm_rust)

    payload = decompress(data)
    law, frames = parse_header(payload)
    body = memoryview(payload)[HEADER.size :]

    if HAS_NUMPY and frames > 0:
        # NumPy vectorized path
        codes = np.frombuffer(body, dtype=np.uint8)
        table = _get_numpy_expand_table(law)
        # Single take for all codes (faster than two takes + stack)
        all_samples = np.take(table, codes)  # shape: (2*frames,)
        # Interleave: [L0, R0, L1, R1, ...] from [L0..L{n-1}, R0..R{n-1}]
        pcm_np = np.empty(frames * 2, dtype="<u2")
        pcm_np[0::2] = all_samples[:frames]
        pcm_np[1::2] = all_samples[frames:]
        return law, frames, pcm_np.tobytes()

    # Pure Python fallback
    low, high = expansion_tables(law)
    pcm: bytearray = bytearray(frames * 4)
    for channel in range(CHANNELS):
        plane = bytes(body[channel * frames : (channel + 1) * frames])
        pcm[channel * 2 :: 4] = plane.translate(low)
        pcm[channel * 2 + 1 :: 4] = plane.translate(high)
    return law, frames, bytes(pcm)


# Overloads for file path vs bytes input
PathLike = Union[str, "os.PathLike[str]"]
BytesOrFile = Union[bytes, BinaryIO, PathLike]


@overload
def decode(input_: bytes) -> tuple[Law, int, bytes]: ...


@overload
def decode(input_: PathLike) -> tuple[Law, int, bytes]: ...


@overload
def decode(input_: BinaryIO) -> tuple[Law, int, bytes]: ...


def decode(input_: object) -> tuple[Law, int, bytes]:
    """Decode `.g711.xz` file to (law, frames, interleaved s16le stereo PCM).

    Accepts a bytes-like object, a file path or a binary file object.

    Both modes are read. A VOX (beta) file is not an exact copy of the
    recording; `read_mode` tells which kind a file is.
    """
    if isinstance(input_, (str, os.PathLike)):
        with open(str(input_), "rb") as f:
            data = f.read()
    elif isinstance(input_, (bytes, bytearray, memoryview)):
        data = bytes(input_)
    elif hasattr(input_, "read"):
        data = input_.read()
    else:
        raise TypeError(f"Unsupported input type: {type(input_)}")
    return _decode_bytes(data)


def _encode_bytes(pcm: bytes, vox: bool = False, **vox_options: Any) -> bytes:
    """Encode interleaved s16le stereo 8 kHz PCM to `.g711.xz` bytes.

    Trailing bytes short of a whole frame are ignored. Raises RefusedError
    when the samples are not all values of one G.711 law. With `vox` the PCM
    goes through `vox_pcm` first and the header says MODE_VOX.
    """
    frames = len(pcm) // 4
    if frames > MAX_FRAMES:
        raise FormatError(f"{frames} frames is more than the {MAX_FRAMES} a file may hold")
    if vox:
        pcm = vox_pcm(pcm, **vox_options)[0]
    elif vox_options:
        raise TypeError("vox options need vox=True")
    mode = MODE_VOX if vox else MODE_LOSSLESS

    # Rust backend (fastest); it writes lossless files only
    if HAS_RUST and not vox:
        try:
            return bytes(_rust.encode(pcm))
        except _rust.RefusedError as error:
            raise RefusedError(str(error)) from error
        except ValueError as error:
            raise FormatError(str(error)) from error

    samples = array.array("H")
    samples.frombytes(pcm[: frames * 4])
    if sys.byteorder == "big":
        samples.byteswap()
    left = samples[0::2]
    right = samples[1::2]

    if HAS_NUMPY:
        # NumPy vectorized path
        left_np = np.frombuffer(left, dtype=np.uint16)
        right_np = np.frombuffer(right, dtype=np.uint16)

        for law in LAW_ORDER:
            table = _get_numpy_compress_table(law)
            # Vectorized lookup - invalid samples will map to 256
            left_codes = table[left_np]
            right_codes = table[right_np]
            if np.any(left_codes == 256) or np.any(right_codes == 256):
                continue
            planes = np.concatenate([left_codes, right_codes]).astype(np.uint8).tobytes()
            return pack_file(law, frames, planes, mode)
    else:
        # Pure Python fallback
        for law in LAW_ORDER:
            table_py = compression_table(law)
            try:
                planes = bytes(map(table_py.__getitem__, left)) + bytes(
                    map(table_py.__getitem__, right)
                )
            except ValueError:
                continue
            return pack_file(law, frames, planes, mode)

    raise RefusedError(
        "PCM is not pure G.711 (mu-law or A-law on both channels), refusing to encode"
    )


@overload
def encode(input_: bytes, *, vox: bool = ..., **vox_options: Any) -> bytes: ...


@overload
def encode(input_: PathLike, *, vox: bool = ..., **vox_options: Any) -> bytes: ...


@overload
def encode(input_: BinaryIO, *, vox: bool = ..., **vox_options: Any) -> bytes: ...


def encode(input_: object, *, vox: bool = False, **vox_options: Any) -> bytes:
    """Encode PCM to `.g711.xz` bytes.

    Accepts a bytes-like object, a file path or a binary file object.

    VOX (beta) is off until you say vox: `vox=True` writes a VOX file. The
    PCM goes through `vox_pcm` and is then stored like a lossless file, with
    MODE_VOX in the header. Speech is bit for bit; the file as a whole is not
    an exact copy of the recording. `vox_options` are those of `vox_pcm`
    (threshold_db, hangover_ms, min_quiet_ms, fill_ms, floor_db, peak_db);
    given without `vox=True` they raise TypeError.
    """
    if isinstance(input_, (str, os.PathLike)):
        with open(str(input_), "rb") as f:
            pcm = f.read()
    elif isinstance(input_, (bytes, bytearray, memoryview)):
        pcm = bytes(input_)
    elif hasattr(input_, "read"):
        pcm = input_.read()
    else:
        raise TypeError(f"Unsupported input type: {type(input_)}")
    return _encode_bytes(pcm, vox, **vox_options)


def frame_levels(samples: Any) -> list[float]:
    """VOX (beta): the level in dBFS of every whole 20 ms frame of one channel.

    `samples` is one channel as signed 16-bit values. Level is
    20 * log10(rms / 32768); a frame of all zeros counts as rms 0.5.
    """
    count = len(samples) // VOX_FRAME
    if HAS_NUMPY:
        whole = np.asarray(samples, dtype=np.int64)[: count * VOX_FRAME].reshape(count, VOX_FRAME)
        energies: list[int] = (whole * whole).sum(axis=1).tolist()
    else:
        energies = []
        for start in range(0, count * VOX_FRAME, VOX_FRAME):
            chunk = samples[start : start + VOX_FRAME]
            energies.append(sum(map(operator.mul, chunk, chunk)))
    levels = []
    for energy in energies:
        rms = max(math.sqrt(energy / VOX_FRAME), 0.5)
        levels.append(20.0 * math.log10(rms / 32768.0))
    return levels


def vox_runs(
    levels: list[float],
    threshold_db: float = VOX_THRESHOLD_DB,
    hangover_ms: int = VOX_HANGOVER_MS,
    min_quiet_ms: int = VOX_MIN_QUIET_MS,
    floor_db: float | None = VOX_FLOOR_DB,
    peak_db: float | None = VOX_PEAK_DB,
) -> list[tuple[int, int]]:
    """VOX (beta): the runs of frames to replace, as (first, past the last).

    A frame is active when its level is above `threshold_db`. Active frames
    are kept, with `hangover_ms` of frames before and after each of them. Of
    the runs that are left, only those at least `min_quiet_ms` long are
    candidates, so pauses inside speech stay whole. A candidate is left alone
    when its median level is at or below `floor_db` (the line is digitally
    silent, so whatever comes through is a real sound), or when any of its
    frames is more than `peak_db` above its median (something happens in it).
    What remains is even line noise.
    """
    if hangover_ms < 0 or min_quiet_ms < 0:
        raise ValueError("hangover_ms and min_quiet_ms must not be negative")
    count = len(levels)
    reach = hangover_ms // 20
    kept = [False] * count
    for step in (1, -1):
        remaining = 0
        for index in range(count)[::step]:
            if levels[index] > threshold_db:
                remaining = reach + 1
            if remaining > 0:
                kept[index] = True
                remaining -= 1
    shortest = max(1, -(-min_quiet_ms // 20))
    runs = []
    start = -1
    for index in range(count + 1):
        quiet = index < count and not kept[index]
        if quiet and start < 0:
            start = index
        elif not quiet and start >= 0:
            runs.append((start, index))
            start = -1
    chosen = []
    for first, last in runs:
        if last - first < shortest:
            continue
        ordered = sorted(levels[first:last])
        middle = len(ordered) // 2
        median = (
            ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2.0
        )
        if floor_db is not None and median <= floor_db:
            continue
        if peak_db is not None and ordered[-1] - median > peak_db:
            continue
        chosen.append((first, last))
    return chosen


def vox_pcm(pcm: bytes, fill_ms: int = VOX_FILL_MS, **vox_options: Any) -> tuple[bytes, int]:
    """VOX (beta): replace long stretches of even line noise in PCM.

    `pcm` is interleaved s16le stereo at 8 kHz. Each channel is treated on its
    own, see `vox_runs` for the options. A replaced run keeps its own first
    `fill_ms` of audio and repeats it to the end of the run, so the noise
    keeps its level and sound while the data becomes periodic and compresses
    like silence. Every other sample is returned as it is, and every sample
    of the result is a sample the channel already had.

    Returns the new PCM and the number of samples that changed.
    """
    if fill_ms < 1:
        raise ValueError("fill_ms must be at least 1")
    frames = len(pcm) // 4
    samples = array.array("h")
    samples.frombytes(pcm[: frames * 4])
    if sys.byteorder == "big":
        samples.byteswap()
    period = fill_ms * RATE // 1000
    changed = 0
    for channel in range(CHANNELS):
        plane = samples[channel::2]
        original = plane[:]
        for first, last in vox_runs(frame_levels(plane), **vox_options):
            start, stop = first * VOX_FRAME, last * VOX_FRAME
            if stop - start > period:
                pattern = plane[start : start + period]
                repeats = -(-(stop - start) // period)
                plane[start:stop] = (pattern * repeats)[: stop - start]
        changed += sum(map(operator.ne, plane, original))
        samples[channel::2] = plane
    if sys.byteorder == "big":
        samples.byteswap()
    return samples.tobytes() + pcm[frames * 4 :], changed


def read_wav(path: PathLike) -> bytes:
    """Return the PCM of a 2-channel 16-bit 8000 Hz WAV file."""
    try:
        with wave.open(str(path), "rb") as source:
            params = source.getparams()
            if (params.nchannels, params.sampwidth, params.framerate) != (CHANNELS, 2, RATE):
                raise FormatError(
                    f"WAV is {params.nchannels} ch, {params.sampwidth * 8}-bit,"
                    f" {params.framerate} Hz; expected {CHANNELS} ch, 16-bit, {RATE} Hz"
                )
            return source.readframes(params.nframes)
    except (wave.Error, EOFError) as error:
        raise FormatError(f"not a readable WAV file: {error}") from error


def write_wav(path: PathLike, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as sink:
        sink.setnchannels(CHANNELS)
        sink.setsampwidth(2)
        sink.setframerate(RATE)
        sink.writeframes(pcm)


def replace_suffix(path: str, old: str, new: str) -> str:
    """Swap a (possibly double) extension; os.path.splitext cuts .g711.xz wrongly."""
    if path.lower().endswith(old):
        return path[: -len(old)] + new
    return path + new


def command_info(args: argparse.Namespace) -> int:
    status = 0
    for path in args.files:
        try:
            with open(path, "rb") as source:
                data = source.read()
            payload = decompress(data)
            law, frames = parse_header(payload)
        except (OSError, FormatError) as error:
            print(f"{path}: error: {error}", file=sys.stderr)
            status = EXIT_BAD_INPUT
            continue
        seconds = frames / RATE
        bitrate = len(data) * 8 / seconds / 1000 if frames else 0.0
        print(f"{path}:")
        print(f"  format    {MAGIC.decode()} version {VERSION}")
        vox = payload[7] == MODE_VOX
        note = " (beta): quiet line noise replaced, not an exact copy" if vox else ""
        print(f"  mode      {MODE_NAMES[payload[7]]}{note}")
        print(f"  law       {LAW_NAMES[law]}")
        print(f"  channels  {CHANNELS} (left caller, right callee)")
        print(f"  rate      {RATE} Hz")
        print(f"  frames    {frames}")
        print(f"  duration  {seconds:.3f} s")
        print(f"  size      {len(data)} bytes ({bitrate:.1f} kbit/s)")
    return status


def command_decode(args: argparse.Namespace) -> int:
    output = args.output or replace_suffix(args.input, SUFFIX, ".wav")
    with open(args.input, "rb") as source:
        data = source.read()
    law, frames, pcm = decode(data)
    write_wav(output, pcm)
    duration = f"{frames} frames, {frames / RATE:.3f} s"
    print(f"{args.input} -> {output}: {LAW_NAMES[law]}, {duration}{MODE_NOTES[read_mode(data)]}")
    return 0


def command_encode(args: argparse.Namespace) -> int:
    suffix = VOX_SUFFIX if args.vox else SUFFIX
    output = args.output or replace_suffix(args.input, ".wav", suffix)
    data = _encode_bytes(read_wav(args.input), args.vox)
    with open(output, "wb") as sink:
        sink.write(data)
    payload = decompress(data)
    law_bytes: bytes = payload[5:6]  # law is at offset 5 in header
    law: Law = law_bytes  # type: ignore[assignment]
    print(f"{args.input} -> {output}: {LAW_NAMES[law]}{MODE_NOTES[payload[7]]}, {len(data)} bytes")
    return 0


def command_transcode(args: argparse.Namespace) -> int:
    if os.path.exists(args.output) and os.path.samefile(args.input, args.output):
        raise FormatError("transcoding is lossy, refusing to write over the input file")
    with open(args.input, "rb") as source:
        data = source.read()
    target_law: Law = args.law.encode()  # 'u' or 'a' -> b'u' or b'a'
    transcoded = transcode_law(data, target_law)
    with open(args.output, "wb") as sink:
        sink.write(transcoded)
    note = MODE_NOTES[read_mode(data)]
    print(f"{args.input} -> {args.output}: {LAW_NAMES[target_law]}{note}, {len(transcoded)} bytes")
    return 0


def build_parser() -> argparse.ArgumentParser:
    # No abbreviations anywhere: `--v` must not stand for `--vox`
    parser = argparse.ArgumentParser(
        description="Read, decode and encode .g711.xz call recordings.", allow_abbrev=False
    )
    commands = parser.add_subparsers(dest="command", required=True)

    info = commands.add_parser("info", help="show the header of .g711.xz files", allow_abbrev=False)
    info.add_argument("files", nargs="+", metavar="FILE")
    info.set_defaults(handler=command_info)

    decoder = commands.add_parser(
        "decode", help="decode .g711.xz to lossless stereo WAV", allow_abbrev=False
    )
    decoder.add_argument("input", metavar="FILE.g711.xz")
    decoder.add_argument("output", nargs="?", metavar="OUT.wav")
    decoder.set_defaults(handler=command_decode)

    encoder = commands.add_parser(
        "encode", help="encode a 2 ch 16-bit 8 kHz WAV to .g711.xz", allow_abbrev=False
    )
    encoder.add_argument("input", metavar="FILE.wav")
    encoder.add_argument("output", nargs="?", metavar="OUT.g711.xz")
    encoder.add_argument(
        "--vox",
        action="store_true",
        help="beta: write a VOX file, speech bit for bit, long stretches of even line noise"
        " replaced; not an exact copy of the recording",
    )
    encoder.set_defaults(handler=command_encode)

    transcode = commands.add_parser(
        "transcode",
        help="convert .g711.xz to the other law (lossy, writes a new file)",
        allow_abbrev=False,
    )
    transcode.add_argument("input", metavar="FILE.g711.xz")
    transcode.add_argument("law", choices=["u", "a"], help="target law: u=mu-law, a=A-law")
    transcode.add_argument("output", metavar="OUT.g711.xz")
    transcode.set_defaults(handler=command_transcode)
    return parser


def main(argv: list[str] | None = None) -> int:
    words = sys.argv[1:] if argv is None else list(argv)
    # argparse fills an optional output name before it reads an option that
    # stands in front of it, so the `--vox` of encode is moved right behind the
    # subcommand. Words after `--` are file names and stay where they are.
    end = words.index("--") if "--" in words else len(words)
    if words[:1] == ["encode"] and "--vox" in words[1:end]:
        others = [word for word in words[1:end] if word != "--vox"]
        words = words[:1] + ["--vox"] + others + words[end:]
    args = build_parser().parse_args(words)
    try:
        return int(args.handler(args))
    except RefusedError as error:
        print(f"refused: {error}", file=sys.stderr)
        return EXIT_REFUSED
    except (OSError, FormatError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT


if __name__ == "__main__":
    sys.exit(main())
