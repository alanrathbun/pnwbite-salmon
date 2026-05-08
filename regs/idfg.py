"""IDFG spring Chinook season-status scraper.

IDFG publishes structured season-status tables at:
  https://idfg.idaho.gov/fish/chinook/spring/rules

Each table has a <caption> naming the river (Clearwater River, Salmon River, etc.)
and rows with Location + Season Status cells. Status values include:
  "Open"                    → open=True
  "Open, limited days per week" → open=True  (restricted but open)
  "Closed"                  → open=False
  "Season has not started"  → open=False (pre-season; treat as closed)
  "Season has ended"        → open=False

Note: https://idfg.idaho.gov/rules/fish/changes returned 404 as of May 2026.
The spring Chinook season-status page is the authoritative real-time source.

Sections we care about (keyed to section_key used throughout the system):
  - IDFG_CLEARWATER_LOWER: Mainstem Clearwater (Lewiston area)
  - IDFG_CLEARWATER_MID:   North/Middle/South Forks above Lewiston
  - IDFG_SALMON:           Salmon River (Riggins area / Lower Salmon)

Conservative policy as elsewhere: status is open=True unless the status cell
explicitly says "Closed", "Season has not started", or "Season has ended".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup

from utils import fetch

URL = "https://idfg.idaho.gov/fish/chinook/spring/rules"

# Map (table caption text fragment) → section_key for broad grouping.
# Rows within each table are further classified by location text.
_CAPTION_MAP = [
    ("clearwater", "IDFG_CLEARWATER_LOWER"),  # default for Clearwater group
    ("salmon", "IDFG_SALMON"),
]

# Location-level overrides: more-specific phrases override the caption default.
# Ordered longest-match first to prevent "clearwater" stealing "north fork".
_LOCATION_MAP = [
    ("mainstem clearwater", "IDFG_CLEARWATER_LOWER"),
    ("north fork clearwater", "IDFG_CLEARWATER_MID"),
    ("south fork clearwater", "IDFG_CLEARWATER_MID"),
    ("middle fork clearwater", "IDFG_CLEARWATER_MID"),
    ("upper clearwater", "IDFG_CLEARWATER_MID"),
    ("lower clearwater", "IDFG_CLEARWATER_LOWER"),
    ("clearwater river", "IDFG_CLEARWATER_LOWER"),
    ("lower salmon river", "IDFG_SALMON"),
    ("little salmon river", "IDFG_SALMON"),
    ("salmon river", "IDFG_SALMON"),
]

# Explicit closure signals in the Season Status cell.
_CLOSE_RE = re.compile(
    r"\b(closed|closure|has not started|not started|has ended|season ended|no fishing)\b",
    re.IGNORECASE,
)

# Open signals — any text containing "open" not preceded by a negation.
_OPEN_RE = re.compile(r"\bopen\b", re.IGNORECASE)


@dataclass(frozen=True)
class RegStatus:
    authority: str
    section_key: str
    open: bool
    reason: str
    last_checked: datetime


def parse_changes(html: str) -> list[RegStatus]:
    """Parse IDFG spring Chinook rules HTML; return RegStatus list for known sections.

    Scans tables with captions matching our sections. Each table row contains a
    Location cell and a Season Status cell. Status is determined from the status
    cell text; location text overrides the table-level section_key for specificity.
    """
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now()
    out: list[RegStatus] = []

    for table in soup.find_all("table"):
        cap_el = table.find("caption")
        if not cap_el:
            continue
        caption = cap_el.get_text(" ", strip=True).lower()

        # Determine default section_key for this table from the caption.
        default_key = _caption_key(caption)
        if not default_key:
            continue  # Not a river table we care about

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            loc_text = cells[0].get_text(" ", strip=True)
            status_text = cells[1].get_text(" ", strip=True)

            # Skip header row
            if loc_text.lower() in ("location", "season status") or not status_text:
                continue

            # Refine section_key using the location text.
            section_key = _location_key(loc_text) or default_key

            reason = _trim(f"{loc_text}: {status_text}")

            if _CLOSE_RE.search(status_text):
                out.append(RegStatus("IDFG", section_key, False, reason, now))
            elif _OPEN_RE.search(status_text):
                out.append(RegStatus("IDFG", section_key, True, reason, now))
            # else: ambiguous status — skip (conservative)

    # De-duplicate: closures beat opens for same section; otherwise first wins.
    by_key: dict[str, RegStatus] = {}
    for s in out:
        prior = by_key.get(s.section_key)
        if prior is None:
            by_key[s.section_key] = s
        elif not s.open and prior.open:
            by_key[s.section_key] = s

    return list(by_key.values())


def _caption_key(caption: str) -> str | None:
    """Return section_key for a table caption, or None if not a tracked river."""
    for phrase, key in _CAPTION_MAP:
        if phrase in caption:
            return key
    return None


def _location_key(location: str) -> str | None:
    """Return section_key from a location string using longest-match first."""
    loc = location.lower()
    for phrase, key in sorted(_LOCATION_MAP, key=lambda kv: -len(kv[0])):
        if phrase in loc:
            return key
    return None


def _trim(s: str) -> str:
    """Return the first sentence, capped at 240 chars."""
    return re.split(r"(?<=[.!?])\s+", s.strip(), maxsplit=1)[0][:240]


def fetch_status() -> list[RegStatus]:
    """Fetch live IDFG season-status page and return RegStatus list."""
    return parse_changes(fetch(URL))
