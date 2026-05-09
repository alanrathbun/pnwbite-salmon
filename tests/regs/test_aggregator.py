"""Tests for regs.fetch_all aggregator's tuple return shape and per-agency staleness.

After Phase 1.5b B5, fetch_all returns a 3-tuple:
``(pamphlet_layer, emergency_layer, agency_meta)``.

The aggregator must:
1. Return three separate dicts.
2. Mark an agency ``ok=False`` and ``last_successful_check=None`` when its
   scraper raises, instead of silently swallowing the failure.
3. Still return successful agencies' results (one failure must not poison
   the whole batch).

WDFW's emergency layer no longer flows through `regs.wdfw_fetch` (that legacy
regex parser was retired). Instead the layer is built from
`regs.fetch_active_rules` + the Claude classifier. We patch
`regs.fetch_active_rules` to return [] (i.e., no active emergency rules) and
focus the assertions on ODFW/IDFG behaviour (the stable contract).
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


def test_fetch_all_returns_tuple_with_layers_and_agency_meta():
    """All agencies succeed → ok=True for each, layered statuses returned."""
    with patch("regs.fetch_active_rules", return_value=[]), \
         patch("regs.odfw_fetch", return_value=[_make_status("ODFW", "ODFW_MID_COL")]), \
         patch("regs.idfg_fetch", return_value=[_make_status("IDFG", "IDFG_SALMON")]):
        pamphlet_layer, emergency_layer, agency_meta = regs_mod.fetch_all()

    # Emergency layer: ODFW + IDFG section_keys present
    assert "ODFW_MID_COL" in emergency_layer
    assert "IDFG_SALMON" in emergency_layer

    # Pamphlet layer: each encoded section is a dict[str, RegStatus]
    assert isinstance(pamphlet_layer, dict)

    # agency_meta: each agency present and ok=True with a timestamp
    for name in ("WDFW", "ODFW", "IDFG", "WDFW_PAMPHLET"):
        assert name in agency_meta
        assert agency_meta[name]["ok"] is True
        assert agency_meta[name]["last_successful_check"] is not None
        assert agency_meta[name]["error"] is None


def test_fetch_all_marks_failed_agency_in_meta_but_keeps_others():
    """If WDFW emergency fetch raises, ODFW and IDFG results are still returned
    and WDFW is flagged ok=False with last_successful_check=None."""
    def boom(*_args, **_kwargs):
        raise RuntimeError("wdfw page returned 503")

    with patch("regs.fetch_active_rules", side_effect=boom), \
         patch("regs.odfw_fetch", return_value=[_make_status("ODFW", "ODFW_MID_COL")]), \
         patch("regs.idfg_fetch", return_value=[_make_status("IDFG", "IDFG_SALMON")]):
        pamphlet_layer, emergency_layer, agency_meta = regs_mod.fetch_all()

    # WDFW failed: marked accordingly
    assert agency_meta["WDFW"]["ok"] is False
    assert agency_meta["WDFW"]["last_successful_check"] is None
    assert "503" in agency_meta["WDFW"]["error"]

    # Other agencies still succeed
    assert agency_meta["ODFW"]["ok"] is True
    assert agency_meta["IDFG"]["ok"] is True

    # Statuses from successful agencies still in the emergency layer
    assert "ODFW_MID_COL" in emergency_layer
    assert "IDFG_SALMON" in emergency_layer


def test_fetch_all_truncates_long_error_messages():
    """Long error tracebacks must be truncated so they don't bloat report_data."""
    def boom(*_args, **_kwargs):
        raise RuntimeError("x" * 1000)

    with patch("regs.fetch_active_rules", side_effect=boom), \
         patch("regs.odfw_fetch", return_value=[]), \
         patch("regs.idfg_fetch", return_value=[]):
        _, _, agency_meta = regs_mod.fetch_all()

    assert len(agency_meta["WDFW"]["error"]) <= 200
