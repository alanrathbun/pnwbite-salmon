"""Long-range forecast extension: build_report_data should emit 366 entries
per (launch, species) with simplified shape past day 7."""
from datetime import date

import pytest

from fishing_report import build_report_data
from sources.dart import RuntimingCurve
from storage import FileStorage


def _minimal_inputs(today: date) -> dict:
    """Tiny inputs dict that exercises the per-launch loop with at least one launch."""
    daily_avg = {i: 100.0 for i in range(1, 367)}
    curves: dict = {}
    for dam in ("BON", "TDA", "JDA", "MCN", "IHR", "LMN", "PRD", "WEL", "RRH", "RIS", "LGR"):
        for sp in ("chinook", "chinook", "sockeye", "chinook",
                   "coho", "steelhead", "steelhead"):
            curves[(dam, sp)] = RuntimingCurve(dam_key=dam, species=sp, daily_avg=daily_avg)
    return {
        "today": today,
        "flows": [],
        "counts": [],
        "pamphlet_regs": {},
        "emergency_regs": {},
        "regs_agency_meta": {},
        "usgs_by_launch": {},
        "nws_by_launch": {},
        "curves": curves,
        "creel": [],
        "climatology_by_launch": {},
    }


def test_build_report_data_emits_366_entries_per_launch_species(tmp_path):
    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 10)
    out = build_report_data(_minimal_inputs(today), storage=storage)
    # Every forecast list should have 366 entries
    assert out["forecasts"], "forecasts dict is empty"
    for fkey, days in out["forecasts"].items():
        assert len(days) == 366, f"{fkey} has {len(days)} entries, expected 366"


def test_build_report_data_long_range_entries_are_simplified(tmp_path):
    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 10)
    out = build_report_data(_minimal_inputs(today), storage=storage)
    fkey = next(iter(out["forecasts"]))
    days = out["forecasts"][fkey]
    near = days[0]  # day 0
    long_ = days[10]  # day 10 → past the 7-day boundary
    # Near-term entry has full fields
    assert near["long_range"] is False
    assert "techniques" in near
    assert "wind_mph" in near
    # Long-range entry has only the simplified shape
    assert long_["long_range"] is True
    assert "wind_mph" not in long_
    assert "water_temp_f" not in long_
    assert "techniques" not in long_
    assert "run_pace_forecast" in long_
    assert "open" in long_


def test_build_report_data_includes_climatology_in_long_range_entries(tmp_path):
    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 10)
    inputs = _minimal_inputs(today)
    # Provide climatology only for the first primary launch
    from stations import primary_stations
    first_key = primary_stations()[0]["key"]
    inputs["climatology_by_launch"][first_key] = {
        f"{(date.fromordinal(today.toordinal() + 10)).strftime('%m-%d')}": {
            "high_f": 71.5, "low_f": 48.2,
        }
    }
    out = build_report_data(inputs, storage=storage)
    fkey_with_clim = next(k for k in out["forecasts"] if k.endswith(f"::{first_key}"))
    days = out["forecasts"][fkey_with_clim]
    assert days[10]["climatology"] == {"high_f": 71.5, "low_f": 48.2}


def test_build_report_data_long_range_omits_climatology_when_missing(tmp_path):
    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 10)
    out = build_report_data(_minimal_inputs(today), storage=storage)
    fkey = next(iter(out["forecasts"]))
    days = out["forecasts"][fkey]
    assert "climatology" not in days[10]


def test_build_report_data_near_term_unchanged(tmp_path):
    """Days 0-6 keep the legacy shape and existing scoring."""
    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 10)
    out = build_report_data(_minimal_inputs(today), storage=storage)
    fkey = next(iter(out["forecasts"]))
    days = out["forecasts"][fkey]
    for i in range(7):
        assert days[i]["long_range"] is False
        # Existing fields all present
        for required in ("date", "score", "verdict", "techniques", "wind_mph", "water_temp_f", "flow_cfs", "no_run_data"):
            assert required in days[i], f"day {i} missing {required}"


def test_build_report_data_long_range_uses_pamphlet_date_ranges(tmp_path, monkeypatch):
    """A pamphlet section whose YAML rules close it on a future date must
    show open=False in the long-range forecast for that future day, even when
    today is well outside the closure window."""
    from datetime import date
    from unittest.mock import patch
    from regs.wdfw_pamphlet import RegStatus
    from datetime import datetime

    storage = FileStorage(root=tmp_path)
    today = date(2026, 3, 1)  # 31 days before a future closure window
    inputs = _minimal_inputs(today)

    # Pretend the first primary launch maps to a pamphlet section that closes
    # on day-offset 35 (April 5).
    from stations import primary_stations
    target_launch_key = primary_stations()[0]["key"]

    def _fake_pamphlet_status(section_id, *, today, species="salmon_hatchery_steelhead"):
        # Return CLOSED only for the target section on April 5 (offset 35);
        # OPEN otherwise. Doesn't reproduce the YAML format, just stubs the func.
        target_day = date(2026, 4, 5)
        if section_id == "test_section_id" and today == target_day:
            return RegStatus(
                authority="WDFW",
                section_key=section_id,
                open=False,
                reason="closed per pamphlet stub",
                last_checked=datetime.now(),
            )
        return RegStatus(
            authority="WDFW",
            section_key=section_id,
            open=True,
            reason="open per pamphlet stub",
            last_checked=datetime.now(),
        )

    # Inject pamphlet_section into the launch via a copy of primary_stations()
    # — but stations.py is module-level so easiest is to monkeypatch the
    # function used in the loop (primary_stations) to return a launch list
    # where target launch carries a pamphlet_section.
    real_primary = primary_stations()
    patched_stations = []
    for s in real_primary:
        if s["key"] == target_launch_key:
            patched_stations.append({**s, "pamphlet_section": "test_section_id"})
        else:
            patched_stations.append(s)

    with patch("fishing_report.primary_stations", return_value=patched_stations), \
         patch("fishing_report.STATIONS", patched_stations), \
         patch("fishing_report.pamphlet_status_for_section", side_effect=_fake_pamphlet_status), \
         patch("regs.pamphlet_status_for_section", side_effect=_fake_pamphlet_status):
        out = build_report_data(inputs, storage=storage)

    fkey = next(k for k in out["forecasts"] if k.endswith(f"::{target_launch_key}"))
    days = out["forecasts"][fkey]
    # Day 0 (today) uses resolve_for_day which finds nothing in emergency_projections
    # and calls pamphlet_status_for_section → stub returns OPEN for today.
    assert days[0]["open"] is True
    # Day 35 (April 5) should show closed via the pamphlet stub
    assert days[35]["date"] == "2026-04-05"
    assert days[35]["open"] is False, "future-day pamphlet closure not reflected"
    # Day 30 (March 31) — pamphlet says open → open
    assert days[30]["open"] is True
    # Day 35 score should be 0 because closed
    assert days[35]["score"] == 0.0


def test_build_report_data_includes_top_picks_by_date(tmp_path):
    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 10)
    out = build_report_data(_minimal_inputs(today), storage=storage)
    assert "top_picks_by_date" in out
    # Should have an entry for today and for today+365
    assert today.isoformat() in out["top_picks_by_date"]
    far_off = (date.fromordinal(today.toordinal() + 365)).isoformat()
    assert far_off in out["top_picks_by_date"]
    # Each date entry is keyed by species
    assert "chinook" in out["top_picks_by_date"][today.isoformat()]


def test_build_report_data_includes_season_heatmap(tmp_path):
    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 10)
    out = build_report_data(_minimal_inputs(today), storage=storage)
    assert "season_heatmap" in out
    assert "chinook" in out["season_heatmap"]
    # Heatmap has up to 366 entries per species
    assert 1 <= len(out["season_heatmap"]["chinook"]) <= 366


def test_build_report_data_includes_pamphlet_expires(tmp_path):
    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 10)
    out = build_report_data(_minimal_inputs(today), storage=storage)
    # Echoed at top level (may be None if YAML metadata absent in test env)
    assert "pamphlet_expires" in out


def test_build_report_data_emergency_projection_opens_future_day(tmp_path, monkeypatch):
    """An emergency Projection with status=open on a future day flips that day
    from default-CLOSED (pamphlet) to OPEN in the forecast."""
    from datetime import date
    from regs.emergency_types import Projection

    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 14)
    inputs = _minimal_inputs(today)
    # Pretend the first primary launch maps to a pamphlet section that is
    # default-CLOSED, with an emergency Projection opening day +6.
    from stations import primary_stations
    target_launch_key = primary_stations()[0]["key"]

    def _stub_pamphlet_status(section_id, *, today, species="salmon_hatchery_steelhead"):
        """Pretend the section is default-CLOSED for every day."""
        from datetime import datetime
        from regs.wdfw_pamphlet import RegStatus
        if section_id != "test_section_id":
            return None
        return RegStatus(authority="WDFW", section_key=section_id, open=False,
                         reason="default-closed", last_checked=datetime.now())

    real_primary = primary_stations()
    patched_stations = []
    for s in real_primary:
        if s["key"] == target_launch_key:
            patched_stations.append({**s, "pamphlet_section": "test_section_id"})
        else:
            patched_stations.append(s)

    # Populate inputs["emergency_regs"] with the Projection fixture so that
    # build_report_data (which reads emergency_projections from inputs) sees it.
    open_day = today.replace(day=20)  # offset 6
    em_projections = {"test_section_id": [Projection(
        section_id="test_section_id", status="open",
        effective_from=open_day, effective_to=open_day,
        reason="test opener", authority="WDFW",
    )]}
    inputs["emergency_regs"] = em_projections

    from unittest.mock import patch
    with patch("fishing_report.primary_stations", return_value=patched_stations), \
         patch("fishing_report.STATIONS", patched_stations), \
         patch("fishing_report.pamphlet_status_for_section", side_effect=_stub_pamphlet_status), \
         patch("regs.pamphlet_status_for_section", side_effect=_stub_pamphlet_status):
        out = build_report_data(inputs, storage=storage)

    fkey = next(k for k in out["forecasts"] if k.endswith(f"::{target_launch_key}"))
    days = out["forecasts"][fkey]
    # Day +5 should still be closed (pamphlet baseline).
    assert days[5]["open"] is False, "day before opener should be closed"
    # Day +6 (the open Projection date) should be open.
    assert days[6]["date"] == open_day.isoformat()
    assert days[6]["open"] is True, "emergency-opened day should be open"
    # Day +7 should be closed again (back to pamphlet baseline).
    assert days[7]["open"] is False, "day after opener should be closed"
