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
    r = _rule()
    c = Classification(
        section_ids=["hanford_lower_i182_to_snyder"],
        status="closed",
        effective_from=date(2026, 5, 1),
        effective_to=date(2026, 6, 30),
        confidence=0.95,
        reasoning="Rule explicitly mentions Hanford Reach lower section.",
    )
    save_cached_classification(r, c)
    loaded = load_cached_classification(r)
    assert loaded == c


def test_load_classification_missing_returns_none(cache_dir):
    assert load_cached_classification(_rule()) is None
