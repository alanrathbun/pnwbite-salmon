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
