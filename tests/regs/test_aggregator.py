"""Tests for regs.fetch_all aggregator's tuple return shape and per-agency staleness.

The aggregator must:
1. Return ``(statuses, agency_meta)`` — both as separate dicts.
2. Mark an agency ``ok=False`` and ``last_successful_check=None`` when its
   scraper raises, instead of silently swallowing the failure.
3. Still return successful agencies' results (one failure must not poison
   the whole batch).
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

import regs as regs_mod
from regs.wdfw import RegStatus


def _make_status(authority: str, key: str, *, is_open: bool = True) -> RegStatus:
    return RegStatus(
        authority=authority,
        section_key=key,
        open=is_open,
        reason="test",
        last_checked=datetime.now(),
    )


def test_fetch_all_returns_tuple_with_statuses_and_agency_meta():
    """All three agencies succeed → ok=True for each, full statuses returned."""
    with patch("regs.wdfw_fetch", return_value=[_make_status("WDFW", "WDFW_HANFORD_REACH")]), \
         patch("regs.odfw_fetch", return_value=[_make_status("ODFW", "ODFW_MID_COL")]), \
         patch("regs.idfg_fetch", return_value=[_make_status("IDFG", "IDFG_SALMON")]):
        statuses, agency_meta = regs_mod.fetch_all()

    # statuses: each section_key present
    assert "WDFW_HANFORD_REACH" in statuses
    assert "ODFW_MID_COL" in statuses
    assert "IDFG_SALMON" in statuses

    # agency_meta: each agency present and ok=True with a timestamp
    for name in ("WDFW", "ODFW", "IDFG"):
        assert name in agency_meta
        assert agency_meta[name]["ok"] is True
        assert agency_meta[name]["last_successful_check"] is not None
        assert agency_meta[name]["error"] is None


def test_fetch_all_marks_failed_agency_in_meta_but_keeps_others():
    """If WDFW raises, ODFW and IDFG results are still returned and WDFW
    is flagged ok=False with last_successful_check=None."""
    def boom():
        raise RuntimeError("wdfw page returned 503")

    with patch("regs.wdfw_fetch", side_effect=boom), \
         patch("regs.odfw_fetch", return_value=[_make_status("ODFW", "ODFW_MID_COL")]), \
         patch("regs.idfg_fetch", return_value=[_make_status("IDFG", "IDFG_SALMON")]):
        statuses, agency_meta = regs_mod.fetch_all()

    # WDFW failed: marked accordingly
    assert agency_meta["WDFW"]["ok"] is False
    assert agency_meta["WDFW"]["last_successful_check"] is None
    assert "503" in agency_meta["WDFW"]["error"]

    # Other agencies still succeed
    assert agency_meta["ODFW"]["ok"] is True
    assert agency_meta["IDFG"]["ok"] is True

    # Statuses from successful agencies still present
    assert "ODFW_MID_COL" in statuses
    assert "IDFG_SALMON" in statuses
    # WDFW's section is absent (no fallback default-open here; that's the
    # caller's responsibility).
    assert "WDFW_HANFORD_REACH" not in statuses


def test_fetch_all_truncates_long_error_messages():
    """Long error tracebacks must be truncated so they don't bloat report_data."""
    def boom():
        raise RuntimeError("x" * 1000)

    with patch("regs.wdfw_fetch", side_effect=boom), \
         patch("regs.odfw_fetch", return_value=[]), \
         patch("regs.idfg_fetch", return_value=[]):
        _, agency_meta = regs_mod.fetch_all()

    assert len(agency_meta["WDFW"]["error"]) <= 200
