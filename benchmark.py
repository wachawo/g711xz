#!/usr/bin/env python3
"""Benchmark g711xz decode/encode with and without NumPy."""

import os
import sys
import time

# Import the module
sys.path.insert(0, os.path.dirname(__file__))
import g711xz

# Test vector from test file
VECTOR_FILE = bytes.fromhex(
    "fd377a585a000004e6d6b4460200210100000000372797d601001f4352473701750200401f"
    "0000080000007ff0e1d2c3b4a5967f706152433425000095f458a96aad003a000138201829"
    "770c1fb6f37d010000000004595a"
)


# Create a larger test payload: 1M frames (125 seconds of audio at 8kHz)
# We'll use the vector payload as a template and repeat it
def create_large_test(frames=1_000_000):
    """Create a large test file with repeated vector data."""
    # Decode the vector file to get PCM
    law, vector_frames, pcm = g711xz.decode(VECTOR_FILE)

    # Calculate how many times to repeat
    repeats = frames // vector_frames
    if repeats < 1:
        repeats = 1

    # Repeat PCM
    large_pcm = pcm * repeats
    actual_frames = vector_frames * repeats

    # Encode it back
    large_data = g711xz.encode(large_pcm)

    print(f"Created test data: {actual_frames} frames, {len(large_data)} bytes compressed")
    return large_data, actual_frames, law


def benchmark_decode(data, frames, iterations=5):
    """Benchmark decode function."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        law, f, pcm = g711xz.decode(data)
        end = time.perf_counter()
        times.append(end - start)
    avg_time = sum(times) / len(times)
    throughput = frames / avg_time
    return avg_time, throughput


def benchmark_encode(pcm, frames, iterations=5):
    """Benchmark encode function."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        g711xz.encode(pcm)
        end = time.perf_counter()
        times.append(end - start)
    avg_time = sum(times) / len(times)
    throughput = frames / avg_time
    return avg_time, throughput


def main():
    print("=" * 60)
    print("g711xz NumPy Vectorized Backend Benchmark")
    print("=" * 60)
    print(f"NumPy available: {g711xz.HAS_NUMPY}")
    if g711xz.HAS_NUMPY:
        import numpy as np

        print(f"NumPy version: {np.__version__}")
    print()

    # Create large test data (1M frames)
    print("Generating test data (1M frames)...")
    data, frames, law = create_large_test(1_000_000)

    # Also get the PCM for encode benchmark
    _, _, pcm = g711xz.decode(data)
    # Trim to exact frames
    pcm = pcm[: frames * 4]

    print(f"Test data: {frames} frames ({frames / RATE:.1f}s), {len(data)} bytes compressed")
    print()

    # Benchmark decode
    print("Benchmarking DECODE...")
    decode_time, decode_throughput = benchmark_decode(data, frames)
    print(f"  Average time: {decode_time * 1000:.2f} ms")
    print(f"  Throughput: {decode_throughput:,.0f} frames/sec ({decode_throughput / RATE:.2f}x)")
    print()

    # Benchmark encode
    print("Benchmarking ENCODE...")
    encode_time, encode_throughput = benchmark_encode(pcm, frames)
    print(f"  Average time: {encode_time * 1000:.2f} ms")
    print(f"  Throughput: {encode_throughput:,.0f} frames/sec ({encode_throughput / RATE:.2f}x)")
    print()

    # Test without NumPy by temporarily disabling it
    print("=" * 60)
    print("Testing fallback path (simulating no NumPy)...")

    # Save original HAS_NUMPY
    original_has_numpy = g711xz.HAS_NUMPY
    g711xz.HAS_NUMPY = False

    # Force reimport of functions that check HAS_NUMPY
    # We need to re-run decode/encode with the fallback
    decode_time_fb, decode_throughput_fb = benchmark_decode(data, frames)
    print(
        f"  DECODE fallback: {decode_time_fb * 1000:.2f} ms ({decode_throughput_fb:,.0f} frames/s)"
    )

    encode_time_fb, encode_throughput_fb = benchmark_encode(pcm, frames)
    print(
        f"  ENCODE fallback: {encode_time_fb * 1000:.2f} ms ({encode_throughput_fb:,.0f} frames/s)"
    )

    g711xz.HAS_NUMPY = original_has_numpy

    print()
    print("=" * 60)
    print("SPEEDUP SUMMARY")
    print("=" * 60)
    if original_has_numpy:
        decode_speedup = decode_time_fb / decode_time
        encode_speedup = encode_time_fb / encode_time
        print(f"Decode speedup: {decode_speedup:.2f}x")
        print(f"Encode speedup: {encode_speedup:.2f}x")
        print(f"Overall speedup: {(decode_speedup + encode_speedup) / 2:.2f}x")
    print("=" * 60)


if __name__ == "__main__":
    RATE = 8000
    main()
