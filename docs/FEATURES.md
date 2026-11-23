# g711xz Features

## Exit Codes

The `g711xz` command returns the following exit codes:

- **0** - Success
- **2** - Bad input: a damaged or foreign file, a WAV of the wrong format, a file that cannot be opened, or wrong command line arguments
- **3** - Encode refused: the PCM is not pure G.711, so a lossless file cannot be made

| Code | Constant | Prefix on stderr | Meaning |
|---|---|---|---|
| 0 | | | Success |
| 2 | `EXIT_BAD_INPUT` | `error:` | Damaged or foreign file, wrong WAV, OS error, usage error |
| 3 | `EXIT_REFUSED` | `refused:` | `encode`: the PCM is not pure G.711 |

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

# A valid VOX file is read like a lossless one
g711xz decode rec.vox.g711.xz
echo $?  # Returns 0
```

Errors go to stderr with an `error:` prefix (exit code 2) or a `refused:` prefix (exit code 3). A VOX file is not an error and has no exit code of its own: the commands that read it name the mode in their output. With several files, `info` reports each bad file, still prints the others and returns 2.

### Output of `info`

```
FILE:
  format    CRG7 version 1
  mode      lossless | vox (beta): quiet line noise replaced, not an exact copy
  law       mu-law (PCMU) | A-law (PCMA)
  channels  2 (left caller, right callee)
  rate      8000 Hz
  frames    number of frames per channel
  duration  seconds
  size      file size in bytes (average bitrate in kbit/s)
```

The `mode` line is printed for every file, right after `format`. A lossless file:

```
rec.g711.xz:
  format    CRG7 version 1
  mode      lossless
  law       mu-law (PCMU)
  channels  2 (left caller, right callee)
  rate      8000 Hz
  frames    480000
  duration  60.000 s
  size      108316 bytes (14.4 kbit/s)
```

A VOX file:

```
rec.vox.g711.xz:
  format    CRG7 version 1
  mode      vox (beta): quiet line noise replaced, not an exact copy
  law       mu-law (PCMU)
  channels  2 (left caller, right callee)
  rate      8000 Hz
  frames    480000
  duration  60.000 s
  size      95318 bytes (12.7 kbit/s)
```

## Commands

```
g711xz info      FILE.g711.xz [FILE.g711.xz ...]
g711xz decode    FILE.g711.xz [OUT.wav]
g711xz encode    FILE.wav     [OUT.g711.xz] [--vox]
g711xz transcode FILE.g711.xz {u,a} OUT.g711.xz
```

`--vox` belongs to `encode` only and goes after the subcommand, in any position; the examples put it last. It is written in full: `--v` and `--vo` are usage errors. `g711xz --vox encode ...` is a usage error (exit code 2). `info`, `decode` and `transcode` take no flag: they read both modes and the file header says which one it is.

### info

Prints the header of each file, the mode, the duration and the average bitrate. It reads lossless and VOX files alike, and its `mode` line is the way to tell them apart.

### decode

Writes a 2-channel, 16-bit, 8000 Hz WAV with the PCM stored in the file: for a lossless file that is the exact PCM of the recording. Without `OUT.wav` the output is the input name with `.g711.xz` replaced by `.wav`.

Both modes are decoded, with no flag. For a VOX file the result line ends with `, vox (not an exact copy)`, so the output says when the WAV is not the exact recording.

### encode

Reads a 2-channel, 16-bit, 8000 Hz WAV and writes a `.g711.xz` file. Without `OUT.g711.xz` the output is the input name with `.wav` replaced by `.g711.xz`.

Encoding is refused when the samples are not all values of one G.711 law. No output file is written in that case.

### encode --vox (beta)

```bash
g711xz encode rec.wav --vox
g711xz encode rec.wav rec.vox.g711.xz --vox
```

Writes a VOX file. Speech is kept bit for bit; long stretches of even line noise are replaced by a short piece of the same noise repeated, which compresses like silence. The file is marked in its header, `info` shows it, and it is **not an exact copy of the recording**. Off by default: without `--vox` the file is lossless.

Without an output name the file is the input name with `.wav` replaced by `.vox.g711.xz`. The result line says what was written:

```
rec.wav -> rec.vox.g711.xz: mu-law (PCMU), vox (not an exact copy), 95318 bytes
```

See [VOX Mode (Beta)](#vox-mode-beta).

### transcode

Converts a file to the other law: `u` for mu-law, `a` for A-law.

```bash
g711xz transcode rec.g711.xz a rec.alaw.g711.xz
```

This is the one lossy command. The two laws have different sample values, so every sample moves to the nearest value of the target law and the result no longer decodes to the original PCM. The output name is required and the command refuses to write over its input. A file that is already in the target law is copied unchanged.

Both modes are converted, with no flag, and the mode is kept: a VOX file gives a VOX file, and its result line contains `, vox (not an exact copy)`.

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
| Rust | `g711xz._rust` is importable | in the wheels on PyPI, or built from source |
| NumPy | `numpy` is importable | `pip3 install numpy` |
| Pure Python | always available | standard library only |

- ✅ PyPI has wheels with the Rust extension for Linux (x86_64 and aarch64, glibc and musl), macOS and Windows x64; anywhere else pip installs a pure Python wheel that works without the other two backends
- ✅ `g711xz.HAS_RUST` and `g711xz.HAS_NUMPY` tell which accelerators were found
- ✅ The test suite checks every backend it can import against the same vectors
- ✅ The Rust extension uses xz-utils (liblzma), the same library as Python's lzma module: the payload and the decoded PCM are identical across backends, and with the same xz-utils version so are the compressed bytes

### Building the Rust Extension

Not needed when installing a wheel from PyPI. Building from source requires a Rust toolchain, a C compiler (xz-utils is built from source and linked statically), [maturin](https://www.maturin.rs/) and an active virtualenv.

```bash
pip3 install maturin
maturin develop --release
```

This builds `g711xz/_rust.*.so` in place. Remove that file to go back to the Python backends.

## VOX Mode (Beta)

The lossless file cannot shrink line noise: noise is random, and random data does not compress. The VOX mode gives the noise up and keeps everything else.

- ✅ Speech is stored bit for bit, with 800 ms kept before and after it
- ✅ Pauses shorter than 1 s are never touched, so words and their boundaries stay whole
- ✅ A replaced stretch repeats its own first 250 ms: it keeps the level and the sound of the line, and every sample is one the channel really had
- ✅ A digitally silent line is left alone, and so is any stretch where something happens (a frame more than 6 dB above the noise around it)
- ✅ A speech-to-text transcript of a VOX file keeps 99.96% of the words of the transcript of the original recording
- ✅ About 11% smaller than the lossless file on average, at the same encoding cost. The gain follows the share of line noise in a recording: 1 to 4% where it is mostly speech, far more where it is mostly noise
- ❌ Not an exact copy of the recording: the replaced noise is gone
- ❌ Needs 0.0.3 or later. Releases up to 0.0.2 refuse such a file: it is marked as mode 1 in the header

It is a beta: the file layout will not change, but the defaults of the options may.

### One Word, Off by Default

VOX is off until you say `vox` when writing: without the word g711xz never writes a VOX file. Reading needs no word at all. The header of the file says which mode it is, and every reader opens both.

| | Without `vox` | With `vox=True` / `--vox` |
|---|---|---|
| `encode`, `encode_stream` | a lossless file | a VOX file |

| | Takes `vox` | Reads |
|---|---|---|
| `decode`, `decode_stream`, `transcode_law`, `parse_header`, `unpack_header` | no | both modes |
| `info`, `read_mode` | no | both modes, and report which one |

### Writing

```bash
g711xz encode rec.wav --vox                      # writes rec.vox.g711.xz
g711xz encode rec.wav out.vox.g711.xz --vox
```

```python
data = g711xz.encode(pcm, vox=True)                                       # a VOX file, default options
data = g711xz.encode(pcm, vox=True, hangover_ms=1200, min_quiet_ms=2000)  # a more careful one
voxed, changed = g711xz.vox_pcm(pcm)                                      # the PCM a VOX file decodes to
```

`vox` is keyword-only. The options are library-only, the command line has no tuning flags:

| Option | Default | Meaning |
|---|---|---|
| `threshold_db` | `-45.0` | a 20 ms frame above this level is active |
| `hangover_ms` | `800` | kept before and after every active frame |
| `min_quiet_ms` | `1000` | only quiet stretches at least this long are replaced |
| `fill_ms` | `250` | the piece of its own noise a replaced stretch repeats |
| `floor_db` | `-70.0` | a stretch whose median level is at or below this is left alone |
| `peak_db` | `6.0` | a stretch with a frame this far above its median is left alone |

An option given without `vox=True` raises `TypeError("vox options need vox=True")`, so a tuned call can never silently write a lossless file. An unknown option name raises `TypeError` as well. PCM that is not pure G.711 raises `RefusedError` as in the lossless mode.

### Reading

```bash
g711xz decode rec.vox.g711.xz            # writes rec.vox.wav
g711xz transcode rec.vox.g711.xz a rec.alaw.vox.g711.xz
```

```python
law, frames, pcm = g711xz.decode(data)      # a lossless or a VOX file
```

- `decode`, `decode_stream` and `transcode_law` read both modes and take no `vox` argument: a call written for 0.0.2 reads a VOX file unchanged
- `parse_header` and `unpack_header` accept both modes as well, so code that reads a file through the lower level helpers works on a VOX file too
- `transcode_law` keeps the mode: a VOX file gives a VOX file, also when it is already in the target law and is returned unchanged
- On the command line `decode` and `transcode` say what they read: for a VOX file the result line carries `, vox (not an exact copy)`
- A VOX file is never an error. A damaged one raises `FormatError` like a damaged lossless file
- The audio handed out says nothing about the mode. Code that needs the exact recording asks the mode first, see below

### Asking the Mode

```python
if g711xz.read_mode("rec.g711.xz") == g711xz.MODE_VOX:
    ...
```

`read_mode(source)` takes what `decode` takes (the file content as `bytes`, a path, or a binary file object), reads only the header and returns `MODE_LOSSLESS` or `MODE_VOX`. It raises `FormatError` for a bad file. This is the check for code that must have the exact recording: skip or reject the file when the answer is `MODE_VOX`.

```bash
g711xz info rec.g711.xz | grep -q '^  mode      vox'
```

`info` prints the mode line for every file. Its second word is the stable token, always `lossless` or `vox`. The exit code does not tell the modes apart: `decode` returns 0 for both.

### Declare It Once

There is no module-level switch and no environment variable, and only writing has anything to declare. A pipeline that wants one place to turn VOX on or off keeps a constant of its own and passes it to the encoder:

```python
VOX = False     # the one place that decides

data = g711xz.encode(pcm, vox=VOX)
law, frames, pcm = g711xz.decode(path)      # reads whatever was written
```

`functools.partial(g711xz.encode, vox=True)` does the same for a single function. A consumer of exact recordings checks `read_mode` before it decodes.

### File Names

Both modes use the `.g711.xz` extension, and header byte 7 is the only authority.

- The recommended name for a VOX file is `NAME.vox.g711.xz` (`g711xz.VOX_SUFFIX`). It still ends in `.g711.xz`, so existing globs keep matching
- `g711xz encode rec.wav --vox` without an output name writes `rec.vox.g711.xz`, so a VOX file and a lossless file of the same recording do not land on one name
- `g711xz decode rec.vox.g711.xz` without an output name writes `rec.vox.wav`
- An output name given explicitly is used as it is. The mode is never read from a name and no name is rejected: a VOX file called `rec.g711.xz` is still a VOX file, and a lossless file called `x.vox.g711.xz` is still lossless
- A consumer of exact recordings whose `*.g711.xz` glob picks up a VOX file gets its audio with no error, so it filters on `read_mode` or on the `mode` line of `info`, not on the name

### Caveats

- A VOX file decoded to WAV loses the mark: the WAV is plain audio, and encoding it again gives a lossless file of the altered audio, so keep `.vox` in the name.
- Mode 0 means "not VOX", not "never transcoded": `transcode` is lossy too and writes mode 0 for a lossless input.

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
- Law must be `u` or `a`, channels 2, the mode 0 or 1, the sample rate 8000
- Both modes are read by every command and function, with no switch; `info`, `read_mode` and the result lines of `decode` and `transcode` say which mode a file is
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
- `unknown mode X, this reader knows 0 (lossless) and 1 (vox)` - A mode this version does not know
- `sample rate is X, expected 8000` - Not an 8 kHz recording
- `X frames is more than the 691200000 a file may hold` - Longer than one day
- `damaged: X code bytes for Y frames, expected Z` - Body length does not match the header

### WAV Errors
- `not a readable WAV file: ...` - Not a WAV file, or a damaged one
- `WAV is X ch, Y-bit, Z Hz; expected 2 ch, 16-bit, 8000 Hz` - A WAV of another format

### Refusals
- `PCM is not pure G.711 (mu-law or A-law on both channels), refusing to encode` - The samples are not all values of one law

### VOX
- `vox options need vox=True` - `encode` or `encode_stream` got a VOX option while `vox` is off (`TypeError`)

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

Decodes a `.g711.xz` file. `source` is the file content as `bytes`, a path, or a binary file object. Both modes are decoded; the PCM of a VOX file is not the exact recording, and `read_mode` tells which mode it is. Raises `FormatError` when the input is not a valid version 1 file.

`encode(source, *, vox=False, **vox_options) -> bytes`

Encodes raw PCM and returns the content of a `.g711.xz` file. `source` is PCM as `bytes`, or a path or binary file object holding raw PCM (not a WAV file; use `read_wav` for that). Raises `RefusedError` when the samples are not all values of one law. With `vox=True` the result is a VOX file; the options are listed under [VOX Mode (Beta)](#vox-mode-beta).

`read_mode(source) -> int`

Returns `MODE_LOSSLESS` or `MODE_VOX` for the same kinds of `source` as `decode`, reading only the header. Raises `FormatError` for a bad file.

`vox` is keyword-only and belongs to `encode` and `encode_stream` alone. The reading functions have the signatures of 0.0.2, so every call written for 0.0.2 works unchanged and reads both modes.

### WAV Files

`read_wav(path) -> pcm`

Returns the PCM of a 2-channel, 16-bit, 8000 Hz WAV. Raises `FormatError` for any other WAV format or an unreadable file.

`write_wav(path, pcm)`

Writes PCM as a 2-channel, 16-bit, 8000 Hz WAV.

### Streaming

`decode_stream(file_obj) -> iterator of (law, index, left, right)`

Reads a binary file object and yields one tuple per frame, the samples as signed 16-bit integers. The file is decompressed incrementally and the PCM is never built, so the memory used is the two code planes, 2 bytes per frame. Because the channels are stored one after the other, the first frame comes out only after the whole left channel was read.

Both modes are read. A damaged header raises `FormatError` before the first frame. Damage further in (a truncated stream, a wrong body length) raises it at the end, after the frames that could be read.

`encode_stream(pcm_chunks, total_frames=None, *, vox=False, **vox_options) -> iterator of bytes`

Takes an iterable of PCM chunks, cut anywhere, and yields the pieces of one `.g711.xz` file. The law in the header depends on every sample, so nothing is yielded before the input ends: this saves the caller a join, not memory. `total_frames`, when given, is checked against the input and a mismatch raises `FormatError`. Raises `RefusedError` like `encode`, and takes `vox` and the VOX options like `encode`.

### Converting Between Laws

`transcode_law(data, target_law) -> bytes`

The library form of the `transcode` command: takes the content of a file and returns the content of a file in the target law. Lossy. Both modes are read and the mode is kept: a VOX file gives a VOX file, also when it is already in the target law.

`transcode_codes(codes, from_law, to_law) -> bytes` does the same for raw code bytes, and `translation_table(from_law, to_law)` returns the 256-byte table behind both.

### Lower Level

| Function | Purpose |
|---|---|
| `decompress(data)` | xz stream to payload, `FormatError` on a bad stream |
| `read_payload(file_obj)` | the same from a file object, piece by piece |
| `parse_header(payload)` | validate a payload of either mode, return `(law, frames)` |
| `unpack_header(payload)` | validate only the 16 header bytes, either mode, return `(law, frames)` |
| `pack_file(law, frames, planes, mode=MODE_LOSSLESS)` | header and code planes to the content of a file |
| `vox_pcm(pcm, fill_ms=VOX_FILL_MS, **vox_options)` | `(pcm, changed)`: the PCM a VOX file would decode to |
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
| `VOX_SUFFIX` | `".vox.g711.xz"`, the recommended name of a VOX file |
| `MAX_FRAMES` | `691200000`, one day of audio |
| `MAX_PAYLOAD` | `16 + 2 * MAX_FRAMES` bytes |
| `HEADER` | `struct.Struct("<4sBcBBII")` |
| `EXIT_BAD_INPUT`, `EXIT_REFUSED` | `2`, `3` |
| `MODE_LOSSLESS`, `MODE_VOX` | `0`, `1`, header byte 7 |
| `MODE_NAMES` | `{MODE_LOSSLESS: "lossless", MODE_VOX: "vox"}` |
| `VOX_FRAME` | `160` samples, 20 ms |
| `VOX_THRESHOLD_DB`, `VOX_HANGOVER_MS`, `VOX_MIN_QUIET_MS` | `-45.0`, `800`, `1000` |
| `VOX_FILL_MS`, `VOX_FLOOR_DB`, `VOX_PEAK_DB` | `250`, `-70.0`, `6.0` |
| `HAS_NUMPY`, `HAS_RUST` | whether an optional accelerator was found |

### Exceptions

All are subclasses of `ValueError`.

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
