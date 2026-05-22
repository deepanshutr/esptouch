"""Tests for the ESP-TOUCH encoding-correctness audit module."""

from __future__ import annotations

from esptouch.audit import AuditResult, run_audit


def test_run_audit_passes_for_known_vector() -> None:
    result = run_audit()
    assert isinstance(result, AuditResult)
    assert result.ok is True
    assert result.checked > 0
    assert result.failures == []


def test_run_audit_reports_guide_code_check() -> None:
    """The audit explicitly verifies the guide-code preamble."""
    result = run_audit()
    assert any("guide code" in line for line in result.checks)
