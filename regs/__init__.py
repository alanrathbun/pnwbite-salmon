"""3-layer regs aggregator.

Layer 0 (default)  : OPEN
Layer 1 (baseline) : WDFW pamphlet YAML  — fine-grained, per pamphlet section_id
Layer 2 (overlay)  : Emergency rules (WDFW classifier + ODFW + IDFG scrapers)

resolve(section_id, today) consults Layer 2 first, falls back to Layer 1, and
returns None when neither layer has an entry (caller defaults to OPEN).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Iterable

from regs.emergency_classifier import classify_rule
from regs.emergency_types import Classification, EmergencyRule
from regs.idfg import fetch_status as idfg_fetch
from regs.odfw import fetch_status as odfw_fetch
from regs.wdfw import RegStatus  # dataclass exported for callers
from regs.wdfw_emergency import fetch_active_rules
from regs.wdfw_pamphlet import load_pamphlet
from regs.wdfw_pamphlet import status_for_all_sections as pamphlet_statuses

log = logging.getLogger("regs")


def fetch_all(today: date | None = None) -> tuple[
    dict[str, RegStatus],   # pamphlet_layer
    dict[str, RegStatus],   # emergency_layer
    dict[str, dict],        # agency_meta
]:
    """Build the two layers + agency_meta for today's report run.

    Pamphlet layer always succeeds (local YAML). Emergency layer is built from:
      - WDFW advanced-search rules + classifier
      - ODFW + IDFG existing scrapers (still keyed by their existing section keys)
    """
    if today is None:
        today = date.today()

    # Layer 1 — pamphlet
    pamphlet_layer: dict[str, RegStatus] = {}
    try:
        pamphlet_layer = pamphlet_statuses(today=today)
        agency_meta_pamphlet = {"ok": True, "last_successful_check": datetime.now().isoformat(), "error": None}
    except Exception as e:  # noqa: BLE001
        log.exception("pamphlet load failed")
        agency_meta_pamphlet = {"ok": False, "last_successful_check": None, "error": str(e)[:200]}

    # Layer 2 — emergency
    emergency_layer: dict[str, RegStatus] = {}
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
            for sid in classification.section_ids:
                rs = RegStatus(
                    authority="WDFW",
                    section_key=sid,
                    open=(classification.status == "open"),
                    reason=f"emergency: {rule.title} ({classification.reasoning})"[:240],
                    last_checked=datetime.now(),
                )
                # If multiple emergency rules apply to the same section, closures win.
                prior = emergency_layer.get(sid)
                if prior is None or (not rs.open and prior.open):
                    emergency_layer[sid] = rs
        agency_meta["WDFW"] = {"ok": True, "last_successful_check": datetime.now().isoformat(), "error": None}
    except Exception as e:  # noqa: BLE001
        log.exception("WDFW emergency fetch failed")
        agency_meta["WDFW"] = {"ok": False, "last_successful_check": None, "error": str(e)[:200]}

    # ODFW + IDFG keep their existing section-key scheme
    for name, fn in (("ODFW", odfw_fetch), ("IDFG", idfg_fetch)):
        try:
            for s in fn():
                prior = emergency_layer.get(s.section_key)
                if prior is None or (not s.open and prior.open):
                    emergency_layer[s.section_key] = s
            agency_meta[name] = {"ok": True, "last_successful_check": datetime.now().isoformat(), "error": None}
        except Exception as e:  # noqa: BLE001
            log.exception("%s fetch failed", name)
            agency_meta[name] = {"ok": False, "last_successful_check": None, "error": str(e)[:200]}

    return pamphlet_layer, emergency_layer, agency_meta


def resolve(
    pamphlet_layer: dict[str, RegStatus],
    emergency_layer: dict[str, RegStatus],
    section_id: str,
    today: date,
) -> RegStatus | None:
    """3-layer precedence lookup.

    Returns the emergency-layer status if present (overrides in either direction);
    otherwise falls back to the pamphlet layer; returns None if neither has an
    entry. Caller treats None as default-OPEN.
    """
    em = emergency_layer.get(section_id)
    if em is not None:
        return em
    pa = pamphlet_layer.get(section_id)
    if pa is not None:
        return pa
    return None


def is_open(
    pamphlet_layer: dict[str, RegStatus],
    emergency_layer: dict[str, RegStatus],
    section_id: str,
    today: date,
) -> bool:
    """Convenience wrapper: True if section is open today (default-open if unknown)."""
    s = resolve(pamphlet_layer, emergency_layer, section_id, today)
    return True if s is None else s.open


def closure_reason(
    pamphlet_layer: dict[str, RegStatus],
    emergency_layer: dict[str, RegStatus],
    section_id: str,
    today: date,
) -> str | None:
    s = resolve(pamphlet_layer, emergency_layer, section_id, today)
    return s.reason if s and not s.open else None
