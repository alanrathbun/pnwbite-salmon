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


def fetch_all() -> dict[str, RegStatus]:
    """Run all three scrapers and merge into {section_key: RegStatus}.

    Each agency may fail independently; failures degrade silently and the
    section's status is treated as 'open by default' downstream.
    """
    out: dict[str, RegStatus] = {}
    for fn in (wdfw_fetch, odfw_fetch, idfg_fetch):
        try:
            for s in fn():
                # If multiple sources mention the same section_key (rare cross-state
                # references), preferring the more restrictive (closed) wins.
                prior = out.get(s.section_key)
                if prior is None:
                    out[s.section_key] = s
                elif not s.open and prior.open:
                    out[s.section_key] = s
        except Exception:
            # Network/parse errors don't block the report; downstream banners
            # will surface staleness via .regs_cache.json's last_successful_check.
            continue
    return out


def is_open(statuses: dict[str, RegStatus], section_key: str) -> bool:
    """Default-open: section is open unless we have a confirmed closure."""
    s = statuses.get(section_key)
    return True if s is None else s.open


def closure_reason(statuses: dict[str, RegStatus], section_key: str) -> str | None:
    s = statuses.get(section_key)
    return s.reason if s and not s.open else None
