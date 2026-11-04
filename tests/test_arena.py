"""Tests for the live arena's capture slicing and packet counting (no Mininet, no root)."""

import struct

from fl_ids.arena.make_slices import write_prefix
from fl_ids.arena.server import count_packets


def _write_pcap(path, n):
    with open(path, "wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for i in range(n):
            payload = bytes([i % 256]) * (20 + i)
            f.write(struct.pack("<IIII", i, 0, len(payload), len(payload)))
            f.write(payload)


def test_count_packets(tmp_path):
    p = tmp_path / "a.pcap"
    _write_pcap(p, 37)
    assert count_packets(p) == 37


def test_write_prefix_keeps_first_n_whole_packets(tmp_path):
    src, dst = tmp_path / "a.pcap", tmp_path / "b.pcap"
    _write_pcap(src, 50)
    assert write_prefix(src, dst, 10) == 10
    assert count_packets(dst) == 10


def test_write_prefix_shorter_capture_is_kept_whole(tmp_path):
    src, dst = tmp_path / "a.pcap", tmp_path / "b.pcap"
    _write_pcap(src, 5)
    assert write_prefix(src, dst, 3000) == 5
    assert count_packets(dst) == 5
