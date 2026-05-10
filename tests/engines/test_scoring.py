import pytest
from engines.scoring import (
    score,
    bite_window,
    creel_signal,
    temp_band_factor,
    rank_picks,
    Pick,
)


def test_score_zero_when_closed():
    s = score(open_status=0, run_status_now=1.0, run_status_forecast=1.0,
              bite_window=1.0, creel_signal=1.0)
    assert s == 0.0


def test_score_multiplies_factors():
    s = score(open_status=1, run_status_now=1.0, run_status_forecast=1.2,
              bite_window=1.1, creel_signal=1.05)
    assert s == pytest.approx(1.0 * 1.2 * 1.1 * 1.05, rel=1e-9)


def test_temp_band_factor_inside_optimal_returns_one():
    bands = (44, 46, 58, 60, 65)  # spring chinook
    assert temp_band_factor(50, *bands) == 1.0


def test_temp_band_factor_at_cold_edge():
    bands = (44, 46, 58, 60, 65)
    assert temp_band_factor(43, *bands) == pytest.approx(0.7)


def test_temp_band_factor_way_too_hot():
    bands = (44, 46, 58, 60, 65)
    assert temp_band_factor(70, *bands) == pytest.approx(0.2)


def test_creel_signal_improving_above_one():
    assert creel_signal(trend="improving", latest_per_rod=0.4) > 1.0


def test_creel_signal_no_data_neutral():
    assert creel_signal(trend="no_data", latest_per_rod=None) == 1.0


def test_bite_window_dampens_for_far_days():
    near = bite_window(temp_factor=1.0, flow_factor=1.0, wind_factor=1.0,
                      light_factor=1.0, day_offset=1)
    far = bite_window(temp_factor=1.0, flow_factor=1.0, wind_factor=1.0,
                     light_factor=1.0, day_offset=6)
    assert far < near


def test_rank_picks_dedupes_to_max_two_per_launch():
    candidates = [
        Pick(launch="vernita", day_offset=0, score=0.95, technique="A"),
        Pick(launch="vernita", day_offset=1, score=0.92, technique="A"),
        Pick(launch="vernita", day_offset=2, score=0.90, technique="A"),  # 3rd at vernita — drop
        Pick(launch="ringold", day_offset=0, score=0.85, technique="B"),
        Pick(launch="heller_bar", day_offset=0, score=0.80, technique="C"),
    ]
    top = rank_picks(candidates, k=3, max_per_launch=2)
    launches = [p.launch for p in top]
    assert launches.count("vernita") == 2
    assert "ringold" in launches
    assert len(top) == 3


def test_score_long_range_multiplies_open_and_run_forecast():
    from engines.scoring import score_long_range
    assert score_long_range(open_status=1.0, run_status_forecast=0.8) == 0.8
    assert score_long_range(open_status=0.0, run_status_forecast=0.9) == 0.0
    assert score_long_range(open_status=1.0, run_status_forecast=0.0) == 0.0


def test_score_long_range_clamps_to_unit_interval():
    from engines.scoring import score_long_range
    # Inputs above 1.0 (e.g. pace_ratio = 1.4) should clamp to 1.0
    assert score_long_range(open_status=1.0, run_status_forecast=1.4) == 1.0
    # Negative inputs (shouldn't happen but be defensive) clamp to 0
    assert score_long_range(open_status=1.0, run_status_forecast=-0.5) == 0.0
