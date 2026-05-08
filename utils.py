"""Common utilities: HTTP fetch with retry, Meeus sun_times, linear least-squares fit.

Ported from pikeminnow with light cleanup. Use these instead of re-implementing.
"""
from __future__ import annotations

import math
import time
from datetime import date, datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

import requests

USER_AGENT = "salmon-report/1.0 (https://salmon.pnwbite.com — alan@local)"
DEFAULT_TIMEOUT = 20


class FetchError(RuntimeError):
    """Raised when fetch fails permanently after retries."""


def fetch(url: str, *, retries: int = 3, backoff: float = 1.0, timeout: int = DEFAULT_TIMEOUT, headers: dict | None = None) -> str:
    """HTTP GET with linear backoff. 4xx errors raise immediately; 5xx + network errors retry."""
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=h, timeout=timeout)
            if 400 <= r.status_code < 500:
                raise FetchError(f"GET {url} -> {r.status_code}")
            if r.status_code >= 500:
                last_err = FetchError(f"GET {url} -> {r.status_code}")
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
                    continue
                raise last_err
            return r.text
        except FetchError:
            raise
        except requests.RequestException as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
                continue
            raise FetchError(f"GET {url} failed: {e}") from e
    assert last_err is not None
    raise FetchError(str(last_err))


def sun_times(lat: float, lon: float, day: date, *, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Approximate sunrise and sunset using Meeus' simplified algorithm.

    Returns timezone-aware datetimes in the provided tz.
    """
    n = day.toordinal() - date(day.year, 1, 1).toordinal() + 1
    j_star = n - lon / 360.0
    M = (357.5291 + 0.98560028 * j_star) % 360
    C = (1.9148 * math.sin(math.radians(M))
         + 0.0200 * math.sin(math.radians(2 * M))
         + 0.0003 * math.sin(math.radians(3 * M)))
    lam = (M + C + 180 + 102.9372) % 360
    j_transit = 2451545.0 + j_star + 0.0053 * math.sin(math.radians(M)) - 0.0069 * math.sin(math.radians(2 * lam))
    decl = math.degrees(math.asin(math.sin(math.radians(lam)) * math.sin(math.radians(23.44))))
    cos_h = ((math.sin(math.radians(-0.83)) - math.sin(math.radians(lat)) * math.sin(math.radians(decl))) /
             (math.cos(math.radians(lat)) * math.cos(math.radians(decl))))
    cos_h = max(-1.0, min(1.0, cos_h))
    H = math.degrees(math.acos(cos_h))
    j_set = j_transit + H / 360.0
    j_rise = j_transit - H / 360.0

    def jd_to_dt(jd: float) -> datetime:
        secs = (jd - 2440587.5) * 86400.0
        return datetime.fromtimestamp(secs, tz=tz)

    return jd_to_dt(j_rise), jd_to_dt(j_set)


def linear_fit(xs: Iterable[float], ys: Iterable[float]) -> tuple[float, float]:
    """Ordinary least-squares fit. Returns (slope, intercept)."""
    xs = list(xs)
    ys = list(ys)
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return 0.0, mean_y
    slope = num / den
    intercept = mean_y - slope * mean_x
    return slope, intercept


def extrapolate_at(fit: tuple[float, float], x: float) -> float:
    slope, intercept = fit
    return slope * x + intercept


def hours_between(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 3600.0
