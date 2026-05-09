"""Tests for the WDFW pamphlet section-status lookup."""
from datetime import date

import pytest

from regs.wdfw_pamphlet import (
    status_for_section,
    status_for_all_sections,
    _date_in_range,
    load_pamphlet,
    RegStatus,
)


def test_load_pamphlet_returns_sections():
    sections = load_pamphlet()
    assert sections, "expected non-empty pamphlet sections"
    ids = {s["id"] for s in sections}
    assert "mcnary_tailrace" in ids
    assert "mcnary_pool" in ids


def test_mcnary_tailrace_closed_in_may():
    """User-reported bug: McNary Tailrace shown as open on May 8 2026 but is CLOSED."""
    st = status_for_section("mcnary_tailrace", today=date(2026, 5, 8))
    assert st is not None
    assert st.open is False
    assert "closed" in st.reason.lower() or "Closed" in st.reason


def test_mcnary_tailrace_open_in_august():
    st = status_for_section("mcnary_tailrace", today=date(2026, 8, 15))
    assert st is not None
    assert st.open is True


def test_mcnary_tailrace_closed_late_september():
    """Sept 18-30 is a closure inside an otherwise-open fall season."""
    st = status_for_section("mcnary_tailrace", today=date(2026, 9, 25))
    assert st is not None
    assert st.open is False


def test_mcnary_pool_open_in_january():
    """McNary Pool (above the dam) is OPEN Jan 1 - Mar 31, unlike McNary Tailrace."""
    st = status_for_section("mcnary_pool", today=date(2026, 2, 1))
    assert st is not None
    assert st.open is True


def test_mcnary_pool_closed_in_april():
    """McNary Pool is closed Apr 1 - Jun 15."""
    st = status_for_section("mcnary_pool", today=date(2026, 5, 8))
    assert st is not None
    assert st.open is False


def test_unknown_section_returns_none():
    """Unknown section_id should return None so caller can fall back."""
    assert status_for_section("nonexistent_section") is None


def test_implicit_closure_when_no_matching_range():
    """Hanford CRC 535 has no salmon retention period in May (only Jul + Aug-Dec).
    Implicit closure for salmon retention."""
    st = status_for_section(
        "hanford_ringold_wasteway_to_ringold_hatchery",
        today=date(2026, 5, 8),
    )
    assert st is not None
    assert st.open is False


def test_hanford_open_in_september():
    """Hanford CRC 535 IS open Aug 16 - Dec 31."""
    st = status_for_section(
        "hanford_ringold_wasteway_to_ringold_hatchery",
        today=date(2026, 9, 15),
    )
    assert st is not None
    assert st.open is True


def test_priest_rapids_tail_closed_in_may():
    """CRC 537 lists Jul-Aug + Sep-Oct only; May is implicitly closed for salmon."""
    st = status_for_section(
        "priest_rapids_to_wanapum",
        today=date(2026, 5, 8),
    )
    assert st is not None
    assert st.open is False


def test_status_for_all_sections_returns_dict():
    out = status_for_all_sections(today=date(2026, 5, 8))
    assert isinstance(out, dict)
    assert "mcnary_tailrace" in out
    assert out["mcnary_tailrace"].open is False


def test_date_in_range_simple():
    assert _date_in_range(date(2026, 5, 15), "05-01..05-31")
    assert _date_in_range(date(2026, 5, 1), "05-01..05-31")
    assert _date_in_range(date(2026, 5, 31), "05-01..05-31")
    assert not _date_in_range(date(2026, 6, 1), "05-01..05-31")
    assert not _date_in_range(date(2026, 4, 30), "05-01..05-31")


def test_date_in_range_wraparound():
    """Year-wraparound (Dec 1 - Jan 31) covers both months."""
    assert _date_in_range(date(2026, 12, 15), "12-01..01-31")
    assert _date_in_range(date(2026, 1, 15), "12-01..01-31")
    assert not _date_in_range(date(2026, 6, 15), "12-01..01-31")


def test_pamphlet_filename():
    from regs.wdfw_pamphlet import pamphlet_filename
    assert pamphlet_filename() == "25WAFW_LR7.pdf"


def test_pamphlet_version():
    from regs.wdfw_pamphlet import pamphlet_version
    assert pamphlet_version() == "2025-2026"


# ---------------------------------------------------------------------------
# Mid-Columbia mainstem regression tests (Bonneville Dam to McNary Dam).
# One closed + one open assertion per new section_id. Spring (May 8) is
# closed almost everywhere on the mainstem; Aug 15 / Sept 5 fall windows
# are open in the dam-pool sections (CRC 527, 529, 531).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("section_id,today,expected_open", [
    # Bonneville Dam to Hood River Bridge (CRC 527)
    ("bonneville_to_hood_river", date(2026, 5, 8), False),    # Apr 1-Jun 15 closed
    ("bonneville_to_hood_river", date(2026, 8, 15), True),    # Aug 1-Sept 17 open

    # Hood River Bridge to Tower Island power lines (CRC 527)
    ("hood_river_to_tower_island", date(2026, 5, 8), False),  # closed
    ("hood_river_to_tower_island", date(2026, 8, 15), True),  # open

    # Tower Island power lines to Port of The Dalles boat ramp (CRC 527)
    ("tower_island_to_dalles_ramp", date(2026, 5, 8), False),
    ("tower_island_to_dalles_ramp", date(2026, 8, 15), True),

    # Port of The Dalles boat ramp to Hwy 197 Bridge (CRC 527)
    ("dalles_ramp_to_hwy197", date(2026, 5, 8), False),
    ("dalles_ramp_to_hwy197", date(2026, 8, 15), True),

    # WA shore Hwy 197 Bridge to navigation lock wall (CRC 527, bank-only).
    # Salmon table continues across a page-column break (header on p55 right
    # column, table on p56 left column). Same fall windows as adjacent CRC 527
    # sections, with bank-only restriction on WA shore.
    ("hwy197_to_dalles_lock", date(2026, 5, 8), False),   # Apr 1-Jun 15 closed
    ("hwy197_to_dalles_lock", date(2026, 8, 15), True),   # Aug 1-Sept 17 open

    # The Dalles Dam tailrace to John Day Pool (CRC 529)
    ("dalles_dam_to_jda_pool", date(2026, 5, 8), False),
    ("dalles_dam_to_jda_pool", date(2026, 8, 15), True),       # Aug 1-Aug 31 open

    # Rufus to John Day Dam (CRC 529)
    ("rufus_to_jda_dam", date(2026, 5, 8), False),
    ("rufus_to_jda_dam", date(2026, 8, 15), True),

    # John Day Dam tailrace 3,000'-400' (CRC 529)
    ("jda_dam_tailrace", date(2026, 5, 8), False),
    ("jda_dam_tailrace", date(2026, 8, 15), True),

    # John Day Dam to Patterson Ferry Rd / mid-Columbia pool (CRC 531)
    ("jda_dam_to_patterson", date(2026, 5, 8), False),
    ("jda_dam_to_patterson", date(2026, 8, 15), True),

    # Patterson Ferry Rd to I-82/Hwy 395 Bridge (CRC 531, Maryhill area)
    ("patterson_to_i82_395", date(2026, 5, 8), False),
    ("patterson_to_i82_395", date(2026, 8, 15), True),

    # I-82/Hwy 395 Bridge to McNary Dam (CRC 531)
    ("i82_395_to_mcnary_dam", date(2026, 5, 8), False),
    ("i82_395_to_mcnary_dam", date(2026, 8, 15), True),
])
def test_mid_columbia_mainstem_status(section_id, today, expected_open):
    st = status_for_section(section_id, today=today)
    assert st is not None, f"section {section_id} missing from YAML"
    assert st.open is expected_open, (
        f"section {section_id} on {today.isoformat()}: "
        f"expected open={expected_open}, got open={st.open} (reason: {st.reason})"
    )


def test_mid_columbia_mainstem_late_september_closure():
    """Sept 18-30 is an explicit closure inside otherwise-open fall season for
    the CRC 527/529/531 sections. Spot-check a couple."""
    for sid in ("bonneville_to_hood_river", "jda_dam_to_patterson",
                "i82_395_to_mcnary_dam"):
        st = status_for_section(sid, today=date(2026, 9, 25))
        assert st is not None, f"section {sid} missing from YAML"
        assert st.open is False, (
            f"section {sid} should be closed Sept 25 (Sept 18-30 closure)"
        )


# ---------------------------------------------------------------------------
# Mid-Columbia tributaries regression tests (Bonneville Dam to McNary Dam,
# WA-jurisdiction tribs only).
#
# One open + one closed assertion per encoded section_id, except:
#   - little_white_salmon_*  (purely-closed sections for salmon: two closed
#     dates on different months are used).
#   - rock_creek_klickitat_lower (encoded with empty salmon list because the
#     pamphlet says it "inherits" rules from the adjacent Columbia River
#     stretch — v1 encoder cannot reflect this; default-closed is the
#     conservative choice. Two closed dates are used.)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("section_id,today,expected_open", [
    # Drano Lake CRC 618 (downstream of LWS NFH, upstream of Hwy 14 Bridge).
    # Salmon table on PDF p82 (printed): Jan 1-Mar 15 open (steelhead-only),
    # Mar 16-Jun 30 open, Jul 1-Jul 31 open, Aug 1-Oct 31 open, Nov 1-Dec 31
    # open. Effectively year-round open with seasonal limits.
    ("drano_lake", date(2026, 5, 8), True),    # Mar 16-Jun 30 spring chinook
    ("drano_lake", date(2026, 12, 31), True),  # Nov 1-Dec 31 open
    # NOTE: Drano has no implicit-closed period — the table covers all 12 months.
    # No "expected_open=False" case is plausible from the pamphlet text.

    # Drano Lake CRC 618 west arm (west of easternmost pillar of Hwy 14 Bridge).
    # Same effective table as the main Drano section.
    ("drano_lake_west_arm", date(2026, 5, 8), True),
    ("drano_lake_west_arm", date(2026, 12, 31), True),

    # Wind River mouth to Hwy 14 Bridge CRC 680 (lower Wind below the dam).
    # Mar 16-Jun 30 open, Jul 1-Sep 30 open, Oct 1-Oct 31 open, Nov 1-Mar 15
    # open (steelhead-only). Year-round open with seasonal restrictions.
    ("wind_river_mouth_to_hwy14", date(2026, 5, 8), True),    # spring open
    ("wind_river_mouth_to_hwy14", date(2026, 8, 15), True),   # summer open
    # Same table for Hwy 14 Bridge to 400' below Shipherd Falls CRC 679.
    ("wind_river_hwy14_to_shipherd", date(2026, 5, 8), True),
    ("wind_river_hwy14_to_shipherd", date(2026, 8, 15), True),
    # Wind River 100' above Shipherd Falls to 400' below Coffer Dam CRC 677.
    # Salmon and hatchery steelhead May 1-Jun 30 only.
    ("wind_river_shipherd_to_coffer", date(2026, 5, 8), True),    # May open
    ("wind_river_shipherd_to_coffer", date(2026, 8, 15), False),  # implicit closed
    # Wind River 100' above Coffer Dam to 800 yards below Carson NFH CRC 677.
    ("wind_river_coffer_to_carson", date(2026, 5, 8), True),
    ("wind_river_coffer_to_carson", date(2026, 8, 15), False),

    # Klickitat River mouth (BNSF Railroad Bridge) to Fisher Hill Bridge
    # CRC 607. Salmon Sat before Memorial Day-July 31 + Aug 1-Jan 31; Apr 1
    # to Fri before Memorial Day open Mon/Wed/Sat only for salmon+steelhead.
    # Effectively closed only Feb 1-Mar 31 (between the two windows).
    ("klickitat_mouth_to_fisher_hill", date(2026, 5, 13), True),   # Wed in Apr 1-May 22 Mon/Wed/Sat window — encoded open (matcher does not enforce day-of-week)
    ("klickitat_mouth_to_fisher_hill", date(2026, 9, 15), True),   # Aug 1-Jan 31
    ("klickitat_mouth_to_fisher_hill", date(2026, 3, 1), False),   # implicit Feb-Mar closed

    # Klickitat River 400' upstream from #5 fishway (Lyle Falls) to below
    # Klickitat Salmon Hatchery CRC 608. Salmon Sat before Memorial Day-Jul 31
    # + Aug 1-Nov 30. Effectively closed Dec 1 - Sat before Memorial Day.
    ("klickitat_lyle_to_hatchery", date(2026, 9, 15), True),   # Aug 1-Nov 30
    ("klickitat_lyle_to_hatchery", date(2026, 3, 1), False),   # implicit closed

    # Little White Salmon River — Drano markers to NFH intake CRC (no): the
    # only mainstem section on the WA side is CLOSED WATERS (no salmon ever).
    # Encoded with empty salmon list; conservative-closed all year.
    ("little_white_salmon_lower", date(2026, 5, 8), False),
    ("little_white_salmon_lower", date(2026, 9, 15), False),

    # Little White Salmon River upstream of NFH intake — trout-only, no salmon.
    ("little_white_salmon_upper", date(2026, 5, 8), False),
    ("little_white_salmon_upper", date(2026, 9, 15), False),

    # White Salmon River mouth (BNSF RR Bridge) to County Rd Bridge below
    # former powerhouse CRC 508. Salmon Apr 1-Jun 30 + Jul 1-Jul 31 +
    # Aug 1-Oct 31 + Nov 1-Mar 31 — year-round open in some form.
    ("white_salmon_lower", date(2026, 5, 8), True),    # Apr 1-Jun 30
    ("white_salmon_lower", date(2026, 9, 15), True),   # Aug 1-Oct 31

    # White Salmon County Rd Bridge to 400' below Big Brother Falls CRC 508.
    # Salmon Sat before Memorial Day-Jul 31 + Aug 1-Oct 31. Closed Nov-pre-MD.
    ("white_salmon_upper", date(2026, 9, 15), True),   # Aug 1-Oct 31
    ("white_salmon_upper", date(2026, 3, 1), False),   # implicit closed

    # Rock Creek (Klickitat Co.) mouth to ACOE Park: pamphlet says rules
    # "are the same as those in the adjacent portion of the Columbia River."
    # v1 encoder cannot dereference adjacent sections — encoded with empty
    # list (default-closed is the safe fallback). Two closed dates.
    ("rock_creek_klickitat_lower", date(2026, 5, 8), False),
    ("rock_creek_klickitat_lower", date(2026, 9, 15), False),

    # Rock Creek (Skamania Co.) mouth to falls (~RM 1) CRC 632. Salmon
    # Aug 1-Dec 31. Closed Jan 1-Jul 31.
    ("rock_creek_skamania_lower", date(2026, 9, 15), True),    # Aug 1-Dec 31
    ("rock_creek_skamania_lower", date(2026, 5, 8), False),    # implicit closed
])
def test_mid_columbia_tribs_status(section_id, today, expected_open):
    st = status_for_section(section_id, today=today)
    assert st is not None, f"section {section_id} missing from YAML"
    assert st.open is expected_open, (
        f"section {section_id} on {today.isoformat()}: "
        f"expected open={expected_open}, got open={st.open} (reason: {st.reason})"
    )
