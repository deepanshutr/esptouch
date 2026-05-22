# CLAUDE.md — esptouch

Clean-room ESP-TOUCH (Espressif SmartConfig) Wi-Fi provisioning library.

## Conventions

- Python 3.11+; `from __future__ import annotations` first line of every module.
- `encoder.py` is **pure** — no I/O, no globals, deterministic. Keep it that way.
- The public API (`run`, `NewBulb`, `EsptouchError`) is import-stable:
  wiz-core and tuya-core both `from esptouch import ...`. Do not rename.
- `run()`'s signature is frozen:
  `run(ssid, password, *, timeout_s, on_join, bssid, local_ip, poll_interval_s=5.0)`.
- Tests use `pytest`; `asyncio_mode = "auto"` (no `@pytest.mark.asyncio`).
- Run `uv run ruff check esptouch tests`, `uv run mypy esptouch`,
  `uv run pytest -v`, `uv run python -m esptouch.audit` before commit.

## Don't repeat

- `run()` does NO discovery — the caller supplies `on_join`. This is what
  keeps the library reusable by tuya-core. Do not couple it to a registry.
- ESP-TOUCH is 2.4 GHz only and broadcasts to 255.255.255.255.
- `audit.py` is a CI gate; re-run `python -m esptouch.audit` after any
  change to `encoder.py`.
- This library is clean-room — reproduced from the documented Espressif
  SmartConfig wire format. No third-party code is vendored. Keep it so.
