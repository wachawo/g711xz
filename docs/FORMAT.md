# The `.g711.xz` file format

Version 1 of the format. This document is enough to write an independent
reader or writer.

## What a file is

One file is one recorded phone call: stereo, 8 kHz, left channel = caller,
right channel = callee. The file holds the 8-bit G.711 codes of both channels,
one channel after the other, behind a 16-byte header, all inside one standard
xz stream.

Decoding gives back the recorder's 16-bit PCM bit for bit. That is the whole
contract: `decode(encode(pcm)) == pcm`, always.

## Why it is lossless and still small

A recorder that receives PCMU or PCMA only expands the codes it was sent, so
every 16-bit sample is one of 255 (mu-law) or 256 (A-law) values. Storing the
8-bit code instead of the 16-bit sample loses nothing.

Plan on roughly 2 to 4 kB per second of call, about the size of 32 kbit/s
Opus. Quiet lines compress better, noisy ones worse. Raw PCM is 32 kB per
second. The format is not a way to save space over a lossy codec; it is a way
to keep the exact audio at a comparable size.

## Layout

The file is one xz stream (`.xz` container, LZMA2, CRC64 check). Any xz decoder
reads it. The decompressed payload is:

| Offset | Size | Field | Value |
|---|---|---|---|
| 0 | 4 | magic | `CRG7` |
| 4 | 1 | version | `1` |
| 5 | 1 | law | ASCII `u` (mu-law) or `a` (A-law) |
| 6 | 1 | channels | `2` |
| 7 | 1 | reserved | `0` |
| 8 | 4 | sample rate, u32 little-endian | `8000` |
| 12 | 4 | frames per channel, u32 little-endian | N |
| 16 | N | codes of channel 0 (left, caller) | one byte per sample |
| 16+N | N | codes of channel 1 (right, callee) | one byte per sample |

In Python the header is `struct.Struct("<4sBcBBII")`, 16 bytes. The payload is
exactly `16 + 2*N` bytes; anything else is a damaged file.

The layout is planar, not interleaved: all of the left channel, then all of
the right. One law covers both channels.

The codes are plain ITU-T G.711, the same bytes an RTP PCMU or PCMA payload
carries. Expansion to a signed 16-bit sample:

```python
def expand_ulaw(code):
    value = ~code & 0xFF
    magnitude = ((((value & 0x0F) << 3) + 0x84) << ((value >> 4) & 0x07)) - 0x84
    return -magnitude if value & 0x80 else magnitude

def expand_alaw(code):
    value = code ^ 0x55
    exponent = (value >> 4) & 0x07
    mantissa = value & 0x0F
    if exponent == 0:
        magnitude = (mantissa << 4) + 8
    else:
        magnitude = ((mantissa << 4) + 0x108) << (exponent - 1)
    return magnitude if value & 0x80 else -magnitude
```

Ranges: mu-law -32124..32124, A-law -32256..32256.

## Reading a file

1. Decompress the xz stream.
2. Check the header: magic `CRG7`, version 1, law `u` or `a`, channels 2,
   reserved 0, rate 8000. Refuse anything else, and refuse an unknown version
   rather than guess.
3. Check the body is exactly `frames * 2` bytes.
4. Expand each code through the table of the file's law and interleave:
   output frame i is `(left[i], right[i])` as s16 little-endian.

The result is interleaved s16le stereo PCM at 8 kHz.

A complete decoder to WAV, standard library only:

```python
import lzma, struct, sys, wave

HEADER = struct.Struct("<4sBcBBII")
EXPAND = {b"u": expand_ulaw, b"a": expand_alaw}   # the two functions above

def decode_g711xz(data: bytes) -> bytes:
    payload = lzma.decompress(data)
    magic, version, law, channels, reserved, rate, frames = HEADER.unpack_from(payload)
    if (magic, version, channels, reserved, rate) != (b"CRG7", 1, 2, 0, 8000) or law not in EXPAND:
        raise ValueError("not a .g711.xz version 1 file")
    body = payload[HEADER.size:]
    if len(body) != frames * channels:
        raise ValueError(f"damaged: {len(body)} codes for {frames} frames")
    samples = [EXPAND[law](code) & 0xFFFF for code in range(256)]
    low = bytes(sample & 0xFF for sample in samples)
    high = bytes(sample >> 8 for sample in samples)
    pcm = bytearray(frames * 4)
    for channel in range(channels):
        plane = body[channel * frames:(channel + 1) * frames]
        pcm[channel * 2::4] = plane.translate(low)
        pcm[channel * 2 + 1::4] = plane.translate(high)
    return bytes(pcm)

with open(sys.argv[1], "rb") as source:
    pcm = decode_g711xz(source.read())
with wave.open(sys.argv[2], "wb") as sink:
    sink.setnchannels(2); sink.setsampwidth(2); sink.setframerate(8000)
    sink.writeframes(pcm)
```

By hand, with nothing but `xz` and `sox`:

```bash
xz -dc rec.g711.xz | head -c 16 | xxd
```

```bash
# Left channel of a mu-law file as WAV. FRAMES is the u32 at offset 12; use -t al for A-law.
xz -dc rec.g711.xz | tail -c +17 | head -c $FRAMES | sox -t ul -r 8000 -c 1 - left.wav
```

## Writing a file

Input is interleaved s16le stereo PCM at 8 kHz. Trailing bytes short of a
whole frame are ignored. Zero frames is a valid file.

1. Find the law: every sample of both channels must be a value of the mu-law
   table, or every sample a value of the A-law table. Mu-law is tried first.
2. If neither holds, refuse. Do not round to the nearest code: that would be a
   lossy file wearing a lossless name. Store such a call in another format.
3. Map each sample back to its code and write the header, the left plane and
   the right plane as one xz stream.

What gets refused in practice: another codec on a leg, the two legs on
different laws, and an A-law leg with gaps. A gap is silence that a recorder
filled with PCM 0, and A-law has no code for 0 (its smallest magnitude is 8).

Two details that matter for a compatible encoder:

- Mu-law has two codes for sample 0: `0xFF` and `0x7F`. The encoder keeps the
  lower code, `0x7F`. So the code stream is not necessarily the bytes that were
  on the wire: the PCM is what round-trips, not the RTP payload. Files from two
  encoders are comparable only by their decoded PCM.
- xz settings: preset 6, with the LZMA2 dictionary cut to the size of the codes
  (`max(4096, min(8 MiB, frames * 2))`). Preset 6 otherwise asks for about
  94 MB per encoder. Any settings decode the same; they only affect memory use
  and file size.

## Telling files apart

- By content: an xz stream starts with `fd 37 7a 58 5a 00`, and the payload of
  a `.g711.xz` file starts with `CRG7`. An xz file without `CRG7` is something
  else.
- By name: the extension is double, `.g711.xz`. `os.path.splitext` cuts it
  after `.g711`, so strip the suffix explicitly.

## What is not in the file

The file carries no metadata: no call id, no timestamps, no party numbers.
Keep those in the file name or beside the file.

## Properties of the audio

- A lost packet is whatever the recorder wrote in its place, usually exact
  PCM 0. The two channels keep the alignment they had on the wire.
- Sizes: one hour is 28.8 M frames, 57.6 MB of codes, 115 MB of PCM. A simple
  decoder holds all of it in memory.
- Because the layout is planar, a streaming decoder cannot emit interleaved PCM
  until it has the whole left plane (N bytes, 8 kB per second of call).

## Test vector

Eight frames of mu-law. The whole file, 88 bytes, as hex:

```
fd377a585a000004e6d6b4460200210100000000372797d601001f4352473701750200401f0000080000007ff0e1d2c3b4a5967f706152433425000095f458a96aad003a000138201829770c1fb6f37d010000000004595a
```

Decompressed payload, 32 bytes (header, left plane, right plane):

```
4352473701750200401f000008000000 7ff0e1d2c3b4a596 7f70615243342500
```

Expected samples:

```
left   0   120   356   812   1692   3388   6652   12924
right  0  -120  -356  -812  -1692  -3388  -6652  -32124
```

Expected PCM (s16le, interleaved), 32 bytes, sha256
`c6803f47d9b7b6062fffacff870666c06bf43435b8078f0ed966eeda7208a9d6`:

```
00000000780088ff64019cfe2c03d4fc9c0664f93c0dc4f2fc1904e67c328482
```

The first left sample was built from code `0xFF` and is stored as `0x7F`: the
two-zeros rule above, visible in the payload.

An encoder does not have to reproduce the 88 bytes of the file: different xz
implementations compress the same payload to different bytes. The payload and
the decoded PCM are what must match.

## Versioning

The format version is the contract. A change to the layout means version 2,
and a reader refuses a version it does not know.
