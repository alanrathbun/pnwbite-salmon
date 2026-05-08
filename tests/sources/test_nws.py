import json
from pathlib import Path
import pytest
import requests_mock

from sources.nws import (
    resolve_grid,
    parse_hourly_forecast,
    HourlyForecast,
    fetch_hourly_for_point,
)
from storage import FileStorage


FIX = Path(__file__).parent.parent / "fixtures/nws"


def test_resolve_grid_caches_result(tmp_path):
    storage = FileStorage(root=tmp_path)
    points = json.loads((FIX / "points.json").read_text())
    with requests_mock.Mocker() as m:
        m.get("https://api.weather.gov/points/46.6483,-119.8833", json=points)
        grid_url = resolve_grid(46.6483, -119.8833, storage=storage)
        assert grid_url.startswith("https://api.weather.gov/")
    # second call should NOT hit the network — cache is populated
    cached = storage.read_json("nws_grid")
    assert cached is not None
    assert "46.6483,-119.8833" in cached


def test_parse_hourly_forecast_returns_periods():
    doc = json.loads((FIX / "forecast_hourly.json").read_text())
    periods = parse_hourly_forecast(doc)
    assert len(periods) >= 24, "expected at least 24 hourly periods"
    p = periods[0]
    assert isinstance(p, HourlyForecast)
    assert p.air_temp_f is not None
    assert p.wind_mph is not None
    assert p.start_time.tzinfo is not None
