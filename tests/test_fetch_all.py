from datetime import date, datetime, timezone
from unittest.mock import patch

from fishing_report import fetch_all, build_report_data
from storage import FileStorage
from sources.fpc_flow import FlowRecord
from sources.fpc_counts import CountRecord
from sources.dart import RuntimingCurve
from sources.usgs import GaugeReading
from sources.nws import HourlyForecast
from sources.creel import CreelEntry
from regs.wdfw import RegStatus


def _flat_curve(dam, species):
    return RuntimingCurve(dam_key=dam, species=species,
                          daily_avg={i: 100.0 for i in range(1, 367)})


def _make_inputs(today=date(2026, 4, 27)):
    return {
        "today": today,
        "flows": [FlowRecord("BON", today, 200.0), FlowRecord("PRD", today, 130.0),
                  FlowRecord("MCN", today, 180.0), FlowRecord("LGR", today, 40.0)],
        "counts": [CountRecord("BON", "spring_chinook", today, 5000)],
        "curves": {("BON", "spring_chinook"): _flat_curve("BON", "spring_chinook"),
                   ("PRD", "spring_chinook"): _flat_curve("PRD", "spring_chinook"),
                   ("MCN", "spring_chinook"): _flat_curve("MCN", "spring_chinook"),
                   ("LGR", "spring_chinook"): _flat_curve("LGR", "spring_chinook")},
        "usgs_by_site": {"12472800": [
            GaugeReading("12472800", "flow_cfs", datetime(2026, 4, 27, 12, tzinfo=timezone.utc), 130000),
            GaugeReading("12472800", "water_temp_f", datetime(2026, 4, 27, 12, tzinfo=timezone.utc), 52.0),
        ]},
        "nws_by_launch": {"vernita": [
            HourlyForecast(start_time=datetime(2026, 4, 27, 6, tzinfo=timezone.utc),
                           end_time=datetime(2026, 4, 27, 7, tzinfo=timezone.utc),
                           air_temp_f=48.0, wind_mph=8.0, wind_dir="W", sky_pct=10, short="Sunny"),
        ]},
        "usgs_by_launch": {"vernita": [
            GaugeReading("12472800", "flow_cfs", datetime(2026, 4, 27, 12, tzinfo=timezone.utc), 130000),
            GaugeReading("12472800", "water_temp_f", datetime(2026, 4, 27, 12, tzinfo=timezone.utc), 52.0),
        ]},
        "creel": [
            CreelEntry("WDFW", "wdfw_hanford", "spring_chinook", date(2026, 4, 20), 0.4, "")
        ],
        "regs": {"WDFW_HANFORD_REACH": RegStatus(
            authority="WDFW", section_key="WDFW_HANFORD_REACH", open=True,
            reason="Open through May 31", last_checked=datetime.now(),
        )},
    }


def test_build_report_data_returns_serializable_structure(tmp_path):
    storage = FileStorage(root=tmp_path)
    inputs = _make_inputs()
    data = build_report_data(inputs, storage=storage)
    # Required top-level keys
    for k in ("forecasts", "runtiming", "regs", "creel", "launches", "generated_at"):
        assert k in data
    # Forecasts is keyed by (species, launch_key) and contains 7 days of entries.
    assert isinstance(data["forecasts"], dict)
    sample_key = next(iter(data["forecasts"]))
    assert isinstance(sample_key, str)  # JSON-serializable key
    days = data["forecasts"][sample_key]
    assert len(days) == 7
    for d in days:
        assert "score" in d and "verdict" in d and "techniques" in d


def test_build_report_data_skips_closed_sections(tmp_path):
    storage = FileStorage(root=tmp_path)
    inputs = _make_inputs()
    inputs["regs"]["WDFW_HANFORD_REACH"] = RegStatus(
        authority="WDFW", section_key="WDFW_HANFORD_REACH", open=False,
        reason="Closed for emergency", last_checked=datetime.now(),
    )
    data = build_report_data(inputs, storage=storage)
    # Hanford launches should still appear, but their entries should have score=0.
    hanford_keys = [k for k in data["forecasts"] if "vernita" in k or "ringold" in k]
    assert hanford_keys
    for k in hanford_keys:
        for d in data["forecasts"][k]:
            assert d["score"] == 0.0


def test_build_report_data_persists_to_storage(tmp_path):
    storage = FileStorage(root=tmp_path)
    data = build_report_data(_make_inputs(), storage=storage)
    cached = storage.read_json("report_data")
    assert cached is not None
    assert cached["generated_at"] == data["generated_at"]


def test_no_run_data_flag_when_ref_state_missing(tmp_path):
    """Launches whose ref_dams are not in FPC_DAMS should be flagged
    no_run_data=True on every day in their forecast.
    """
    storage = FileStorage(root=tmp_path)
    inputs = _make_inputs()
    # Drop curves entirely so every launch gets ref_state=None.
    inputs["curves"] = {}
    data = build_report_data(inputs, storage=storage)
    # Every forecast day should be marked no_run_data.
    for fkey, days in data["forecasts"].items():
        for d in days:
            assert d.get("no_run_data") is True, (
                f"{fkey} day {d['date']} missing no_run_data flag"
            )


def test_score_below_great_when_no_run_data(tmp_path):
    """Without run data, score should not bubble up to GREAT (>= 0.9)."""
    storage = FileStorage(root=tmp_path)
    inputs = _make_inputs()
    inputs["curves"] = {}
    data = build_report_data(inputs, storage=storage)
    for fkey, days in data["forecasts"].items():
        for d in days:
            if d.get("no_run_data"):
                assert d["verdict"] != "GREAT", (
                    f"{fkey} on {d['date']} has GREAT despite no run data"
                )


def test_no_run_data_false_when_curve_present(tmp_path):
    """When ref_state is built (curve present + counts), no_run_data is False."""
    storage = FileStorage(root=tmp_path)
    # Add the species curves the test launches actually want.
    inputs = _make_inputs()
    extra_species = ["fall_chinook", "summer_chinook", "sockeye", "summer_steelhead"]
    for sp in extra_species:
        for dam in ("BON", "PRD", "MCN", "LGR"):
            inputs["curves"][(dam, sp)] = _flat_curve(dam, sp)
    data = build_report_data(inputs, storage=storage)
    # Vernita has ref_dams=[PRD, MCN] and species [fall_chinook, summer_chinook,
    # sockeye, summer_steelhead], so any of these forecast keys should be
    # populated with run data.
    key = "fall_chinook::vernita"
    assert key in data["forecasts"]
    for d in data["forecasts"][key]:
        assert d.get("no_run_data") is False
