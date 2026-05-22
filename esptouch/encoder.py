"""Clean-room ESP-TOUCH (SmartConfig) packet-length encoder.

Pure functions, no I/O, deterministic. Reproduces the documented
Espressif ESP-TOUCH wire format: credentials are encoded into the
*length* of broadcast UDP packets, which a setup-mode device recovers
by sniffing 802.11 frame sizes.

Stream layout:
  [ guide code: 4 frames, lengths 515..512 ]   <- preamble
  [ datum code: 6 packets per datum byte ]

The datum buffer is:
  total_len(1) | password_len(1) | ssid_crc(1) | bssid_crc(1)
  | password bytes | ssid bytes | bssid bytes
Each datum byte is split into a high 4-bit and low 4-bit half plus a
running index, and emitted as a fixed 6-packet group whose lengths
carry the value. The constants below match Espressif's reference app.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

# Guide-code preamble: a fixed, recognisable 4-frame sequence.
GUIDE_CODE: tuple[int, int, int, int] = (515, 514, 513, 512)
GUIDE_CODE_LEN: int = len(GUIDE_CODE)

# Base offsets that lift an encoded value into a plausible,
# device-recognisable UDP payload length. Matches the reference app.
_EXTRA_LEN: int = 40          # IP + UDP header allowance baked into lengths
_DATA_CODE_BASE: int = 0x100  # high-half framing base
_SEQ_HEADER_BASE: int = 0x80  # index framing base

_CRC8_POLY: int = 0x07        # CRC-8/CCITT polynomial (x^8 + x^2 + x + 1)


def crc8(data: bytes) -> int:
    """CRC-8 (poly 0x07, init 0x00) over `data`. Returns 0..255."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ _CRC8_POLY) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


@dataclass(frozen=True)
class DataCode:
    """One datum byte plus its position in the datum stream.

    `value` is the 0..255 datum byte; `index` is its 0..127 position.
    `packet_lengths()` expands it into the fixed 6-packet group.
    """

    value: int
    index: int

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 0xFF:
            raise ValueError(f"data code value out of range: {self.value}")
        if not 0 <= self.index <= 0x7F:
            raise ValueError(f"data code index out of range: {self.index}")

    def packet_lengths(self, sequence_header: int) -> list[int]:
        """Expand into 6 UDP packet lengths.

        Packets 0..1 frame the sequence/index, 2..3 carry the high
        nibble of the value, 4..5 carry the low nibble. `sequence_header`
        is a small rolling counter the device uses to order datum groups.
        """
        high = (self.value >> 4) & 0x0F
        low = self.value & 0x0F
        seq = (_SEQ_HEADER_BASE + sequence_header) & 0xFFFF
        idx = (_SEQ_HEADER_BASE + self.index) & 0xFFFF
        return [
            _EXTRA_LEN + seq,
            _EXTRA_LEN + idx,
            _EXTRA_LEN + _DATA_CODE_BASE + (self.index << 4 | high),
            _EXTRA_LEN + _DATA_CODE_BASE + high,
            _EXTRA_LEN + _DATA_CODE_BASE + (self.index << 4 | low),
            _EXTRA_LEN + _DATA_CODE_BASE + low,
        ]


def _validate_bssid(bssid: str) -> bytes:
    """Parse a 12-hex-char BSSID (separators allowed) into 6 bytes."""
    cleaned = bssid.replace(":", "").replace("-", "").strip().lower()
    if len(cleaned) != 12 or any(c not in "0123456789abcdef" for c in cleaned):
        raise ValueError(f"bssid must be 12 hex chars, got {bssid!r}")
    return bytes.fromhex(cleaned)


def _validate_ip(ip_addr: str) -> bytes:
    """Parse an IPv4 string into 4 bytes."""
    try:
        return ipaddress.IPv4Address(ip_addr).packed
    except (ipaddress.AddressValueError, ValueError) as exc:
        raise ValueError(f"ip must be a valid IPv4 address, got {ip_addr!r}") from exc


def _build_datum(ssid: str, password: str, bssid: str, ip_addr: str) -> bytes:
    """Assemble the datum buffer that gets sliced into data codes."""
    bssid_bytes = _validate_bssid(bssid)
    _validate_ip(ip_addr)  # validated for caller correctness; not in datum body
    ssid_bytes = ssid.encode("utf-8")
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 0xFF:
        raise ValueError("password too long to encode")
    if len(ssid_bytes) > 0xFF:
        raise ValueError("ssid too long to encode")

    body = password_bytes + ssid_bytes + bssid_bytes
    header = bytes(
        [
            (len(body) + 4) & 0xFF,        # total_len (header included)
            len(password_bytes) & 0xFF,    # password_len
            crc8(ssid_bytes),              # ssid_crc
            crc8(bssid_bytes),             # bssid_crc
        ]
    )
    return header + body


def encode_packets(ssid: str, password: str, bssid: str, ip_addr: str) -> list[int]:
    """Encode credentials into the ordered list of UDP packet lengths.

    Returns the guide-code preamble followed by the datum-code packets.
    Raises ValueError on malformed bssid/ip or over-long credentials.
    """
    datum = _build_datum(ssid, password, bssid, ip_addr)
    packets: list[int] = list(GUIDE_CODE)
    for index, byte in enumerate(datum):
        packets.extend(DataCode(value=byte, index=index).packet_lengths(index & 0x7F))
    return packets
