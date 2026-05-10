"""Open-Meteo Archive API client.

Fetches daily high/low air temperature for a lat/lon over a multi-year span and
returns a calendar-day climatology averaged across years.

Source: https://open-meteo.com/en/docs/historical-weather-api
No API key required. Free for non-commercial use; we comply by setting a
descriptive User-Agent on the underlying ``utils.fetch`` call.

The returned dict is keyed by ``"MM-DD"`` (zero-padded) and maps to
``{"high_f": float, "low_f": float}``. Leap day (``02-29``) is included only
when at least one year in the span was a leap year.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from utils import fetch

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_climatology(lat: float, lon: float, *, years: int = 10) -> dict[str, dict[str, float]]:
    """Return an mm-dd → {high_f, low_f} dict averaged across the last *years* full years.

    Includes the most recently completed calendar year and goes *years* years back.
    Example: called in 2026 with years=10 → covers 2016-01-01 through 2025-12-31.
    """
    today = date.today()
    end_year = today.year - 1
    start_year = end_year - years + 1
    url = (
        f"{ARCHIVE_URL}"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_year}-01-01&end_date={end_year}-12-31"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&temperature_unit=fahrenheit"
        f"&timezone=America%2FLos_Angeles"
    )
    raw = fetch(url, headers={"Accept": "application/json"})
    doc: dict[str, Any] = json.loads(raw)
    return _average_by_mmdd(doc)


def _average_by_mmdd(doc: dict[str, Any]) -> dict[str, dict[str, float]]:
    daily = doc.get("daily") or {}
    times: list[str] = daily.get("time") or []
    highs: list[float | None] = daily.get("temperature_2m_max") or []
    lows: list[float | None] = daily.get("temperature_2m_min") or []
    if not times:
        return {}
    bucket: dict[str, dict[str, list[float]]] = {}
    for t, hi, lo in zip(times, highs, lows):
        if hi is None or lo is None:
            continue
        mmdd = t[5:10]  # "YYYY-MM-DD" → "MM-DD"
        b = bucket.setdefault(mmdd, {"high": [], "low": []})
        b["high"].append(float(hi))
        b["low"].append(float(lo))
    return {
        mmdd: {
            "high_f": sum(b["high"]) / len(b["high"]),
            "low_f": sum(b["low"]) / len(b["low"]),
        }
        for mmdd, b in bucket.items()
    }
