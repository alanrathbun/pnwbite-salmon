"""Tests for the IDFG spring Chinook season-status scraper (regs/idfg.py).

The fixture is captured from https://idfg.idaho.gov/fish/chinook/spring/rules
(the original https://idfg.idaho.gov/rules/fish/changes URL returned 404 as of
May 2026). The spring rules page has structured tables with Season Status cells
for Clearwater River and Salmon River sections — exactly what we need.

As of the May 2026 capture, all sections show "Open" or "Open, limited days per
week", so the fixture test validates structure and section_key correctness
rather than counts of opens/closes.
"""
from pathlib import Path

from regs.idfg import parse_changes, RegStatus, _location_key, _caption_key

FIX = Path(__file__).parent.parent / "fixtures/regs/idfg_changes.html"


def test_parse_returns_clearwater_or_salmon_sections():
    """Parsed entries must have correct authority, section prefix, and reason."""
    html = FIX.read_text()
    statuses = parse_changes(html)
    # Fixture has Clearwater and Salmon River tables — should produce entries.
    assert len(statuses) > 0, "Expected at least one status entry from fixture"
    for s in statuses:
        assert s.authority == "IDFG"
        assert s.section_key.startswith("IDFG_"), f"unexpected key: {s.section_key}"
        assert s.reason


def test_parse_fixture_has_open_sections():
    """Fixture captured when all sections were open — all should be open=True."""
    html = FIX.read_text()
    statuses = parse_changes(html)
    # All May 2026 sections are open.
    for s in statuses:
        assert s.open is True, f"Expected open but got closed: {s}"


def test_parse_fixture_covers_clearwater_and_salmon():
    """Fixture should include both Clearwater and Salmon sections."""
    html = FIX.read_text()
    statuses = parse_changes(html)
    keys = {s.section_key for s in statuses}
    assert any(k.startswith("IDFG_CLEARWATER") for k in keys), \
        f"No Clearwater section found; keys: {keys}"
    assert "IDFG_SALMON" in keys, f"No Salmon section found; keys: {keys}"


def test_caption_key_maps_known_captions():
    """_caption_key should map river caption strings to section keys."""
    assert _caption_key("clearwater river") == "IDFG_CLEARWATER_LOWER"
    assert _caption_key("salmon river") == "IDFG_SALMON"
    assert _caption_key("lochsa river") is None  # not a tracked section
    assert _caption_key("snake river") is None   # not a tracked section


def test_location_key_maps_specific_locations():
    """_location_key should resolve specific forks to the right section key."""
    assert _location_key("Mainstem Clearwater River - Camas Prairie") == "IDFG_CLEARWATER_LOWER"
    assert _location_key("North Fork Clearwater River - Mouth to Dworshak") == "IDFG_CLEARWATER_MID"
    assert _location_key("South Fork Clearwater River - Mouth") == "IDFG_CLEARWATER_MID"
    assert _location_key("Middle Fork Clearwater River") == "IDFG_CLEARWATER_MID"
    assert _location_key("Lower Salmon River - Rice Creek") == "IDFG_SALMON"
    assert _location_key("Little Salmon River") == "IDFG_SALMON"
    assert _location_key("Lochsa River - Lowell Bridge") is None


def test_parse_empty_html_returns_empty_list():
    """parse_changes on minimal HTML should return [], not raise."""
    statuses = parse_changes("<html><body></body></html>")
    assert statuses == []


def test_parse_explicit_closure_detected():
    """Synthetic HTML with an explicit closure status should parse as closed."""
    html = """
    <html><body><main>
    <table class="cols-3 table">
      <caption>Clearwater River</caption>
      <thead><tr><th>Location</th><th>Season Status</th><th>Season Dates*</th></tr></thead>
      <tbody>
        <tr>
          <td><h5>Mainstem Clearwater River - Camas Prairie Railroad Bridge (Spring 2026)</h5></td>
          <td><h5>Closed</h5></td>
          <td>4/25/26 to 8/10/26</td>
        </tr>
      </tbody>
    </table>
    </main></body></html>
    """
    statuses = parse_changes(html)
    assert len(statuses) == 1
    assert statuses[0].section_key == "IDFG_CLEARWATER_LOWER"
    assert statuses[0].open is False
    assert statuses[0].authority == "IDFG"


def test_parse_explicit_opening_detected():
    """Synthetic HTML with explicit Open status should parse as open=True."""
    html = """
    <html><body><main>
    <table class="cols-3 table">
      <caption>Salmon River</caption>
      <thead><tr><th>Location</th><th>Season Status</th><th>Season Dates*</th></tr></thead>
      <tbody>
        <tr>
          <td><h5>Lower Salmon River - From the Rice Creek Bridge upstream (Spring 2026)</h5></td>
          <td><h5>Open, limited days per week</h5></td>
          <td>4/25/26 to 8/10/26</td>
        </tr>
      </tbody>
    </table>
    </main></body></html>
    """
    statuses = parse_changes(html)
    assert len(statuses) == 1
    assert statuses[0].section_key == "IDFG_SALMON"
    assert statuses[0].open is True


def test_parse_closure_wins_over_open_for_same_section():
    """If a section has both open and closed rows, closure wins."""
    html = """
    <html><body><main>
    <table class="cols-3 table">
      <caption>Clearwater River</caption>
      <thead><tr><th>Location</th><th>Season Status</th><th>Season Dates*</th></tr></thead>
      <tbody>
        <tr>
          <td><h5>Mainstem Clearwater River (Spring 2026)</h5></td>
          <td><h5>Open</h5></td>
          <td>4/25/26 to 8/10/26</td>
        </tr>
        <tr>
          <td><h5>North Fork Clearwater River (Spring 2026)</h5></td>
          <td><h5>Closed</h5></td>
          <td>4/25/26 to 8/10/26</td>
        </tr>
      </tbody>
    </table>
    </main></body></html>
    """
    statuses = parse_changes(html)
    # Mainstem → IDFG_CLEARWATER_LOWER (open), North Fork → IDFG_CLEARWATER_MID (closed)
    # Different section_keys, so both should appear.
    by_key = {s.section_key: s for s in statuses}
    assert by_key["IDFG_CLEARWATER_LOWER"].open is True
    assert by_key["IDFG_CLEARWATER_MID"].open is False


def test_parse_season_not_started_detected_as_closed():
    """'Season has not started' status should resolve to open=False."""
    html = """
    <html><body><main>
    <table class="cols-3 table">
      <caption>Salmon River</caption>
      <thead><tr><th>Location</th><th>Season Status</th><th>Season Dates*</th></tr></thead>
      <tbody>
        <tr>
          <td><h5>Lower Salmon River (Spring 2026)</h5></td>
          <td><h5>Season has not started</h5></td>
          <td>5/1/26 to 8/10/26</td>
        </tr>
      </tbody>
    </table>
    </main></body></html>
    """
    statuses = parse_changes(html)
    assert len(statuses) == 1
    assert statuses[0].open is False
