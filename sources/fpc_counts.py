"""Parse FPC adult count tables.

Source URL: https://www.fpc.org/currentdaily/HistFishTwo_7day-ytd_Adults.htm

Actual page format (verified May 2026): one HTML table with multiple dam sections.
Each section begins with a colspan header row (<th class="dam" colspan="19">DAM NAME</th>),
followed by a species header row, then 7 data rows (one per day) and a YTD footer row.

Column headers are explicit: "SPRING CHINOOK ADULT", "SUMMER CHINOOK ADULT",
"FALL CHINOOK ADULT", "COHO ADULT", "TOTAL STEELHEAD", "SOCKEYE".
No date-based run disambiguation is needed — the page labels species directly.

We map FPC dam names (uppercase) to our 3-letter dam_key codes, then emit only
the species tracked in dam_refs.FPC_DAMS[dam_key]["species_count_cols"].
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup

from utils import fetch
from dam_refs import FPC_DAMS

URL = "https://www.fpc.org/currentdaily/HistFishTwo_7day-ytd_Adults.htm"

# Map the text content of <th class="dam"> to our dam_key.
# Strip leading/trailing whitespace and collapse internal whitespace before lookup.
_DAM_NAME_TO_KEY: dict[str, str] = {
    "BONNEVILLE DAM": "BON",
    "THE DALLES DAM": "TDA",
    "JOHN DAY DAM": "JDA",
    "MCNARY DAM": "MCN",
    "ICE HARBOR DAM": "IHR",
    "LOWER MONUMENTAL DAM": "LMN",
    "PRIEST RAPIDS DAM": "PRD",
    "WELLS DAM": "WEL",
    "ROCKY REACH DAM": "RRH",
    "ROCK ISLAND DAM": "RIS",
    "LOWER GRANITE DAM": "LGR",
}

# Map normalised column header text to our species keys.
# Chinook sub-runs (spring/summer/fall) all collapse into the consolidated
# "chinook" key — dam counters don't actually distinguish them in their
# downstream reporting and we treat them as a single species. Likewise,
# steelhead is a single key.
_HEADER_TO_SPECIES: dict[str, str] = {
    "SPRING CHINOOK ADULT": "chinook",
    "SUMMER CHINOOK ADULT": "chinook",
    "FALL CHINOOK ADULT": "chinook",
    "COHO ADULT": "coho",
    "SOCKEYE": "sockeye",
    "TOTAL STEELHEAD": "steelhead",
    "STEELHEAD ADULT": "steelhead",
}


@dataclass(frozen=True)
class CountRecord:
    dam_key: str
    species: str
    date: date
    count: int


def _normalise_header(text: str) -> str:
    """Uppercase and collapse whitespace for header matching."""
    return " ".join(text.upper().split())


def _parse_date(cell: str) -> date | None:
    cell = cell.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cell, fmt).date()
        except ValueError:
            continue
    return None


def _parse_count(cell: str) -> int | None:
    """Return integer count, or None for n/a / dash / empty."""
    s = cell.strip().replace(",", "")
    if not s or s == "-" or s.lower() == "n/a":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_adult_counts(html: str) -> list[CountRecord]:
    """Parse FPC adult count HTML, returning CountRecord list for reference dams."""
    soup = BeautifulSoup(html, "lxml")
    records: list[CountRecord] = []

    # The page uses one <table> but we iterate rows looking for dam section headers.
    current_dam_key: str | None = None
    col_to_species: dict[int, str] = {}  # column index -> species key (or "_steelhead")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            # Check if this is a dam section header row.
            first_cell = cells[0]
            if first_cell.get("class") and "dam" in first_cell.get("class", []):
                dam_text = _normalise_header(first_cell.get_text())
                # Strip footnote superscripts (e.g. "LOWER GRANITE DAM 1)");
                # BeautifulSoup already stripped tags, so just clean trailing notation.
                dam_text_clean = re.sub(r"\s+\d+\).*$", "", dam_text).strip()
                current_dam_key = _DAM_NAME_TO_KEY.get(dam_text_clean)
                col_to_species = {}  # reset for new dam section
                continue

            # Check if this is a column header row for the current dam section.
            if current_dam_key is not None and all(c.name == "th" for c in cells):
                col_to_species = {}
                for i, cell in enumerate(cells):
                    h = _normalise_header(cell.get_text())
                    if h in _HEADER_TO_SPECIES:
                        col_to_species[i] = _HEADER_TO_SPECIES[h]
                continue

            # Skip rows that don't belong to a known dam.
            if current_dam_key is None or not col_to_species:
                continue

            # Data row: first cell must parse as a date.
            date_text = cells[0].get_text(strip=True)
            if date_text.upper() in ("DATE", "YTD", ""):
                continue

            row_date = _parse_date(date_text)
            if row_date is None:
                continue

            dam_species = set(FPC_DAMS[current_dam_key]["species_count_cols"].keys())

            for col, species_key in col_to_species.items():
                if col >= len(cells):
                    continue
                count = _parse_count(cells[col].get_text(strip=True))
                if count is None:
                    continue

                if species_key not in dam_species:
                    continue
                # Note: chinook spring/summer/fall columns all map to the
                # consolidated "chinook" key, so a single (dam, date) may emit
                # multiple chinook CountRecords. Downstream consumers
                # (cumulative_through, front_of_run) sum across records, which
                # is exactly the aggregation we want.
                records.append(CountRecord(
                    dam_key=current_dam_key,
                    species=species_key,
                    date=row_date,
                    count=count,
                ))

    return records


def fetch_counts() -> list[CountRecord]:
    """Fetch and parse FPC adult count page. Caller handles caching."""
    return parse_adult_counts(fetch(URL))
