"""NWS gridpoint forecast.

Two-step protocol:
  1. GET https://api.weather.gov/points/{lat},{lon}  → returns a forecastHourly URL
     (and an "office/grid_x/grid_y" identity that's stable). We cache the URL by
     "{lat:.4f},{lon:.4f}" key — saves a roundtrip every cron.
  2. GET that hourly URL → returns 156 periods (~6.5 days) of hourly forecast.

We extract: air temp °F, wind speed mph, wind direction, sky cover, short forecast.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from storage import FileStorage
from utils import fetch

POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
WIND_NUM = re.compile(r"(\d+)\s*to\s*(\d+)|(\d+)")


@dataclass(frozen=True)
class HourlyForecast:
    start_time: datetime
    end_time: datetime
    air_temp_f: float
    wind_mph: float
    wind_dir: str
    sky_pct: int | None
    short: str


def _round_key(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"


def resolve_grid(lat: float, lon: float, *, storage: FileStorage) -> str:
    """Return the forecastHourly URL for this lat/lon. Forever-cached.

    Cache update is routed through ``storage.update_json`` so concurrent
    workers in fetch_all's ThreadPoolExecutor never clobber each other's
    entries. The HTTP fetch happens *outside* the lock to avoid blocking
    other threads on the network round-trip.
    """
    cache: dict[str, str] = storage.read_json("nws_grid") or {}
    key = _round_key(lat, lon)
    if key in cache:
        return cache[key]
    raw = fetch(POINTS_URL.format(lat=lat, lon=lon),
                headers={"Accept": "application/geo+json"})
    doc = json.loads(raw)
    url = doc["properties"]["forecastHourly"]
    storage.update_json("nws_grid", lambda c: {**(c or {}), key: url})
    return url


def parse_hourly_forecast(doc: dict[str, Any]) -> list[HourlyForecast]:
    out: list[HourlyForecast] = []
    for p in doc["properties"]["periods"]:
        wind_str = p.get("windSpeed", "0 mph")
        m = WIND_NUM.search(wind_str)
        if not m:
            wind_mph = 0.0
        else:
            if m.group(1) and m.group(2):
                wind_mph = (int(m.group(1)) + int(m.group(2))) / 2
            else:
                wind_mph = float(m.group(3))
        out.append(HourlyForecast(
            start_time=datetime.fromisoformat(p["startTime"]),
            end_time=datetime.fromisoformat(p["endTime"]),
            air_temp_f=float(p["temperature"]),
            wind_mph=wind_mph,
            wind_dir=p.get("windDirection", ""),
            sky_pct=p.get("probabilityOfPrecipitation", {}).get("value"),
            short=p.get("shortForecast", ""),
        ))
    return out


def fetch_hourly_for_point(lat: float, lon: float, *, storage: FileStorage) -> list[HourlyForecast]:
    url = resolve_grid(lat, lon, storage=storage)
    raw = fetch(url, headers={"Accept": "application/geo+json"})
    return parse_hourly_forecast(json.loads(raw))
