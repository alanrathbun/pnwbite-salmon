from datetime import date
from pathlib import Path

import pytest

from sources.creel import parse_wdfw_pdf, parse_odfw_html, CreelEntry

FIX = Path(__file__).parent.parent / "fixtures/creel"

VALID_SPECIES = {
    "chinook", "chinook", "chinook",
    "sockeye", "coho", "steelhead", "steelhead",
}


# ---------------------------------------------------------------------------
# WDFW PDF tests
# ---------------------------------------------------------------------------

def test_parse_wdfw_pdf_yields_entries():
    pdf_path = FIX / "wdfw_sample.pdf"
    entries = parse_wdfw_pdf(pdf_path)
    assert entries, "expected at least one entry parsed from the WDFW PDF"
    e = entries[0]
    assert isinstance(e, CreelEntry)
    assert e.authority == "WDFW"
    assert e.species in VALID_SPECIES
    assert e.fish_per_rod is None or e.fish_per_rod >= 0


def test_parse_wdfw_pdf_has_expected_districts():
    """The SW-WA Columbia report always covers Drano Lake and Wind River."""
    entries = parse_wdfw_pdf(FIX / "wdfw_sample.pdf")
    districts = {e.district for e in entries}
    # At least one known Columbia tributary district should be present.
    columbia_districts = {
        "wdfw_drano", "wdfw_wind", "wdfw_klickitat",
        "wdfw_cowlitz", "wdfw_kalama", "wdfw_lewis",
    }
    assert columbia_districts & districts, (
        f"No Columbia tributary districts found; got: {districts}"
    )


def test_parse_wdfw_pdf_has_week_ending():
    """The SW-WA report carries a date header that we parse into week_ending."""
    entries = parse_wdfw_pdf(FIX / "wdfw_sample.pdf")
    with_dates = [e for e in entries if e.week_ending is not None]
    assert with_dates, "expected at least some entries to carry a week_ending date"
    e = with_dates[0]
    assert isinstance(e.week_ending, date)
    # Sanity: must be a plausible recent year.
    assert e.week_ending.year >= 2025


def test_parse_wdfw_pdf_fish_per_rod_range():
    """fish_per_rod values, when present, should be in a plausible range."""
    entries = parse_wdfw_pdf(FIX / "wdfw_sample.pdf")
    with_rate = [e for e in entries if e.fish_per_rod is not None]
    for e in with_rate:
        assert 0.0 <= e.fish_per_rod <= 50.0, (
            f"Implausible fish_per_rod={e.fish_per_rod} for {e}"
        )


# ---------------------------------------------------------------------------
# ODFW HTML tests
# ---------------------------------------------------------------------------

def test_parse_odfw_html_yields_entries():
    html = (FIX / "odfw_sample.html").read_text()
    entries = parse_odfw_html(html)
    # ODFW reports may not always have numeric per-rod data; at minimum we should
    # extract qualitative entries with district + species.
    assert entries, "expected at least one entry parsed from the ODFW page"
    e = entries[0]
    assert e.authority == "ODFW"
    assert e.district


def test_parse_odfw_html_species_valid():
    html = (FIX / "odfw_sample.html").read_text()
    entries = parse_odfw_html(html)
    for e in entries:
        assert e.species in VALID_SPECIES, f"Unexpected species: {e.species}"


def test_parse_odfw_html_has_columbia_district():
    """The Columbia Zone page should always mention Bonneville or Lower Columbia."""
    html = (FIX / "odfw_sample.html").read_text()
    entries = parse_odfw_html(html)
    districts = {e.district for e in entries}
    columbia_districts = {"odfw_bonneville", "odfw_lower_columbia", "odfw_dalles"}
    assert columbia_districts & districts, (
        f"No Columbia pool districts found; got: {districts}"
    )


def test_parse_odfw_html_fish_per_angler_range():
    """fish_per_rod values (fish/angler for ODFW), when present, must be plausible."""
    html = (FIX / "odfw_sample.html").read_text()
    entries = parse_odfw_html(html)
    with_rate = [e for e in entries if e.fish_per_rod is not None]
    for e in with_rate:
        assert 0.0 <= e.fish_per_rod <= 20.0, (
            f"Implausible fish_per_rod={e.fish_per_rod} for {e}"
        )


# ---------------------------------------------------------------------------
# CreelEntry structural tests
# ---------------------------------------------------------------------------

def test_creel_entry_supports_no_data():
    e = CreelEntry(
        authority="WDFW",
        district="hanford",
        species="chinook",
        week_ending=date(2026, 4, 20),
        fish_per_rod=None,
        raw_note="closed",
    )
    assert e.fish_per_rod is None
    assert e.authority == "WDFW"
    assert e.district == "hanford"


def test_creel_entry_immutable():
    """CreelEntry is a frozen dataclass."""
    e = CreelEntry(
        authority="ODFW",
        district="odfw_bonneville",
        species="chinook",
        week_ending=None,
        fish_per_rod=0.45,
    )
    with pytest.raises((AttributeError, TypeError)):
        e.fish_per_rod = 1.0  # type: ignore[misc]


def test_creel_entry_hashable():
    """Frozen dataclass instances can be used in sets."""
    e1 = CreelEntry("WDFW", "wdfw_drano", "chinook", date(2026, 5, 3), 1.2)
    e2 = CreelEntry("WDFW", "wdfw_drano", "chinook", date(2026, 5, 3), 1.2)
    assert e1 == e2
    assert len({e1, e2}) == 1
