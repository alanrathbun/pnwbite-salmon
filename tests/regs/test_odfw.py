"""Tests for the ODFW newsroom scraper (regs/odfw.py).

The fixture is captured from myodfw.com/newsroom (dfw.state.or.us/news/ returned
403 as of May 2026). The newsroom is general-purpose ODFW news, not a dedicated
emergency-rules page, so it may contain zero Columbia/Snake regulation entries
at any given capture — that's acceptable. The test validates structure, not count.
"""
from pathlib import Path

from regs.odfw import parse_news, RegStatus, _classify

FIX = Path(__file__).parent.parent / "fixtures/regs/odfw_news.html"


def test_parse_news_returns_only_relevant_sections():
    """Parsed entries must have correct authority, section prefix, and reason."""
    html = FIX.read_text()
    statuses = parse_news(html)
    # If no Snake/Columbia closures/openings in the captured page, empty list is fine.
    for s in statuses:
        assert isinstance(s, RegStatus)
        assert s.authority == "ODFW"
        assert s.section_key.startswith("ODFW_"), f"unexpected key: {s.section_key}"
        assert s.reason, "reason must not be empty"
        assert s.open in (True, False)


def test_classify_maps_known_phrases():
    """_classify should map section phrases to the correct keys."""
    assert _classify("Columbia River salmon regulations") == "ODFW_MID_COL"
    assert _classify("Mid-Columbia fishery update") == "ODFW_MID_COL"
    assert _classify("Mid Columbia Pool closures") == "ODFW_MID_COL"
    assert _classify("Umatilla area report") == "ODFW_MID_COL"
    assert _classify("Boardman boat launch") == "ODFW_MID_COL"
    assert _classify("Snake River closure") == "ODFW_SNAKE"
    assert _classify("Some unrelated hunting article") is None


def test_parse_news_empty_html_returns_empty_list():
    """parse_news on minimal HTML should return an empty list, not raise."""
    statuses = parse_news("<html><body></body></html>")
    assert statuses == []


def test_parse_news_explicit_closure_detected():
    """Synthetic HTML with an explicit Columbia closure should parse as closed."""
    html = """
    <html><body>
    <article>
        <a href="/news/1">Columbia River closed to salmon fishing effective immediately</a>
        <p>The Columbia River is closed to salmon fishing due to low returns.</p>
    </article>
    </body></html>
    """
    statuses = parse_news(html)
    assert len(statuses) == 1
    assert statuses[0].section_key == "ODFW_MID_COL"
    assert statuses[0].open is False
    assert statuses[0].authority == "ODFW"


def test_parse_news_explicit_opening_detected():
    """Synthetic HTML with an explicit Columbia opening should parse as open."""
    html = """
    <html><body>
    <article>
        <a href="/news/2">Columbia River salmon season now opens Saturday</a>
        <p>The Columbia River is open for Chinook salmon beginning this weekend.</p>
    </article>
    </body></html>
    """
    statuses = parse_news(html)
    assert len(statuses) == 1
    assert statuses[0].section_key == "ODFW_MID_COL"
    assert statuses[0].open is True


def test_parse_news_closure_wins_over_open_for_same_section():
    """If the same section has both open and closed articles, closure wins."""
    html = """
    <html><body>
    <article>
        <a href="/news/1">Columbia River now opens for spring Chinook</a>
        <p>Columbia River opens Saturday for Chinook salmon.</p>
    </article>
    <article>
        <a href="/news/2">Columbia River is closed due to emergency</a>
        <p>Columbia River closed to all salmon fishing immediately.</p>
    </article>
    </body></html>
    """
    statuses = parse_news(html)
    assert len(statuses) == 1
    assert statuses[0].open is False
