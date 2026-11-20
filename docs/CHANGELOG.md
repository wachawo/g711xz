# CHANGELOG

0.0.2 (2026-11-20)
========
- Wheels with the Rust extension for Linux (x86_64 and aarch64, glibc and musl), macOS and Windows, plus a pure Python fallback wheel
- The Rust extension releases the GIL while it encodes and decodes
- liblzma (xz-utils) replaces lzma-turbo, so the Rust extension writes the same xz bytes as Python's lzma
- Lookup tables are built once instead of on the stack, and long calls take less memory
- An xz error during encode is raised as FormatError

0.0.1 (2026-11-20)
========
- Same code as 0.0.0, published to PyPI

0.0.0 (2026-11-20)
========
- Command line tool with `info`, `decode`, `encode` and `transcode`
- Python API: `decode`, `encode`, `read_wav`, `write_wav`, `decode_stream`, `encode_stream`, `transcode_law`
- Lossless round trip for mu-law and A-law recordings
- Refusal of PCM that is not pure G.711 (exit code 3)
- Strict reader: header and body validation, truncated stream detection, limit on the decompressed size
- Optional NumPy and Rust backends with a pure Python fallback
- File format specification with a test vector in `docs/FORMAT.md`
