"""ESP-TOUCH (Espressif SmartConfig) Wi-Fi provisioning library.

Public, import-stable API. wiz-core and tuya-core depend on
`from esptouch import run, NewBulb, EsptouchError` — do not rename
`run`, `NewBulb`, or `EsptouchError`.

`run()` broadcasts length-encoded Wi-Fi credentials over UDP and polls a
caller-supplied `on_join` coroutine until a device appears or the timeout
elapses. It performs NO discovery itself — the caller owns discovery and
device-registry access; this keeps the library protocol-pure and reusable.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from esptouch.encoder import encode_packets

log = logging.getLogger(__name__)

# ESP-TOUCH packets are broadcast to the limited-broadcast address; the
# device sniffs frame lengths regardless of destination.
_BROADCAST_ADDR = "255.255.255.255"
_BROADCAST_PORT = 7001  # any port works; the device reads lengths, not ports
_INTER_PACKET_S = 0.008  # ~8ms gap between datagrams (reference-app cadence)


class EsptouchError(RuntimeError):
    """Raised when ESP-TOUCH encoding or the broadcast socket fails."""


@dataclass(frozen=True)
class NewBulb:
    """A device that joined the LAN during an onboarding run."""

    mac: str
    ip: str
    name: str
    rssi: int | None


def _make_broadcast_socket() -> socket.socket:
    """Open a non-blocking UDP socket with SO_BROADCAST enabled."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)
    sock.bind(("0.0.0.0", 0))
    return sock


async def _broadcast_once(sock: socket.socket, packet_lengths: list[int]) -> None:
    """Send one full ESP-TOUCH packet sequence.

    Each entry in `packet_lengths` is the required datagram size; the
    payload is that many zero bytes (the device decodes the *length*,
    not the content).
    """
    loop = asyncio.get_running_loop()
    for length in packet_lengths:
        datagram = b"\x00" * length
        await loop.sock_sendto(sock, datagram, (_BROADCAST_ADDR, _BROADCAST_PORT))
        await asyncio.sleep(_INTER_PACKET_S)


async def run(
    ssid: str,
    password: str,
    *,
    timeout_s: int,
    on_join: Callable[[], Awaitable[list[NewBulb]]],
    bssid: str,
    local_ip: str,
    poll_interval_s: float = 5.0,
) -> list[NewBulb]:
    """Broadcast length-encoded credentials, poll `on_join` until a device joins.

    Args:
        ssid / password: the home Wi-Fi credentials to hand the device.
        timeout_s: hard cap on the broadcast loop (amendment §A1).
        on_join: a coroutine the caller supplies; it is awaited every
            `poll_interval_s` and returns the list of devices that have
            joined so far. The first non-empty result ends the run.
        bssid: the home AP's BSSID, 12 hex chars.
        local_ip: this host's IPv4 on the home LAN.
        poll_interval_s: how often to await `on_join` between broadcasts.

    Returns:
        The devices reported by `on_join`, or [] if the timeout elapsed
        with none.

    Raises:
        EsptouchError: encoding failed (bad bssid/ip/credentials) or the
            broadcast socket raised OSError.
    """
    try:
        packet_lengths = encode_packets(ssid, password, bssid, local_ip)
    except ValueError as exc:
        raise EsptouchError(f"esptouch encoding failed: {exc}") from exc

    deadline = time.monotonic() + timeout_s
    sock = _make_broadcast_socket()
    try:
        while time.monotonic() < deadline:
            try:
                await _broadcast_once(sock, packet_lengths)
            except OSError as exc:
                raise EsptouchError(f"esptouch broadcast failed: {exc}") from exc
            joined = await on_join()
            if joined:
                log.info("esptouch: %d device(s) joined", len(joined))
                return joined
            await asyncio.sleep(poll_interval_s)
    finally:
        sock.close()
    log.info("esptouch: timeout after %ds, no devices joined", timeout_s)
    return []
