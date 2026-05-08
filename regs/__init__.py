"""Aggregator for all three regulators.

A section is OPEN by default unless any agency has it closed. Authority precedence
is informational only; the dict is keyed by section_key, so each section maps to
a single RegStatus regardless of which agency reported it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .wdfw import RegStatus, fetch_status as wdfw_fetch
from .odfw import fetch_status as odfw_fetch
from .idfg import fetch_status as idfg_fetch


def fetch_all() -> tuple[dict[str, RegStatus], dict[str, dict]]:
    """Run all three scrapers and merge into {section_key: RegStatus}.

    Returns ``(statuses_by_section, agency_meta)``.

    ``agency_meta`` is keyed by agency name (WDFW/ODFW/IDFG) and tracks per-
    agency success: ``{"ok": bool, "last_successful_check": isostr|None,
    "error": str|None}``. Callers use this to surface a staleness banner
    when a scraper fails — silently treating a failed agency as "all open"
    is dangerous because it produces false GREEN verdicts during outages.
    """
    out: dict[str, RegStatus] = {}
    agency_meta: dict[str, dict] = {}
    for name, fn in (("WDFW", wdfw_fetch), ("ODFW", odfw_fetch), ("IDFG", idfg_fetch)):
        try:
            results = fn()
            agency_meta[name] = {
                "ok": True,
                "last_successful_check": datetime.now().isoformat(),
                "error": None,
            }
            for s in results:
                # If multiple sources mention the same section_key (rare cross-state
                # references), preferring the more restrictive (closed) wins.
                prior = out.get(s.section_key)
                if prior is None:
                    out[s.section_key] = s
                elif not s.open and prior.open:
                    out[s.section_key] = s
        except Exception as e:  # noqa: BLE001 — we want to capture any scraper failure
            agency_meta[name] = {
                "ok": False,
                "last_successful_check": None,
                "error": str(e)[:200],
            }
    return out, agency_meta


def is_open(statuses: dict[str, RegStatus], section_key: str) -> bool:
    """Default-open: section is open unless we have a confirmed closure."""
    s = statuses.get(section_key)
    return True if s is None else s.open


def closure_reason(statuses: dict[str, RegStatus], section_key: str) -> str | None:
    s = statuses.get(section_key)
    return s.reason if s and not s.open else None
