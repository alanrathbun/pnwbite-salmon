"""End-to-end smoke test using offline fixtures.

Runs build_report_data + render_html against synthetic but realistic inputs
and verifies the resulting HTML contains expected anchors.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path

from storage import FileStorage
from fishing_report import build_report_data
from render import render_html
from sources.fpc_flow import FlowRecord
from sources.fpc_counts import CountRecord
from sources.dart import RuntimingCurve
from sources.usgs import GaugeReading
from sources.nws import HourlyForecast
from sources.creel import CreelEntry
from regs.wdfw import RegStatus


def _full_inputs(today=date(2026, 4, 27)):
    flat_curve = lambda dam, sp: RuntimingCurve(
        dam_key=dam, species=sp, daily_avg={i: 100.0 for i in range(1, 367)}
    )
    inputs = {
        "today": today,
        "flows": [FlowRecord("BON", today, 200.0)],
        "counts": [CountRecord("BON", "spring_chinook", today, 5000)],
        "curves": {(d, s): flat_curve(d, s)
                   for d in ("BON","MCN","PRD","WEL","RRH","RIS","LGR")
                   for s in ("spring_chinook","summer_chinook","sockeye","fall_chinook","coho","summer_steelhead","winter_steelhead")},
        "usgs_by_site": {},
        "usgs_by_launch": {"vernita": [
            GaugeReading("12472800", "flow_cfs", datetime(2026,4,27,12,tzinfo=timezone.utc), 130000),
            GaugeReading("12472800", "water_temp_f", datetime(2026,4,27,12,tzinfo=timezone.utc), 52.0),
        ]},
        "nws_by_launch": {"vernita": []},
        "creel": [CreelEntry("WDFW", "wdfw_hanford", "spring_chinook", date(2026,4,20), 0.4, "")],
        "regs": {},
    }
    return inputs


def test_full_pipeline_produces_valid_html(tmp_path):
    storage = FileStorage(root=tmp_path)
    data = build_report_data(_full_inputs(), storage=storage)
    html = render_html(data)
    # Smoke checks
    assert "<html" in html.lower() and "</html>" in html.lower()
    assert "Salmon" in html
    # All 7 species rendered as tabs
    for sp in ["Spring Chinook", "Summer Chinook", "Sockeye", "Fall Chinook",
              "Coho", "Summer Steelhead", "Winter Steelhead"]:
        assert sp in html
    # At least one launch's data-launch attribute
    assert 'data-launch="vernita"' in html
    # Report data cached
    assert storage.read_json("report_data") is not None


def test_full_pipeline_with_closure_zeros_score(tmp_path):
    storage = FileStorage(root=tmp_path)
    inputs = _full_inputs()
    inputs["regs"]["WDFW_HANFORD_REACH"] = RegStatus(
        authority="WDFW", section_key="WDFW_HANFORD_REACH", open=False,
        reason="closure", last_checked=datetime.now(),
    )
    data = build_report_data(inputs, storage=storage)
    # All Hanford launches' forecasts should have score=0
    for k, days in data["forecasts"].items():
        if "vernita" in k or "ringold" in k or "white_bluffs" in k:
            assert all(d["score"] == 0.0 for d in days)
