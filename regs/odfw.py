"""ODFW news/regs scraper.

ODFW publishes news and regulation updates at myodfw.com/newsroom.
The format is a list of articles with title + teaser body. Same conservative
policy as WDFW: only infer closed/open when the text explicitly says so.

dfw.state.or.us/news/ returns 403 as of May 2026; myodfw.com/newsroom is the
active public newsroom.

Sections we care about (Oregon waters in our scope):
  - ODFW_MID_COL: Boardman/Umatilla pool (Columbia River OR-side)
  - ODFW_SNAKE: Snake River OR-side (rare for our launches but possible)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup

from utils import fetch

URL = "https://myodfw.com/newsroom"

_SECTION_MAP = [
    ("columbia river", "ODFW_MID_COL"),
    ("mid columbia", "ODFW_MID_COL"),
    ("mid-columbia", "ODFW_MID_COL"),
    ("umatilla", "ODFW_MID_COL"),
    ("boardman", "ODFW_MID_COL"),
    ("snake river", "ODFW_SNAKE"),
]

# Explicit closure signals — only these cause open=False.
_CLOSE_RE = re.compile(
    r"\b(closed|closure|closed to|will be closed|will close|not open|will not open)\b",
    re.IGNORECASE,
)

# Open or restriction-within-open-season signals → open=True.
_OPEN_RE = re.compile(
    r"\b(opens|reopens|reopened|opening|will open|is open|now open)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RegStatus:
    authority: str
    section_key: str
    open: bool
    reason: str
    last_checked: datetime


def parse_news(html: str) -> list[RegStatus]:
    """Parse ODFW newsroom HTML and return RegStatus list for known sections.

    Each article element is scanned for location keywords from _SECTION_MAP.
    Only articles with an explicit open or closed signal are returned.
    Articles that are ambiguous (no signal) are skipped — conservative policy.
    """
    soup = BeautifulSoup(html, "lxml")
    now = datetime.now()
    out: list[RegStatus] = []

    # myodfw.com/newsroom: articles are inside <article> tags within .view-content.
    # Fallback: scan all <a> links if no articles found (handles layout changes).
    articles = soup.find_all("article")
    if articles:
        candidates = [
            (art.get_text(" ", strip=True), art)
            for art in articles
        ]
    else:
        # Fallback: treat each link title + its parent block as a candidate
        candidates = []
        for a in soup.find_all("a"):
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 12:
                continue
            parent = (
                a.find_parent(["article", "li", "div", "section"]) or a
            )
            candidates.append((parent.get_text(" ", strip=True), parent))

    for text, _el in candidates:
        section_key = _classify(text)
        if not section_key:
            continue
        if _CLOSE_RE.search(text):
            out.append(RegStatus("ODFW", section_key, False, _trim(text), now))
        elif _OPEN_RE.search(text):
            out.append(RegStatus("ODFW", section_key, True, _trim(text), now))
        # else: ambiguous — skip (conservative)

    # De-duplicate: if same section appears multiple times, closures beat opens;
    # otherwise first occurrence wins.
    by_key: dict[str, RegStatus] = {}
    for s in out:
        prior = by_key.get(s.section_key)
        if prior is None or (not s.open and prior.open):
            by_key[s.section_key] = s
    return list(by_key.values())


def _classify(text: str) -> str | None:
    """Return the section key for the first matching phrase, or None."""
    t = text.lower()
    for phrase, key in _SECTION_MAP:
        if phrase in t:
            return key
    return None


def _trim(s: str) -> str:
    """Return the first sentence, capped at 240 chars."""
    return re.split(r"(?<=[.!?])\s+", s.strip(), maxsplit=1)[0][:240]


def fetch_status() -> list[RegStatus]:
    """Fetch live ODFW newsroom and return RegStatus list."""
    return parse_news(fetch(URL))
