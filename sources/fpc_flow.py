"""Parse FPC flow/spill daily file (fpc.org/currentdaily/flowspil.txt).

The file is plain text with three columnar sections, one per river reach:
  - "Mid-Columbia Projects"   — Grand Coulee, Chief Joseph, Wells, Rocky Reach,
                                Rock Island, Wanapum, Priest Rapids
  - "Snake Basin Projects"    — Dworshak, Brownlee, Hells Canyon (in/out),
                                Lower Granite, Little Goose, Lower Monumental,
                                Ice Harbor
  - "Lower Columbia Projects" — McNary, John Day, The Dalles, Bonneville

Each section has a date column followed by paired (Flow, Spill) columns per dam.
Numeric offsets below (0-based, after stripping the date token) are fixed by
FPC's published format and locked by the captured fixture.

Column mapping (0-based, flow only — spill is flow+1):
  Mid-Columbia:   Wells=4, Rocky Reach=6, Rock Island=8, Priest Rapids=12
  Snake Basin:    Lower Granite=4
  Lower Columbia: McNary=0, Bonneville=6
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from utils import fetch
from dam_refs import all_dam_keys

URL = "https://www.fpc.org/currentdaily/flowspil.txt"

# Section text fragments → list of (dam_key, flow_col_index) for that section.
# flow_col_index is 0-based among the numeric tokens that follow the date.
_SECTIONS: list[tuple[str, list[tuple[str, int]]]] = [
    (
        "Mid-Columbia Projects",
        [
            ("WEL", 4),   # Wells
            ("RRH", 6),   # Rocky Reach
            ("RIS", 8),   # Rock Island
            ("PRD", 12),  # Priest Rapids
        ],
    ),
    (
        "Snake Basin Projects",
        [
            ("LGR", 4),   # Lower Granite
        ],
    ),
    (
        "Lower Columbia Projects",
        [
            ("MCN", 0),   # McNary
            ("BON", 6),   # Bonneville
        ],
    ),
]

_DATE_RE = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\b")
_HEADER_KEYWORDS = {
    "Date", "Flow", "Spill", "Inflow", "Outflow",
    "Grand", "Coulee", "Chief", "Joseph", "Wells",
    "Rocky", "Reach", "Rock", "Island", "Wanapum",
    "Priest", "Rapids", "Dworshak", "Brownlee", "Hells",
    "Canyon", "Lower", "Granite", "Goose", "Monumental",
    "Ice", "Harbor", "McNary", "John", "Day", "Dalles",
    "Bonneville", "PH1", "PH2", "Source", "Fish", "Passage",
    "Center", "Daily", "Average",
}


@dataclass(frozen=True)
class FlowRecord:
    dam_key: str
    date: date
    kcfs: float


def _parse_section(
    lines: list[str],
    start: int,
    dam_cols: list[tuple[str, int]],
) -> list[FlowRecord]:
    """Parse one section starting from start, ending at closing === line."""
    records: list[FlowRecord] = []
    in_data = False
    seen_separator = False

    for line in lines[start:]:
        stripped = line.strip()

        # First === line signals that data rows follow.
        if stripped.startswith("="):
            if not seen_separator:
                seen_separator = True
                in_data = True
            else:
                # Second === line — end of section.
                break
            continue

        if not in_data:
            continue

        if not stripped or stripped.startswith("*") or stripped.startswith("---"):
            continue

        m = _DATE_RE.match(line)
        if not m:
            # Skip header continuation lines (dam names, column labels, blanks).
            continue

        date_str = m.group(1)
        try:
            mm, dd, yyyy = date_str.split("/")
            row_date = date(int(yyyy), int(mm), int(dd))
        except ValueError:
            continue

        # Parse all numeric tokens after the date.
        tail = line[m.end():].split()
        nums: list[float | None] = []
        for t in tail:
            try:
                nums.append(float(t.replace(",", "")))
            except ValueError:
                nums.append(None)  # "---" or similar placeholder

        for dam_key, col_idx in dam_cols:
            if col_idx < len(nums) and nums[col_idx] is not None:
                records.append(FlowRecord(dam_key=dam_key, date=row_date, kcfs=nums[col_idx]))

    return records


def parse_flowspil(text: str) -> list[FlowRecord]:
    """Parse FPC flowspil.txt text, returning FlowRecord list for all reference dams."""
    lines = text.splitlines()
    records: list[FlowRecord] = []

    for section_marker, dam_cols in _SECTIONS:
        for i, line in enumerate(lines):
            if section_marker in line:
                records.extend(_parse_section(lines, i + 1, dam_cols))
                break

    return records


def fetch_flow() -> list[FlowRecord]:
    """Fetch and parse the daily flow file. Caller handles caching."""
    return parse_flowspil(fetch(URL))
