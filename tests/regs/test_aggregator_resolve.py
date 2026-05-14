"""Tests for the 3-layer regs aggregator: resolve() precedence."""
from datetime import date, datetime

import pytest

from regs import resolve
from regs.emergency_types import Projection
from regs.wdfw import RegStatus


def _status(authority="WDFW", section_key="x", is_open=True, reason="ok"):
    return RegStatus(
        authority=authority,
        section_key=section_key,
        open=is_open,
        reason=reason,
        last_checked=datetime.now(),
    )


def _proj(section_key, *, is_open=True, reason="ok", authority="WDFW"):
    """Build an always-active Projection (effective_from=effective_to=None)."""
    return Projection(
        section_id=section_key,
        status="open" if is_open else "closed",
        effective_from=None,
        effective_to=None,
        reason=reason,
        authority=authority,
    )


def test_resolve_emergency_open_overrides_pamphlet_closed():
    pamphlet = {"hanford_lower_i182_to_snyder": _status(section_key="hanford_lower_i182_to_snyder", is_open=False, reason="pamphlet seasonal closure")}
    emergency = {"hanford_lower_i182_to_snyder": [_proj("hanford_lower_i182_to_snyder", is_open=True, reason="emergency reopening for fall chinook")]}
    out = resolve(pamphlet, emergency, "hanford_lower_i182_to_snyder", date(2026, 8, 1))
    assert out is not None
    assert out.open is True
    assert "emergency" in out.reason.lower()


def test_resolve_emergency_closed_overrides_pamphlet_open():
    pamphlet = {"hanford_lower_i182_to_snyder": _status(section_key="hanford_lower_i182_to_snyder", is_open=True)}
    emergency = {"hanford_lower_i182_to_snyder": [_proj("hanford_lower_i182_to_snyder", is_open=False, reason="emergency closure for low returns")]}
    out = resolve(pamphlet, emergency, "hanford_lower_i182_to_snyder", date(2026, 8, 1))
    assert out is not None
    assert out.open is False


def test_resolve_falls_back_to_pamphlet_when_no_emergency(monkeypatch):
    def _stub_pamphlet(section_id, *, today, species="salmon_hatchery_steelhead"):
        return _status(section_key=section_id, is_open=False, reason="pamphlet closure")
    monkeypatch.setattr("regs.pamphlet_status_for_section", _stub_pamphlet)

    pamphlet = {"hanford_lower_i182_to_snyder": _status(section_key="hanford_lower_i182_to_snyder", is_open=False, reason="pamphlet closure")}
    out = resolve(pamphlet, {}, "hanford_lower_i182_to_snyder", date(2026, 5, 1))
    assert out is not None
    assert out.open is False
    assert "pamphlet" in out.reason.lower()


def test_resolve_returns_none_when_section_unknown(monkeypatch):
    monkeypatch.setattr("regs.pamphlet_status_for_section", lambda *args, **kw: None)
    out = resolve({}, {}, "nonexistent_section", date(2026, 5, 1))
    assert out is None


def test_resolve_for_day_closure_window_overrides_pamphlet_open(monkeypatch):
    """Emergency closure projection wins over pamphlet baseline-open for any day in range."""
    from datetime import date
    from regs import resolve_for_day
    from regs.emergency_types import Projection
    em = {"x": [Projection(
        section_id="x", status="closed",
        effective_from=date(2026, 6, 1), effective_to=date(2026, 6, 15),
        reason="emergency closure", authority="WDFW",
    )]}
    # Stub pamphlet to say "open" for any date.
    def _stub_pamphlet(section_id, *, today, species="salmon_hatchery_steelhead"):
        from datetime import datetime
        from regs.wdfw_pamphlet import RegStatus
        return RegStatus(authority="WDFW", section_key=section_id, open=True,
                         reason="pamphlet says open", last_checked=datetime.now())
    monkeypatch.setattr("regs.pamphlet_status_for_section", _stub_pamphlet)

    # Inside the closure window -> closed
    rs = resolve_for_day(em, "x", date(2026, 6, 7))
    assert rs is not None and rs.open is False
    # Outside the closure window -> pamphlet baseline (open)
    rs = resolve_for_day(em, "x", date(2026, 7, 1))
    assert rs is not None and rs.open is True


def test_resolve_for_day_discrete_date_open(monkeypatch):
    """Discrete-date open projection (from==to) applies only on that exact day."""
    from datetime import date
    from regs import resolve_for_day
    from regs.emergency_types import Projection
    em = {"snake_lower_monumental_to_little_goose": [
        Projection(
            section_id="snake_lower_monumental_to_little_goose", status="open",
            effective_from=date(2026, 5, 15), effective_to=date(2026, 5, 15),
            reason="Little Goose one-day opener", authority="WDFW",
        ),
    ]}
    def _stub_pamphlet(section_id, *, today, species="salmon_hatchery_steelhead"):
        from datetime import datetime
        from regs.wdfw_pamphlet import RegStatus
        # pamphlet says CLOSED (no salmon row -> default-closed)
        return RegStatus(authority="WDFW", section_key=section_id, open=False,
                         reason="Closed (no salmon row)", last_checked=datetime.now())
    monkeypatch.setattr("regs.pamphlet_status_for_section", _stub_pamphlet)

    # On the open date -> open
    rs = resolve_for_day(em, "snake_lower_monumental_to_little_goose", date(2026, 5, 15))
    assert rs is not None and rs.open is True
    # Day before -> pamphlet baseline (closed)
    rs = resolve_for_day(em, "snake_lower_monumental_to_little_goose", date(2026, 5, 14))
    assert rs is not None and rs.open is False
    # Day after -> pamphlet baseline (closed)
    rs = resolve_for_day(em, "snake_lower_monumental_to_little_goose", date(2026, 5, 16))
    assert rs is not None and rs.open is False


def test_resolve_for_day_closures_win_over_opens_on_same_day(monkeypatch):
    """When two projections overlap on the same day, a closure overrides an open."""
    from datetime import date
    from regs import resolve_for_day
    from regs.emergency_types import Projection
    em = {"y": [
        Projection(section_id="y", status="open",
                   effective_from=date(2026, 6, 1), effective_to=date(2026, 6, 30),
                   reason="seasonal open", authority="WDFW"),
        Projection(section_id="y", status="closed",
                   effective_from=date(2026, 6, 10), effective_to=date(2026, 6, 12),
                   reason="emergency closure", authority="WDFW"),
    ]}
    def _stub_pamphlet(section_id, *, today, species="salmon_hatchery_steelhead"):
        return None
    monkeypatch.setattr("regs.pamphlet_status_for_section", _stub_pamphlet)

    # Inside closure window -> closed (closures win)
    rs = resolve_for_day(em, "y", date(2026, 6, 11))
    assert rs is not None and rs.open is False
    assert "emergency" in rs.reason.lower()
    # Inside seasonal open window, outside closure -> open
    rs = resolve_for_day(em, "y", date(2026, 6, 5))
    assert rs is not None and rs.open is True


def test_resolve_for_day_no_projections_falls_back_to_pamphlet(monkeypatch):
    """No emergency projections for the section -> pamphlet result is returned."""
    from datetime import date
    from regs import resolve_for_day
    from datetime import datetime
    from regs.wdfw_pamphlet import RegStatus
    def _stub_pamphlet(section_id, *, today, species="salmon_hatchery_steelhead"):
        return RegStatus(authority="WDFW", section_key=section_id, open=True,
                         reason="pamphlet", last_checked=datetime.now())
    monkeypatch.setattr("regs.pamphlet_status_for_section", _stub_pamphlet)

    rs = resolve_for_day({}, "z", date(2026, 7, 1))
    assert rs is not None and rs.open is True


def test_resolve_for_day_returns_none_when_no_data(monkeypatch):
    """No emergency AND pamphlet returns None -> overall None (caller treats as default-open)."""
    from datetime import date
    from regs import resolve_for_day
    monkeypatch.setattr("regs.pamphlet_status_for_section", lambda *args, **kw: None)
    assert resolve_for_day({}, "unknown_section", date(2026, 7, 1)) is None


def test_fetch_all_returns_emergency_projections_shape(monkeypatch, tmp_path):
    """fetch_all's middle return is now dict[str, list[Projection]], not dict[str, RegStatus]."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Stub all the network/LLM dependencies to keep this test offline.
    monkeypatch.setattr("regs.fetch_active_rules", lambda today: [])
    monkeypatch.setattr("regs.odfw_fetch", lambda: [])
    monkeypatch.setattr("regs.idfg_fetch", lambda: [])
    from regs import fetch_all
    from datetime import date
    pam, em, meta = fetch_all(date(2026, 5, 14))
    assert isinstance(em, dict)
    # Each value should be a list (empty if no rules), not a RegStatus.
    for v in em.values():
        assert isinstance(v, list)
