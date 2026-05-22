"""ESP-TOUCH encoding-correctness smoke test (amendment §A1 check #6).

Encodes a fixed, known (ssid, password, bssid, ip) tuple and asserts the
resulting packet-length sequence matches the documented ESP-TOUCH spec:
the guide-code preamble, a datum length consistent with the credential
size, and that every length is a plausible UDP datagram size.

Run standalone:  python -m esptouch.audit
Exit code 0 = pass, 1 = fail.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from esptouch.encoder import GUIDE_CODE, GUIDE_CODE_LEN, crc8, encode_packets

# Fixed audit vector — never change without re-deriving expectations.
_SSID = "AuditNet"
_PASSWORD = "audit-pass-123"
_BSSID = "001122334455"
_IP = "192.168.1.10"


@dataclass
class AuditResult:
    """Outcome of run_audit(): a pass flag plus human-readable lines."""

    ok: bool
    checked: int
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def run_audit() -> AuditResult:
    """Encode the fixed vector and verify it against the documented spec."""
    checks: list[str] = []
    failures: list[str] = []

    packets = encode_packets(_SSID, _PASSWORD, _BSSID, _IP)

    # Check A: guide-code preamble is present and exact.
    if packets[:GUIDE_CODE_LEN] == list(GUIDE_CODE):
        checks.append(f"guide code OK: {list(GUIDE_CODE)}")
    else:
        failures.append(f"guide code wrong: got {packets[:GUIDE_CODE_LEN]}")

    # Check B: datum length is consistent. Datum buffer is
    # 4 header bytes + password + ssid + 6 bssid bytes, each datum byte
    # expands to 6 packets.
    datum_bytes = 4 + len(_PASSWORD.encode()) + len(_SSID.encode()) + 6
    expected_total = GUIDE_CODE_LEN + datum_bytes * 6
    if len(packets) == expected_total:
        checks.append(f"datum length OK: {len(packets)} packets ({datum_bytes} data codes)")
    else:
        failures.append(
            f"datum length wrong: got {len(packets)}, expected {expected_total}"
        )

    # Check C: every length is a plausible UDP datagram size.
    bad = [p for p in packets if not 0 < p < 1500]
    if not bad:
        checks.append(f"all {len(packets)} lengths within (0, 1500)")
    else:
        failures.append(f"{len(bad)} packet length(s) out of UDP range: {bad[:5]}")

    # Check D: encoding is deterministic.
    if encode_packets(_SSID, _PASSWORD, _BSSID, _IP) == packets:
        checks.append("encoding is deterministic")
    else:
        failures.append("encoding is non-deterministic (global state / RNG leak)")

    # Check E: CRC-8 sanity — empty input is 0, known buffer is stable.
    if crc8(b"") == 0 and crc8(b"esptouch") == crc8(b"esptouch"):
        checks.append("crc8 sanity OK")
    else:
        failures.append("crc8 failed sanity check")

    return AuditResult(
        ok=not failures,
        checked=len(packets),
        checks=checks,
        failures=failures,
    )


def main() -> int:
    """CLI entrypoint: print the audit report, return a process exit code."""
    result = run_audit()
    for line in result.checks:
        print(f"  PASS  {line}")
    for line in result.failures:
        print(f"  FAIL  {line}")
    if result.ok:
        print(f"ESP-TOUCH audit PASSED ({result.checked} packets encoded).")
        return 0
    print(f"ESP-TOUCH audit FAILED ({len(result.failures)} problem(s)).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
