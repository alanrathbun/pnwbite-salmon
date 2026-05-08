"""Run-timing engine.

Inputs: live FPC counts (from sources.fpc_counts) + DART 10-yr curves (from sources.dart).
Outputs: per-(species, dam) RuntimingState containing pace_ratio, peak estimates,
and a forecast function for arbitrary days.

Travel lags are point estimates for chinook upstream movement; finer per-species
modeling is out of scope for v1.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sources.fpc_counts import CountRecord
from sources.dart import RuntimingCurve


_TRAVEL_LAGS: dict[tuple[str, str], int] = {
    # Lower Columbia (mainstem mouth → forks)
    ("BON", "TDA"): 1,
    ("TDA", "JDA"): 1,
    ("JDA", "MCN"): 2,
    ("BON", "MCN"): 4,
    # Mid/Upper Columbia
    ("MCN", "PRD"): 2,
    ("PRD", "WEL"): 4,
    ("WEL", "RRH"): 2,
    ("RRH", "RIS"): 2,
    # Snake (downstream → upstream)
    ("MCN", "IHR"): 1,
    ("IHR", "LMN"): 1,
    ("LMN", "LGR"): 3,
    ("MCN", "LGR"): 5,
    ("LGR", "LGR"): 0,
}
# Add same-dam zero-lag entries for every dam mentioned
for (a, b) in list(_TRAVEL_LAGS.keys()):
    _TRAVEL_LAGS.setdefault((a, a), 0)
    _TRAVEL_LAGS.setdefault((b, b), 0)


@dataclass(frozen=True)
class RuntimingState:
    species: str
    dam_key: str
    today: date
    cumulative_count_to_date: float
    cumulative_10yr_avg_to_date: float
    pace_ratio: float
    peak_date_10yr: date | None
    peak_date_estimated: date | None
    front_of_run_at: str | None  # populated by front_of_run() at the report level


def cumulative_through(counts: list[CountRecord], dam: str, species: str, today: date) -> float:
    return sum(r.count for r in counts
               if r.dam_key == dam and r.species == species
               and r.date <= today and r.date.year == today.year)


def cumulative_curve_through(curve: RuntimingCurve, today: date) -> float:
    last_doy = today.timetuple().tm_yday
    return sum(v for doy, v in curve.daily_avg.items() if doy <= last_doy)


def pace_ratio(*, observed: float, expected: float) -> float:
    if expected <= 0:
        return 1.0
    raw = observed / expected
    return max(0.3, min(1.5, raw))


def peak_doy(curve: RuntimingCurve) -> int | None:
    if not curve.daily_avg:
        return None
    return max(curve.daily_avg, key=lambda k: curve.daily_avg[k])


def runtiming_for_dam(
    dam_key: str,
    species: str,
    counts: list[CountRecord],
    curve: RuntimingCurve,
    *,
    today: date,
) -> RuntimingState:
    obs = cumulative_through(counts, dam_key, species, today)
    exp = cumulative_curve_through(curve, today)
    pr = pace_ratio(observed=obs, expected=exp)
    peak_d = peak_doy(curve)
    if peak_d is None:
        peak_10yr: date | None = None
        peak_est: date | None = None
    else:
        peak_10yr = date(today.year, 1, 1) + timedelta(days=peak_d - 1)
        # Faster pace → earlier estimate; slower → later. Cap at ±10 days.
        offset = int(round((1.0 - pr) * 10))
        offset = max(-10, min(10, offset))
        peak_est = peak_10yr + timedelta(days=offset)
    return RuntimingState(
        species=species,
        dam_key=dam_key,
        today=today,
        cumulative_count_to_date=obs,
        cumulative_10yr_avg_to_date=exp,
        pace_ratio=pr,
        peak_date_10yr=peak_10yr,
        peak_date_estimated=peak_est,
        front_of_run_at=None,
    )


def forecast_for_day(
    state: RuntimingState,
    target_day: date,
    *,
    travel_lag_to_target: int = 0,
    curve_daily_avg: dict[int, float] | None = None,
) -> float:
    """Project the species' arrival count at the target dam for `target_day`.

    Approach: shift target_day backward by travel_lag (so we're using the upstream
    dam's curve at "now") and scale by pace_ratio.
    """
    if curve_daily_avg is None:
        # Fallback: assume flat curve at the cumulative-avg-per-day rate
        if state.cumulative_10yr_avg_to_date > 0:
            doy = state.today.timetuple().tm_yday
            avg = state.cumulative_10yr_avg_to_date / max(1, doy)
            curve_daily_avg = {i: avg for i in range(1, 367)}
        else:
            curve_daily_avg = {i: 0.0 for i in range(1, 367)}

    look_day = target_day - timedelta(days=travel_lag_to_target)
    look_doy = look_day.timetuple().tm_yday
    base = curve_daily_avg.get(look_doy, 0.0)
    return base * state.pace_ratio


def front_of_run(
    species: str,
    today_counts: list[CountRecord],
    curves: dict[str, RuntimingCurve],
    *,
    today: date,
    threshold_frac: float = 0.01,
) -> str | None:
    """Return the most-upstream dam where today's count is >= threshold_frac of the 10-yr peak.

    Dam ordering (upstream-ness) for tie-breaks, lowest = most downstream:
      Columbia mainstem: BON < TDA < JDA < MCN < PRD < WEL < RRH < RIS
      Snake (after MCN): IHR < LMN < LGR
    The Snake-side dams sort after the Columbia mainstem here; ties are broken
    by ordering position so a Snake-side run-front correctly outranks a Mid-
    Columbia front when both are populated. LGR is treated as the most upstream
    overall to keep the existing front_of_run semantics.
    """
    upstream_order = [
        "BON", "TDA", "JDA", "MCN",
        "IHR", "LMN",
        "PRD", "WEL", "RRH", "RIS",
        "LGR",
    ]
    counts_by_dam: dict[str, int] = {}
    for r in today_counts:
        if r.species != species or r.date != today:
            continue
        counts_by_dam[r.dam_key] = counts_by_dam.get(r.dam_key, 0) + r.count

    qualifying: list[str] = []
    for dam in upstream_order:
        c = counts_by_dam.get(dam, 0)
        curve = curves.get(dam)
        if curve is None or not curve.daily_avg:
            continue
        peak_val = max(curve.daily_avg.values())
        if peak_val <= 0:
            continue
        if c >= peak_val * threshold_frac:
            qualifying.append(dam)
    return qualifying[-1] if qualifying else None


def travel_lag_days(from_dam: str, to_dam: str) -> int:
    return _TRAVEL_LAGS.get((from_dam, to_dam), 0)
