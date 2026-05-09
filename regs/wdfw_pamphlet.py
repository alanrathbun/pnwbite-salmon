"""WDFW Sport Fishing Pamphlet — section status lookup.

Loads `wdfw_pamphlet.yaml` (a hand-curated extract of the annual pamphlet) and
determines the current open/closed status for any encoded section.

The pamphlet is the canonical source for *seasonal* closures (e.g., McNary
Tailrace closed Jan 1 - Jun 15). The /emergency-rules scraper at WDFW only
publishes in-season *changes*, not the seasonal baseline. This module fills the
gap.

Usage:
    from regs.wdfw_pamphlet import status_for_section
    status_for_section("mcnary_tailrace", today=date(2026, 5, 8))
    # -> RegStatus(authority="WDFW", section_key="mcnary_tailrace", open=False, ...)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

PAMPHLET_PATH = Path(__file__).resolve().parent.parent / "wdfw_pamphlet.yaml"


@dataclass(frozen=True)
class RegStatus:
    """Mirrors regs/{wdfw,odfw,idfg}.RegStatus — keep field-shape compatible."""
    authority: str
    section_key: str
    open: bool
    reason: str
    last_checked: datetime


_pamphlet_cache: list[dict[str, Any]] | None = None


def load_pamphlet(path: Path = PAMPHLET_PATH) -> list[dict[str, Any]]:
    """Load and cache the pamphlet YAML. Returns the list of section dicts."""
    global _pamphlet_cache
    if _pamphlet_cache is not None:
        return _pamphlet_cache
    if not path.exists():
        _pamphlet_cache = []
        return _pamphlet_cache
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _pamphlet_cache = doc.get("sections", [])
    return _pamphlet_cache


def _parse_mmdd(s: str, year: int) -> date:
    """Parse a MM-DD string into a date in the given year."""
    m, d = s.split("-")
    return date(year, int(m), int(d))


def _date_in_range(today: date, range_str: str) -> bool:
    """`range_str` looks like 'MM-DD..MM-DD'. Handles year-wraparound."""
    try:
        start_str, end_str = range_str.split("..")
    except ValueError:
        return False
    start = _parse_mmdd(start_str.strip(), today.year)
    end = _parse_mmdd(end_str.strip(), today.year)
    if start <= end:
        return start <= today <= end
    # Wrap-around (e.g., 12-01..01-31): two windows
    return today >= start or today <= end


_metadata_cache: dict[str, str] | None = None


def _load_metadata(path: Path = PAMPHLET_PATH) -> dict[str, str]:
    """Load top-level pamphlet metadata fields. Cached after first call."""
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache
    if not path.exists():
        _metadata_cache = {}
        return _metadata_cache
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _metadata_cache = {
        "pamphlet_filename": str(doc.get("pamphlet_filename", "")),
        "pamphlet_version": str(doc.get("pamphlet_version", "")),
    }
    return _metadata_cache


def pamphlet_filename() -> str:
    """Return the pamphlet PDF filename encoded in the YAML (e.g., '25WAFW_LR7.pdf')."""
    return _load_metadata().get("pamphlet_filename", "")


def pamphlet_version() -> str:
    """Return the pamphlet version label (e.g., '2025-2026')."""
    return _load_metadata().get("pamphlet_version", "")


def status_for_section(
    section_id: str,
    *,
    today: date | None = None,
    species: str = "salmon_hatchery_steelhead",
) -> RegStatus | None:
    """Determine today's status for a pamphlet section.

    Returns None if the section_id is not encoded in the YAML (caller should
    fall back to default-open). Returns a RegStatus with open=True/False
    otherwise.

    Conservative default: if today's date doesn't match any listed range in
    `species`, the section is treated as CLOSED for that species (the pamphlet
    convention — periods not listed are implicitly closed for retention).
    """
    if today is None:
        today = date.today()
    sections = load_pamphlet()
    section = next((s for s in sections if s.get("id") == section_id), None)
    if section is None:
        return None

    rules = section.get(species) or []
    matched_open = None
    matched_note = ""
    for rule in rules:
        if _date_in_range(today, rule.get("dates", "")):
            if rule.get("status") == "open":
                matched_open = True
                matched_note = rule.get("note", "")
                break
            elif rule.get("status") == "closed":
                matched_open = False
                matched_note = "Closed per WDFW pamphlet seasonal rule"
                break

    if matched_open is None:
        # No matching rule today — implicit closure for salmon retention.
        is_open = False
        reason = (
            f"Closed (no salmon retention period in pamphlet for "
            f"{section.get('description', section_id)} on {today.isoformat()})"
        )
    else:
        is_open = matched_open
        reason = matched_note or (
            f"{'Open' if is_open else 'Closed'} per WDFW pamphlet "
            f"({section.get('description', section_id)})"
        )

    return RegStatus(
        authority="WDFW",
        section_key=section_id,
        open=is_open,
        reason=reason[:240],
        last_checked=datetime.now(),
    )


def status_for_all_sections(
    today: date | None = None,
    *,
    species: str = "salmon_hatchery_steelhead",
) -> dict[str, RegStatus]:
    """Compute status for every encoded section. Useful for the regs aggregator."""
    if today is None:
        today = date.today()
    out: dict[str, RegStatus] = {}
    for section in load_pamphlet():
        sid = section.get("id")
        if not sid:
            continue
        st = status_for_section(sid, today=today, species=species)
        if st is not None:
            out[sid] = st
    return out
