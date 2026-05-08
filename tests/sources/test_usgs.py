import json
from datetime import datetime
from pathlib import Path
from sources.usgs import parse_iv_response, GaugeReading, get_latest

FIXTURE = json.loads((Path(__file__).parent.parent / "fixtures/usgs/sample.json").read_text())


def test_parses_flow_readings():
    readings = parse_iv_response(FIXTURE)
    flow = [r for r in readings if r.parameter == "flow_cfs"]
    assert flow, "expected at least one flow reading"
    r = flow[0]
    assert isinstance(r.dt, datetime) and r.dt.tzinfo is not None
    assert r.value > 0


def test_temp_converted_to_fahrenheit():
    readings = parse_iv_response(FIXTURE)
    temp = [r for r in readings if r.parameter == "water_temp_f"]
    if temp:  # not all sites report temp
        # Plausible water temp range: 28°F to 80°F (the parser must convert C → F).
        for r in temp:
            assert 28.0 <= r.value <= 80.0, f"implausible water temp: {r.value}"


def test_get_latest_picks_most_recent():
    readings = parse_iv_response(FIXTURE)
    latest_flow = get_latest(readings, "flow_cfs")
    if latest_flow is not None:
        assert all(r.dt <= latest_flow.dt for r in readings if r.parameter == "flow_cfs")
