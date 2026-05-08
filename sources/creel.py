"""Creel scrapers.

WDFW: weekly creel summary PDFs (southwest-Washington / Columbia River tributary format).
      The actual document is prose-based, not tabular. Each location appears as a
      sentence fragment:
        "<Location> — <N> bank anglers kept <x> Chinook [...]"
      or
        "<N> boats/<M> rods kept <x> Chinook [...]"
      We extract district, species, angler effort, and kept/released counts, then
      compute fish_per_rod when boat-rod data is present.

ODFW: HTML pages for the Columbia Zone with prose updates per pool/location.
      Section headings (SALMON, STEELHEAD, etc.) delimit species blocks.
      Each paragraph has the form "<Location>: <status>. <N> Chinook kept for
      <M> anglers."  We extract species and kept count per angler when available.

Both yield CreelEntry records with authority + district + species + week_ending +
optional fish_per_rod. Entries with no numeric value are still useful (the run-
timing engine uses presence/absence as a weak signal).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Species classification
# ---------------------------------------------------------------------------

SPECIES_KEYWORDS: dict[str, str] = {
    "spring chinook": "spring_chinook",
    "spring kings": "spring_chinook",
    "summer chinook": "summer_chinook",
    "summer kings": "summer_chinook",
    "fall chinook": "fall_chinook",
    "fall kings": "fall_chinook",
    "chinook": "spring_chinook",  # default to spring outside obvious fall context
    "kings": "fall_chinook",      # ambiguous; default to fall outside spring period
    "sockeye": "sockeye",
    "coho": "coho",
    "silvers": "coho",
    "summer steelhead": "summer_steelhead",
    "winter steelhead": "winter_steelhead",
    "steelhead": "summer_steelhead",  # default; refined by date if needed
}

# Regexes for effort / catch extraction from WDFW prose
_BOATS_RODS_RE = re.compile(r"(\d+)\s+boats?\s*/\s*(\d+)\s+rods?", re.IGNORECASE)
_KEPT_N_RE = re.compile(r"kept\s+(\d+)", re.IGNORECASE)
# WDFW date line: "Date: May 4, 2026"
_DATE_LINE_RE = re.compile(r"Date:\s+(\w+\s+\d+,?\s+\d{4})", re.IGNORECASE)
# ODFW catch: "23 Chinook kept for 50 bank anglers" or "23 Chinook kept for 19 boats (51 anglers)"
_ODFW_KEPT_ANGLERS_RE = re.compile(
    r"(\d+)\s+(?:Chinook|steelhead|coho|sockeye|jack\s+Chinook)[^\n]*kept\s+for\s+(?:\d+\s+boats?\s*\(\s*)?(\d+)\s+anglers",
    re.IGNORECASE,
)
_PER_ROD_RE = re.compile(r"(\d*\.?\d+)\s*fish\s*(?:per|/)\s*(?:rod|angler)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreelEntry:
    authority: str          # "WDFW" or "ODFW"
    district: str           # location slug
    species: str            # e.g. "spring_chinook"
    week_ending: date | None
    fish_per_rod: float | None
    raw_note: str | None = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _classify_species(text: str) -> str | None:
    """Return species key for text using longest-match keywords, or None."""
    t = text.lower()
    # Sort by keyword length descending so "spring chinook" beats "chinook".
    for kw in sorted(SPECIES_KEYWORDS, key=len, reverse=True):
        if kw in t:
            return SPECIES_KEYWORDS[kw]
    return None


def _parse_date_str(s: str) -> date | None:
    s = s.strip().replace(",", "")
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# WDFW PDF parser
# ---------------------------------------------------------------------------

# Map location keywords to district slugs.
_WDFW_LOCATION_MAP: list[tuple[str, str]] = [
    ("drano", "wdfw_drano"),
    ("wind river", "wdfw_wind"),
    ("klickitat", "wdfw_klickitat"),
    ("cowlitz", "wdfw_cowlitz"),
    ("kalama", "wdfw_kalama"),
    ("lewis river", "wdfw_lewis"),
    ("snake", "wdfw_snake"),
    ("lower granite", "wdfw_snake"),
    ("wawawai", "wdfw_snake"),
    ("mcnary", "wdfw_mcnary"),
    ("hanford", "wdfw_hanford"),
    ("wenatchee", "wdfw_upper_columbia"),
    ("rocky reach", "wdfw_upper_columbia"),
    ("wells", "wdfw_upper_columbia"),
    ("brewster", "wdfw_upper_columbia"),
    ("mid columbia", "wdfw_mid_columbia"),
    ("mid-columbia", "wdfw_mid_columbia"),
    ("the dalles", "wdfw_mid_columbia"),
    ("john day", "wdfw_mid_columbia"),
    ("bonneville", "wdfw_lower_columbia"),
    ("columbia river", "wdfw_lower_columbia"),
]


def _wdfw_district(line: str) -> str | None:
    low = line.lower()
    for keyword, slug in _WDFW_LOCATION_MAP:
        if keyword in low:
            return slug
    return None


def _wdfw_fish_per_rod(line: str) -> float | None:
    """Compute fish/rod from boat creel sentence if both kept count and rod count present."""
    # First try an explicit "X fish per rod" phrase.
    m = _PER_ROD_RE.search(line)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    # Otherwise derive from "N boats/M rods kept K Chinook"
    m_br = _BOATS_RODS_RE.search(line)
    m_k = _KEPT_N_RE.search(line)
    if m_br and m_k:
        rods = int(m_br.group(2))
        kept = int(m_k.group(1))
        if rods > 0:
            return round(kept / rods, 4)
    return None


def _is_location_start(line: str) -> bool:
    """Return True if the line begins a new creel location block (has an em-dash)."""
    return "—" in line or (" - " in line and re.search(r"river|lake|creek|pool", line, re.I) is not None)


def parse_wdfw_pdf(path: Path) -> list[CreelEntry]:
    """Parse WDFW SW-Washington Columbia River tributary creel PDF.

    The PDF is prose-based. Each location produces one or two sentences that
    may wrap across multiple PDF text lines.  We first join continuation lines
    to reconstruct full location sentences, then parse each joined block.
    """
    pages_text: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            pages_text.append(t)
    full_text = "\n".join(pages_text)

    # Extract report date from "Date: May 4, 2026" header.
    week_end: date | None = None
    dm = _DATE_LINE_RE.search(full_text)
    if dm:
        week_end = _parse_date_str(dm.group(1))

    # --- Pass 1: join wrapped location lines ---
    # A location line starts with a proper noun (capitalised) followed by " — ".
    # Continuation lines are lower-case-starting or continuation words.
    raw_lines = full_text.splitlines()
    joined_blocks: list[str] = []
    current_block: str = ""
    current_species_ctx: str | None = None

    for raw in raw_lines:
        line = raw.strip()
        if not line:
            if current_block:
                joined_blocks.append(current_block)
                current_block = ""
            continue

        # Section header detection: short, no em-dash or catch words.
        if len(line) < 60 and not re.search(r"—|kept|released|boat|angler|rods?", line, re.I):
            if current_block:
                joined_blocks.append(current_block)
                current_block = ""
            joined_blocks.append(line)
            continue

        if _is_location_start(line):
            # Flush previous block.
            if current_block:
                joined_blocks.append(current_block)
            current_block = line
        else:
            # Continuation of current location block (wrapped line).
            if current_block:
                current_block = current_block + " " + line
            else:
                # Free-floating text (intro paragraphs, etc.) — discard.
                pass

    if current_block:
        joined_blocks.append(current_block)

    # --- Pass 2: extract entries from joined blocks ---
    entries: list[CreelEntry] = []

    for block in joined_blocks:
        block = block.strip()
        if not block:
            continue

        # Update species context from section headings.
        if not _is_location_start(block) and len(block) < 60:
            sp = _classify_species(block)
            if sp:
                current_species_ctx = sp
            continue

        district = _wdfw_district(block)
        if not district:
            continue

        # Classify species: prefer chinook when both chinook and steelhead appear
        # in the same block (chinook is nearly always the primary target species;
        # steelhead mentions are incidental bycatch notes).
        t = block.lower()
        has_chinook = "chinook" in t or "king" in t
        has_steelhead = "steelhead" in t
        if has_chinook and has_steelhead:
            # Count occurrences to pick dominant species.
            n_chinook = t.count("chinook") + t.count("king")
            n_steel = t.count("steelhead")
            if n_chinook >= n_steel:
                species: str | None = "spring_chinook"
            else:
                species = "summer_steelhead"
        else:
            species = _classify_species(block) or current_species_ctx

        if not species:
            species = "spring_chinook"  # default for SWWA spring season

        fish_per_rod = _wdfw_fish_per_rod(block)

        entries.append(CreelEntry(
            authority="WDFW",
            district=district,
            species=species,
            week_ending=week_end,
            fish_per_rod=fish_per_rod,
            raw_note=block[:240],
        ))

    return entries


# ---------------------------------------------------------------------------
# ODFW HTML parser
# ---------------------------------------------------------------------------

# Map location keywords to district slugs (ODFW).
_ODFW_LOCATION_MAP: list[tuple[str, str]] = [
    ("lower columbia", "odfw_lower_columbia"),
    ("bonneville pool", "odfw_bonneville"),
    ("bonneville", "odfw_bonneville"),
    ("the dalles pool", "odfw_dalles"),
    ("the dalles", "odfw_dalles"),
    ("john day pool", "odfw_john_day"),
    ("john day", "odfw_john_day"),
    ("umatilla", "odfw_mid_columbia"),
    ("boardman", "odfw_mid_columbia"),
    ("snake", "odfw_snake"),
    ("columbia", "odfw_lower_columbia"),  # fallback generic Columbia mention
]


def _odfw_district(text: str) -> str | None:
    t = text.lower()
    for keyword, slug in _ODFW_LOCATION_MAP:
        if keyword in t:
            return slug
    return None


def _odfw_fish_per_angler(text: str) -> float | None:
    """Extract fish/angler from ODFW prose when kept + angler counts are present."""
    # Explicit "X fish per rod" phrase.
    m = _PER_ROD_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    # Derive from "N Chinook kept for M anglers" (or boats with M anglers in parens).
    # Look for patterns like "23 Chinook kept for 50 bank anglers" or
    # "16 Chinook kept, and one steelhead released for 19 boats (51 anglers)"
    kept_m = re.search(r"\b(\d+)\s+(?:Chinook|steelhead|coho|sockeye)[^\n.]*?kept", text, re.I)
    anglers_m = re.search(
        r"kept[^.]*?\bfor\s+(?:\d+\s+boats?\s*\(\s*)?(\d+)\s+(?:bank\s+)?anglers",
        text, re.I
    )
    if kept_m and anglers_m:
        kept = int(kept_m.group(1))
        anglers = int(anglers_m.group(1))
        if anglers > 0:
            return round(kept / anglers, 4)
    return None


def parse_odfw_html(html: str) -> list[CreelEntry]:
    """Parse ODFW Columbia Zone fishing report HTML.

    The page has a prose-based recreation report with paragraphs such as:
      "<Location>: <status>. <N> Chinook kept for <M> anglers."
    We find paragraphs under the main content and extract species + district +
    optional per-angler catch rate.
    """
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main") or soup.find("article") or soup.body

    entries: list[CreelEntry] = []
    seen: set[tuple[str, str]] = set()  # (district, species) dedup

    current_species: str | None = None

    # Walk all block elements in document order.
    for el in main.find_all(["p", "li", "h2", "h3", "h4", "strong"]):
        text = el.get_text(" ", strip=True)
        if not text or len(text) < 10:
            continue

        # Detect species-section heading (all-caps or known phrases).
        if el.name in ("h2", "h3", "h4", "strong") or (
            el.name == "p" and text.isupper() and len(text) < 80
        ):
            sp = _classify_species(text)
            if sp:
                current_species = sp
            continue

        # Skip non-salmon paragraphs (sturgeon, walleye, etc.).
        if any(
            kw in text.lower()
            for kw in ("sturgeon", "walleye", "pikeminnow", "smelt", "regulation")
        ):
            # Only skip if no salmon/steelhead keyword present
            if not any(
                kw in text.lower()
                for kw in ("chinook", "coho", "sockeye", "steelhead", "salmon")
            ):
                continue

        district = _odfw_district(text)
        if not district:
            continue

        species = _classify_species(text) or current_species
        if not species:
            continue

        # Deduplicate (district, species) keeping first occurrence (highest-priority paragraph).
        key = (district, species)
        if key in seen:
            continue
        seen.add(key)

        fish_per_angler = _odfw_fish_per_angler(text)

        entries.append(CreelEntry(
            authority="ODFW",
            district=district,
            species=species,
            week_ending=None,
            fish_per_rod=fish_per_angler,
            raw_note=text[:240],
        ))

    return entries
