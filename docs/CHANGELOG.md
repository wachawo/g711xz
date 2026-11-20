# CHANGELOG

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
