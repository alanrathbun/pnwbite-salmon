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


def test_pamphlet_expires():
    from regs.wdfw_pamphlet import pamphlet_expires
    assert pamphlet_expires() == date(2026, 6, 30)


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


# ---------------------------------------------------------------------------
# Upper Columbia mainstem regression tests (Wanapum Dam to Chief Joseph Dam).
# Encoded from PDF page 62 (printed page 60) of 25WAFW_LR7.pdf. Sections
# proceed downstream-to-upstream from Wanapum Dam tailrace upstream to the
# Chief Joseph Dam tailrace CLOSED WATERS zone (which is NOT encoded — see
# A2/A3 precedent). Above Chief Joseph Dam = Lake Roosevelt (lakes section,
# not part of the Columbia mainstem rivers regs).
#
# Salmon tables on these sections share a common pattern: short summer-only
# windows (Jul 1-Aug 31 or Jul 16-Aug 31), plus a Sept 1-Oct 15 follow-on
# window for the two pool sections immediately above Wanapum Dam (CRC 539).
# All other dates are implicitly closed for salmon retention.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("section_id,today,expected_open", [
    # Wanapum Dam to Rock Island Dam (CRC 539). Salmon Jul 1-Aug 31 +
    # Sept 1-Oct 15. Same pool above Wanapum, two retention windows.
    ("wanapum_to_rock_island", date(2026, 5, 8), False),     # implicit closed
    ("wanapum_to_rock_island", date(2026, 8, 15), True),     # Jul 1-Aug 31 open
    ("wanapum_to_rock_island", date(2026, 9, 30), True),     # Sept 1-Oct 15 open

    # Rock Island Dam to Rocky Reach Dam (CRC 541). Salmon Jul 1-Aug 31 only.
    # No Sept window (unlike the section immediately downstream).
    ("rock_island_to_rocky_reach", date(2026, 5, 8), False),
    ("rock_island_to_rocky_reach", date(2026, 8, 15), True),

    # Rocky Reach Dam to Wells Dam (CRC 543). Salmon Jul 1-Aug 31 only.
    ("rocky_reach_to_wells", date(2026, 5, 8), False),
    ("rocky_reach_to_wells", date(2026, 8, 15), True),

    # Wells Dam to Hwy 173 Bridge at Brewster (CRC 545). Salmon
    # Jul 16-Aug 31 — note the LATER start (Jul 16, not Jul 1) — this is
    # the upstream-most CRC 545 sub-area with the narrowest window.
    ("wells_to_brewster", date(2026, 5, 8), False),         # implicit closed
    ("wells_to_brewster", date(2026, 7, 1), False),         # before Jul 16 start
    ("wells_to_brewster", date(2026, 8, 15), True),         # Jul 16-Aug 31 open

    # Hwy 173 Bridge at Brewster to Hwy 17 (CRC 545). Salmon Jul 1-Aug 31.
    ("brewster_to_hwy17", date(2026, 5, 8), False),
    ("brewster_to_hwy17", date(2026, 8, 15), True),

    # Hwy 17 Bridge to Foster Creek / Chief Joseph Dam tailrace (CRC 545).
    # Salmon Jul 1-Aug 31. Year-round closed to fishing from the Okanogan
    # shore (encoded as note; matcher does not enforce shore-side restrictions).
    ("hwy17_to_foster_creek", date(2026, 5, 8), False),
    ("hwy17_to_foster_creek", date(2026, 8, 15), True),
])
def test_upper_columbia_mainstem_status(section_id, today, expected_open):
    st = status_for_section(section_id, today=today)
    assert st is not None, f"section {section_id} missing from YAML"
    assert st.open is expected_open, (
        f"section {section_id} on {today.isoformat()}: "
        f"expected open={expected_open}, got open={st.open} (reason: {st.reason})"
    )


# ---------------------------------------------------------------------------
# Upper Columbia tributaries regression tests (Wenatchee, Entiat, Methow,
# Okanogan, Similkameen). Encoded from PDF pages 62-76 (printed) of
# 25WAFW_LR7.pdf. These tribs are notable because the *pamphlet itself*
# does not list any salmon retention period — salmon retention on the
# upper Columbia tribs is opened via in-season WDFW emergency rule, not
# the standing pamphlet. Per A3 precedent (little_white_salmon_*,
# rock_creek_klickitat_lower) and the plan's lesson #7
# ("year-round-closed tributaries: encode salmon_hatchery_steelhead: []
# with explanatory comment"), every upper-Columbia trib section is
# encoded with an empty salmon list — default-closed is the conservative
# fallback, and emergency rules will flip them open in-season via the
# B1-B6 aggregator (not yet implemented).
#
# Each section therefore has TWO closed-date assertions (no plausible
# open date exists from the pamphlet text alone). When emergency-rule
# layering lands (Phase B), those will override these defaults.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("section_id,today,expected_open", [
    # Entiat River CRC 586. PDF p62 (printed). Table lists Whitefish only
    # (Dec 1-Last Day Feb), no salmon row. Two sub-sections share the same
    # whitefish-only structure.
    ("entiat_river_lower", date(2026, 5, 8), False),
    ("entiat_river_lower", date(2026, 9, 15), False),
    ("entiat_river_upper", date(2026, 5, 8), False),
    ("entiat_river_upper", date(2026, 9, 15), False),

    # Methow River CRC 621. PDF p69 (printed). Lower section
    # (mouth-to-Burma-Rd) is CLOSED WATERS. Three middle-river sub-sections
    # (Burma->Gold Creek; Gold Creek->Foghorn Dam; Foghorn->Weeman Bridge)
    # list trout/steelhead/whitefish but NO salmon row.
    ("methow_river_mouth_to_burma", date(2026, 5, 8), False),     # CLOSED WATERS
    ("methow_river_mouth_to_burma", date(2026, 9, 15), False),
    ("methow_river_burma_to_gold_creek", date(2026, 5, 8), False),
    ("methow_river_burma_to_gold_creek", date(2026, 9, 15), False),
    ("methow_river_gold_creek_to_foghorn_dam", date(2026, 5, 8), False),
    ("methow_river_gold_creek_to_foghorn_dam", date(2026, 9, 15), False),
    ("methow_river_foghorn_to_weeman_bridge", date(2026, 5, 8), False),
    ("methow_river_foghorn_to_weeman_bridge", date(2026, 9, 15), False),

    # Okanogan River CRC 627. PDF p70 (printed). Three sub-sections
    # (mouth->Hwy 97; Hwy 97->Malott; Malott->Oroville) and a CLOSED
    # WATERS section (Oroville->Zosel Dam). Pamphlet lists trout,
    # steelhead (closed), other game fish — NO salmon row in any
    # sub-section. Sockeye fishery in the Malott->Oroville stretch
    # opens via emergency rule.
    ("okanogan_river_mouth_to_hwy97", date(2026, 5, 8), False),
    ("okanogan_river_mouth_to_hwy97", date(2026, 9, 15), False),
    ("okanogan_river_hwy97_to_malott", date(2026, 5, 8), False),
    ("okanogan_river_hwy97_to_malott", date(2026, 9, 15), False),
    ("okanogan_river_malott_to_oroville", date(2026, 5, 8), False),
    ("okanogan_river_malott_to_oroville", date(2026, 9, 15), False),

    # Similkameen River CRC 629. PDF p71-72 (printed). Two sub-sections
    # (mouth->400' below Enloe Dam; Enloe Dam->Canadian border).
    # Pamphlet lists Trout July 1-Sept 15 catch-and-release, steelhead
    # closed, whitefish Dec 1-Feb. NO salmon row.
    ("similkameen_river_mouth_to_enloe", date(2026, 5, 8), False),
    ("similkameen_river_mouth_to_enloe", date(2026, 9, 15), False),
    ("similkameen_river_enloe_to_canada", date(2026, 5, 8), False),
    ("similkameen_river_enloe_to_canada", date(2026, 9, 15), False),

    # Wenatchee River CRC 674. PDF p76 (printed). Lower section
    # (mouth->Icicle Rd Bridge) lists "All game fish Year-round Closed"
    # — blanket-closed in the pamphlet. Above Icicle Rd Bridge to
    # Wenatchee Lake = CLOSED WATERS. Sockeye and summer chinook
    # fisheries on the lower Wenatchee open via emergency rule only.
    ("wenatchee_river_lower", date(2026, 5, 8), False),
    ("wenatchee_river_lower", date(2026, 9, 15), False),
    ("wenatchee_river_above_icicle", date(2026, 5, 8), False),
    ("wenatchee_river_above_icicle", date(2026, 9, 15), False),
])
def test_upper_columbia_tribs_status(section_id, today, expected_open):
    st = status_for_section(section_id, today=today)
    assert st is not None, f"section {section_id} missing from YAML"
    assert st.open is expected_open, (
        f"section {section_id} on {today.isoformat()}: "
        f"expected open={expected_open}, got open={st.open} (reason: {st.reason})"
    )


# ---------------------------------------------------------------------------
# Snake mainstem WA-side regression tests (Sacajawea/Pasco upstream to the
# Idaho border at Asotin / Heller Bar / OR-ID border). Encoded from PDF
# pages 75-76 (printed pages 73-74) of 25WAFW_LR7.pdf. The pamphlet splits
# the WA-side Snake mainstem into eight sub-sections by CRC zone:
#
#   CRC 640: mouth (Burbank-Pasco RR Bridge, RM 1.25) -> Goose Island
#            (downstream end), and Goose Island -> 400' below Ice Harbor Dam.
#   CRC 642: Ice Harbor Dam -> 400' below Lower Monument Dam.
#   CRC 644: Lower Monument Dam -> Little Goose Dam.
#   CRC 646: Little Goose Dam -> Lower Granite Dam.
#   CRC 648: Lower Granite Dam -> WA/ID state line in Clarkston.
#   CRC 650: WA/ID state line -> Bridge St. Bridge (Blue Bridge), and
#            Blue Bridge -> OR/ID border. (CRC 650 is the WA/ID boundary
#            water reach; both Idaho and Washington licenses are honored.)
#
# Every Snake-mainstem sub-section in the pamphlet shares the SAME
# salmon-and-steelhead table:
#   - No salmon row (implicit-closure for salmon retention).
#   - Hatchery steelhead Apr 1-Jun 30 closed; Jul 1-Aug 31 catch-and-release;
#     Sept 1-Mar 31 retention (Min size 20", Daily limit 3).
#
# Encoded as a single retention window 09-01..03-31 (the steelhead retention
# period) with wraparound. Dates outside that window fall through to default-
# closed (matches pamphlet implicit-closure). The Jul-Aug C&R period is NOT
# encoded as "open" because our `salmon_hatchery_steelhead` semantic is
# retention-eligible, not "any fishing allowed". One open + one closed
# assertion per section_id.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("section_id,today,expected_open", [
    # CRC 640: Burbank-Pasco RR Bridge (RM 1.25) to downstream end of Goose Island.
    ("snake_mouth_to_goose_island", date(2026, 5, 8), False),    # implicit closed
    ("snake_mouth_to_goose_island", date(2026, 9, 15), True),    # Sep 1-Mar 31 retention

    # CRC 640: Goose Island (downstream end) to 400' below Ice Harbor Dam.
    ("snake_goose_island_to_ice_harbor", date(2026, 5, 8), False),
    ("snake_goose_island_to_ice_harbor", date(2026, 9, 15), True),

    # CRC 642: Ice Harbor Dam to 400' below Lower Monument Dam.
    ("snake_ice_harbor_to_lower_monumental", date(2026, 5, 8), False),
    ("snake_ice_harbor_to_lower_monumental", date(2026, 9, 15), True),

    # CRC 644: Lower Monument Dam to Little Goose Dam.
    ("snake_lower_monumental_to_little_goose", date(2026, 5, 8), False),
    ("snake_lower_monumental_to_little_goose", date(2026, 9, 15), True),

    # CRC 646: Little Goose Dam to Lower Granite Dam.
    ("snake_little_goose_to_lower_granite", date(2026, 5, 8), False),
    ("snake_little_goose_to_lower_granite", date(2026, 9, 15), True),

    # CRC 648: Lower Granite Dam to WA/ID state line in Clarkston.
    ("snake_lower_granite_to_wa_id_clarkston", date(2026, 5, 8), False),
    ("snake_lower_granite_to_wa_id_clarkston", date(2026, 9, 15), True),

    # CRC 650 (WA/ID boundary water): WA/ID state line in Clarkston to Blue Bridge.
    ("snake_wa_id_to_blue_bridge", date(2026, 5, 8), False),
    ("snake_wa_id_to_blue_bridge", date(2026, 9, 15), True),

    # CRC 650 (WA/ID boundary water): Blue Bridge to OR/ID border (Heller Bar /
    # Grande Ronde mouth area; upstream end of WA-jurisdiction Snake mainstem).
    ("snake_blue_bridge_to_or_id_border", date(2026, 5, 8), False),
    ("snake_blue_bridge_to_or_id_border", date(2026, 9, 15), True),

    # Spot-check the wrap-around end of the Sept 1-Mar 31 window for one
    # section: Feb 15 should be inside the window (today <= Mar 31).
    ("snake_lower_monumental_to_little_goose", date(2026, 2, 15), True),
    # And the implicit-closure side (Apr 15 — outside any retention window).
    ("snake_lower_monumental_to_little_goose", date(2026, 4, 15), False),
])
def test_snake_mainstem_status(section_id, today, expected_open):
    st = status_for_section(section_id, today=today)
    assert st is not None, f"section {section_id} missing from YAML"
    assert st.open is expected_open, (
        f"section {section_id} on {today.isoformat()}: "
        f"expected open={expected_open}, got open={st.open} (reason: {st.reason})"
    )


# ---------------------------------------------------------------------------
# Lower Columbia mainstem regression tests (Pacific to Bonneville Dam).
# Encoded from PDF pages 50-54 (printed) of 25WAFW_LR7.pdf. Sections proceed
# downstream-to-upstream: Buoy 10 -> Megler/Astoria Bridge -> Tongue Point ->
# Puget Island -> Longview Bridge -> Warrior Rock -> I-5 Bridge -> Nav Marker
# 82 / Fir Point -> Beacon Rock -> Hamilton Island -> Bonneville fish ladder.
#
# Salmon tables on these sections share a common backbone:
#   - Jan 1 to last day of Feb (encoded 01-01..02-28; 2026 is non-leap):
#     adult salmon + hatchery steelhead retention, release all but Chinook.
#   - Mar 1-31: similar but tighter limits.
#   - Apr 1-Jun 15 closed (or Apr 1-Jul 31 in the Buoy 10 reach, or Apr 1-
#     Sep 15 in Youngs Bay Control Zone).
#   - Aug-Oct: multiple seasonal Chinook/coho windows.
#   - Sept 18-30 closed in CRC 521 / 523 / 525 sections (drop-in closure).
#   - Sept 7-30 closed in puget_island_to_longview (CRC 521 variant).
#
# Spring (May 8) is closed almost everywhere; Aug 15 falls inside the Aug 1-
# Sept 6/17 windows which are open in every section. Sept 25 is closed in
# every CRC 521/523/525 section due to the Sept 18-30 inner-window closure.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("section_id,today,expected_open", [
    # Buoy 10 to Megler-Astoria Bridge (CRC 519). Apr 1-Jul 31 closed window
    # (longer than the upstream sections); Aug 1-Dec 31 open in seasonal sub-
    # windows; Jan-Feb open.
    ("buoy10_to_megler_astoria", date(2026, 5, 8), False),    # Apr 1-Jul 31 closed
    ("buoy10_to_megler_astoria", date(2026, 8, 15), True),    # Aug 7-25 open
    ("buoy10_to_megler_astoria", date(2026, 1, 15), True),    # Jan 1-Feb 28 open

    # Youngs Bay Control Zone (CRC 519, sub-area). Apr 1-Sept 15 closed
    # (longest spring/summer closure in lower Columbia; tribal allocation).
    ("youngs_bay_control_zone", date(2026, 5, 8), False),     # Apr 1-Sept 15 closed
    ("youngs_bay_control_zone", date(2026, 8, 15), False),    # Apr 1-Sept 15 closed (still)
    ("youngs_bay_control_zone", date(2026, 9, 20), True),     # Sept 16-30 coho open
    ("youngs_bay_control_zone", date(2026, 1, 15), True),     # Jan 1-Feb 28 open

    # Megler-Astoria Bridge to Tongue Point (CRC 519). Standard table:
    # Apr 1-Jun 15 closed, then summer/fall multi-window; Sep 7-30 coho-only.
    ("megler_astoria_to_tongue_point", date(2026, 5, 8), False),   # Apr 1-Jun 15 closed
    ("megler_astoria_to_tongue_point", date(2026, 8, 15), True),   # Aug 7-25 open

    # Tongue Point to west end of Puget Island (CRC 521). Standard table:
    # Apr 1-May 15 closed, May 16-Jun 15 steelhead; multi-window summer/fall.
    ("tongue_point_to_puget_island", date(2026, 5, 8), False),     # Apr 1-May 15 closed
    ("tongue_point_to_puget_island", date(2026, 8, 15), True),     # Aug 7-25 open
    ("tongue_point_to_puget_island", date(2026, 5, 25), True),     # May 16-Jun 15 open

    # Knappa Slough & Blind Slough (CRC 521, sub-area). Year-round open
    # (continuous salmon retention, DL 2). No implicit-closed period.
    ("knappa_blind_slough", date(2026, 5, 8), True),
    ("knappa_blind_slough", date(2026, 12, 31), True),

    # West end of Puget Island to Longview Bridge (CRC 521). Apr 1-May 15
    # closed, May 16-Jun 15 steelhead, Jun 16-Jul 31, Aug 1-Sep 6, Sep 7-30
    # CLOSED, Oct 1-31, Nov 1-Dec 31.
    ("puget_island_to_longview", date(2026, 5, 8), False),         # Apr 1-May 15 closed
    ("puget_island_to_longview", date(2026, 8, 15), True),         # Aug 1-Sep 6 open
    ("puget_island_to_longview", date(2026, 9, 20), False),        # Sep 7-30 closed

    # Longview Bridge to Warrior Rock line (CRC 523). Standard table:
    # Apr 1-May 15 closed, May 16-Jun 15 steelhead; Sep 18-30 inner closure.
    ("longview_to_warrior_rock", date(2026, 5, 8), False),         # Apr 1-May 15 closed
    ("longview_to_warrior_rock", date(2026, 8, 15), True),         # Aug 1-Sep 17 open
    ("longview_to_warrior_rock", date(2026, 9, 25), False),        # Sep 18-30 closed

    # Warrior Rock line to I-5 Bridge (CRC 523). Same table as above.
    ("warrior_rock_to_i5", date(2026, 5, 8), False),
    ("warrior_rock_to_i5", date(2026, 8, 15), True),

    # I-5 Bridge to Navigation Marker 82 / Fir Point (CRC 525). Jan 1-Mar 31
    # release-all open, Apr 1-Jun 15 closed, then Jun 16-Dec 31 multi-window.
    ("i5_to_nav_marker_82", date(2026, 5, 8), False),              # Apr 1-Jun 15 closed
    ("i5_to_nav_marker_82", date(2026, 8, 15), True),              # Aug 1-Sep 17 open

    # Navigation Marker 82 / Fir Point to Beacon Rock (CRC 525). Same table.
    ("nav_marker_82_to_beacon_rock", date(2026, 5, 8), False),
    ("nav_marker_82_to_beacon_rock", date(2026, 8, 15), True),

    # Sand Island (Rooster Rock) sub-area (CRC 525). Jan 1-Apr 30 CLOSED
    # WATERS, May 1-Jun 15 closed for salmon, then standard table.
    ("sand_island_rooster_rock", date(2026, 2, 15), False),        # Jan 1-Apr 30 CLOSED
    ("sand_island_rooster_rock", date(2026, 5, 8), False),         # May 1-Jun 15 closed
    ("sand_island_rooster_rock", date(2026, 8, 15), True),         # Aug 1-Sep 17 open

    # Beacon Rock to Hamilton Island boat ramp (CRC 525). Jan 1-Mar 31
    # release-all open, Apr 1-Jun 15 closed; importantly Nov 1-Dec 31 is
    # also CLOSED here (unlike other CRC 525 sections which are open Nov-Dec).
    ("beacon_rock_to_hamilton_island", date(2026, 5, 8), False),
    ("beacon_rock_to_hamilton_island", date(2026, 8, 15), True),
    ("beacon_rock_to_hamilton_island", date(2026, 12, 15), False), # Nov 1-Dec 31 closed

    # Hamilton Island boat ramp to ~4,000' below fish ladder (CRC 525,
    # hand-casted line bank-only). Standard CRC 525 table.
    ("hamilton_island_to_bradford_island_4000", date(2026, 5, 8), False),
    ("hamilton_island_to_bradford_island_4000", date(2026, 8, 15), True),

    # ~4,000' below fish ladder to 600' below fish ladder (CRC 525,
    # hand-casted line bank-only). Same salmon table as above. Sturgeon
    # year-round closed for this stretch (encoded in note).
    ("bradford_4000_to_600", date(2026, 5, 8), False),
    ("bradford_4000_to_600", date(2026, 8, 15), True),
])
def test_lower_columbia_mainstem_status(section_id, today, expected_open):
    st = status_for_section(section_id, today=today)
    assert st is not None, f"section {section_id} missing from YAML"
    assert st.open is expected_open, (
        f"section {section_id} on {today.isoformat()}: "
        f"expected open={expected_open}, got open={st.open} (reason: {st.reason})"
    )


# ---------------------------------------------------------------------------
# Lower Columbia tributaries regression tests (Pacific to Bonneville Dam,
# WA-jurisdiction tribs only). Encoded from PDF pages 49-78 (printed) of
# 25WAFW_LR7.pdf, alphabetical Columbia Basin Rivers Special Rules section.
#
# Salmon-retention patterns common to many of these tribs:
#   - Late fall only (Aug 1-Nov 30 or Aug 1-Dec 31 or Nov 1-Dec 31): typical
#     coho/Chinook fishery in the smaller Columbia tribs.
#   - Cowlitz / Kalama / Lewis: longer windows (Jan 1-Jul 31 + Aug 1-Dec 31
#     i.e. effectively year-round open in some form) reflecting the larger
#     hatchery-supported fisheries.
#   - Year-round-closed tribs (Chinook River, Deep River, Elochoman above
#     West Fork, Lewis River above Eagle Cliff, ...) are encoded with
#     `salmon_hatchery_steelhead: []` per A3 / lesson-#7 convention.
#
# One open + one closed assertion per encoded section_id, except:
#   - chinook_river / deep_river / elochoman_above_west_fork: purely-closed
#     for salmon — two closed dates on different months are used.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("section_id,today,expected_open", [
    # Abernathy Creek CRC 501 (Cowlitz Co.). Salmon Nov 1-Dec 31.
    ("abernathy_creek_lower", date(2026, 5, 8), False),       # implicit closed
    ("abernathy_creek_lower", date(2026, 11, 15), True),      # Nov 1-Dec 31 open
    ("abernathy_creek_upper", date(2026, 5, 8), False),
    ("abernathy_creek_upper", date(2026, 11, 15), True),

    # Blue Creek CRC 507 (Lewis Co., trib to Cowlitz). Salmon Aug 1-Dec 31.
    ("blue_creek", date(2026, 5, 8), False),                  # implicit closed
    ("blue_creek", date(2026, 9, 15), True),                  # Aug 1-Dec 31 open

    # Cedar Creek and tributaries CRC 609 (Clark Co., trib to East Fork
    # Lewis). Salmon Nov 1-Dec 31. Two encoded reaches share the same table.
    ("cedar_creek_lower", date(2026, 5, 8), False),
    ("cedar_creek_lower", date(2026, 11, 15), True),
    ("cedar_creek_upper", date(2026, 5, 8), False),
    ("cedar_creek_upper", date(2026, 11, 15), True),

    # Chinook River CRC 515 (Pacific Co.). No salmon row in pamphlet —
    # year-round closed for salmon retention. Two closed-date assertions.
    ("chinook_river", date(2026, 5, 8), False),
    ("chinook_river", date(2026, 9, 15), False),

    # Coal Creek CRC 517 (Cowlitz Co.). Salmon Nov 1-Dec 31.
    ("coal_creek", date(2026, 5, 8), False),
    ("coal_creek", date(2026, 11, 15), True),

    # Coweeman River and tributaries CRC 557 (Cowlitz Co.). Salmon Nov 1-Dec 31.
    ("coweeman_river", date(2026, 5, 8), False),
    ("coweeman_river", date(2026, 11, 15), True),

    # Cowlitz River CRC 561 (Cowlitz/Lewis Co.). Five encoded sub-sections;
    # the first four share the same salmon table (Jan 1-Jul 31 + Aug 1-Dec 31
    # — effectively year-round open). The last (above Jody's Bridge) is
    # listed as Salmon Year-round.
    ("cowlitz_mouth_to_lexington", date(2026, 5, 8), True),     # Jan 1-Jul 31 open
    ("cowlitz_mouth_to_lexington", date(2026, 9, 15), True),    # Aug 1-Dec 31 open
    ("cowlitz_lexington_to_mill_creek", date(2026, 5, 8), True),
    ("cowlitz_lexington_to_mill_creek", date(2026, 9, 15), True),
    ("cowlitz_mill_creek_to_barrier_dam", date(2026, 5, 8), True),
    ("cowlitz_mill_creek_to_barrier_dam", date(2026, 9, 15), True),
    ("cowlitz_intake_to_mayfield_powerhouse", date(2026, 5, 8), True),
    ("cowlitz_intake_to_mayfield_powerhouse", date(2026, 9, 15), True),
    ("cowlitz_jodys_bridge_upstream", date(2026, 5, 8), True),  # Year-round
    ("cowlitz_jodys_bridge_upstream", date(2026, 12, 31), True),

    # Deep River CRC 580 (Wahkiakum Co.). Pamphlet table lists Trout +
    # Steelhead + Other game fish only — NO salmon row. Year-round closed
    # for salmon retention. Two closed-date assertions.
    ("deep_river", date(2026, 5, 8), False),
    ("deep_river", date(2026, 9, 15), False),

    # Delameter Creek CRC 568 (Cowlitz Co.). Salmon Aug 1-Oct 31.
    ("delameter_creek", date(2026, 5, 8), False),
    ("delameter_creek", date(2026, 9, 15), True),

    # Elochoman River CRC 583/584 (Wahkiakum Co.). Three encoded reaches
    # share the same salmon table: Sat-before-MD-Mar 15 (steelhead-and-
    # salmon) + Apr 16-Fri-before-MD (combo Chinook/steelhead). The matcher
    # is day-blind, so Sat-before-MD is approximated as 05-23 (latest
    # Memorial Day Sat in 2026 is May 23) and Fri-before-MD as 05-22.
    # Encoded as 05-23..03-15 wraparound for the salmon window. Above the
    # West Fork, the pamphlet drops the salmon row entirely (steelhead-only).
    ("elochoman_mouth_to_foster", date(2026, 6, 15), True),       # Sat-MD-Mar 15
    ("elochoman_mouth_to_foster", date(2026, 9, 15), True),       # Aug 1-Oct 31 stationary
    ("elochoman_mouth_to_foster", date(2026, 4, 1), False),       # implicit closed (Mar 16-Apr 15)
    ("elochoman_foster_to_beaver", date(2026, 6, 15), True),
    ("elochoman_foster_to_beaver", date(2026, 4, 1), False),
    ("elochoman_beaver_to_hatchery", date(2026, 6, 15), True),
    ("elochoman_beaver_to_hatchery", date(2026, 4, 1), False),
    ("elochoman_hatchery_to_west_fork", date(2026, 6, 15), True),
    ("elochoman_hatchery_to_west_fork", date(2026, 4, 1), False),
    # Above West Fork: no salmon row. Two closed dates.
    ("elochoman_above_west_fork", date(2026, 5, 8), False),
    ("elochoman_above_west_fork", date(2026, 11, 15), False),

    # Germany Creek and Tributaries CRC 589 (Cowlitz Co.). Salmon Nov 1-Dec 31.
    ("germany_creek", date(2026, 5, 8), False),
    ("germany_creek", date(2026, 11, 15), True),

    # Grays River CRC 594/595 (Wahkiakum Co.). Three lower reaches share
    # the same salmon table (Sat-MD-Jul 31 + Aug 1-Dec 31). Above South
    # Fork = Selective-gear all-trout, no salmon row.
    ("grays_river_mouth_to_barr", date(2026, 6, 15), True),     # Sat-MD-Jul 31
    ("grays_river_mouth_to_barr", date(2026, 9, 15), True),     # Aug 1-Dec 31
    ("grays_river_mouth_to_barr", date(2026, 4, 1), False),     # implicit closed
    ("grays_river_barr_to_hwy4", date(2026, 6, 15), True),
    ("grays_river_barr_to_hwy4", date(2026, 4, 1), False),
    ("grays_river_hwy4_to_sf_mouth", date(2026, 6, 15), True),
    ("grays_river_hwy4_to_sf_mouth", date(2026, 4, 1), False),

    # Grays River East Fork CRC 597 (Lewis/Pacific Co.). Salmon
    # Sat-MD-July 31 + Aug 1-Oct 31.
    ("grays_river_east_fork", date(2026, 6, 15), True),         # Sat-MD-Jul 31
    ("grays_river_east_fork", date(2026, 9, 15), True),         # Aug 1-Oct 31
    ("grays_river_east_fork", date(2026, 12, 15), False),       # implicit closed

    # Grays River West Fork CRC 596 (Wahkiakum Co.). Salmon Sat-MD-Dec 31.
    # Continuous from late May through year end.
    ("grays_river_west_fork", date(2026, 6, 15), True),
    ("grays_river_west_fork", date(2026, 11, 15), True),
    ("grays_river_west_fork", date(2026, 4, 1), False),         # implicit closed

    # Green River CRC 565/566 (Cowlitz Co., trib to Toutle). Three encoded
    # reaches share Salmon Aug 1-Nov 30 (lower/middle) or Aug 1-Aug 31
    # (single reach 400' below to 400' above intake — encoded as middle).
    ("green_river_lower", date(2026, 5, 8), False),
    ("green_river_lower", date(2026, 9, 15), True),             # Aug 1-Nov 30
    ("green_river_above_intake_to_miners", date(2026, 5, 8), False),
    ("green_river_above_intake_to_miners", date(2026, 9, 15), True),

    # Hamilton Creek CRC 598 (Skamania Co., trib to lower Columbia).
    # Salmon Aug 1-Oct 31.
    ("hamilton_creek", date(2026, 5, 8), False),
    ("hamilton_creek", date(2026, 9, 15), True),

    # Kalama River CRC 602/603/604 (Cowlitz Co.). Three encoded reaches
    # share the same salmon table (Jan 1-Jul 31 + Aug 1-Dec 31).
    ("kalama_mouth_to_modrow", date(2026, 5, 8), True),         # Jan 1-Jul 31
    ("kalama_mouth_to_modrow", date(2026, 9, 15), True),        # Aug 1-Dec 31
    ("kalama_modrow_to_pipeline", date(2026, 5, 8), True),
    ("kalama_modrow_to_pipeline", date(2026, 9, 15), True),
    ("kalama_pipeline_to_kalama_falls", date(2026, 5, 8), True),
    ("kalama_pipeline_to_kalama_falls", date(2026, 9, 15), True),
    # Kalama Falls hatchery to Summers Creek CRC 602: NO salmon row.
    ("kalama_above_falls_to_summers", date(2026, 5, 8), False),
    ("kalama_above_falls_to_summers", date(2026, 9, 15), False),

    # Lacamas Creek CRC 567 (Lewis Co., trib to Cowlitz). Salmon Aug 1-Oct 31.
    ("lacamas_creek_lewis", date(2026, 5, 8), False),
    ("lacamas_creek_lewis", date(2026, 9, 15), True),

    # Lewis River CRC 611/615 (Clark/Cowlitz Co.). Encoded reaches share
    # the same salmon table (Jan 1-Apr 30 + Aug 1-Sep 30 + Oct 1-Dec 31).
    # May 1-Jul 31 is implicit closed for salmon retention (lower reaches);
    # Johnson-Colvin and Colvin-Powerlines have an EXPLICIT May 1-31
    # CLOSED WATERS rule on top of that.
    ("lewis_river_mouth_to_ef", date(2026, 1, 15), True),       # Jan 1-Apr 30 open
    ("lewis_river_mouth_to_ef", date(2026, 9, 15), True),       # Aug 1-Sep 30 open
    ("lewis_river_mouth_to_ef", date(2026, 7, 15), False),      # May 1-Jul 31 implicit closed
    ("lewis_river_ef_to_johnson", date(2026, 9, 15), True),
    ("lewis_river_ef_to_johnson", date(2026, 7, 15), False),
    ("lewis_river_johnson_to_colvin", date(2026, 5, 15), False),  # May 1-31 explicit CLOSED WATERS
    ("lewis_river_johnson_to_colvin", date(2026, 9, 15), True),
    ("lewis_river_colvin_to_powerlines", date(2026, 5, 15), False),  # May 1-31 explicit CLOSED WATERS
    ("lewis_river_colvin_to_powerlines", date(2026, 9, 15), True),

    # Lewis River East Fork CRC 613 (Clark Co.). Three encoded reaches share
    # Salmon Sep 16-Dec 31. Spring/summer closed for salmon.
    ("east_fork_lewis_mouth_to_big_eddy", date(2026, 5, 8), False),
    ("east_fork_lewis_mouth_to_big_eddy", date(2026, 11, 15), True),
    ("east_fork_lewis_lucia_to_moulton", date(2026, 5, 8), False),
    ("east_fork_lewis_lucia_to_moulton", date(2026, 11, 15), True),
    ("east_fork_lewis_moulton_to_horseshoe", date(2026, 5, 8), False),
    ("east_fork_lewis_moulton_to_horseshoe", date(2026, 11, 15), True),

    # Little Washougal River CRC 661 (Clark Co.). Salmon Aug 1-Oct 31.
    ("little_washougal", date(2026, 5, 8), False),
    ("little_washougal", date(2026, 9, 15), True),

    # Mill Creek CRC 624 (Cowlitz/Wahkiakum Co.). Salmon Nov 1-Dec 31.
    ("mill_creek_cowlitz", date(2026, 5, 8), False),
    ("mill_creek_cowlitz", date(2026, 11, 15), True),

    # Mill Creek CRC 625 (Lewis Co., trib to Cowlitz, distinct from above).
    # Salmon Aug 1-Oct 31 + Dec 1-Dec 31.
    ("mill_creek_lewis", date(2026, 5, 8), False),
    ("mill_creek_lewis", date(2026, 9, 15), True),
    ("mill_creek_lewis", date(2026, 12, 15), True),

    # Olequa Creek CRC 569 (Cowlitz/Lewis Co.). Salmon Aug 1-Oct 31.
    ("olequa_creek", date(2026, 5, 8), False),
    ("olequa_creek", date(2026, 9, 15), True),

    # Outlet Creek (Silver Lake) CRC 570 (Cowlitz Co.). Salmon Aug 1-Nov 30.
    ("outlet_creek", date(2026, 5, 8), False),
    ("outlet_creek", date(2026, 9, 15), True),

    # Salmon Creek CRC 635 (Clark Co., distinct from Cowlitz/Lewis or
    # Okanogan — drains lower Columbia near Vancouver). Salmon Aug 1-Dec 31.
    ("salmon_creek_clark", date(2026, 5, 8), False),
    ("salmon_creek_clark", date(2026, 9, 15), True),

    # Salmon Creek CRC 561 (Cowlitz/Lewis Co., trib to Cowlitz; not the
    # Clark Co. or Okanogan creek of the same name). Salmon Aug 1-Oct 31.
    ("salmon_creek_cowlitz", date(2026, 5, 8), False),
    ("salmon_creek_cowlitz", date(2026, 9, 15), True),

    # Skamokawa Creek CRC 638 (Wahkiakum Co.). Salmon Nov 1-Dec 31.
    ("skamokawa_creek", date(2026, 5, 8), False),
    ("skamokawa_creek", date(2026, 11, 15), True),

    # Toutle River CRC 573 (mouth to forks). Salmon Aug 1-Nov 30.
    ("toutle_river_mouth_to_forks", date(2026, 5, 8), False),
    ("toutle_river_mouth_to_forks", date(2026, 9, 15), True),

    # Toutle River North Fork CRC 575 (Cowlitz Co.). Two encoded reaches
    # (mouth to Green River; Green River to fish collection facility).
    # Salmon Aug 1-Nov 30 in both.
    ("toutle_north_mouth_to_green", date(2026, 5, 8), False),
    ("toutle_north_mouth_to_green", date(2026, 9, 15), True),
    ("toutle_north_green_to_collection", date(2026, 5, 8), False),
    ("toutle_north_green_to_collection", date(2026, 9, 15), True),

    # Toutle River South Fork CRC 577 (Cowlitz Co.). Two encoded reaches
    # (mouth to 4700 Rd; above 4700 Rd). Salmon Aug 1-Nov 30 in both.
    ("toutle_south_mouth_to_4700", date(2026, 5, 8), False),
    ("toutle_south_mouth_to_4700", date(2026, 9, 15), True),
    ("toutle_south_above_4700", date(2026, 5, 8), False),
    ("toutle_south_above_4700", date(2026, 9, 15), True),

    # Washougal River CRC 667/668 (Clark Co.). Two encoded reaches share
    # Salmon Aug 1-Dec 31.
    ("washougal_mouth_to_county_line", date(2026, 5, 8), False),
    ("washougal_mouth_to_county_line", date(2026, 9, 15), True),
    ("washougal_county_line_to_salmon_falls", date(2026, 5, 8), False),
    ("washougal_county_line_to_salmon_falls", date(2026, 9, 15), True),

    # Washougal River West (North) Fork CRC 665 (Skamania Co.).
    # Salmon Aug 1-Dec 31.
    ("washougal_west_fork", date(2026, 5, 8), False),
    ("washougal_west_fork", date(2026, 9, 15), True),
])
def test_lower_columbia_tribs_status(section_id, today, expected_open):
    st = status_for_section(section_id, today=today)
    assert st is not None, f"section {section_id} missing from YAML"
    assert st.open is expected_open, (
        f"section {section_id} on {today.isoformat()}: "
        f"expected open={expected_open}, got open={st.open} (reason: {st.reason})"
    )


# ---------------------------------------------------------------------------
# Snake River WA-side tributaries regression tests. Encoded from PDF pages
# 46, 62-63, 70, 74-75 (printed) of 25WAFW_LR7.pdf.
#
# The pamphlet "SNAKE RIVER TRIBUTARIES" blanket rule (printed p73) declares
# all Snake River tributaries CLOSED WATERS *except* Palouse, Tucannon,
# Asotin Creek, and Grande Ronde — so only those four are encoded here. The
# blanket-closure entry itself is NOT encoded as a section (its semantic is
# "no rule for unlisted tribs", which our default-closed behavior already
# represents by omission).
#
# Salmon-retention pattern across all four: NONE. Every encoded reach has
# no salmon row at all, matching the pamphlet's implicit closure for
# salmon retention.
#
# Hatchery steelhead retention is the actual "open" period:
#   - Tucannon River (mouth to Tucannon Hatchery Rd Br): Aug 1-Apr 15.
#   - Tucannon River (above Rainbow Lake intake to Cow Camp Br): no
#     steelhead row (above-anadromous). Year-round closed.
#   - Palouse River lower (mouth to Palouse Falls): Aug 1-Apr 15.
#   - Palouse River above falls: no steelhead row. Year-round closed.
#   - Asotin Creek: steelhead "Sat-MD-Oct 31 Closed" (only row). Year-round
#     closed for retention.
#   - Asotin Creek N. Fork (mouth to USFS bdy): same — Year-round closed.
#   - Grande Ronde lower (mouth to County Rd Br): Jan 1-Apr 15 retention;
#     Aug 1-Dec 31 catch-and-release (NOT encoded as open per A6 convention).
#   - Grande Ronde upper (County Rd Br to OR state line): Aug 1-Apr 15
#     retention.
#
# Two assertions per section_id (one open + one closed where applicable;
# two closed for purely-closed sections per A3 / lesson-#7 convention).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("section_id,today,expected_open", [
    # Tucannon River lower (mouth to Tucannon Hatchery Rd Bridge) CRC 653.
    # Hatchery steelhead Aug 1-Apr 15 retention (no salmon row).
    ("tucannon_river_lower", date(2026, 5, 8), False),     # implicit closed (May)
    ("tucannon_river_lower", date(2026, 9, 15), True),     # Aug 1-Apr 15 retention
    ("tucannon_river_lower", date(2026, 2, 15), True),     # wrap-around still inside
    ("tucannon_river_lower", date(2026, 6, 15), False),    # Apr 16-Jul 31 closed

    # Tucannon River upper (500' above Rainbow Lake intake to Cow Camp Br)
    # CRC 653. No salmon row + no hatchery steelhead row → year-round closed.
    ("tucannon_river_upper", date(2026, 5, 8), False),
    ("tucannon_river_upper", date(2026, 9, 15), False),

    # Palouse River lower (mouth to base of Palouse Falls) CRC 652.
    # Hatchery steelhead Aug 1-Apr 15 retention (no salmon row).
    ("palouse_river_lower", date(2026, 5, 8), False),       # Apr 16-Jul 31 closed
    ("palouse_river_lower", date(2026, 9, 15), True),       # Aug 1-Apr 15 retention

    # Palouse River above falls (incl WA-side tribs except Rock Creek and
    # Hog Canyon Creek) CRC 652. No salmon row + no hatchery steelhead row →
    # year-round closed.
    ("palouse_river_above_falls", date(2026, 5, 8), False),
    ("palouse_river_above_falls", date(2026, 9, 15), False),

    # Asotin Creek (Asotin Co., mainstem). No CRC. No salmon row;
    # hatchery steelhead "Sat-MD to Oct 31 Closed" with no other steelhead
    # row → year-round closed for salmon and hatchery steelhead retention.
    ("asotin_creek", date(2026, 5, 8), False),
    ("asotin_creek", date(2026, 9, 15), False),

    # Asotin Creek North Fork (mouth to USFS boundary). No CRC. Same table
    # as mainstem: year-round closed for salmon/hatchery steelhead retention.
    ("asotin_creek_north_fork", date(2026, 5, 8), False),
    ("asotin_creek_north_fork", date(2026, 9, 15), False),

    # Grande Ronde River lower (mouth to County Rd Bridge) CRC 592.
    # No salmon row. Hatchery steelhead Jan 1-Apr 15 retention; Aug 1-
    # Dec 31 C&R (NOT encoded as open per A6 retention-only convention).
    ("grande_ronde_lower", date(2026, 5, 8), False),        # Apr 16-Dec 31 implicit
    ("grande_ronde_lower", date(2026, 2, 15), True),        # Jan 1-Apr 15 retention
    ("grande_ronde_lower", date(2026, 9, 15), False),       # Aug 1-Dec 31 is C&R only

    # Grande Ronde River upper (County Rd Bridge to OR state line) CRC 592.
    # No salmon row. Hatchery steelhead Aug 1-Apr 15 retention.
    ("grande_ronde_upper", date(2026, 5, 8), False),        # Apr 16-Jul 31 closed
    ("grande_ronde_upper", date(2026, 9, 15), True),        # Aug 1-Apr 15 retention
])
def test_snake_wa_tribs_status(section_id, today, expected_open):
    st = status_for_section(section_id, today=today)
    assert st is not None, f"section {section_id} missing from YAML"
    assert st.open is expected_open, (
        f"section {section_id} on {today.isoformat()}: "
        f"expected open={expected_open}, got open={st.open} (reason: {st.reason})"
    )
