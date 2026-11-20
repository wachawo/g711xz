## g711xz - lossless storage for G.711 call recordings

[![CI](https://github.com/wachawo/g711xz/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/g711xz/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/wachawo/g711xz/branch/main/graph/badge.svg)](https://codecov.io/gh/wachawo/g711xz?branch=main)
[![PyPI](https://img.shields.io/pypi/v/g711xz.svg)](https://pypi.org/project/g711xz/)
[![Downloads](https://img.shields.io/pypi/dm/g711xz.svg)](https://pypi.org/project/g711xz/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/g711xz/blob/main/LICENSE)
[![Python](https://img.shields.io/pypi/pyversions/g711xz.svg)](https://pypi.org/project/g711xz/)

Every call that crosses a phone network as PCMU or PCMA is already compressed: each 16-bit sample is one of at most 256 values. Store it as WAV and every second byte is redundant. Store it as MP3 or Opus and the codec quietly rewrites the audio, in ways a person barely hears and a speech recognizer does.

g711xz keeps the call exactly as it arrived. It turns the samples back into their 8-bit G.711 codes, packs them with xz, and gives back the original PCM bit for bit. Ringing and silence shrink to almost nothing; a conversation takes more space than Opus. It is a command line tool and a pure Python library for Linux, macOS, and Windows.

**[English](https://github.com/wachawo/g711xz/blob/main/README.md)** | [Spanish](https://github.com/wachawo/g711xz/blob/main/docs/README_ES.md) | [Portuguese](https://github.com/wachawo/g711xz/blob/main/docs/README_PT.md) | [French](https://github.com/wachawo/g711xz/blob/main/docs/README_FR.md) | [German](https://github.com/wachawo/g711xz/blob/main/docs/README_DE.md) | [Italian](https://github.com/wachawo/g711xz/blob/main/docs/README_IT.md) | [Russian](https://github.com/wachawo/g711xz/blob/main/docs/README_RU.md) | [Chinese](https://github.com/wachawo/g711xz/blob/main/docs/README_ZH.md) | [Japanese](https://github.com/wachawo/g711xz/blob/main/docs/README_JA.md) | [Hindi](https://github.com/wachawo/g711xz/blob/main/docs/README_HI.md)

### Requirements

- **Python 3.9 or higher**
- **Linux, macOS, Windows**: no platform-specific requirements
- **Dependencies**: none, the standard library is enough
- **Optional**: NumPy or the Rust extension, used as accelerators when present

### File Format

One file is one recorded call: the left channel is the caller, the right channel is the callee.

- ✅ Lossless: decoding returns the recorder's 16-bit PCM bit for bit
- ✅ mu-law (PCMU) and A-law (PCMA)
- ✅ About a quarter smaller than xz on the raw PCM
- ✅ One standard xz stream, readable with `xz` alone
- ❌ Audio that is not pure G.711: refused instead of rounded
- ❌ Metadata: the file holds the audio and nothing else

### How it compares

| | PCM | xz | g711xz | Opus 32 kbit/s | MP3 32 kbit/s |
|---|---|---|---|---|---|
| Decodes back to the original | yes | yes | yes | no | no |
| Words matching the original transcript, % | 100 | 99.9 | 99.9 | 94.2 | 93.8 |
| Calls with a word-for-word identical transcript, % | 100 | 99.8 | 99.8 | 67.3 | 60.5 |
| Average size, kbit/s | 256 | 24.7 | 18.8 | 20.2 | 32.4 |
| 5-minute call, MB | 9.60 | 2.29 | 1.77 | 0.97 | 1.20 |
| CPU to encode, relative to Opus | 0 | 0.4 | 0.2 | 1 | 0.16 |

- **xz alone is lossless too, just bigger.** It compresses the 16-bit samples, g711xz the 8-bit codes they were made from: xz comes out about 30% larger and takes twice the CPU.
- **The 0.1% is the recognizer, not the file.** The lossless formats decode to exactly the original bytes; a second pass of the same audio does not always give the same words.
- **Why a conversation is larger than Opus and MP3.** They work to a bitrate and throw away whatever does not fit. g711xz keeps every sample, and in speech the low bits of each G.711 code carry line noise and fine detail that no lossless compressor can shrink. Ringing and silence work the other way: they compress to almost nothing, so across many calls g711xz comes out smaller on average.

### Installation

```bash
pip3 install g711xz
```

Or from GitHub:

```bash
pip3 install git+https://github.com/wachawo/g711xz.git
```

### Usage

```bash
# Show the header, duration and bitrate of a file
g711xz info rec.g711.xz

# Decode to a lossless stereo WAV (writes rec.wav)
g711xz decode rec.g711.xz

# Decode to a chosen file
g711xz decode rec.g711.xz out.wav

# Encode a 2-channel 16-bit 8000 Hz WAV (writes rec.g711.xz)
g711xz encode rec.wav

# Convert to the other law, lossy (u = mu-law, a = A-law)
g711xz transcode rec.g711.xz a rec.alaw.g711.xz

# Show help
g711xz --help
```

Example output of `g711xz info`:

```
rec.g711.xz:
  format    CRG7 version 1
  law       mu-law (PCMU)
  channels  2 (left caller, right callee)
  rate      8000 Hz
  frames    480000
  duration  60.000 s
  size      108316 bytes (14.4 kbit/s)
```

### Python API

```python
import g711xz

# Decode: law is b"u" or b"a", pcm is interleaved s16le stereo at 8000 Hz
law, frames, pcm = g711xz.decode("rec.g711.xz")
g711xz.write_wav("rec.wav", pcm)

# Encode: returns the bytes of a .g711.xz file
data = g711xz.encode(g711xz.read_wav("rec.wav"))
```

Encoding raises `g711xz.RefusedError` when the PCM is not pure G.711, and reading raises `g711xz.FormatError` for a damaged file.

### Exit codes

| Code | Meaning |
|------|---------|
| 0    | Success. |
| 2    | Bad input: a damaged or foreign file, a WAV of the wrong format, a missing file, bad CLI args. |
| 3    | Encode refused: the PCM is not pure G.711, so a lossless file cannot be made. |

### Commands

- `info FILE [FILE ...]` - Show the header, duration and bitrate
- `decode FILE.g711.xz [OUT.wav]` - Decode to a lossless stereo WAV
- `encode FILE.wav [OUT.g711.xz]` - Encode a 2-channel 16-bit 8000 Hz WAV
- `transcode FILE.g711.xz {u,a} OUT.g711.xz` - Convert to the other law (lossy)
- `-h, --help` - Show help

### Features

- **Lossless round trip** for mu-law and A-law recordings
- **Strict encoder**: refuses audio that is not pure G.711 instead of storing it with losses
- **Strict reader**: rejects damaged, truncated and oversized files
- **Streaming decoder** that never builds the whole PCM in memory
- **Conversion between laws** (mu-law to A-law and back)
- **Optional accelerators**: NumPy and a Rust extension, with a pure Python fallback
- **Cross-platform** (Linux, macOS, Windows)

**[Features Documentation](https://github.com/wachawo/g711xz/blob/main/docs/FEATURES.md)** - Comprehensive guide to commands, the Python API, validation rules, error messages, and examples.

**[File Format](https://github.com/wachawo/g711xz/blob/main/docs/FORMAT.md)** - Specification of the `.g711.xz` layout with a test vector, enough to write an independent reader or writer.

### Development Tools

```bash
pip3 install -e ".[dev]"
ruff check .
ruff format --check .
mypy g711xz

# Optional Rust extension (needs a Rust toolchain and an active virtualenv)
maturin develop --release
```

### Testing

```bash
pytest --cov=g711xz --cov-report=term-missing --cov-report=xml
# CI automatically uploads coverage.xml to Codecov

# Standard library only
python3 -m unittest -v test_g711xz
```

### License

MIT License
