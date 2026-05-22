"""Tests for the clean-room ESP-TOUCH packet-length encoder."""

from __future__ import annotations

import pytest

from esptouch.encoder import (
    GUIDE_CODE,
    GUIDE_CODE_LEN,
    DataCode,
    crc8,
    encode_packets,
)


def test_crc8_known_vector() -> None:
    """crc8 of the empty input is 0; crc8 is stable for a known buffer."""
    assert crc8(b"") == 0
    once = crc8(b"abc")
    assert 0 <= once <= 255
    assert crc8(b"abc") == once  # deterministic


def test_datacode_emits_six_packet_lengths() -> None:
    """One data code expands to a fixed 6-packet group of positive ints."""
    dc = DataCode(value=0x5A, index=3)
    lengths = dc.packet_lengths(sequence_header=0)
    assert len(lengths) == 6
    assert all(isinstance(x, int) and x > 0 for x in lengths)


def test_datacode_is_deterministic() -> None:
    a = DataCode(value=0x5A, index=3).packet_lengths(sequence_header=0)
    b = DataCode(value=0x5A, index=3).packet_lengths(sequence_header=0)
    assert a == b


def test_datacode_rejects_out_of_range_value() -> None:
    with pytest.raises(ValueError, match="value"):
        DataCode(value=999, index=0)


def test_datacode_rejects_out_of_range_index() -> None:
    with pytest.raises(ValueError, match="index"):
        DataCode(value=0, index=999)


def test_encode_starts_with_guide_code() -> None:
    pkts = encode_packets("MyWiFi", "secret123", "aabbccddeeff", "192.168.1.42")
    assert pkts[:GUIDE_CODE_LEN] == list(GUIDE_CODE)
    assert GUIDE_CODE == (515, 514, 513, 512)


def test_encode_returns_non_empty_int_list() -> None:
    pkts = encode_packets("MyWiFi", "secret123", "aabbccddeeff", "192.168.1.42")
    assert len(pkts) > GUIDE_CODE_LEN
    assert all(isinstance(p, int) for p in pkts)


def test_encode_all_lengths_are_valid_udp_sizes() -> None:
    pkts = encode_packets("MyWiFi", "secret123", "aabbccddeeff", "192.168.1.42")
    assert all(0 < p < 1500 for p in pkts)


def test_encode_is_deterministic() -> None:
    a = encode_packets("MyWiFi", "secret123", "aabbccddeeff", "192.168.1.42")
    b = encode_packets("MyWiFi", "secret123", "aabbccddeeff", "192.168.1.42")
    assert a == b


def test_encode_longer_password_yields_more_packets() -> None:
    """Datum length scales with the credential length."""
    short = encode_packets("MyWiFi", "pw", "aabbccddeeff", "192.168.1.42")
    long = encode_packets("MyWiFi", "a-much-longer-passphrase", "aabbccddeeff", "192.168.1.42")
    assert len(long) > len(short)


def test_encode_rejects_bad_bssid() -> None:
    with pytest.raises(ValueError, match="bssid"):
        encode_packets("MyWiFi", "secret123", "not-hex", "192.168.1.42")


def test_encode_rejects_bad_ip() -> None:
    with pytest.raises(ValueError, match="ip"):
        encode_packets("MyWiFi", "secret123", "aabbccddeeff", "999.999.999.999")
