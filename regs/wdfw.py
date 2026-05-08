"""WDFW emergency rule changes scraper.

WDFW publishes emergency rule changes at wdfw.wa.gov/fishing/regulations/emergency-rules.
Each entry is a list item with a title describing the change. We classify by matching
the title against known section phrases and infer open/closed from the title text.

Conservative: when the title is ambiguous (e.g., a bare "Fishery Change"), we skip
rather than risk a false closure. False-closes are worse than missed-closes for a
fishing-recommendation app — closures only stick when text says "closed", "closure",
or "closed to" explicitly.

"limit reduced", "modified", "extended", "change" entries are treated as open=True
since those are restrictions within an open season, not closures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup

from utils import fetch

URL = "https://wdfw.wa.gov/fishing/regulations/emergency-rules"


@dataclass(frozen=True)
class RegStatus:
    authority: str
    section_key: str
    open: bool
    reason: str
    last_checked: datetime
    effective_from: datetime | None = None
    effective_to: datetime | None = None


_SECTION_MAP = [
    ("hanford reach", "WDFW_HANFORD_REACH"),
    ("drano lake", "WDFW_DRANO"),
    ("wind river", "WDFW_WIND"),
    ("klickitat river mouth", "WDFW_KLICKITAT_MOUTH"),
    ("klickitat river", "WDFW_KLICKITAT_MOUTH"),
    ("klickitat", "WDFW_KLICKITAT_MOUTH"),
    ("mid columbia", "WDFW_MID_COL_POOL"),
    ("mid-columbia", "WDFW_MID_COL_POOL"),
    ("mcnary pool", "WDFW_MCNARY_POOL"),
    ("upper columbia", "WDFW_UPPER_COL"),
    ("snake river", "WDFW_LOWER_SNAKE"),
]

# Explicit closure signals — only these cause open=False.
_CLOSE_RE = re.compile(
    r"\b(closed|closure|closed to|will be closed|will close|not open|will not open)\b",
    re.IGNORECASE,
)

# Open or restriction-within-open-season signals → open=True.
_OPEN_RE = re.compile(
    r"\b(open|reopens|reopened|will open|to open|reduced|limit|modified|"
    r"change|extended|fishery change|daily limit)\b",
    re.IGNORECASE,
)


def classify_section(text: str) -> str | None:
    """Return the section key for a known area phrase, or None."""
    t = text.lower()
    for phrase, key in _SECTION_MAP:
        if phrase in t:
            return key
    return None


def parse_rule_changes(html: str) -> list[RegStatus]:
    """Parse WDFW emergency rules HTML and return RegStatus list for known sections."""
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now()
    out: list[RegStatus] = []

    # WDFW's emergency-rules page lists entries as <li> elements, each containing
    # a single <a> whose text is the full rule-change title. The title is the only
    # text on this listing page; detail lives on linked sub-pages. We classify and
    # infer status from the title alone.
    #
    # Fallback: also scan any <a> in case the DOM structure changes.
    candidates: list[str] = []
    for li in soup.find_all("li"):
        txt = li.get_text(" ", strip=True)
        if txt:
            candidates.append(txt)

    # If no <li> found with meaningful text, fall back to scanning anchors.
    if not candidates:
        for a in soup.find_all("a"):
            txt = a.get_text(" ", strip=True)
            if txt and len(txt) >= 8:
                candidates.append(txt)

    for title in candidates:
        section_key = classify_section(title)
        if not section_key:
            continue

        if _CLOSE_RE.search(title):
            is_open = False
            reason = _first_sentence(title)
        elif _OPEN_RE.search(title):
            is_open = True
            reason = _first_sentence(title)
        else:
            # Ambiguous title — skip rather than risk a false close.
            continue

        out.append(RegStatus(
            authority="WDFW",
            section_key=section_key,
            open=is_open,
            reason=reason,
            last_checked=now,
        ))

    # De-duplicate: if the same section appears multiple times, closures win over
    # opens; otherwise first occurrence wins.
    by_key: dict[str, RegStatus] = {}
    for s in out:
        prior = by_key.get(s.section_key)
        if prior is None:
            by_key[s.section_key] = s
            continue
        # Prefer closures over opens when both are present.
        if not s.open and prior.open:
            by_key[s.section_key] = s

    return list(by_key.values())


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return parts[0][:240] if parts else text[:240]


def fetch_status() -> list[RegStatus]:
    """Fetch live WDFW emergency rules and return RegStatus list."""
    return parse_rule_changes(fetch(URL))
