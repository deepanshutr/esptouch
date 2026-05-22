"""Tests for the esptouch.run() async broadcast wrapper."""

from __future__ import annotations

import pytest

from esptouch import EsptouchError, NewBulb, run


async def test_run_returns_bulbs_when_on_join_reports_one(mocker) -> None:
    """run() stops early and returns as soon as on_join yields a bulb."""
    # Don't touch a real socket: stub the broadcast send.
    mocker.patch("esptouch._broadcast_once", new=mocker.AsyncMock())

    async def fake_on_join() -> list[NewBulb]:
        return [NewBulb(mac="d8a0118dc5c3", ip="192.168.1.9", name="bulb-8", rssi=-55)]

    bulbs = await run(
        "HomeNet", "secret123", timeout_s=10, on_join=fake_on_join,
        bssid="aabbccddeeff", local_ip="192.168.1.42", poll_interval_s=0.01,
    )
    assert len(bulbs) == 1
    assert bulbs[0].mac == "d8a0118dc5c3"
    assert bulbs[0].name == "bulb-8"


async def test_run_returns_empty_on_timeout(mocker) -> None:
    """If on_join never reports a bulb, run() returns [] after timeout_s."""
    mocker.patch("esptouch._broadcast_once", new=mocker.AsyncMock())

    async def never() -> list[NewBulb]:
        return []

    bulbs = await run(
        "HomeNet", "secret123", timeout_s=1, on_join=never,
        bssid="aabbccddeeff", local_ip="192.168.1.42", poll_interval_s=0.05,
    )
    assert bulbs == []


async def test_run_broadcasts_repeatedly_until_timeout(mocker) -> None:
    """The broadcast loop runs more than once over a multi-poll timeout."""
    send = mocker.patch("esptouch._broadcast_once", new=mocker.AsyncMock())

    async def never() -> list[NewBulb]:
        return []

    await run(
        "HomeNet", "secret123", timeout_s=1, on_join=never,
        bssid="aabbccddeeff", local_ip="192.168.1.42", poll_interval_s=0.05,
    )
    assert send.await_count >= 2


async def test_run_wraps_socket_failure_as_esptouch_error(mocker) -> None:
    """An OSError from the broadcast socket surfaces as EsptouchError."""
    mocker.patch(
        "esptouch._broadcast_once",
        new=mocker.AsyncMock(side_effect=OSError("network unreachable")),
    )

    async def never() -> list[NewBulb]:
        return []

    with pytest.raises(EsptouchError, match="network unreachable"):
        await run(
            "HomeNet", "secret123", timeout_s=1, on_join=never,
            bssid="aabbccddeeff", local_ip="192.168.1.42", poll_interval_s=0.05,
        )


async def test_run_rejects_bad_credentials_input() -> None:
    """Malformed bssid raises EsptouchError (encoder ValueError is wrapped)."""

    async def never() -> list[NewBulb]:
        return []

    with pytest.raises(EsptouchError, match="bssid"):
        await run(
            "HomeNet", "secret123", timeout_s=1, on_join=never,
            bssid="not-hex", local_ip="192.168.1.42", poll_interval_s=0.05,
        )


def test_newbulb_is_a_simple_value_object() -> None:
    b = NewBulb(mac="aabbccddeeff", ip="192.168.1.5", name="bulb-1", rssi=-40)
    assert b.mac == "aabbccddeeff"
    assert b.rssi == -40
