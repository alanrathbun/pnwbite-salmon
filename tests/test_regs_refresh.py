from datetime import datetime
from regs_refresh import refresh_regs_in_data
from regs.wdfw import RegStatus


def test_refresh_overrides_open_status_in_existing_data():
    existing = {
        "regs": {"WDFW_HANFORD_REACH": {"open": True, "reason": "old", "authority": "WDFW",
                                        "last_checked": "2026-04-27T05:35:00"}},
        "forecasts": {"fall_chinook::vernita": [
            {"date": "2026-04-27", "score": 0.7, "verdict": "GOOD",
             "techniques": [{"rank": 1, "method": "x", "label": "x", "gear": {}, "notes": ""}],
             "wind_mph": 5.0, "water_temp_f": 55.0, "flow_cfs": 100000},
        ]},
        "launches": [{"key": "vernita", "regs_section": "WDFW_HANFORD_REACH",
                      "parent_key": None, "species": ["fall_chinook"]}],
        "top_picks": {"fall_chinook": [{"launch": "vernita", "day_offset": 0, "score": 0.7, "technique": "x"}]},
    }
    new_regs = {"WDFW_HANFORD_REACH": RegStatus(
        authority="WDFW", section_key="WDFW_HANFORD_REACH", open=False,
        reason="emergency closure", last_checked=datetime.now(),
    )}
    updated = refresh_regs_in_data(existing, new_regs)
    assert updated["regs"]["WDFW_HANFORD_REACH"]["open"] is False
    # Closure should zero out the score
    assert updated["forecasts"]["fall_chinook::vernita"][0]["score"] == 0.0
    # Top picks should be re-filtered to drop the now-closed pick
    assert updated["top_picks"]["fall_chinook"] == []


def test_refresh_preserves_prior_status_when_agency_failed():
    """If WDFW scrape fails this round, the prior WDFW closure should NOT
    be wiped from the cached regs dict by the merge step."""
    existing = {
        "regs": {
            "WDFW_HANFORD_REACH": {"open": False, "reason": "old closure",
                                    "authority": "WDFW",
                                    "last_checked": "2026-04-27T05:35:00"},
            "ODFW_MID_COL": {"open": True, "reason": "open through May",
                              "authority": "ODFW",
                              "last_checked": "2026-04-27T05:35:00"},
        },
        "forecasts": {},
        "launches": [],
        "top_picks": {},
    }
    # WDFW fails this round; new_regs only contains ODFW.
    new_regs = {}  # no WDFW status emitted because the scrape blew up
    agency_meta = {
        "WDFW": {"ok": False, "last_successful_check": None, "error": "boom"},
        "ODFW": {"ok": True, "last_successful_check": "2026-04-27T12:00:00", "error": None},
        "IDFG": {"ok": True, "last_successful_check": "2026-04-27T12:00:00", "error": None},
    }
    updated = refresh_regs_in_data(existing, new_regs, agency_meta)
    # WDFW closure persists despite scrape failure
    assert updated["regs"]["WDFW_HANFORD_REACH"]["open"] is False
    assert updated["regs"]["WDFW_HANFORD_REACH"]["reason"] == "old closure"
    # Agency meta was attached so renderer can show banner
    assert updated["regs_agency_meta"]["WDFW"]["ok"] is False


def test_refresh_includes_agency_meta_in_output():
    existing = {"regs": {}, "forecasts": {}, "launches": [], "top_picks": {}}
    agency_meta = {
        "WDFW": {"ok": True, "last_successful_check": "2026-04-27T12:00:00", "error": None},
    }
    updated = refresh_regs_in_data(existing, {}, agency_meta)
    assert updated["regs_agency_meta"] == agency_meta
