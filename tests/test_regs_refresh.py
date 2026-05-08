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
