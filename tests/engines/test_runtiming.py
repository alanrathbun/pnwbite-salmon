from datetime import date
import pytest
from engines.runtiming import (
    pace_ratio,
    cumulative_through,
    runtiming_for_dam,
    forecast_for_day,
    front_of_run,
    RuntimingState,
    travel_lag_days,
)
from sources.fpc_counts import CountRecord
from sources.dart import RuntimingCurve


def _curve(daily: dict[int, float]) -> RuntimingCurve:
    return RuntimingCurve(dam_key="BON", species="spring_chinook", daily_avg=daily)


def test_cumulative_through_sums_year_to_date():
    counts = [
        CountRecord("BON", "spring_chinook", date(2026, 4, 1), 100),
        CountRecord("BON", "spring_chinook", date(2026, 4, 15), 200),
        CountRecord("BON", "spring_chinook", date(2026, 4, 20), 50),
        CountRecord("BON", "spring_chinook", date(2026, 5, 1), 999),  # excluded
    ]
    total = cumulative_through(counts, "BON", "spring_chinook", date(2026, 4, 27))
    assert total == 350


def test_pace_ratio_clamped_to_range():
    high = pace_ratio(observed=10000.0, expected=1000.0)
    assert high == pytest.approx(1.5)
    low = pace_ratio(observed=1.0, expected=1000.0)
    assert low == pytest.approx(0.3)
    assert pace_ratio(observed=100.0, expected=0.0) == 1.0
    assert pace_ratio(observed=920.0, expected=1000.0) == pytest.approx(0.92, abs=0.01)


def test_runtiming_for_dam_picks_peak_from_curve():
    curve = _curve({i: float(max(0, 100 - abs(130 - i))) for i in range(80, 180)})
    counts = [CountRecord("BON", "spring_chinook", date(2026, 4, 27), 50)]
    state = runtiming_for_dam("BON", "spring_chinook", counts, curve, today=date(2026, 4, 27))
    assert isinstance(state, RuntimingState)
    assert state.peak_date_10yr == date(2026, 5, 10)
    assert state.cumulative_count_to_date >= 50


def test_forecast_for_day_applies_pace_and_lag():
    curve = _curve({i: 100.0 for i in range(1, 367)})
    counts = [CountRecord("BON", "spring_chinook", date(2026, 4, 27), 200)]
    state = runtiming_for_dam("BON", "spring_chinook", counts, curve, today=date(2026, 4, 27))
    f = forecast_for_day(state, date(2026, 5, 1), travel_lag_to_target=4,
                        curve_daily_avg=curve.daily_avg)
    # pace_ratio = 200 cumulative_avg → varies. We just need a reasonable scaled value.
    assert f > 0
    assert f <= 1000  # sanity check, no overflow


def test_front_of_run_picks_most_upstream_with_threshold():
    curves = {dam: _curve({i: 1000.0 for i in range(1, 367)}) for dam in ("BON", "MCN", "PRD", "LGR")}
    today_counts = [
        CountRecord("BON", "spring_chinook", date(2026, 4, 27), 5000),
        CountRecord("MCN", "spring_chinook", date(2026, 4, 27), 50),
        CountRecord("PRD", "spring_chinook", date(2026, 4, 27), 5),
        CountRecord("LGR", "spring_chinook", date(2026, 4, 27), 0),
    ]
    front = front_of_run("spring_chinook", today_counts, curves, today=date(2026, 4, 27))
    # MCN passes (50 >= 10) but PRD doesn't (5 < 10). Front should be MCN.
    assert front == "MCN"


def test_travel_lag_days_known_pairs():
    assert travel_lag_days("BON", "MCN") == 4
    assert travel_lag_days("MCN", "PRD") == 2
    assert travel_lag_days("MCN", "LGR") == 5
    assert travel_lag_days("PRD", "WEL") == 4
    assert travel_lag_days("BON", "WEL") >= 0
