"""Planner pivots over the per-launch forecast dict.

Four pure functions, all keyed off the in-memory ``forecasts`` dict that
``build_report_data`` produces. None of these touch storage or do I/O —
they exist so the cron can pre-compute a small set of ranking views and
ship them in the report payload. Closed launches (``open == False``) are
excluded from every ranking.

Forecast-key shape: ``"<species>::<launch_key>"``.
Tie-breaking: alphabetic launch_key, then alphabetic species, then alphabetic
date, for deterministic output.
"""
from __future__ import annotations


def _split_key(key: str) -> tuple[str, str]:
    species, _, launch = key.partition("::")
    return species, launch


def top_launches_by_species_date(
    forecasts: dict[str, list[dict]],
    species: str,
    date_iso: str,
    *,
    k: int = 5,
) -> list[dict]:
    """Top *k* launches for a given (species, date), best-score first."""
    candidates: list[tuple[float, str, dict]] = []
    for fkey, days in forecasts.items():
        sp, launch = _split_key(fkey)
        if sp != species:
            continue
        entry = next((d for d in days if d.get("date") == date_iso), None)
        if entry is None or not entry.get("open", True):
            continue
        candidates.append((float(entry.get("score") or 0.0), launch, entry))
    candidates.sort(key=lambda t: (-t[0], t[1]))
    out: list[dict] = []
    for score_val, launch, entry in candidates[:k]:
        item = {"launch": launch, "score": score_val}
        techs = entry.get("techniques") or []
        if techs:
            item["technique"] = techs[0].get("label", "")
        out.append(item)
    return out


def top_dates_by_launch_species(
    forecasts: dict[str, list[dict]],
    launch_key: str,
    species: str,
    *,
    k: int = 5,
) -> list[dict]:
    """Top *k* dates for a (launch, species), best-score first."""
    fkey = f"{species}::{launch_key}"
    days = forecasts.get(fkey) or []
    open_days = [d for d in days if d.get("open", True)]
    open_days.sort(key=lambda d: (-(float(d.get("score") or 0.0)), d.get("date", "")))
    out: list[dict] = []
    for d in open_days[:k]:
        item = {"date": d.get("date"), "score": float(d.get("score") or 0.0)}
        techs = d.get("techniques") or []
        if techs:
            item["technique"] = techs[0].get("label", "")
        out.append(item)
    return out


def top_pairs_by_date(
    forecasts: dict[str, list[dict]],
    date_iso: str,
    *,
    k: int = 5,
) -> list[dict]:
    """Top *k* (launch, species) pairs across all forecasts on a given date."""
    candidates: list[tuple[float, str, str, dict]] = []
    for fkey, days in forecasts.items():
        sp, launch = _split_key(fkey)
        entry = next((d for d in days if d.get("date") == date_iso), None)
        if entry is None or not entry.get("open", True):
            continue
        candidates.append((float(entry.get("score") or 0.0), launch, sp, entry))
    candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
    out: list[dict] = []
    for score_val, launch, sp, entry in candidates[:k]:
        item = {"launch": launch, "species": sp, "score": score_val}
        techs = entry.get("techniques") or []
        if techs:
            item["technique"] = techs[0].get("label", "")
        out.append(item)
    return out


def season_heatmap_for_species(
    forecasts: dict[str, list[dict]],
    species: str,
) -> list[dict]:
    """For each date in the forecast horizon, the best score across all open
    launches for *species*. Returns empty list if the species has no entries."""
    by_date: dict[str, float] = {}
    found_any = False
    for fkey, days in forecasts.items():
        sp, _ = _split_key(fkey)
        if sp != species:
            continue
        found_any = True
        for d in days:
            if not d.get("open", True):
                continue
            date_iso = d.get("date")
            if not date_iso:
                continue
            score_val = float(d.get("score") or 0.0)
            if score_val > by_date.get(date_iso, -1.0):
                by_date[date_iso] = score_val
    if not found_any:
        return []
    return [{"date": d, "score": s} for d, s in sorted(by_date.items())]
