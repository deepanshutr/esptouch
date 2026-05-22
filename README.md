# esptouch

A clean-room Python implementation of Espressif's **ESP-TOUCH**
(SmartConfig) Wi-Fi provisioning protocol — no third-party code, MIT.

ESP-TOUCH hands Wi-Fi credentials to a device already in setup/promiscuous
mode by encoding the SSID + password into the *length* of broadcast UDP
packets, which the device recovers by sniffing 802.11 frame sizes.

## Install

Not published to PyPI. Depend on it as a git dependency:

```toml
# in your pyproject.toml
dependencies = ["esptouch @ git+https://github.com/deepanshutr/esptouch.git"]
```

For local development, install the clone editable:

```bash
uv pip install -e ~/github.com/deepanshutr/esptouch
```

## Usage

```python
from esptouch import run, NewBulb, EsptouchError

async def on_join() -> list[NewBulb]:
    # caller-supplied: return devices that have joined the LAN so far
    ...

bulbs = await run(
    "MyHomeWiFi", "secret",
    timeout_s=60,
    on_join=on_join,
    bssid="aabbccddeeff",       # home AP BSSID, 12 hex chars
    local_ip="192.168.1.42",    # this host's IPv4 on the home LAN
)
```

`run()` broadcasts length-encoded credentials and awaits `on_join` every
`poll_interval_s` (default 5.0) until it reports a device or `timeout_s`
elapses. It performs no discovery itself — the caller owns that — keeping
the library protocol-pure and reusable.

The host must be on the **2.4 GHz** target Wi-Fi (ESP-TOUCH is 2.4 GHz
only) for the device to receive the broadcast.

## Audit

`python -m esptouch.audit` runs an encoding-correctness smoke test against
a fixed known vector. It is a CI gate.

## Consumers

- [wiz-core](https://github.com/deepanshutr/wiz-core) — Philips WiZ daemon
- tuya-core — Tuya bulb daemon (planned)
