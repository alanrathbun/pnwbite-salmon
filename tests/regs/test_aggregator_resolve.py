"""Tests for the 3-layer regs aggregator: resolve() precedence."""
from datetime import date, datetime

import pytest

from regs import resolve
from regs.wdfw import RegStatus


def _status(authority="WDFW", section_key="x", is_open=True, reason="ok"):
    return RegStatus(
        authority=authority,
        section_key=section_key,
        open=is_open,
        reason=reason,
        last_checked=datetime.now(),
    )


def test_resolve_emergency_open_overrides_pamphlet_closed():
    pamphlet = {"hanford_lower_i182_to_snyder": _status(section_key="hanford_lower_i182_to_snyder", is_open=False, reason="pamphlet seasonal closure")}
    emergency = {"hanford_lower_i182_to_snyder": _status(section_key="hanford_lower_i182_to_snyder", is_open=True, reason="emergency reopening for fall chinook")}
    out = resolve(pamphlet, emergency, "hanford_lower_i182_to_snyder", date(2026, 8, 1))
    assert out is not None
    assert out.open is True
    assert "emergency" in out.reason.lower()


def test_resolve_emergency_closed_overrides_pamphlet_open():
    pamphlet = {"hanford_lower_i182_to_snyder": _status(section_key="hanford_lower_i182_to_snyder", is_open=True)}
    emergency = {"hanford_lower_i182_to_snyder": _status(section_key="hanford_lower_i182_to_snyder", is_open=False, reason="emergency closure for low returns")}
    out = resolve(pamphlet, emergency, "hanford_lower_i182_to_snyder", date(2026, 8, 1))
    assert out is not None
    assert out.open is False


def test_resolve_falls_back_to_pamphlet_when_no_emergency():
    pamphlet = {"hanford_lower_i182_to_snyder": _status(section_key="hanford_lower_i182_to_snyder", is_open=False, reason="pamphlet closure")}
    out = resolve(pamphlet, {}, "hanford_lower_i182_to_snyder", date(2026, 5, 1))
    assert out is not None
    assert out.open is False
    assert "pamphlet" in out.reason.lower()


def test_resolve_returns_none_when_section_unknown():
    out = resolve({}, {}, "nonexistent_section", date(2026, 5, 1))
    assert out is None
