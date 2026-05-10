import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from sources.climatology_cache import get_or_refresh
from storage import FileStorage


def _launch_stub(key="mcnary_tailrace", lat=46.6483, lon=-119.8833):
    return {"key": key, "lat": lat, "lon": lon}


def test_get_or_refresh_calls_fetch_when_cache_missing(tmp_path):
    storage = FileStorage(root=tmp_path)
    sample = {"01-01": {"high_f": 41.0, "low_f": 28.0}}
    with patch("sources.climatology_cache.fetch_climatology", return_value=sample) as f:
        out = get_or_refresh(_launch_stub(), storage=storage)
    assert out == sample
    f.assert_called_once_with(46.6483, -119.8833, years=10)
    # Cache file is on disk under climatology-cache/<key>.json
    p = tmp_path / "climatology-cache" / "mcnary_tailrace.json"
    assert p.exists()
    blob = json.loads(p.read_text())
    assert blob["daily"] == sample
    assert blob["lat"] == 46.6483
    assert "fetched_at" in blob


def test_get_or_refresh_uses_cache_when_fresh(tmp_path):
    storage = FileStorage(root=tmp_path)
    p = tmp_path / "climatology-cache"
    p.mkdir()
    (p / "mcnary_tailrace.json").write_text(json.dumps({
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "open-meteo-archive-v1",
        "lat": 46.6483, "lon": -119.8833,
        "years": [2016, 2025],
        "daily": {"02-15": {"high_f": 50.0, "low_f": 30.0}},
    }))
    with patch("sources.climatology_cache.fetch_climatology") as f:
        out = get_or_refresh(_launch_stub(), storage=storage)
    f.assert_not_called()
    assert out == {"02-15": {"high_f": 50.0, "low_f": 30.0}}


def test_get_or_refresh_refreshes_when_stale(tmp_path):
    storage = FileStorage(root=tmp_path)
    p = tmp_path / "climatology-cache"
    p.mkdir()
    stale = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    (p / "mcnary_tailrace.json").write_text(json.dumps({
        "fetched_at": stale,
        "source": "open-meteo-archive-v1",
        "lat": 46.6483, "lon": -119.8833,
        "years": [2014, 2023],
        "daily": {"02-15": {"high_f": 40.0, "low_f": 20.0}},
    }))
    fresh = {"02-15": {"high_f": 55.0, "low_f": 33.0}}
    with patch("sources.climatology_cache.fetch_climatology", return_value=fresh) as f:
        out = get_or_refresh(_launch_stub(), storage=storage)
    f.assert_called_once()
    assert out == fresh


def test_get_or_refresh_falls_back_to_stale_cache_on_fetch_failure(tmp_path):
    storage = FileStorage(root=tmp_path)
    p = tmp_path / "climatology-cache"
    p.mkdir()
    stale = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    last_good = {"02-15": {"high_f": 40.0, "low_f": 20.0}}
    (p / "mcnary_tailrace.json").write_text(json.dumps({
        "fetched_at": stale,
        "source": "open-meteo-archive-v1",
        "lat": 46.6483, "lon": -119.8833,
        "years": [2014, 2023],
        "daily": last_good,
    }))
    with patch("sources.climatology_cache.fetch_climatology", side_effect=RuntimeError("net fail")):
        out = get_or_refresh(_launch_stub(), storage=storage)
    # Returns last-good rather than raising
    assert out == last_good


def test_get_or_refresh_returns_none_when_no_cache_and_fetch_fails(tmp_path):
    storage = FileStorage(root=tmp_path)
    with patch("sources.climatology_cache.fetch_climatology", side_effect=RuntimeError("net fail")):
        out = get_or_refresh(_launch_stub(), storage=storage)
    assert out is None
