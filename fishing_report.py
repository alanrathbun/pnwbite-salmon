"""Daily entry point: orchestrates fetch_all() then render() and writes outputs.

Two top-level functions:
  * ``fetch_all`` hits every live source in parallel and returns a raw inputs dict.
  * ``build_report_data`` is a pure transformation (raw inputs -> JSON-shaped
    report_data) and writes the result to ``storage`` under the ``report_data``
    key for downstream consumers (the renderer, the regs-refresh job).

``main`` ties them together and writes ``report.html`` via the renderer added
in Task 19.  The render import is deferred so this module remains importable
for unit-testing ``build_report_data`` in isolation.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from stations import STATIONS, primary_stations
from dam_refs import all_dam_keys, FPC_DAMS
from storage import FileStorage, default_root

from sources import fpc_flow, fpc_counts, usgs, nws, dart
from sources.climatology_cache import get_or_refresh
from regs import fetch_all as regs_fetch_all, resolve as regs_resolve
from engines.runtiming import (
    RuntimingState, runtiming_for_dam, forecast_for_day, front_of_run,
    travel_lag_days,
)
from engines.bait_rules import load_rules_file, match_rule, techniques_from_rule
from engines.scoring import (
    Pick, score, bite_window, creel_signal, temp_band_factor,
    wind_factor, light_factor, rank_picks,
)

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
PROJECT_ROOT = Path(__file__).parent

ALL_SPECIES = [
    "spring_chinook", "summer_chinook", "sockeye", "fall_chinook",
    "coho", "summer_steelhead", "winter_steelhead",
]

# Per-species water temp bands: (way_cold, optimal_low, optimal_high, hot, way_hot)
TEMP_BANDS: dict[str, tuple[float, float, float, float, float]] = {
    "spring_chinook":   (44, 46, 58, 60, 65),
    "summer_chinook":   (48, 50, 62, 65, 70),
    "sockeye":          (44, 46, 55, 58, 62),
    "fall_chinook":     (50, 52, 62, 65, 68),
    "coho":             (48, 50, 60, 63, 68),
    "summer_steelhead": (44, 46, 58, 60, 65),
    "winter_steelhead": (36, 38, 48, 52, 58),
}

log = logging.getLogger("salmon_report")


# ---------------------------------------------------------------------------
# Helpers used by fetch_all
# ---------------------------------------------------------------------------


def _safe_result(fut, *, default):
    try:
        return fut.result()
    except Exception as e:  # noqa: BLE001 — we want to swallow per-source errors
        log.warning("source fetch failed: %s", e)
        return default


def _safe_fetch_odfw_creel():
    """Fetch and parse ODFW Columbia Zone HTML; isolated so the future is testable."""
    from sources.creel import parse_odfw_html
    from utils import fetch as http_fetch
    html = http_fetch("https://myodfw.com/recreation-report/fishing-report/columbia-zone")
    return parse_odfw_html(html)


# ---------------------------------------------------------------------------
# fetch_all: parallel I/O
# ---------------------------------------------------------------------------


def fetch_all(*, storage: FileStorage, today: date) -> dict:
    """Hit every live source in parallel; return a raw inputs dict.

    Per-source failures degrade silently to their default empty value via
    ``_safe_result`` — the build step downstream is responsible for treating
    missing data as "no signal" rather than blowing up.
    """
    inputs: dict = {"today": today}

    with ThreadPoolExecutor(max_workers=16) as pool:
        f_flow = pool.submit(fpc_flow.fetch_flow)
        f_counts = pool.submit(fpc_counts.fetch_counts)
        f_regs = pool.submit(regs_fetch_all, today)

        # Per-launch USGS + NWS
        usgs_futs: dict[str, object] = {}
        for s in primary_stations():
            site = s.get("usgs_site")
            if site:
                usgs_futs[s["key"]] = pool.submit(usgs.fetch_for_site, site)
        nws_futs = {
            s["key"]: pool.submit(
                nws.fetch_hourly_for_point, s["lat"], s["lon"], storage=storage,
            )
            for s in primary_stations()
        }
        clim_futs = {
            s["key"]: pool.submit(get_or_refresh, s, storage=storage)
            for s in primary_stations()
        }

        # Per-(dam, species) DART curves
        dart_futs: dict[tuple[str, str], object] = {}
        for dam in all_dam_keys():
            for sp in FPC_DAMS[dam]["species_count_cols"]:
                dart_futs[(dam, sp)] = pool.submit(
                    dart.fetch_or_cached, dam, sp, storage=storage,
                )

        # Creel: ODFW only for v1 (WDFW PDF discovery is v1.5)
        f_creel_odfw = pool.submit(_safe_fetch_odfw_creel)

        inputs["flows"] = _safe_result(f_flow, default=[])
        inputs["counts"] = _safe_result(f_counts, default=[])
        regs_result = _safe_result(f_regs, default=({}, {}, {}))
        # regs_fetch_all returns a 3-tuple
        # ``(pamphlet_layer, emergency_layer, agency_meta)`` after Phase 1.5b B5.
        # Tolerate the empty default in case the future ever fails before the call.
        if isinstance(regs_result, tuple) and len(regs_result) == 3:
            (
                inputs["pamphlet_regs"],
                inputs["emergency_regs"],
                inputs["regs_agency_meta"],
            ) = regs_result
        else:
            inputs["pamphlet_regs"] = {}
            inputs["emergency_regs"] = {}
            inputs["regs_agency_meta"] = {}
        inputs["usgs_by_launch"] = {
            key: _safe_result(fut, default=[]) for key, fut in usgs_futs.items()
        }
        inputs["nws_by_launch"] = {
            key: _safe_result(fut, default=[]) for key, fut in nws_futs.items()
        }
        inputs["climatology_by_launch"] = {
            key: _safe_result(fut, default=None) for key, fut in clim_futs.items()
        }
        inputs["curves"] = {
            (dam, sp): _safe_result(
                fut,
                default=dart.RuntimingCurve(dam_key=dam, species=sp, daily_avg={}),
            )
            for (dam, sp), fut in dart_futs.items()
        }
        inputs["creel"] = _safe_result(f_creel_odfw, default=[])

    return inputs


# ---------------------------------------------------------------------------
# build_report_data: pure transformation
# ---------------------------------------------------------------------------


def _verdict(s: float) -> str:
    if s >= 0.9:
        return "GREAT"
    if s >= 0.7:
        return "GOOD"
    if s >= 0.5:
        return "FAIR"
    return "POOR"


def _flow_band(flow_cfs: float | None) -> str:
    if flow_cfs is None:
        return "normal"
    if flow_cfs < 80000:
        return "low"
    if flow_cfs > 180000:
        return "high"
    return "normal"


def _clarity_band(flow_cfs: float | None) -> str:
    if flow_cfs is not None and flow_cfs > 180000:
        return "stained"
    return "clear"


def _wind_for_day(periods, target_day: date) -> float:
    matching = [p for p in periods if p.start_time.date() == target_day]
    if not matching:
        return 5.0  # default fair
    return sum(p.wind_mph for p in matching) / len(matching)


def _serialize_launch(s: dict) -> dict:
    return {k: v for k, v in s.items()}


def _serialize_creel(c) -> dict:
    return {
        "authority": c.authority,
        "district": c.district,
        "species": c.species,
        "week_ending": c.week_ending.isoformat() if c.week_ending else None,
        "fish_per_rod": c.fish_per_rod,
    }


def _serialize_runtiming_state(state: RuntimingState) -> dict:
    return {
        "species": state.species,
        "dam_key": state.dam_key,
        "pace_ratio": state.pace_ratio,
        "cumulative_count": state.cumulative_count_to_date,
        "cumulative_avg": state.cumulative_10yr_avg_to_date,
        "peak_date_10yr": state.peak_date_10yr.isoformat() if state.peak_date_10yr else None,
        "peak_date_estimated": (
            state.peak_date_estimated.isoformat() if state.peak_date_estimated else None
        ),
    }


def _creel_for_launch(launch: dict, creel_entries: list) -> tuple[str, float | None]:
    """Return (trend, latest_per_rod) for a launch's creel district."""
    entries = [e for e in creel_entries if e.district == launch["creel_district"]]
    if not entries:
        return ("no_data", None)
    latest = max(entries, key=lambda e: e.week_ending or date(2000, 1, 1))
    prior = sorted(
        [e for e in entries if e is not latest],
        key=lambda e: e.week_ending or date(2000, 1, 1),
    )
    if not prior or latest.fish_per_rod is None or prior[-1].fish_per_rod is None:
        return ("steady", latest.fish_per_rod)
    delta = latest.fish_per_rod - prior[-1].fish_per_rod
    trend = "improving" if delta > 0.05 else ("declining" if delta < -0.05 else "steady")
    return (trend, latest.fish_per_rod)


def build_report_data(inputs: dict, *, storage: FileStorage) -> dict:
    """Pure transformation: raw source data → JSON-shaped report_data dict.

    Composes:
      * per-(species, dam) run-timing state
      * per-species front-of-run dam (where the leading edge of the run sits today)
      * per-launch 7-day forecasts: open status × run pace × forecasted run pace
        × bite window × creel signal, with bait-rule-derived techniques
      * top-3 picks per species across all open launches
    Then writes the result via ``storage.write_json("report_data", ...)``.
    """
    today: date = inputs["today"]
    counts = inputs["counts"]
    curves: dict[tuple[str, str], dart.RuntimingCurve] = inputs["curves"]
    usgs_by_launch = inputs.get("usgs_by_launch", {})
    nws_by_launch = inputs.get("nws_by_launch", {})
    creel_entries = inputs["creel"]
    # Phase 1.5b: regs is now two layers + an emergency overlay. Older callers
    # (and existing tests) may still pass a flat ``regs`` dict — treat that as
    # the emergency layer for back-compat (its semantics — a single authoritative
    # status per section_key — match the old shape).
    pamphlet_layer: dict[str, "RegStatus"] = inputs.get("pamphlet_regs", {}) or {}
    emergency_layer: dict[str, "RegStatus"] = inputs.get("emergency_regs", {}) or {}
    if not pamphlet_layer and not emergency_layer and "regs" in inputs:
        emergency_layer = inputs["regs"] or {}

    rules = load_rules_file(PROJECT_ROOT / "bait_rules.yaml")

    # Build run-timing per (species, dam). Keep both the live RuntimingState
    # objects (needed to feed forecast_for_day cleanly) and the JSON-serialized
    # dicts (what we ship to the renderer).
    runtiming_states: dict[tuple[str, str], RuntimingState] = {}
    runtiming: dict[str, object] = {}
    for sp in ALL_SPECIES:
        for dam in all_dam_keys():
            curve = curves.get((dam, sp))
            if curve is None:
                continue
            state = runtiming_for_dam(dam, sp, counts, curve, today=today)
            runtiming_states[(dam, sp)] = state
            runtiming[f"{dam}_{sp}"] = _serialize_runtiming_state(state)

        # Front of run for this species (today)
        species_curves = {
            dam: curves[(dam, sp)] for dam in all_dam_keys() if (dam, sp) in curves
        }
        front = front_of_run(
            sp, [c for c in counts if c.date == today], species_curves, today=today,
        )
        runtiming[f"front_{sp}"] = front

    # Per-launch closure resolution. Computed once per launch (status is
    # species-independent) so the renderer can read closure state directly off
    # each serialized launch without re-deriving it from the flattened
    # ``regs`` dict — that legacy lookup uses the coarse ``regs_section``
    # key and silently misses pamphlet closures keyed by ``pamphlet_section``.
    # 3-layer resolution: emergency overlay (Layer 2) wins over pamphlet
    # baseline (Layer 1); otherwise default-OPEN. Prefer the launch's
    # fine-grained pamphlet_section when set; fall back to its coarse
    # regs_section (used for ODFW/IDFG and pre-pamphlet WDFW launches).
    launch_status: dict[str, "RegStatus | None"] = {}
    for s in STATIONS:
        pamphlet_section = s.get("pamphlet_section")
        if pamphlet_section:
            launch_status[s["key"]] = regs_resolve(
                pamphlet_layer, emergency_layer, pamphlet_section, today,
            )
        else:
            legacy_section = s.get("regs_section")
            launch_status[s["key"]] = (
                regs_resolve(pamphlet_layer, emergency_layer, legacy_section, today)
                if legacy_section else None
            )

    # Per-launch forecasts: 7 days × species
    forecasts: dict[str, list[dict]] = {}
    candidates_by_species: dict[str, list[Pick]] = {sp: [] for sp in ALL_SPECIES}

    for launch in primary_stations():
        for sp in launch["species"]:
            key = f"{sp}::{launch['key']}"
            days_out: list[dict] = []

            # Pick the first ref_dam that we have a curve+state for.
            ref_dam: str | None = None
            ref_state: RuntimingState | None = None
            target_curve: dart.RuntimingCurve | None = None
            for candidate in launch.get("ref_dams", []) or []:
                st = runtiming_states.get((candidate, sp))
                cv = curves.get((candidate, sp))
                if st is not None and cv is not None:
                    ref_dam = candidate
                    ref_state = st
                    target_curve = cv
                    break

            rs = launch_status.get(launch["key"])
            if rs is not None and not rs.open:
                open_status = 0.0
            else:
                open_status = 1.0
            # No run data → treat run-timing as "unknown", not "perfect". A 1.0
            # default would let scores bubble up to GREAT for launches whose
            # ref_dam isn't in FPC_DAMS (e.g. klickitat_mouth → TDA before TDA
            # was added). 0.6 keeps them in FAIR-or-below territory and the
            # ``no_run_data`` flag below lets the renderer call it out.
            run_now = ref_state.pace_ratio if ref_state else 0.6

            usgs_readings = usgs_by_launch.get(launch["key"], [])
            sorted_readings = sorted(usgs_readings, key=lambda r: r.dt, reverse=True)
            latest_temp = next(
                (r.value for r in sorted_readings if r.parameter == "water_temp_f"),
                None,
            )
            latest_flow = next(
                (r.value for r in sorted_readings if r.parameter == "flow_cfs"),
                None,
            )

            tband = TEMP_BANDS[sp]
            tfac = temp_band_factor(latest_temp if latest_temp is not None else tband[1], *tband)

            ctrend, latest_fpr = _creel_for_launch(launch, creel_entries)
            cs = creel_signal(trend=ctrend, latest_per_rod=latest_fpr)

            # Daily-avg-per-day proxy for normalising the forecast against expected.
            cum_avg = ref_state.cumulative_10yr_avg_to_date if ref_state else 0.0
            doy_today = today.timetuple().tm_yday
            daily_avg_proxy = (cum_avg / max(1, doy_today)) if cum_avg > 0 else 1.0

            for offset in range(7):
                day = today + timedelta(days=offset)

                if ref_state and target_curve and ref_dam:
                    fc = forecast_for_day(
                        ref_state,
                        day,
                        travel_lag_to_target=travel_lag_days(ref_dam, ref_dam),
                        curve_daily_avg=target_curve.daily_avg,
                    )
                    rsf = max(0.0, min(1.5, fc / max(1.0, daily_avg_proxy)))
                else:
                    # Same fallback rationale as run_now: no run data → unknown,
                    # not perfect. Keeps cold-start scores below GREAT.
                    rsf = 0.6

                wind = _wind_for_day(nws_by_launch.get(launch["key"], []), day)
                # Daily aggregate, not a dawn-specific score — neutral light.
                # The dawn bonus belongs in an hourly view.
                bw = bite_window(
                    temp_factor=tfac,
                    flow_factor=1.0,
                    wind_factor=wind_factor(wind),
                    light_factor=light_factor(is_dawn_or_dusk=False, midday_clear=False),
                    day_offset=offset,
                )
                sc = score(
                    open_status=open_status,
                    run_status_now=run_now,
                    run_status_forecast=rsf,
                    bite_window=bw,
                    creel_signal=cs,
                )
                verdict = _verdict(sc)

                rule = match_rule(
                    rules,
                    species=sp,
                    reach_type=launch["reach_type"],
                    flow_band=_flow_band(latest_flow),
                    clarity_band=_clarity_band(latest_flow),
                )
                techniques = (
                    [
                        {
                            "rank": t.rank,
                            "method": t.method,
                            "label": t.label,
                            "gear": t.gear,
                            "notes": t.notes,
                        }
                        for t in techniques_from_rule(rule)
                    ]
                    if rule
                    else []
                )

                day_entry = {
                    "date": day.isoformat(),
                    "score": round(sc, 3),
                    "verdict": verdict,
                    "techniques": techniques,
                    "wind_mph": round(wind, 1),
                    "water_temp_f": latest_temp,
                    "flow_cfs": latest_flow,
                    "no_run_data": ref_state is None,
                }
                days_out.append(day_entry)

                if open_status > 0:
                    candidates_by_species[sp].append(
                        Pick(
                            launch=launch["key"],
                            day_offset=offset,
                            score=sc,
                            technique=techniques[0]["label"] if techniques else "",
                        )
                    )

            forecasts[key] = days_out

    # Top-3 picks per species
    top_picks: dict[str, list[dict]] = {}
    for sp in ALL_SPECIES:
        picks = rank_picks(candidates_by_species[sp], k=3, max_per_launch=2)
        top_picks[sp] = [
            {
                "launch": p.launch,
                "day_offset": p.day_offset,
                "score": round(p.score, 3),
                "technique": p.technique,
            }
            for p in picks
        ]

    # Serialized regs: flatten both layers into a single dict for the renderer
    # and the regs-refresh job (both still index by section_key). Emergency
    # entries override pamphlet entries with the same key — matches resolve()'s
    # precedence so the merged dict is consistent with per-launch decisions.
    regs_out: dict[str, dict] = {}
    for skey, st in pamphlet_layer.items():
        regs_out[skey] = {
            "open": st.open,
            "reason": st.reason,
            "authority": st.authority,
            "last_checked": st.last_checked.isoformat(),
        }
    for skey, st in emergency_layer.items():
        regs_out[skey] = {
            "open": st.open,
            "reason": st.reason,
            "authority": st.authority,
            "last_checked": st.last_checked.isoformat(),
        }

    # Decorate each launch with its resolved closure state so the renderer can
    # show the correct OPEN/CLOSED banner without doing its own regs lookup.
    serialized_launches: list[dict] = []
    for s in STATIONS:
        sl = _serialize_launch(s)
        rs = launch_status.get(s["key"])
        if rs is not None:
            sl["closed_today"] = not rs.open
            sl["closure_reason"] = rs.reason
            sl["closure_authority"] = rs.authority
            sl["closure_last_checked"] = rs.last_checked.isoformat()
        else:
            sl["closed_today"] = False
            sl["closure_reason"] = None
            sl["closure_authority"] = None
            sl["closure_last_checked"] = None
        serialized_launches.append(sl)

    data = {
        "generated_at": datetime.now(LOCAL_TZ).isoformat(),
        "today": today.isoformat(),
        "launches": serialized_launches,
        "forecasts": forecasts,
        "runtiming": runtiming,
        "top_picks": top_picks,
        "regs": regs_out,
        "regs_agency_meta": inputs.get("regs_agency_meta", {}),
        "creel": [_serialize_creel(c) for c in creel_entries],
    }
    storage.write_json("report_data", data)
    return data


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    storage = FileStorage(root=default_root())
    today = datetime.now(LOCAL_TZ).date()
    log.info("salmon report run starting; today=%s", today)
    inputs = fetch_all(storage=storage, today=today)
    data = build_report_data(inputs, storage=storage)
    # render is built in Task 19; defer import so this module can be imported
    # for testing build_report_data in isolation.
    from render import render_html  # noqa: WPS433 — intentional lazy import
    html = render_html(data)
    storage.write("report_html", html)
    log.info("report.html written: %d bytes", len(html))
    # Purge Cloudflare cache so the new report is immediately visible at the edge.
    try:
        from cloudflare import purge_cache
        purge_cache()
    except Exception as e:
        log.warning("cache purge failed: %s", e)


if __name__ == "__main__":
    main()
