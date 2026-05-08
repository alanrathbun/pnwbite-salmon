from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
import pytest
import requests_mock
from utils import fetch, FetchError, sun_times, linear_fit, extrapolate_at, hours_between


def test_fetch_returns_text_on_200():
    with requests_mock.Mocker() as m:
        m.get("https://example.com/data", text="hello")
        assert fetch("https://example.com/data") == "hello"


def test_fetch_retries_on_5xx_then_succeeds():
    with requests_mock.Mocker() as m:
        m.get(
            "https://example.com/data",
            [{"status_code": 503}, {"status_code": 503}, {"text": "ok", "status_code": 200}],
        )
        assert fetch("https://example.com/data", retries=3, backoff=0) == "ok"


def test_fetch_raises_after_exhausted_retries():
    with requests_mock.Mocker() as m:
        m.get("https://example.com/data", status_code=503)
        with pytest.raises(FetchError):
            fetch("https://example.com/data", retries=2, backoff=0)


def test_fetch_raises_on_4xx_immediately():
    with requests_mock.Mocker() as m:
        m.get("https://example.com/data", status_code=404)
        with pytest.raises(FetchError):
            fetch("https://example.com/data", retries=3, backoff=0)


def test_sun_times_vernita_in_late_april():
    # Vernita Bridge, 2026-04-27. Sunrise/sunset shouldn't be wildly off.
    sr, ss = sun_times(46.6483, -119.8833, date(2026, 4, 27), tz=ZoneInfo("America/Los_Angeles"))
    # Sunrise should be between 5am and 7am Pacific in late April.
    assert 5 <= sr.hour <= 7, f"sunrise too far off: {sr}"
    # Sunset should be between 7pm and 9pm Pacific in late April.
    assert 19 <= ss.hour <= 21, f"sunset too far off: {ss}"
    # Both should be timezone-aware.
    assert sr.tzinfo is not None
    assert ss.tzinfo is not None


def test_linear_fit_perfect_line():
    # y = 2x + 1
    xs = [0.0, 1.0, 2.0, 3.0]
    ys = [1.0, 3.0, 5.0, 7.0]
    slope, intercept = linear_fit(xs, ys)
    assert abs(slope - 2.0) < 1e-9
    assert abs(intercept - 1.0) < 1e-9


def test_linear_fit_handles_constant():
    slope, intercept = linear_fit([0.0, 1.0, 2.0], [5.0, 5.0, 5.0])
    assert abs(slope) < 1e-9
    assert abs(intercept - 5.0) < 1e-9


def test_extrapolate_at_uses_fit():
    fit = (2.0, 1.0)  # y = 2x + 1
    assert abs(extrapolate_at(fit, 10.0) - 21.0) < 1e-9


def test_hours_between_basic():
    a = datetime(2026, 4, 27, 6, 0, tzinfo=timezone.utc)
    b = datetime(2026, 4, 27, 9, 30, tzinfo=timezone.utc)
    assert abs(hours_between(a, b) - 3.5) < 1e-9
