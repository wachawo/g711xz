# g711xz Features

## Exit Codes

The `g711xz` command returns the following exit codes:

- **0** - Success
- **2** - Bad input: a damaged or foreign file, a WAV of the wrong format, a file that cannot be opened, or wrong command line arguments
- **3** - Encode refused: the PCM is not pure G.711, so a lossless file cannot be made

### Examples

```bash
# Success
g711xz decode rec.g711.xz
echo $?  # Returns 0

# Not a .g711.xz file
g711xz info notes.txt
echo $?  # Returns 2

# File not found
g711xz decode missing.g711.xz
echo $?  # Returns 2

# 8 kHz stereo WAV whose samples are not G.711 values
g711xz encode resampled.wav
echo $?  # Returns 3
```

Errors go to stderr with an `error:` prefix (exit code 2) or a `refused:` prefix (exit code 3). With several files, `info` reports each bad file, still prints the others and returns 2.

### Output of `info`

```
FILE:
  format    CRG7 version 1
  law       mu-law (PCMU) | A-law (PCMA)
  channels  2 (left caller, right callee)
  rate      8000 Hz
  frames    number of frames per channel
  duration  seconds
  size      file size in bytes (average bitrate in kbit/s)
```

## Commands

```
g711xz info      FILE.g711.xz [FILE.g711.xz ...]
g711xz decode    FILE.g711.xz [OUT.wav]
g711xz encode    FILE.wav     [OUT.g711.xz]
g711xz transcode FILE.g711.xz {u,a} OUT.g711.xz
```

### info

Prints the header of each file, the duration and the average bitrate.

### decode

Writes a 2-channel, 16-bit, 8000 Hz WAV with the exact PCM of the recording. Without `OUT.wav` the output is the input name with `.g711.xz` replaced by `.wav`.

### encode

Reads a 2-channel, 16-bit, 8000 Hz WAV and writes a `.g711.xz` file. Without `OUT.g711.xz` the output is the input name with `.wav` replaced by `.g711.xz`.

Encoding is refused when the samples are not all values of one G.711 law. No output file is written in that case.

### transcode

Converts a file to the other law: `u` for mu-law, `a` for A-law.

```bash
g711xz transcode rec.g711.xz a rec.alaw.g711.xz
```

This is the one lossy command. The two laws have different sample values, so every sample moves to the nearest value of the target law and the result no longer decodes to the original PCM. The output name is required and the command refuses to write over its input. A file that is already in the target law is copied unchanged.

## Platform Support

### Linux, macOS, Windows
- ✅ All commands
- ✅ The whole Python API
- ✅ No platform-specific code and no required dependencies
- ✅ A file written on one platform reads on any other

### Backends

The codec picks the fastest implementation it can import. All of them produce the same PCM and read each other's files.

| Backend | Used when | Notes |
|---|---|---|
| Rust | `g711xz._rust` is importable | built locally, see below |
| NumPy | `numpy` is importable | `pip3 install numpy` |
| Pure Python | always available | standard library only |

- ✅ The package from PyPI is pure Python and works without the other two
- ✅ `g711xz.HAS_RUST` and `g711xz.HAS_NUMPY` tell which accelerators were found
- ✅ The test suite checks every backend it can import against the same vectors
- ❌ The compressed bytes are not identical between the Rust backend and the others: they use different xz encoders. The payload inside the xz stream and the decoded PCM are identical

### Building the Rust Extension

Requires a Rust toolchain (rustc 1.97.1 or newer), [maturin](https://www.maturin.rs/) and an active virtualenv.

```bash
pip3 install maturin
maturin develop --release
```

This builds `g711xz/_rust.*.so` in place. Remove that file to go back to the Python backends.

## Supported Format

| Property | Value |
|---|---|
| Container | one xz stream (LZMA2, CRC64 check) |
| Magic and version | `CRG7`, version 1 |
| Laws | mu-law (PCMU, `u`) or A-law (PCMA, `a`), one law for both channels |
| Channels | 2, stored one after the other: left (caller), then right (callee) |
| Sample rate | 8000 Hz |
| Sample | one 8-bit G.711 code, expanded to signed 16-bit PCM on decoding |
| Length | up to 691200000 frames, one day of audio |
| Metadata | none |

The full specification with the header layout, the expansion formulas and a test vector is in **[FORMAT.md](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)**.

### WAV Files

- Input for `encode`: 2 channels, 16-bit, 8000 Hz
- Output of `decode`: 2 channels, 16-bit, 8000 Hz, the exact PCM of the recording

### PCM

In the Python API, PCM is always `bytes` of interleaved signed 16-bit little-endian stereo samples at 8000 Hz: `left[0], right[0], left[1], right[1], ...`, four bytes per frame. A law is `b"u"` (mu-law) or `b"a"` (A-law).

## Validation Rules

### Reading
- The file must be one complete xz stream
- The payload must hold the 16-byte header
- Magic must be `CRG7` and the version must be 1: an unknown version is refused, not guessed
- Law must be `u` or `a`, channels 2, the reserved byte 0, the sample rate 8000
- The body must be exactly `frames * 2` bytes
- The payload must not be longer than one day of audio

### Encoding
- Every sample of both channels must be a value of the mu-law table, or every sample a value of the A-law table
- Mu-law is tried first
- Samples are never rounded to the nearest code: audio that does not fit is refused
- Mu-law has two codes for sample 0 (`0xFF` and `0x7F`): the lower code `0x7F` is stored
- Trailing bytes short of a whole frame are ignored
- Zero frames is a valid file
- More than one day of audio is refused

### What Gets Refused in Practice
- Another codec on one of the legs
- The two legs on different laws
- An A-law leg with gaps filled with PCM 0: A-law has no code for 0
- Anything that was resampled, mixed, normalised or decoded from MP3 or Opus

### Transcoding
- The output name is required
- Writing over the input file is refused
- The result is lossy: it decodes to the nearest samples of the target law

## Error Messages

### Stream Errors
- `not a valid xz stream: ...` - Not an xz file, or a corrupted one
- `not a valid xz stream: truncated` - The file ends before the xz stream does
- `payload is longer than X bytes, not a call recording` - More data than one day of audio

### Header Errors
- `payload is X bytes, shorter than the header` - Less than 16 bytes inside the xz stream
- `bad magic X, not a .g711.xz file` - An xz file of another kind
- `unknown format version X, this reader knows 1` - A newer format version
- `unknown law X` - Law byte is neither `u` nor `a`
- `channels is X, expected 2` - Not a stereo recording
- `reserved byte is X, expected 0` - Reserved header byte is set
- `sample rate is X, expected 8000` - Not an 8 kHz recording
- `X frames is more than the 691200000 a file may hold` - Longer than one day
- `damaged: X code bytes for Y frames, expected Z` - Body length does not match the header

### WAV Errors
- `not a readable WAV file: ...` - Not a WAV file, or a damaged one
- `WAV is X ch, Y-bit, Z Hz; expected 2 ch, 16-bit, 8000 Hz` - A WAV of another format

### Refusals
- `PCM is not pure G.711 (mu-law or A-law on both channels), refusing to encode` - The samples are not all values of one law

### Other Errors
- `transcoding is lossy, refusing to write over the input file` - `transcode` was given the same input and output
- `unknown target law X` - `transcode_law` was given a law other than `b"u"` or `b"a"`
- `expected X frames, got Y` - `encode_stream` got a different number of frames than `total_frames`

The text after the colon in `not a valid xz stream: ...` and the way `X` is printed come from the backend in use and can differ between them.

## Python API

```python
import g711xz
```

### Decoding and Encoding

`decode(source) -> (law, frames, pcm)`

Decodes a `.g711.xz` file. `source` is the file content as `bytes`, a path, or a binary file object. Raises `FormatError` when the input is not a valid version 1 file.

`encode(source) -> bytes`

Encodes raw PCM and returns the content of a `.g711.xz` file. `source` is PCM as `bytes`, or a path or binary file object holding raw PCM (not a WAV file; use `read_wav` for that). Raises `RefusedError` when the samples are not all values of one law.

### WAV Files

`read_wav(path) -> pcm`

Returns the PCM of a 2-channel, 16-bit, 8000 Hz WAV. Raises `FormatError` for any other WAV format or an unreadable file.

`write_wav(path, pcm)`

Writes PCM as a 2-channel, 16-bit, 8000 Hz WAV.

### Streaming

`decode_stream(file_obj) -> iterator of (law, index, left, right)`

Reads a binary file object and yields one tuple per frame, the samples as signed 16-bit integers. The file is decompressed incrementally and the PCM is never built, so the memory used is the two code planes, 2 bytes per frame. Because the channels are stored one after the other, the first frame comes out only after the whole left channel was read.

A damaged header raises `FormatError` before the first frame. Damage further in (a truncated stream, a wrong body length) raises it at the end, after the frames that could be read.

`encode_stream(pcm_chunks, total_frames=None) -> iterator of bytes`

Takes an iterable of PCM chunks, cut anywhere, and yields the pieces of one `.g711.xz` file. The law in the header depends on every sample, so nothing is yielded before the input ends: this saves the caller a join, not memory. `total_frames`, when given, is checked against the input and a mismatch raises `FormatError`. Raises `RefusedError` like `encode`.

### Converting Between Laws

`transcode_law(data, target_law) -> bytes`

The library form of the `transcode` command: takes the content of a file and returns the content of a file in the target law. Lossy.

`transcode_codes(codes, from_law, to_law) -> bytes` does the same for raw code bytes, and `translation_table(from_law, to_law)` returns the 256-byte table behind both.

### Lower Level

| Function | Purpose |
|---|---|
| `decompress(data)` | xz stream to payload, `FormatError` on a bad stream |
| `read_payload(file_obj)` | the same from a file object, piece by piece |
| `parse_header(payload)` | validate a payload, return `(law, frames)` |
| `unpack_header(payload)` | validate only the 16 header bytes, return `(law, frames)` |
| `pack_file(law, frames, planes)` | header and code planes to the content of a file |
| `expand_ulaw(code)`, `expand_alaw(code)` | one G.711 code to a signed 16-bit sample |
| `expansion_tables(law)` | `(low, high)` byte tables for `bytes.translate` |
| `compression_table(law)` | list indexed by the unsigned 16-bit sample, giving its code or 256 |
| `replace_suffix(path, old, new)` | swap an extension, safe for the double `.g711.xz` |

### Constants

| Name | Value |
|---|---|
| `MAGIC` | `b"CRG7"` |
| `VERSION` | `1` |
| `CHANNELS` | `2` |
| `RATE` | `8000` |
| `SUFFIX` | `".g711.xz"` |
| `MAX_FRAMES` | `691200000`, one day of audio |
| `MAX_PAYLOAD` | `16 + 2 * MAX_FRAMES` bytes |
| `HEADER` | `struct.Struct("<4sBcBBII")` |
| `EXIT_BAD_INPUT`, `EXIT_REFUSED` | `2`, `3` |
| `HAS_NUMPY`, `HAS_RUST` | whether an optional accelerator was found |

### Exceptions

Both are subclasses of `ValueError`.

- `FormatError` - The input is not a valid `.g711.xz` version 1 file, or not a WAV of the expected format
- `RefusedError` - The PCM is not made of the values of a single G.711 law, so a lossless file cannot be made

## Examples

### Round Trip

```python
law, frames, pcm = g711xz.decode("rec.g711.xz")
print(law, frames / g711xz.RATE, "seconds")

data = g711xz.encode(pcm)
assert g711xz.decode(data)[2] == pcm
```

### Fall Back to Another Format

```python
try:
    data = g711xz.encode(pcm)
except g711xz.RefusedError:
    data = None     # store this call in another format
```

### Read Only the Header

```python
with open("rec.g711.xz", "rb") as source:
    law, frames = g711xz.parse_header(g711xz.decompress(source.read()))
```

### Scan a Recording Without Building the PCM

```python
with open("rec.g711.xz", "rb") as source:
    loudest = max(abs(left) for law, index, left, right in g711xz.decode_stream(source))
```

### Convert to Other Audio Formats

Everything goes through the PCM. Decode to WAV first.

| Target | How | Lossless |
|---|---|---|
| WAV | `g711xz decode rec.g711.xz rec.wav` | yes |
| MP3 | `lame --quiet -m s -b 32 rec.wav rec.mp3` | no |
| Ogg/Opus | `opusenc --quiet --bitrate 32 --speech rec.wav rec.ogg` | no |

- Keep the two channels apart (true stereo, `-m s` for MP3): the channel is the only thing that says who is speaking
- Do not resample, dither or normalise on the way to WAV, or the result is no longer the recording
- Only WAV, or another lossless container of the same PCM, can be turned back into a `.g711.xz`. PCM decoded from MP3 or Opus is no longer made of G.711 values and the encoder will refuse it

## Limits, Memory and Speed

- A reader refuses a file whose payload is longer than `MAX_PAYLOAD`, one day of audio, and the encoder refuses to write one. Without a limit a few kilobytes of xz could expand to gigabytes of zeros
- Except for `decode_stream`, the whole recording is held in memory: 4 bytes of PCM and 2 bytes of codes per frame, so 115 MB of PCM and 58 MB of codes for a one-hour call
- A one-minute call encodes in a fraction of a second and decodes in a few hundredths
