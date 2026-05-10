"""Ranking score calculator.

score = open_status × run_status_now × run_status_forecast × bite_window × creel_signal

Multiplicative; no floor by design (any factor near 0 should suppress the pick).
Top-N picker dedupes to at most `max_per_launch` entries per launch (default 2).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pick:
    launch: str
    day_offset: int   # 0 = today, 1 = tomorrow, ...
    score: float
    technique: str


def score(*, open_status: float, run_status_now: float, run_status_forecast: float,
          bite_window: float, creel_signal: float) -> float:
    return open_status * run_status_now * run_status_forecast * bite_window * creel_signal


def temp_band_factor(temp_f: float, way_cold: float, optimal_low: float,
                     optimal_high: float, hot: float, way_hot: float) -> float:
    """Piecewise:
       temp_f >= way_hot          -> 0.2
       hot     <= temp_f < way_hot -> 0.5
       optimal_low <= temp_f <= optimal_high -> 1.0
       way_cold < temp_f < optimal_low       -> 0.7
       temp_f <= way_cold                    -> 0.7  (cold edge same as cold side)
    """
    if temp_f >= way_hot:
        return 0.2
    if temp_f >= hot:
        return 0.5
    if optimal_low <= temp_f <= optimal_high:
        return 1.0
    return 0.7


def flow_factor(prev_kcfs: float, today_kcfs: float) -> float:
    if prev_kcfs <= 0:
        return 1.0
    delta = (today_kcfs - prev_kcfs) / prev_kcfs
    return 0.8 if delta > 0.15 else 1.0


def wind_factor(wind_mph: float) -> float:
    if wind_mph >= 20:
        return 0.6
    if wind_mph >= 10:
        return 0.9
    return 1.0


def light_factor(*, is_dawn_or_dusk: bool, midday_clear: bool) -> float:
    if is_dawn_or_dusk:
        return 1.1
    if midday_clear:
        return 0.9
    return 1.0


def bite_window(*, temp_factor: float, flow_factor: float, wind_factor: float,
                light_factor: float, day_offset: int) -> float:
    raw = temp_factor * flow_factor * wind_factor * light_factor
    # Forecast uncertainty decay: confidence falls ~3 % per day out
    confidence = 0.97 ** day_offset
    if day_offset >= 4:
        # Days 4-7 also nudge toward neutral: f' = 0.5 + 0.5 * f
        raw = 0.5 + 0.5 * raw
    return max(0.3, min(1.2, raw * confidence))


def creel_signal(*, trend: str, latest_per_rod: float | None) -> float:
    base = {"improving": 1.2, "steady": 1.0, "declining": 0.8, "no_data": 1.0}.get(trend, 1.0)
    if latest_per_rod is not None and latest_per_rod > 0:
        base += 0.05
    return max(0.7, min(1.3, base))


def rank_picks(candidates: list[Pick], *, k: int, max_per_launch: int = 2) -> list[Pick]:
    by_score = sorted(candidates, key=lambda p: p.score, reverse=True)
    out: list[Pick] = []
    counts: dict[str, int] = {}
    for p in by_score:
        if counts.get(p.launch, 0) >= max_per_launch:
            continue
        out.append(p)
        counts[p.launch] = counts.get(p.launch, 0) + 1
        if len(out) >= k:
            break
    return out


def score_long_range(*, open_status: float, run_status_forecast: float) -> float:
    """Simplified score for days >7 out where weather is climatology-only.

    Multiplicative blend of regs status and forecast run pace; clamped to
    [0.0, 1.0]. Closed launches stay at 0; high-pace open launches approach 1.
    """
    raw = open_status * run_status_forecast
    return max(0.0, min(1.0, raw))
