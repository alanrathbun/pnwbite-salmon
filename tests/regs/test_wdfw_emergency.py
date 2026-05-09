"""Tests for the WDFW emergency-rules advanced-search fetcher."""
from datetime import date
from pathlib import Path

import pytest

from regs.wdfw_emergency import parse_advanced_search, fetch_active_rules


FIXTURE = Path(__file__).parent / "fixtures" / "wdfw_advanced_search_sample.html"


def test_parse_advanced_search_returns_rules():
    html = FIXTURE.read_text(encoding="utf-8")
    rules = parse_advanced_search(html)
    assert len(rules) > 0, "expected at least one rule in fixture"
    r = rules[0]
    assert r.url.startswith("https://wdfw.wa.gov/")
    assert r.title


def test_parse_advanced_search_extracts_effective_dates():
    html = FIXTURE.read_text(encoding="utf-8")
    rules = parse_advanced_search(html)
    dated = [r for r in rules if r.effective_from is not None]
    assert dated, "expected at least one rule with parseable effective_from date"


def test_fetch_active_rules_filters_by_today():
    """fetch_active_rules(today) returns only rules where effective_from <= today <= effective_to."""
    rules = fetch_active_rules(today=date(2026, 5, 8), html=FIXTURE.read_text(encoding="utf-8"))
    for r in rules:
        if r.effective_from:
            assert r.effective_from <= date(2026, 5, 8)
        if r.effective_to:
            assert r.effective_to >= date(2026, 5, 8)
