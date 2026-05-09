"""Tests for the WDFW pamphlet section-status lookup."""
from datetime import date

import pytest

from regs.wdfw_pamphlet import (
    status_for_section,
    status_for_all_sections,
    _date_in_range,
    load_pamphlet,
    RegStatus,
)


def test_load_pamphlet_returns_sections():
    sections = load_pamphlet()
    assert sections, "expected non-empty pamphlet sections"
    ids = {s["id"] for s in sections}
    assert "mcnary_tailrace" in ids
    assert "mcnary_pool" in ids


def test_mcnary_tailrace_closed_in_may():
    """User-reported bug: McNary Tailrace shown as open on May 8 2026 but is CLOSED."""
    st = status_for_section("mcnary_tailrace", today=date(2026, 5, 8))
    assert st is not None
    assert st.open is False
    assert "closed" in st.reason.lower() or "Closed" in st.reason


def test_mcnary_tailrace_open_in_august():
    st = status_for_section("mcnary_tailrace", today=date(2026, 8, 15))
    assert st is not None
    assert st.open is True


def test_mcnary_tailrace_closed_late_september():
    """Sept 18-30 is a closure inside an otherwise-open fall season."""
    st = status_for_section("mcnary_tailrace", today=date(2026, 9, 25))
    assert st is not None
    assert st.open is False


def test_mcnary_pool_open_in_january():
    """McNary Pool (above the dam) is OPEN Jan 1 - Mar 31, unlike McNary Tailrace."""
    st = status_for_section("mcnary_pool", today=date(2026, 2, 1))
    assert st is not None
    assert st.open is True


def test_mcnary_pool_closed_in_april():
    """McNary Pool is closed Apr 1 - Jun 15."""
    st = status_for_section("mcnary_pool", today=date(2026, 5, 8))
    assert st is not None
    assert st.open is False


def test_unknown_section_returns_none():
    """Unknown section_id should return None so caller can fall back."""
    assert status_for_section("nonexistent_section") is None


def test_implicit_closure_when_no_matching_range():
    """Hanford CRC 535 has no salmon retention period in May (only Jul + Aug-Dec).
    Implicit closure for salmon retention."""
    st = status_for_section(
        "hanford_ringold_wasteway_to_ringold_hatchery",
        today=date(2026, 5, 8),
    )
    assert st is not None
    assert st.open is False


def test_hanford_open_in_september():
    """Hanford CRC 535 IS open Aug 16 - Dec 31."""
    st = status_for_section(
        "hanford_ringold_wasteway_to_ringold_hatchery",
        today=date(2026, 9, 15),
    )
    assert st is not None
    assert st.open is True


def test_priest_rapids_tail_closed_in_may():
    """CRC 537 lists Jul-Aug + Sep-Oct only; May is implicitly closed for salmon."""
    st = status_for_section(
        "priest_rapids_to_wanapum",
        today=date(2026, 5, 8),
    )
    assert st is not None
    assert st.open is False


def test_status_for_all_sections_returns_dict():
    out = status_for_all_sections(today=date(2026, 5, 8))
    assert isinstance(out, dict)
    assert "mcnary_tailrace" in out
    assert out["mcnary_tailrace"].open is False


def test_date_in_range_simple():
    assert _date_in_range(date(2026, 5, 15), "05-01..05-31")
    assert _date_in_range(date(2026, 5, 1), "05-01..05-31")
    assert _date_in_range(date(2026, 5, 31), "05-01..05-31")
    assert not _date_in_range(date(2026, 6, 1), "05-01..05-31")
    assert not _date_in_range(date(2026, 4, 30), "05-01..05-31")


def test_date_in_range_wraparound():
    """Year-wraparound (Dec 1 - Jan 31) covers both months."""
    assert _date_in_range(date(2026, 12, 15), "12-01..01-31")
    assert _date_in_range(date(2026, 1, 15), "12-01..01-31")
    assert not _date_in_range(date(2026, 6, 15), "12-01..01-31")


def test_pamphlet_filename():
    from regs.wdfw_pamphlet import pamphlet_filename
    assert pamphlet_filename() == "25WAFW_LR7.pdf"


def test_pamphlet_version():
    from regs.wdfw_pamphlet import pamphlet_version
    assert pamphlet_version() == "2025-2026"
