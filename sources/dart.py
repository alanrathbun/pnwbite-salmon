"""DART historical run-timing curves.

DART (cbr.washington.edu/dart) publishes 10-year-average daily passage at every
mainstem dam, downloadable as CSV. The query URL uses:

    outputFormat=csv   (plain CSV, not HTML)
    year=<YYYY>        (a real calendar year — the 10yr avg columns are always
                        present as long as avg=1 is passed)
    avg=1              (include *10Yr average columns)
    proj=<DAM>         (e.g. BON, MCN, PRD)
    startdate=1/1
    enddate=12/31

Returned CSV columns (verified May 2026):
    Project, Date (YYYY-MM-DD), Chinook Run, Chin, Chin10Yr, JChin, JChin10Yr,
    Stlhd, Stlhd10Yr, WStlhd, WStlhd10Yr, Sock, Sock10Yr, Coho, Coho10Yr,
    JCoho, JCoho10Yr, Shad, Shad10Yr, …

We derive day-of-year from the Date column and index the daily_avg dict by DOY.
The ``species`` argument controls which *10Yr column to extract; the mapping is
in DART_AVG_COL.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from storage import FileStorage
from utils import fetch

# Most-recent complete year to use as the year parameter when fetching 10yr avgs.
# 2024 is used because it's a leap year (366 days) and has complete data.
_DEFAULT_YEAR = 2024

URL_TEMPLATE = (
    "https://www.cbr.washington.edu/dart/cs/php/rpt/adult_daily.php"
    "?outputFormat=csv&year={year}&proj={dam}&startdate=1%2F1&enddate=12%2F31"
    "&run=&avg=1&span=no"
)

# Map our species keys to the *10Yr column name in DART's CSV output.
DART_AVG_COL: dict[str, str] = {
    "spring_chinook": "Chin10Yr",
    "summer_chinook": "Chin10Yr",
    "fall_chinook": "Chin10Yr",
    "sockeye": "Sock10Yr",
    "coho": "Coho10Yr",
    "summer_steelhead": "Stlhd10Yr",
    "winter_steelhead": "WStlhd10Yr",
}

# Default column for parse_dart_curve when no species is specified.
_DEFAULT_AVG_COL = "Chin10Yr"


@dataclass(frozen=True)
class RuntimingCurve:
    dam_key: str
    species: str
    daily_avg: dict[int, float]  # day-of-year (1-366) -> 10-yr avg count


def parse_dart_curve(
    csv_text: str,
    *,
    dam_key: str = "",
    species: str = "",
    col_hint: str = "",
) -> RuntimingCurve:
    """Parse a DART adult_daily CSV into a RuntimingCurve.

    Parameters
    ----------
    csv_text:
        Raw CSV content from the DART adult_daily endpoint.
    dam_key:
        Optional dam identifier (e.g. "BON") stored on the returned curve.
    species:
        Optional species key (e.g. "spring_chinook") used to select the
        correct *10Yr column.  When omitted, ``col_hint`` is tried; failing
        that, the first *10Yr column found is used.
    col_hint:
        Explicit *10Yr column name override (e.g. "Chin10Yr").
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[dict[str, str]] = []
    try:
        for row in reader:
            rows.append(row)
    except Exception:
        pass

    if not rows:
        return RuntimingCurve(dam_key=dam_key, species=species, daily_avg={})

    # Determine which 10Yr column to use.
    fieldnames = reader.fieldnames or list(rows[0].keys())
    avg_col = _pick_avg_col(fieldnames, species=species, col_hint=col_hint)
    date_col = _pick_date_col(fieldnames)

    out: dict[int, float] = {}
    for row in rows:
        doy = _row_to_doy(row, date_col)
        if doy is None:
            continue
        cell = row.get(avg_col)
        if cell is None:
            continue
        raw = cell.strip()
        if not raw:
            continue
        try:
            val = float(raw.replace(",", ""))
        except ValueError:
            continue
        if 1 <= doy <= 366:
            out[doy] = val

    return RuntimingCurve(dam_key=dam_key, species=species, daily_avg=out)


def _pick_avg_col(fieldnames: list[str], *, species: str, col_hint: str) -> str:
    """Return the best *10Yr column name given species/col_hint context."""
    # Explicit hint wins.
    if col_hint and col_hint in fieldnames:
        return col_hint
    # Species mapping wins.
    if species and species in DART_AVG_COL:
        candidate = DART_AVG_COL[species]
        if candidate in fieldnames:
            return candidate
    # Default Chinook column.
    if _DEFAULT_AVG_COL in fieldnames:
        return _DEFAULT_AVG_COL
    # Last resort: first column whose name ends in "10Yr" (case-insensitive).
    for f in fieldnames:
        if f.strip().lower().endswith("10yr"):
            return f
    # Fall through: return last column (positional fallback).
    return fieldnames[-1]


def _pick_date_col(fieldnames: list[str]) -> str:
    """Return the column name for the Date field."""
    for f in fieldnames:
        if f.strip().lower() == "date":
            return f
    # Fallback: second column (index 1) which is Date in the known schema.
    if len(fieldnames) >= 2:
        return fieldnames[1]
    return fieldnames[0]


def _row_to_doy(row: dict[str, str], date_col: str) -> int | None:
    """Convert a date-column value (YYYY-MM-DD) to day-of-year (1-366)."""
    cell = row.get(date_col)
    if cell is None:
        return None
    raw = cell.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            d = datetime.strptime(raw, fmt).date()
            return d.timetuple().tm_yday
        except ValueError:
            continue
    return None


def daily_average_for(curve: RuntimingCurve, d: date) -> float | None:
    """Return the 10-yr average count for the day-of-year corresponding to *d*."""
    doy = d.timetuple().tm_yday
    return curve.daily_avg.get(doy)


def fetch_curve(dam_key: str, species: str, *, year: int = _DEFAULT_YEAR) -> RuntimingCurve:
    """Download and parse a DART 10-yr-average curve for *dam_key* + *species*."""
    raw = fetch(URL_TEMPLATE.format(dam=dam_key, year=year))
    return parse_dart_curve(raw, dam_key=dam_key, species=species)


def fetch_or_cached(
    dam_key: str, species: str, *, storage: FileStorage, year: int = _DEFAULT_YEAR
) -> RuntimingCurve:
    """Return cached curve, or fetch and store it.

    Cache is keyed by ``{dam_key}_{species}``.  Delete
    ``.dart_runtiming_cache.json`` to force a refresh.

    Cache writes go through ``storage.update_json`` so concurrent workers
    populating different (dam, species) pairs in fetch_all's
    ThreadPoolExecutor don't lose entries via read-modify-write races. The
    HTTP fetch runs outside the lock so other threads aren't blocked on
    network I/O.
    """
    cache: dict[str, dict[str, float]] = storage.read_json("dart_runtiming") or {}
    key = f"{dam_key}_{species}"
    if key in cache:
        return RuntimingCurve(
            dam_key=dam_key,
            species=species,
            daily_avg={int(k): v for k, v in cache[key].items()},
        )
    curve = fetch_curve(dam_key, species, year=year)
    serialized = {str(k): v for k, v in curve.daily_avg.items()}
    storage.update_json("dart_runtiming", lambda c: {**(c or {}), key: serialized})
    return curve
