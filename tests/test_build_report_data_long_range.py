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
        for sp in ("spring_chinook", "summer_chinook", "sockeye", "fall_chinook",
                   "coho", "summer_steelhead", "winter_steelhead"):
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
