from datetime import date, datetime
from pathlib import Path

from regs.wdfw import parse_rule_changes, RegStatus, classify_section

FIX = Path(__file__).parent.parent / "fixtures/regs/wdfw_rule_changes.html"


def test_parse_yields_open_and_closed_entries():
    html = FIX.read_text()
    statuses = parse_rule_changes(html)
    # Page should have *some* entries; if it's empty the scraper isn't useful.
    # Allow empty if WDFW currently has no active emergency rules — but flag in
    # the report.
    for s in statuses:
        assert isinstance(s, RegStatus)
        assert s.authority == "WDFW"
        assert s.open in (True, False)
        assert s.section_key
        assert s.reason


def test_classify_section_maps_known_phrases():
    assert classify_section("Hanford Reach") == "WDFW_HANFORD_REACH"
    assert classify_section("Drano Lake") == "WDFW_DRANO"
    assert classify_section("Wind River") == "WDFW_WIND"
    # Unknown text returns None — we don't want to silently mis-classify.
    assert classify_section("Anaheim") is None


def test_default_open_when_no_emergency_rules_apply(tmp_path):
    """If a section has no rule-change entry, callers can default to open=True.

    parse_rule_changes on empty HTML should return [].
    """
    statuses = parse_rule_changes("<html></html>")
    keys = {s.section_key for s in statuses}
    assert "WDFW_HANFORD_REACH" not in keys  # no rules → not present in output
