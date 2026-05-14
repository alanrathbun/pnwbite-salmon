"""3-layer regs aggregator.

Layer 0 (default)  : OPEN
Layer 1 (baseline) : WDFW pamphlet YAML — fine-grained, per pamphlet section_id
Layer 2 (overlay)  : Emergency projections (WDFW classifier + ODFW + IDFG scrapers)

resolve_for_day(emergency_projections, section_id, day) consults Layer 2's
date-bounded projections, then falls back to the pamphlet for `day`, returning
None when neither layer has an entry for `section_id` on `day` (caller defaults
to OPEN).
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from regs.emergency_classifier import classify_rule
from regs.emergency_types import Projection
from regs.idfg import fetch_status as idfg_fetch
from regs.odfw import fetch_status as odfw_fetch
from regs.wdfw import RegStatus
from regs.wdfw_emergency import fetch_active_rules
from regs.wdfw_pamphlet import load_pamphlet
from regs.wdfw_pamphlet import status_for_all_sections as pamphlet_statuses
from regs.wdfw_pamphlet import status_for_section as pamphlet_status_for_section

log = logging.getLogger("regs")


def fetch_all(today: date | None = None) -> tuple[
    dict[str, RegStatus],          # pamphlet_layer (today-only snapshot)
    dict[str, list[Projection]],   # emergency_projections (date-bounded, projects forward)
    dict[str, dict],               # agency_meta
]:
    """Build the pamphlet snapshot (today) + emergency projections (date-bounded) + agency meta."""
    if today is None:
        today = date.today()

    # Layer 1 — pamphlet (still a today-only snapshot for the legacy `resolve` path)
    pamphlet_layer: dict[str, RegStatus] = {}
    try:
        pamphlet_layer = pamphlet_statuses(today=today)
        agency_meta_pamphlet = {"ok": True, "last_successful_check": datetime.now().isoformat(), "error": None}
    except Exception as e:  # noqa: BLE001
        log.exception("pamphlet load failed")
        agency_meta_pamphlet = {"ok": False, "last_successful_check": None, "error": str(e)[:200]}

    # Layer 2 — emergency projections
    emergency_projections: dict[str, list[Projection]] = {}
    agency_meta: dict[str, dict] = {"WDFW_PAMPHLET": agency_meta_pamphlet}

    # WDFW emergency via advanced-search + Claude classifier
    try:
        rules = fetch_active_rules(today)
        sections_for_prompt = [
            {"id": s["id"], "description": s.get("description", "")}
            for s in load_pamphlet()
        ]
        for rule in rules:
            classification = classify_rule(rule, sections_for_prompt)
            if classification is None:
                continue
            for p in classification.projections:
                emergency_projections.setdefault(p.section_id, []).append(p)
        agency_meta["WDFW"] = {"ok": True, "last_successful_check": datetime.now().isoformat(), "error": None}
    except Exception as e:  # noqa: BLE001
        log.exception("WDFW emergency fetch failed")
        agency_meta["WDFW"] = {"ok": False, "last_successful_check": None, "error": str(e)[:200]}

    # ODFW + IDFG keep their existing today-only RegStatus output; we wrap each
    # as a single Projection with effective_from=effective_to=None ("always
    # active for this run"). The per-day caller filters by date, so a None/None
    # range means "this projection applies on every day of the forecast".
    for name, fn in (("ODFW", odfw_fetch), ("IDFG", idfg_fetch)):
        try:
            for s in fn():
                emergency_projections.setdefault(s.section_key, []).append(Projection(
                    section_id=s.section_key,
                    status=("open" if s.open else "closed"),
                    effective_from=None,
                    effective_to=None,
                    reason=s.reason,
                    authority=s.authority,
                ))
            agency_meta[name] = {"ok": True, "last_successful_check": datetime.now().isoformat(), "error": None}
        except Exception as e:  # noqa: BLE001
            log.exception("%s fetch failed", name)
            agency_meta[name] = {"ok": False, "last_successful_check": None, "error": str(e)[:200]}

    return pamphlet_layer, emergency_projections, agency_meta


def _projection_applies_on(p: Projection, day: date) -> bool:
    if p.effective_from is not None and day < p.effective_from:
        return False
    if p.effective_to is not None and day > p.effective_to:
        return False
    return True


def resolve_for_day(
    emergency_projections: dict[str, list[Projection]],
    section_id: str,
    day: date,
) -> RegStatus | None:
    """Per-day 3-layer precedence lookup.

    1. Find emergency projections matching section_id with day in range.
       Closures win over opens on the same day.
    2. Otherwise, fall back to the pamphlet's per-day status_for_section.
    3. Return None if neither layer has an entry (caller defaults to OPEN).
    """
    matching = [p for p in emergency_projections.get(section_id, []) if _projection_applies_on(p, day)]
    closures = [p for p in matching if p.status == "closed"]
    if closures:
        p = closures[0]
        return RegStatus(authority=p.authority, section_key=section_id, open=False,
                         reason=p.reason, last_checked=datetime.now())
    opens = [p for p in matching if p.status == "open"]
    if opens:
        p = opens[0]
        return RegStatus(authority=p.authority, section_key=section_id, open=True,
                         reason=p.reason, last_checked=datetime.now())
    return pamphlet_status_for_section(section_id, today=day)


def resolve(
    pamphlet_layer: dict[str, RegStatus],
    emergency_projections: dict[str, list[Projection]],
    section_id: str,
    today: date,
) -> RegStatus | None:
    """Back-compat shim — today-only resolution via resolve_for_day.

    Note: the second argument was previously ``emergency_layer: dict[str, RegStatus]``
    (today-only). It is now ``emergency_projections: dict[str, list[Projection]]``
    (date-bounded). Old callers that pass the new-shape value continue to work;
    old callers that pass the old RegStatus-valued dict will silently get wrong
    results — they should be updated to pass lists of Projections.
    """
    return resolve_for_day(emergency_projections, section_id, today)


def is_open(
    pamphlet_layer: dict[str, RegStatus],
    emergency_projections: dict[str, list[Projection]],
    section_id: str,
    today: date,
) -> bool:
    """Convenience: True if the section is open per the 3-layer resolution
    on `today`. Default-OPEN when neither layer has data."""
    rs = resolve_for_day(emergency_projections, section_id, today)
    return True if rs is None else rs.open


def closure_reason(
    pamphlet_layer: dict[str, RegStatus],
    emergency_projections: dict[str, list[Projection]],
    section_id: str,
    today: date,
) -> str | None:
    s = resolve_for_day(emergency_projections, section_id, today)
    return s.reason if s and not s.open else None
