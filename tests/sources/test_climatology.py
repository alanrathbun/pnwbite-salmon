import json
from datetime import date
from pathlib import Path

import requests_mock
from freezegun import freeze_time

from sources.climatology import fetch_climatology

FIX = Path(__file__).parent.parent / "fixtures/climatology"


@freeze_time("2026-05-10")
def test_fetch_climatology_averages_daily_high_low_by_mmdd():
    with requests_mock.Mocker() as m:
        m.get(
            "https://archive-api.open-meteo.com/v1/archive",
            text=(FIX / "openmeteo_archive.json").read_text(),
        )
        normals = fetch_climatology(46.6483, -119.8833, years=10)
    # Should have 366 keys (leap year included since the 10-year span covers 2020 + 2024)
    assert len(normals) == 366
    assert "01-01" in normals
    assert "07-15" in normals
    assert "12-31" in normals
    # Each entry has high_f and low_f as floats
    entry = normals["07-15"]
    assert isinstance(entry["high_f"], float)
    assert isinstance(entry["low_f"], float)
    # Sanity: July 15 high should be warmer than January 1 high in PNW
    assert normals["07-15"]["high_f"] > normals["01-01"]["high_f"]


def test_fetch_climatology_handles_missing_leap_day_in_short_span():
    """If a span doesn't include a leap year, 02-29 may be absent."""
    # Build a synthetic 1-year response without a leap day
    body = {
        "daily": {
            "time": ["2023-01-01", "2023-07-15", "2023-12-31"],
            "temperature_2m_max": [40.0, 90.0, 40.0],
            "temperature_2m_min": [25.0, 60.0, 25.0],
        }
    }
    with requests_mock.Mocker() as m:
        m.get("https://archive-api.open-meteo.com/v1/archive", json=body)
        normals = fetch_climatology(0.0, 0.0, years=1)
    assert "01-01" in normals
    assert "02-29" not in normals
    # Averaging a single year just returns that year's value
    assert normals["07-15"]["high_f"] == 90.0
    assert normals["07-15"]["low_f"] == 60.0


def test_fetch_climatology_averages_across_years():
    """Two years of January 1 data should average correctly."""
    body = {
        "daily": {
            "time": ["2023-01-01", "2024-01-01"],
            "temperature_2m_max": [40.0, 50.0],
            "temperature_2m_min": [20.0, 30.0],
        }
    }
    with requests_mock.Mocker() as m:
        m.get("https://archive-api.open-meteo.com/v1/archive", json=body)
        normals = fetch_climatology(0.0, 0.0, years=2)
    assert normals["01-01"]["high_f"] == 45.0
    assert normals["01-01"]["low_f"] == 25.0


def test_fetch_climatology_returns_empty_dict_when_no_daily_data():
    """Defensive parse: missing or empty `daily` returns {} rather than raising."""
    with requests_mock.Mocker() as m:
        m.get("https://archive-api.open-meteo.com/v1/archive", json={})
        assert fetch_climatology(0.0, 0.0, years=1) == {}
    with requests_mock.Mocker() as m:
        m.get("https://archive-api.open-meteo.com/v1/archive", json={"daily": {}})
        assert fetch_climatology(0.0, 0.0, years=1) == {}
