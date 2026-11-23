"""Tests for g711xz, standard library unittest. Run: python3 -m unittest -v"""

import contextlib
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

    def test_unknown_mode(self):
        self.assert_bad(xz(self.header(reserved=2) + b"\x7f\x7f"))
        self.assert_bad(xz(self.header(reserved=255) + b"\x7f\x7f"))

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


def line_noise(law, frames, seed):
    """Even line noise of one law, about -55 dBFS."""
    values = [
        value
        for value in sorted({g711xz.EXPAND[law](code) for code in range(256)})
        if abs(value) <= 100
    ]
    source = random.Random(seed)
    return [values[source.randrange(len(values))] for _ in range(frames)]


def tone(law, frames):
    """A loud tone on the lattice of one law."""
    values = sorted({g711xz.EXPAND[law](code) for code in range(256)})
    wave = [8000 * ((index % 26) - 13) / 13 for index in range(frames)]
    return [min(values, key=lambda value: abs(value - sample)) for sample in wave]


class VoxMode(unittest.TestCase):
    """Beta: speech bit for bit, long stretches of even line noise replaced."""

    RATE = 8000

    def call(self, law=b"u"):
        # left: noise, a tone at 2-3 s, then 9 s of noise; right: noise only
        left = line_noise(law, 12 * self.RATE, 1)
        left[2 * self.RATE : 3 * self.RATE] = tone(law, self.RATE)
        right = line_noise(law, 12 * self.RATE, 2)
        return left, right

    def channels(self, pcm):
        samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        return list(samples[0::2]), list(samples[1::2])

    def test_speech_kept_and_noise_replaced(self):
        for law in (b"u", b"a"):
            left, right = self.call(law)
            pcm = interleave(left, right)
            replaced, changed = g711xz.vox_pcm(pcm)
            new_left, new_right = self.channels(replaced)
            # the tone and 800 ms either side are untouched
            kept = slice(2 * self.RATE - 6400, 3 * self.RATE + 6400)
            self.assertTrue(new_left[kept] == left[kept])
            # the long noise tail starts as it was and then repeats every 250 ms
            start = 3 * self.RATE + 6400
            self.assertTrue(new_left[start : start + 2000] == left[start : start + 2000])
            self.assertTrue(new_left[start + 2000 :] == new_left[start:-2000])
            self.assertTrue(new_right[:2000] == right[:2000])
            self.assertTrue(new_right[2000:] == new_right[:-2000])
            self.assertEqual(
                changed, sum(a != b for a, b in zip(left + right, new_left + new_right))
            )
            self.assertGreater(changed, 0)
            self.assertLessEqual(set(new_left), set(left))

    def test_short_pause_is_kept(self):
        left, right = self.call()
        # a second tone 2.4 s after the first: the pause between is under 800 + 1000 + 800 ms
        left[5 * self.RATE + 3200 : 6 * self.RATE + 3200] = tone(b"u", self.RATE)
        replaced, _ = g711xz.vox_pcm(interleave(left, right))
        new_left, _ = self.channels(replaced)
        kept = slice(2 * self.RATE, 6 * self.RATE + 3200)
        self.assertTrue(new_left[kept] == left[kept])

    def test_digitally_silent_line_is_left_alone(self):
        left, right = self.call()
        quiet = [0] * (12 * self.RATE)
        quiet[7 * self.RATE : 7 * self.RATE + 400] = [56] * 400
        pcm = interleave(left, quiet)
        replaced, _ = g711xz.vox_pcm(pcm)
        self.assertTrue(self.channels(replaced)[1] == quiet)

    def test_run_with_an_event_is_left_alone(self):
        left, right = self.call()
        # one frame at -47 dBFS: under the threshold, well over the noise around it
        right[6 * self.RATE : 6 * self.RATE + 160] = [148, -148] * 80
        replaced, _ = g711xz.vox_pcm(interleave(left, right))
        self.assertTrue(self.channels(replaced)[1] == right)

    def test_options(self):
        left, right = self.call()
        pcm = interleave(left, right)
        self.assertTrue(g711xz.vox_pcm(pcm, threshold_db=-90.0)[0] == pcm)
        self.assertTrue(g711xz.vox_pcm(pcm, min_quiet_ms=60000)[0] == pcm)
        longer = g711xz.vox_pcm(pcm, fill_ms=500)[0]
        self.assertFalse(longer == g711xz.vox_pcm(pcm)[0])
        with self.assertRaises(ValueError):
            g711xz.vox_pcm(pcm, fill_ms=0)
        with self.assertRaises(ValueError):
            g711xz.vox_pcm(pcm, hangover_ms=-1)

    def test_short_and_empty_input(self):
        self.assertEqual(g711xz.vox_pcm(b""), (b"", 0))
        short = interleave([8] * 100, [16] * 100)
        self.assertEqual(g711xz.vox_pcm(short + b"\x01"), (short + b"\x01", 0))

    def test_backends_agree(self):
        pcm = interleave(*self.call())
        expected = g711xz.vox_pcm(pcm)
        with mock.patch.object(g711xz, "HAS_NUMPY", False):
            self.assertTrue(g711xz.vox_pcm(pcm) == expected)

    def test_vox_file(self):
        pcm = interleave(*self.call())
        replaced, _ = g711xz.vox_pcm(pcm)
        data = g711xz.encode(pcm, vox=True)
        payload = lzma.decompress(data)
        self.assertEqual(payload[7], g711xz.MODE_VOX)
        self.assertTrue(payload[16:] == lzma.decompress(g711xz.encode(replaced))[16:])
        self.assertLess(len(data), len(g711xz.encode(pcm)))
        backends = (
            {"HAS_RUST": g711xz.HAS_RUST},
            {"HAS_RUST": False},
            {"HAS_RUST": False, "HAS_NUMPY": False},
        )
        for flags in backends:
            with mock.patch.multiple(g711xz, **flags):
                self.assertTrue(g711xz.decode(data) == (b"u", 12 * self.RATE, replaced))
                self.assertTrue(g711xz.encode(pcm, vox=True) == data)

    def test_lossless_is_the_default(self):
        pcm = interleave(*self.call())
        data = g711xz.encode(pcm)
        self.assertEqual(lzma.decompress(data)[7], g711xz.MODE_LOSSLESS)
        self.assertTrue(g711xz.encode(pcm, vox=False) == data)
        self.assertTrue(b"".join(g711xz.encode_stream([pcm])) == data)
        self.assertTrue(g711xz.decode(data)[2] == pcm)

    def test_options_reach_the_encoder(self):
        pcm = interleave(*self.call())
        lossless = lzma.decompress(g711xz.encode(pcm))
        kept = lzma.decompress(g711xz.encode(pcm, vox=True, threshold_db=-90.0))
        self.assertEqual(kept[7], g711xz.MODE_VOX)
        self.assertTrue(kept[16:] == lossless[16:])
        longer = g711xz.encode(pcm, vox=True, fill_ms=500)
        self.assertTrue(g711xz.decode(longer)[2] == g711xz.vox_pcm(pcm, fill_ms=500)[0])
        with self.assertRaises(TypeError):
            g711xz.encode(pcm, vox=True, no_such_option=1)

    def test_options_need_vox(self):
        pcm = interleave([0], [0])
        for options in ({"fill_ms": 500}, {"threshold_db": -50.0}, {"no_such_option": 1}):
            with self.assertRaisesRegex(TypeError, "vox options need vox=True"):
                g711xz.encode(pcm, **options)
            with self.assertRaisesRegex(TypeError, "vox options need vox=True"):
                g711xz.encode(pcm, vox=False, **options)
            with self.assertRaisesRegex(TypeError, "vox options need vox=True"):
                list(g711xz.encode_stream([pcm], **options))

    def test_vox_is_keyword_only(self):
        pcm = interleave([0], [0])
        with self.assertRaises(TypeError):
            g711xz.encode(pcm, True)
        with self.assertRaises(TypeError):
            g711xz.encode_stream([pcm], 1, True)

    def test_encode_stream(self):
        pcm = interleave(*self.call())
        chunks = [pcm[start : start + 50000] for start in range(0, len(pcm), 50000)]
        data = b"".join(g711xz.encode_stream(chunks, 12 * self.RATE, vox=True))
        self.assertTrue(data == g711xz.encode(pcm, vox=True))
        tuned = b"".join(g711xz.encode_stream(chunks, vox=True, fill_ms=500))
        self.assertTrue(tuned == g711xz.encode(pcm, vox=True, fill_ms=500))

    def test_refused_like_encode(self):
        with self.assertRaises(g711xz.RefusedError):
            g711xz.encode(interleave([121], [0]), vox=True)

    def test_readers_take_no_vox_argument(self):
        data = g711xz.encode(interleave([0], [0]), vox=True)
        payload = lzma.decompress(data)
        calls = (
            lambda **options: g711xz.decode(data, **options),
            lambda **options: g711xz.decode_stream(io.BytesIO(data), **options),
            lambda **options: g711xz.transcode_law(data, b"a", **options),
            lambda **options: g711xz.parse_header(payload, **options),
            lambda **options: g711xz.unpack_header(payload, **options),
        )
        for call in calls:
            for value in (True, False):
                with self.assertRaises(TypeError):
                    call(vox=value)
        for name in ("VoxError", "EXIT_VOX", "VOX_REFUSAL"):
            self.assertFalse(hasattr(g711xz, name))
            self.assertNotIn(name, g711xz.__all__)

    def test_unknown_mode_is_a_format_error(self):
        data = xz(g711xz.HEADER.pack(b"CRG7", 1, b"u", 2, 2, 8000, 1) + b"\x7f\x7f")
        readers = (
            g711xz.decode,
            g711xz.read_mode,
            lambda file: g711xz.transcode_law(file, b"a"),
            lambda file: list(g711xz.decode_stream(io.BytesIO(file))),
        )
        for flags in ({"HAS_RUST": g711xz.HAS_RUST}, {"HAS_RUST": False}):
            with mock.patch.multiple(g711xz, **flags):
                for reader in readers:
                    with self.assertRaises(g711xz.FormatError):
                        reader(data)

    def test_readers_take_both_modes(self):
        pcm = interleave(*noise(b"u", 400))
        for flags in ({"HAS_RUST": g711xz.HAS_RUST}, {"HAS_RUST": False}):
            for vox in (False, True):
                data = g711xz.encode(pcm, vox=vox)
                with mock.patch.multiple(g711xz, **flags):
                    self.assertTrue(g711xz.decode(data) == (b"u", 400, pcm))
                    self.assertTrue(g711xz.decode(io.BytesIO(data)) == (b"u", 400, pcm))
                    frames = list(g711xz.decode_stream(io.BytesIO(data)))
                    self.assertEqual(len(frames), 400)
                    self.assertTrue(interleave(*zip(*[frame[2:] for frame in frames])) == pcm)
                    # a file that is already in the target law comes back as it is
                    self.assertTrue(g711xz.transcode_law(data, b"u") == data)
                    converted = g711xz.transcode_law(data, b"a")
                    self.assertEqual(g711xz.decode(converted)[:2], (b"a", 400))
                # the mode is carried over
                payload = lzma.decompress(converted)
                self.assertEqual((payload[5:6], payload[7]), (b"a", int(vox)))
                self.assertEqual(g711xz.read_mode(converted), int(vox))

    def test_header_helpers_take_both_modes(self):
        pcm = interleave(*noise(b"u", 400))
        for vox in (False, True):
            payload = lzma.decompress(g711xz.encode(pcm, vox=vox))
            for helper in (g711xz.parse_header, g711xz.unpack_header):
                self.assertEqual(helper(payload), (b"u", 400))
            with self.assertRaises(g711xz.FormatError):
                g711xz.parse_header(payload[:-1])

    def test_damaged_vox_file_is_a_format_error(self):
        data = g711xz.encode(interleave(*noise(b"u", 400)), vox=True)
        wrong_body = xz(g711xz.HEADER.pack(b"CRG7", 1, b"u", 2, 1, 8000, 2) + b"\x7f\x7f\x7f")
        readers = (
            g711xz.decode,
            lambda file: g711xz.transcode_law(file, b"a"),
            lambda file: list(g711xz.decode_stream(io.BytesIO(file))),
        )
        for flags in ({"HAS_RUST": g711xz.HAS_RUST}, {"HAS_RUST": False}):
            with mock.patch.multiple(g711xz, **flags):
                for damaged in (data[:-10], wrong_body):
                    for reader in readers:
                        with self.assertRaises(g711xz.FormatError):
                            reader(damaged)

    def test_header_split_over_xz_streams(self):
        # the Rust backend reads xz streams that follow each other as one file
        pcm = interleave(*noise(b"u", 400))

        def attempt(file):
            try:
                return g711xz.decode(file)
            except g711xz.FormatError as error:
                return type(error)

        for vox in (False, True):
            payload = lzma.decompress(g711xz.encode(pcm, vox=vox))
            files = (
                xz(payload[:7]) + xz(payload[7:]),
                xz(b"") + xz(payload),
                xz(payload[:7]) + bytes(8) + xz(payload[7:]),
            )
            for file in files:
                self.assertEqual(g711xz.read_mode(file), int(vox))
                for flags in ({"HAS_RUST": g711xz.HAS_RUST}, {"HAS_RUST": False}):
                    with mock.patch.multiple(g711xz, **flags):
                        result = attempt(file)
                    if flags["HAS_RUST"]:
                        self.assertTrue(result == (b"u", 400, pcm))
                    else:
                        self.assertIs(result, g711xz.FormatError)

    def test_read_mode(self):
        pcm = interleave(*noise(b"a", 400))
        with tempfile.TemporaryDirectory() as directory:
            for vox, mode in ((False, g711xz.MODE_LOSSLESS), (True, g711xz.MODE_VOX)):
                data = g711xz.encode(pcm, vox=vox)
                path = os.path.join(directory, f"rec{mode}.g711.xz")
                with open(path, "wb") as sink:
                    sink.write(data)
                self.assertEqual(g711xz.read_mode(data), mode)
                self.assertEqual(g711xz.read_mode(bytearray(data)), mode)
                self.assertEqual(g711xz.read_mode(memoryview(data)), mode)
                self.assertEqual(g711xz.read_mode(path), mode)
                self.assertEqual(g711xz.read_mode(pathlib.Path(path)), mode)
                self.assertEqual(g711xz.read_mode(io.BytesIO(data)), mode)
                with open(path, "rb") as source:
                    self.assertEqual(g711xz.read_mode(source), mode)
        self.assertEqual(g711xz.MODE_NAMES, {0: "lossless", 1: "vox"})

    def test_read_mode_reads_only_the_header(self):
        data = g711xz.encode(interleave(*noise(b"u", 100000)), vox=True)
        self.assertGreater(len(data), 2 * 65536)
        source = io.BytesIO(data)
        self.assertEqual(g711xz.read_mode(source), g711xz.MODE_VOX)
        self.assertLessEqual(source.tell(), 65536)
        # the damage is past the header
        self.assertEqual(g711xz.read_mode(data[:-10]), g711xz.MODE_VOX)

    def test_read_mode_bad_input(self):
        short = xz(b"CRG7")
        for data in (b"", b"OggS" + bytes(60), VECTOR_FILE[:20], short, xz(b"x" * 64)):
            with self.assertRaises(g711xz.FormatError):
                g711xz.read_mode(data)
        with self.assertRaises(TypeError):
            g711xz.read_mode(12345)
        with self.assertRaises(OSError):
            g711xz.read_mode(os.path.join(tempfile.gettempdir(), "missing", "rec.g711.xz"))

    def test_removed_names(self):
        for name in ("encode_voice", "gate_pcm", "gate_runs", "MODE_VOICE", "GATE_FRAME"):
            self.assertFalse(hasattr(g711xz, name))
        for name in g711xz.__all__:
            self.assertTrue(hasattr(g711xz, name), name)
            self.assertFalse(name.startswith("_"))


class VoxCommandLine(unittest.TestCase):
    """The command line writes a VOX file only with --vox and reads one without."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pcm = interleave(*noise(b"u", 400))
        self.wav = self.path("rec.wav")
        g711xz.write_wav(self.wav, self.pcm)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def run_main(self, *argv):
        """Return (exit code, stdout, stderr) of one command."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = g711xz.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def read(self, name):
        with open(self.path(name), "rb") as source:
            return source.read()

    def test_default_output_names(self):
        code, out, _ = self.run_main("encode", self.wav, "--vox")
        self.assertEqual(code, 0)
        vox = self.path("rec.vox.g711.xz")
        self.assertEqual(os.path.basename(vox), "rec" + g711xz.VOX_SUFFIX)
        self.assertTrue(self.read("rec.vox.g711.xz") == g711xz.encode(self.pcm, vox=True))
        size = len(self.read("rec.vox.g711.xz"))
        self.assertEqual(
            out, f"{self.wav} -> {vox}: mu-law (PCMU), vox (not an exact copy), {size} bytes\n"
        )
        # the lossless file gets its own name and neither writes over the other
        code, out, _ = self.run_main("encode", self.wav)
        self.assertEqual(code, 0)
        lossless = self.read("rec.g711.xz")
        self.assertTrue(lossless == g711xz.encode(self.pcm))
        self.assertEqual(
            out, f"{self.wav} -> {self.path('rec.g711.xz')}: mu-law (PCMU), {len(lossless)} bytes\n"
        )
        self.assertEqual(g711xz.read_mode(vox), g711xz.MODE_VOX)
        # the mark stays in the name of the decoded WAV
        code, out, _ = self.run_main("decode", vox)
        self.assertEqual(code, 0)
        self.assertTrue(out.endswith(", 400 frames, 0.050 s, vox (not an exact copy)\n"))
        self.assertTrue(g711xz.read_wav(self.path("rec.vox.wav")) == self.pcm)

    def test_explicit_output_name_is_used_as_given(self):
        target = self.path("plain.g711.xz")
        self.assertEqual(self.run_main("encode", self.wav, target, "--vox")[0], 0)
        self.assertEqual(self.run_main("encode", "--vox", self.wav, target)[0], 0)
        self.assertEqual(g711xz.read_mode(target), g711xz.MODE_VOX)
        self.assertEqual(os.listdir(self.tmp.name).count("rec.vox.g711.xz"), 0)

    def test_flag_before_the_subcommand_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as caught, contextlib.redirect_stderr(io.StringIO()):
            g711xz.main(["--vox", "encode", self.wav])
        self.assertEqual(caught.exception.code, 2)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            g711xz.main(["info", "--vox", self.wav])
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            g711xz.main(["encode", "--voice", self.wav])

    def test_flag_in_any_position(self):
        for position in range(1, 4):
            target = self.path(f"out{position}.g711.xz")
            command = ["encode", self.wav, target]
            command.insert(position, "--vox")
            self.assertEqual(self.run_main(*command)[0], 0)
            self.assertEqual(g711xz.read_mode(target), g711xz.MODE_VOX)
        # after `--` the word is the output name, not the flag
        home = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            self.assertEqual(self.run_main("encode", self.wav, "--", "--vox")[0], 0)
        finally:
            os.chdir(home)
        self.assertEqual(g711xz.read_mode(self.path("--vox")), g711xz.MODE_LOSSLESS)

    def test_flag_on_a_reader_is_a_usage_error(self):
        source = self.path("rec.vox.g711.xz")
        self.assertEqual(self.run_main("encode", self.wav, "--vox")[0], 0)
        before = sorted(os.listdir(self.tmp.name))
        commands = (
            ["decode", source, self.path("out.wav")],
            ["transcode", source, "a", self.path("out.alaw.g711.xz")],
            ["info", source],
        )
        for command in commands:
            for position in range(1, len(command) + 1):
                words = list(command)
                words.insert(position, "--vox")
                silenced = contextlib.redirect_stderr(io.StringIO())
                with self.assertRaises(SystemExit) as caught, silenced:
                    g711xz.main(words)
                self.assertEqual(caught.exception.code, 2)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), before)

    def test_abbreviated_flag_is_a_usage_error(self):
        source = self.path("rec.vox.g711.xz")
        self.assertEqual(self.run_main("encode", self.wav, "--vox")[0], 0)
        before = sorted(os.listdir(self.tmp.name))
        commands = (
            ["encode", self.wav, self.path("short.g711.xz")],
            ["decode", source, self.path("short.wav")],
            ["transcode", source, "a", self.path("short.alaw.g711.xz")],
        )
        for command in commands:
            for flag in ("--v", "--vo"):
                silenced = contextlib.redirect_stderr(io.StringIO())
                with self.assertRaises(SystemExit) as caught, silenced:
                    g711xz.main([*command, flag])
                self.assertEqual(caught.exception.code, 2)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), before)

    def test_damaged_vox_file_exits_2(self):
        self.assertEqual(self.run_main("encode", self.wav, "--vox")[0], 0)
        damaged = self.path("cut.vox.g711.xz")
        with open(damaged, "wb") as sink:
            sink.write(self.read("rec.vox.g711.xz")[:-10])
        before = sorted(os.listdir(self.tmp.name))
        commands = (
            ["decode", damaged, self.path("cut.wav")],
            ["transcode", damaged, "a", self.path("cut.alaw.g711.xz")],
            ["info", damaged],
        )
        for command in commands:
            code, out, err = self.run_main(*command)
            self.assertEqual((code, out), (g711xz.EXIT_BAD_INPUT, ""))
            self.assertIn("error: not a valid xz stream", err)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), before)

    def test_exit_codes(self):
        self.assertEqual((g711xz.EXIT_BAD_INPUT, g711xz.EXIT_REFUSED), (2, 3))
        self.assertFalse(hasattr(g711xz, "EXIT_VOX"))

    def test_decode_reads_a_vox_file(self):
        # the header, not the name, says what the file is
        source = self.path("rec.g711.xz")
        self.assertEqual(self.run_main("encode", self.wav, source, "--vox")[0], 0)
        target = self.path("out.wav")
        code, out, err = self.run_main("decode", source, target)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(
            out,
            f"{source} -> {target}: mu-law (PCMU), 400 frames, 0.050 s, vox (not an exact copy)\n",
        )
        self.assertTrue(g711xz.read_wav(target) == self.pcm)

    def test_transcode_reads_a_vox_file(self):
        source = self.path("rec.vox.g711.xz")
        target = self.path("rec.alaw.vox.g711.xz")
        self.assertEqual(self.run_main("encode", self.wav, "--vox")[0], 0)
        for law, name in (("a", "A-law (PCMA)"), ("u", "mu-law (PCMU)")):
            code, out, err = self.run_main("transcode", source, law, target)
            self.assertEqual((code, err), (0, ""))
            size = len(self.read("rec.alaw.vox.g711.xz"))
            self.assertEqual(
                out, f"{source} -> {target}: {name}, vox (not an exact copy), {size} bytes\n"
            )
            self.assertEqual(g711xz.read_mode(target), g711xz.MODE_VOX)
            self.assertTrue(
                self.read("rec.alaw.vox.g711.xz")
                == g711xz.transcode_law(self.read("rec.vox.g711.xz"), law.encode())
            )

    def test_lossless_file_is_read_as_before(self):
        source = self.path("rec.g711.xz")
        self.assertEqual(self.run_main("encode", self.wav)[0], 0)
        code, out, err = self.run_main("decode", source, self.path("plain.wav"))
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.endswith(": mu-law (PCMU), 400 frames, 0.050 s\n"))
        self.assertTrue(g711xz.read_wav(self.path("plain.wav")) == self.pcm)
        target = self.path("rec.alaw.g711.xz")
        code, out, _ = self.run_main("transcode", source, "a", target)
        self.assertEqual(code, 0)
        self.assertTrue(
            out.endswith(f": A-law (PCMA), {len(self.read('rec.alaw.g711.xz'))} bytes\n")
        )
        self.assertEqual(g711xz.read_mode(target), g711xz.MODE_LOSSLESS)
        self.assertTrue(
            self.read("rec.alaw.g711.xz") == g711xz.transcode_law(self.read("rec.g711.xz"), b"a")
        )

    def test_info_mode_line(self):
        self.assertEqual(self.run_main("encode", self.wav)[0], 0)
        self.assertEqual(self.run_main("encode", self.wav, "--vox")[0], 0)
        vox_line = "  mode      vox (beta): quiet line noise replaced, not an exact copy"
        expected = {"rec.g711.xz": "  mode      lossless", "rec.vox.g711.xz": vox_line}
        for name, line in expected.items():
            code, out, err = self.run_main("info", self.path(name))
            self.assertEqual((code, err), (0, ""))
            lines = out.splitlines()
            self.assertEqual(lines[1], "  format    CRG7 version 1")
            self.assertEqual(lines[2], line)
            self.assertEqual(lines[3], "  law       mu-law (PCMU)")
        # info takes several files of both modes
        code, out, _ = self.run_main("info", *[self.path(name) for name in expected])
        self.assertEqual(code, 0)
        modes = [line.split()[1] for line in out.splitlines() if line.startswith("  mode")]
        self.assertEqual(modes, ["lossless", "vox"])


if __name__ == "__main__":
    unittest.main()
