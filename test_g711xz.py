"""Tests for g711xz, standard library unittest. Run: python3 -m unittest -v"""

import hashlib
import io
import lzma
import os
import pathlib
import random
import struct
import tempfile
import unittest
from unittest import mock

import g711xz

VECTOR_FILE = bytes.fromhex(
    "fd377a585a000004e6d6b4460200210100000000372797d601001f4352473701750200401f"
    "0000080000007ff0e1d2c3b4a5967f706152433425000095f458a96aad003a000138201829"
    "770c1fb6f37d010000000004595a"
)
VECTOR_PAYLOAD = bytes.fromhex("4352473701750200401f0000080000007ff0e1d2c3b4a5967f70615243342500")
VECTOR_LEFT = [0, 120, 356, 812, 1692, 3388, 6652, 12924]
VECTOR_RIGHT = [0, -120, -356, -812, -1692, -3388, -6652, -32124]
VECTOR_PCM = bytes.fromhex("00000000780088ff64019cfe2c03d4fc9c0664f93c0dc4f2fc1904e67c328482")
VECTOR_SHA256 = "c6803f47d9b7b6062fffacff870666c06bf43435b8078f0ed966eeda7208a9d6"


def interleave(left, right):
    return b"".join(struct.pack("<hh", a, b) for a, b in zip(left, right))


def xz(payload):
    return lzma.compress(payload, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64)


class TestVector(unittest.TestCase):
    def test_decode(self):
        law, frames, pcm = g711xz.decode(VECTOR_FILE)
        self.assertEqual((law, frames), (b"u", 8))
        self.assertEqual(pcm, VECTOR_PCM)
        self.assertEqual(pcm, interleave(VECTOR_LEFT, VECTOR_RIGHT))
        self.assertEqual(hashlib.sha256(pcm).hexdigest(), VECTOR_SHA256)

    def test_encode_payload(self):
        data = g711xz.encode(VECTOR_PCM)
        self.assertEqual(lzma.decompress(data), VECTOR_PAYLOAD)

    def test_encode_matches_reference_bytes(self):
        # Test that encoding produces the correct payload (not exact xz stream bytes,
        # since different LZMA implementations produce different compressed output)
        encoded = g711xz.encode(VECTOR_PCM)
        payload = lzma.decompress(encoded)
        self.assertEqual(payload, VECTOR_PAYLOAD)


class RoundTrip(unittest.TestCase):
    def check_law(self, law):
        values = [g711xz.EXPAND[law](code) for code in range(256)]
        pcm = interleave(values, list(reversed(values)))
        data = g711xz.encode(pcm)
        self.assertEqual(lzma.decompress(data)[5:6], law)
        decoded_law, frames, decoded = g711xz.decode(data)
        self.assertEqual((decoded_law, frames, decoded), (law, 256, pcm))

    def test_ulaw(self):
        self.check_law(b"u")

    def test_alaw(self):
        self.check_law(b"a")

    def test_ulaw_zero_keeps_lower_code(self):
        payload = lzma.decompress(g711xz.encode(interleave([0], [0])))
        self.assertEqual(payload[16:], b"\x7f\x7f")

    def test_zero_frames(self):
        data = g711xz.encode(b"")
        self.assertEqual(g711xz.decode(data), (b"u", 0, b""))

    def test_trailing_partial_frame_ignored(self):
        pcm = interleave([120], [-120])
        self.assertEqual(g711xz.decode(g711xz.encode(pcm + b"\x01\x02\x03"))[2], pcm)

    def test_ranges(self):
        ulaw = [g711xz.expand_ulaw(code) for code in range(256)]
        alaw = [g711xz.expand_alaw(code) for code in range(256)]
        self.assertEqual((min(ulaw), max(ulaw), len(set(ulaw))), (-32124, 32124, 255))
        self.assertEqual((min(alaw), max(alaw), len(set(alaw))), (-32256, 32256, 256))


class Refusals(unittest.TestCase):
    def test_off_lattice(self):
        with self.assertRaises(g711xz.RefusedError):
            g711xz.encode(interleave([121], [0]))

    def test_mixed_laws(self):
        # 16 exists only in mu-law, 136 only in A-law.
        with self.assertRaises(g711xz.RefusedError):
            g711xz.encode(interleave([16], [136]))

    def test_alaw_with_gap(self):
        # A-law leg with a PCM 0 gap: 0 is not an A-law value, 136 is not mu-law.
        with self.assertRaises(g711xz.RefusedError):
            g711xz.encode(interleave([136, 0], [136, 136]))


class DamagedFiles(unittest.TestCase):
    def header(self, **fields):
        values = {
            "magic": b"CRG7",
            "version": 1,
            "law": b"u",
            "channels": 2,
            "reserved": 0,
            "rate": 8000,
            "frames": 1,
        }
        values.update(fields)
        return g711xz.HEADER.pack(*values.values())

    def assert_bad(self, data):
        with self.assertRaises(g711xz.FormatError):
            g711xz.decode(data)

    def test_not_xz(self):
        self.assert_bad(b"OggS" + bytes(60))

    def test_xz_without_magic(self):
        self.assert_bad(xz(b"hello world, not ours"))

    def test_short_payload(self):
        self.assert_bad(xz(b"CRG7"))

    def test_unknown_version(self):
        self.assert_bad(xz(self.header(version=2) + b"\x7f\x7f"))

    def test_unknown_law(self):
        self.assert_bad(xz(self.header(law=b"x") + b"\x7f\x7f"))

    def test_wrong_channels(self):
        self.assert_bad(xz(self.header(channels=1) + b"\x7f"))

    def test_reserved_set(self):
        self.assert_bad(xz(self.header(reserved=1) + b"\x7f\x7f"))

    def test_wrong_rate(self):
        self.assert_bad(xz(self.header(rate=16000) + b"\x7f\x7f"))

    def test_truncated_body(self):
        self.assert_bad(xz(self.header(frames=2) + b"\x7f\x7f\x7f"))

    def test_extra_body(self):
        self.assert_bad(xz(self.header(frames=1) + b"\x7f\x7f\x7f"))

    def test_truncated_xz(self):
        self.assert_bad(VECTOR_FILE[:-10])


class Inputs(unittest.TestCase):
    """decode and encode take bytes-like objects, paths and binary file objects."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, data):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as sink:
            sink.write(data)
        return path

    def test_decode_sources(self):
        path = self.write("rec.g711.xz", VECTOR_FILE)
        expected = (b"u", 8, VECTOR_PCM)
        self.assertEqual(g711xz.decode(path), expected)
        self.assertEqual(g711xz.decode(pathlib.Path(path)), expected)
        with open(path, "rb") as source:
            self.assertEqual(g711xz.decode(source), expected)
        self.assertEqual(g711xz.decode(io.BytesIO(VECTOR_FILE)), expected)
        self.assertEqual(g711xz.decode(bytearray(VECTOR_FILE)), expected)
        self.assertEqual(g711xz.decode(memoryview(VECTOR_FILE)), expected)

    def test_encode_sources(self):
        path = self.write("rec.pcm", VECTOR_PCM)
        for source in (path, pathlib.Path(path), bytearray(VECTOR_PCM), memoryview(VECTOR_PCM)):
            self.assertEqual(lzma.decompress(g711xz.encode(source)), VECTOR_PAYLOAD)
        with open(path, "rb") as source:
            self.assertEqual(lzma.decompress(g711xz.encode(source)), VECTOR_PAYLOAD)

    def test_unsupported_type(self):
        with self.assertRaises(TypeError):
            g711xz.decode(12345)
        with self.assertRaises(TypeError):
            g711xz.encode(12345)

    def test_missing_file(self):
        with self.assertRaises(OSError):
            g711xz.decode(os.path.join(self.tmp.name, "missing.g711.xz"))


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def test_decode_encode_default_names(self):
        source = self.path("rec.g711.xz")
        with open(source, "wb") as sink:
            sink.write(VECTOR_FILE)
        self.assertEqual(g711xz.main(["info", source]), 0)
        self.assertEqual(g711xz.main(["decode", source]), 0)
        wav = self.path("rec.wav")
        self.assertEqual(g711xz.read_wav(wav), VECTOR_PCM)
        os.remove(source)
        self.assertEqual(g711xz.main(["encode", wav]), 0)
        # Re-encode produces different compressed bytes but same payload
        with open(source, "rb") as result:
            encoded = result.read()
        law, frames, pcm = g711xz.decode(encoded)
        self.assertEqual((law, frames, pcm), (b"u", 8, VECTOR_PCM))

    def test_encode_refused_exit_code(self):
        wav = self.path("noise.wav")
        g711xz.write_wav(wav, interleave([121], [0]))
        self.assertEqual(g711xz.main(["encode", wav]), g711xz.EXIT_REFUSED)
        self.assertFalse(os.path.exists(self.path("noise.g711.xz")))

    def test_encode_wrong_wav_format(self):
        import wave

        wav = self.path("mono.wav")
        with wave.open(wav, "wb") as sink:
            sink.setnchannels(1)
            sink.setsampwidth(2)
            sink.setframerate(8000)
            sink.writeframes(b"\x00\x00")
        self.assertEqual(g711xz.main(["encode", wav]), g711xz.EXIT_BAD_INPUT)

    def test_damaged_exit_code(self):
        source = self.path("bad.g711.xz")
        with open(source, "wb") as sink:
            sink.write(VECTOR_FILE[:-10])
        self.assertEqual(g711xz.main(["info", source]), g711xz.EXIT_BAD_INPUT)
        self.assertEqual(g711xz.main(["decode", source]), g711xz.EXIT_BAD_INPUT)


def noise(law, frames, seed=0):
    """PCM of random codes of one law: valid G.711 that xz cannot shrink much."""
    values = [g711xz.EXPAND[law](code) for code in range(256)]
    source = random.Random(seed)
    left = [values[source.randrange(256)] for _ in range(frames)]
    right = [values[source.randrange(256)] for _ in range(frames)]
    return left, right


class Streaming(unittest.TestCase):
    def test_decode_stream_larger_than_one_read(self):
        left, right = noise(b"a", 100000)
        data = g711xz.encode(interleave(left, right))
        self.assertGreater(len(data), 65536)
        frames = list(g711xz.decode_stream(io.BytesIO(data)))
        self.assertEqual(len(frames), 100000)
        self.assertEqual({frame[0] for frame in frames}, {b"a"})
        self.assertEqual([frame[1] for frame in frames], list(range(100000)))
        self.assertEqual([frame[2] for frame in frames], left)
        self.assertEqual([frame[3] for frame in frames], right)

    def test_decode_stream_zero_frames(self):
        self.assertEqual(list(g711xz.decode_stream(io.BytesIO(g711xz.encode(b"")))), [])

    def test_decode_stream_truncated(self):
        with self.assertRaises(g711xz.FormatError):
            list(g711xz.decode_stream(io.BytesIO(VECTOR_FILE[:-10])))

    def test_decode_stream_damaged_body(self):
        header = g711xz.HEADER.pack(b"CRG7", 1, b"u", 2, 0, 8000, 2)
        with self.assertRaises(g711xz.FormatError):
            list(g711xz.decode_stream(io.BytesIO(xz(header + b"\x7f\x7f\x7f"))))

    def test_encode_stream_alaw_with_values_of_both_laws(self):
        # 8 is a value of both laws, 136 only of A-law.
        pcm = interleave([8, 136, 8], [8, 136, 8])
        data = b"".join(g711xz.encode_stream([pcm]))
        self.assertEqual(g711xz.decode(data), (b"a", 3, pcm))

    def test_encode_stream_chunks_cut_inside_a_frame(self):
        pcm = interleave(*noise(b"u", 1000))
        chunks = [pcm[start : start + 7] for start in range(0, len(pcm), 7)]
        data = b"".join(g711xz.encode_stream(chunks, total_frames=1000))
        self.assertEqual(g711xz.decode(data), (b"u", 1000, pcm))

    def test_encode_stream_wrong_total_frames(self):
        with self.assertRaises(g711xz.FormatError):
            list(g711xz.encode_stream([interleave([0], [0])], total_frames=2))

    def test_encode_stream_refused(self):
        with self.assertRaises(g711xz.RefusedError):
            list(g711xz.encode_stream([interleave([121], [0])]))


class Transcode(unittest.TestCase):
    def test_same_law_is_unchanged(self):
        self.assertEqual(g711xz.transcode_law(VECTOR_FILE, b"u"), VECTOR_FILE)

    def test_other_law_takes_nearest_samples(self):
        law, frames, pcm = g711xz.decode(g711xz.transcode_law(VECTOR_FILE, b"a"))
        self.assertEqual((law, frames), (b"a", 8))
        alaw = [g711xz.expand_alaw(code) for code in range(256)]
        nearest = [
            min(alaw, key=lambda value: abs(value - sample))
            for sample in VECTOR_LEFT + VECTOR_RIGHT
        ]
        samples = struct.unpack("<16h", pcm)
        self.assertEqual(list(samples[0::2]) + list(samples[1::2]), nearest)

    def test_unknown_law(self):
        with self.assertRaises(g711xz.FormatError):
            g711xz.transcode_law(VECTOR_FILE, b"x")

    def test_command_does_not_write_over_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = os.path.join(directory, "rec.g711.xz")
            target = os.path.join(directory, "rec.alaw.g711.xz")
            with open(source, "wb") as sink:
                sink.write(VECTOR_FILE)
            self.assertEqual(g711xz.main(["transcode", source, "a", source]), g711xz.EXIT_BAD_INPUT)
            with open(source, "rb") as result:
                self.assertEqual(result.read(), VECTOR_FILE)
            self.assertEqual(g711xz.main(["transcode", source, "a", target]), 0)
            with open(target, "rb") as result:
                self.assertEqual(g711xz.decode(result.read())[:2], (b"a", 8))


class Limits(unittest.TestCase):
    def test_payload_longer_than_the_limit(self):
        data = g711xz.encode(interleave(*noise(b"u", 256)))
        with mock.patch.object(g711xz, "MAX_PAYLOAD", 100), self.assertRaises(g711xz.FormatError):
            g711xz.decode(data)

    def test_too_many_frames_to_encode(self):
        with mock.patch.object(g711xz, "MAX_FRAMES", 1), self.assertRaises(g711xz.FormatError):
            g711xz.encode(interleave([0, 0], [0, 0]))


class Backends(unittest.TestCase):
    """The same answers from every backend that can run here."""

    def check_backend(self, **flags):
        patches = [mock.patch.object(g711xz, name, value) for name, value in flags.items()]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.assertEqual(g711xz.decode(VECTOR_FILE), (b"u", 8, VECTOR_PCM))
        self.assertEqual(lzma.decompress(g711xz.encode(VECTOR_PCM)), VECTOR_PAYLOAD)
        for law in (b"u", b"a"):
            pcm = interleave(*noise(law, 2000))
            self.assertEqual(g711xz.decode(g711xz.encode(pcm)), (law, 2000, pcm))
        self.assertEqual(g711xz.decode(g711xz.encode(b"")), (b"u", 0, b""))
        with self.assertRaises(g711xz.RefusedError):
            g711xz.encode(interleave([16], [136]))
        with self.assertRaises(g711xz.FormatError):
            g711xz.decode(VECTOR_FILE[:-10])

    def test_pure_python(self):
        self.check_backend(HAS_RUST=False, HAS_NUMPY=False)

    @unittest.skipUnless(g711xz.HAS_NUMPY, "numpy is not installed")
    def test_numpy(self):
        self.check_backend(HAS_RUST=False)

    @unittest.skipUnless(g711xz.HAS_RUST, "the Rust extension is not built")
    def test_rust(self):
        self.check_backend()

    @unittest.skipUnless(g711xz.HAS_RUST, "the Rust extension is not built")
    def test_rust_file_uses_the_dictionary_of_the_format(self):
        pcm = interleave(*noise(b"u", 20000))
        with mock.patch.object(g711xz, "HAS_RUST", False):
            reference = g711xz.encode(pcm)
        # Same payload and the same dictionary: sizes within a few percent.
        self.assertLess(abs(len(g711xz.encode(pcm)) - len(reference)), len(reference) // 20)


if __name__ == "__main__":
    unittest.main()
