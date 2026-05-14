"""Tests for the emergency-rule classifier cache. LLM-call tests live in test_emergency_classifier_llm.py."""
from datetime import date, datetime
from pathlib import Path

import pytest

from regs.emergency_classifier import (
    cache_key_for,
    load_cached_classification,
    save_cached_classification,
)
from regs.emergency_types import Classification, EmergencyRule


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    d = tmp_path / "emergency-cache"
    d.mkdir()
    return d


def _rule():
    return EmergencyRule(
        url="https://wdfw.wa.gov/abc",
        title="Hanford closure",
        body="...",
        effective_from=date(2026, 5, 1),
        effective_to=date(2026, 6, 30),
        modified_at=datetime(2026, 5, 1, 12, 0),
    )


def test_cache_key_is_stable():
    k1 = cache_key_for(_rule())
    k2 = cache_key_for(_rule())
    assert k1 == k2


def test_cache_key_unchanged_when_only_modified_at_changes():
    """modified_at is NOT part of the cache key — same url+title+body should hash the same."""
    r1 = _rule()
    r2 = EmergencyRule(**{**r1.__dict__, "modified_at": datetime(2026, 5, 2, 12, 0)})
    assert cache_key_for(r1) == cache_key_for(r2)


def test_cache_key_differs_when_body_changes():
    r1 = _rule()
    r2 = EmergencyRule(**{**r1.__dict__, "body": "totally different rule text"})
    assert cache_key_for(r1) != cache_key_for(r2)


def test_cache_key_differs_when_title_changes():
    r1 = _rule()
    r2 = EmergencyRule(**{**r1.__dict__, "title": "Different title"})
    assert cache_key_for(r1) != cache_key_for(r2)


def test_save_and_load_classification_roundtrip(cache_dir):
    from regs.emergency_types import Projection
    r = _rule()
    p = Projection(
        section_id="hanford_lower_i182_to_snyder",
        status="closed",
        effective_from=date(2026, 5, 1),
        effective_to=date(2026, 6, 30),
        reason="Rule explicitly mentions Hanford Reach lower section.",
        authority="WDFW",
    )
    c = Classification(
        projections=[p],
        confidence=0.95,
        reasoning="Rule explicitly mentions Hanford Reach lower section.",
    )
    save_cached_classification(r, c)
    loaded = load_cached_classification(r)
    assert loaded == c


def test_load_classification_missing_returns_none(cache_dir):
    assert load_cached_classification(_rule()) is None


def test_classify_rule_produces_projection_per_section(monkeypatch, tmp_path):
    """The classifier returns a Classification with projections covering each
    (section_id, date-window) pair found in the rule body."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from datetime import date, datetime
    from regs.emergency_classifier import classify_rule
    from regs.emergency_types import EmergencyRule

    # Stub the Anthropic client to return a deterministic JSON response.
    class _StubResponse:
        def __init__(self, text):
            self.content = [type("M", (), {"text": text})()]
    class _StubMessages:
        def create(self, **_kwargs):
            return _StubResponse('{\n'
                '  "projections": [\n'
                '    {"section_id": "snake_lower_monumental_to_little_goose",\n'
                '     "status": "open",\n'
                '     "effective_from": "2026-05-15", "effective_to": "2026-05-15",\n'
                '     "reason": "Little Goose 1-day opener"},\n'
                '    {"section_id": "snake_lower_monumental_to_little_goose",\n'
                '     "status": "open",\n'
                '     "effective_from": "2026-05-19", "effective_to": "2026-05-19",\n'
                '     "reason": "Little Goose 1-day opener"},\n'
                '    {"section_id": "snake_goose_island_to_ice_harbor",\n'
                '     "status": "open",\n'
                '     "effective_from": "2026-05-20", "effective_to": "2026-05-21",\n'
                '     "reason": "Ice Harbor 2-day opener"}\n'
                '  ],\n'
                '  "confidence": 0.95,\n'
                '  "reasoning": "snake spring chinook fishery change"\n'
                '}')
    class _StubClient:
        messages = _StubMessages()

    monkeypatch.setattr("regs.emergency_classifier._anthropic_client", lambda: _StubClient())

    rule = EmergencyRule(
        url="https://wdfw.wa.gov/x", title="Snake Spring Chinook Fishery Change",
        body="Snake from Texas Rapids to Little Goose: open May 15 and 19. "
             "Below Ice Harbor: open May 20-21.",
        effective_from=date(2026, 5, 13), effective_to=date(2026, 7, 1),
        modified_at=datetime.now(),
    )
    sections = [
        {"id": "snake_lower_monumental_to_little_goose",
         "description": "Snake R, Texas Rapids to Little Goose Dam"},
        {"id": "snake_goose_island_to_ice_harbor",
         "description": "Snake R, Goose Island to Ice Harbor Dam"},
    ]
    c = classify_rule(rule, sections)
    assert c is not None
    assert len(c.projections) == 3
    # Each projection carries authority "WDFW" (set by classifier post-process).
    assert all(p.authority == "WDFW" for p in c.projections)
    # Discrete-date projections survive (from == to).
    discrete = [p for p in c.projections if p.effective_from == p.effective_to]
    assert len(discrete) == 2


def test_classify_rule_returns_none_for_irrelevant_rule(monkeypatch, tmp_path):
    """Empty projections list — rule unrelated to salmon retention — returns None."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from datetime import date, datetime
    from regs.emergency_classifier import classify_rule
    from regs.emergency_types import EmergencyRule

    class _StubResponse:
        def __init__(self, text):
            self.content = [type("M", (), {"text": text})()]
    class _StubMessages:
        def create(self, **_kwargs):
            return _StubResponse('{"projections": [], "confidence": 0.9, "reasoning": "halibut"}')
    class _StubClient:
        messages = _StubMessages()
    monkeypatch.setattr("regs.emergency_classifier._anthropic_client", lambda: _StubClient())

    rule = EmergencyRule(
        url="https://wdfw.wa.gov/halibut",
        title="Marine area halibut", body="halibut rules",
        effective_from=date(2026, 5, 1), effective_to=None,
        modified_at=datetime.now(),
    )
    assert classify_rule(rule, []) is None


def test_classify_rule_caches_projections_to_disk(monkeypatch, tmp_path):
    """The cache survives across calls — second call doesn't hit the API."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from datetime import date, datetime
    from regs.emergency_classifier import classify_rule
    from regs.emergency_types import EmergencyRule

    call_count = {"n": 0}
    class _StubResponse:
        def __init__(self, text): self.content = [type("M", (), {"text": text})()]
    class _StubMessages:
        def create(self, **_kwargs):
            call_count["n"] += 1
            return _StubResponse('{"projections": ['
                '{"section_id": "x", "status": "open",'
                ' "effective_from": "2026-06-01", "effective_to": "2026-06-15",'
                ' "reason": "test"}'
                '], "confidence": 0.9, "reasoning": "test"}')
    class _StubClient:
        messages = _StubMessages()
    monkeypatch.setattr("regs.emergency_classifier._anthropic_client", lambda: _StubClient())

    rule = EmergencyRule(
        url="https://w/x", title="t", body="b",
        effective_from=None, effective_to=None, modified_at=datetime.now(),
    )
    c1 = classify_rule(rule, [{"id": "x", "description": "y"}])
    c2 = classify_rule(rule, [{"id": "x", "description": "y"}])
    assert call_count["n"] == 1  # second call hit the cache
    assert c1 == c2
    assert c1.projections[0].section_id == "x"
