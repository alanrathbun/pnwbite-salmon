"""Tests for the Claude-API classifier path. Anthropic client is mocked."""
import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

from regs.emergency_classifier import classify_rule
from regs.emergency_types import EmergencyRule


def _rule():
    return EmergencyRule(
        url="https://wdfw.wa.gov/abc",
        title="Hanford Reach lower closed to salmon",
        body="The Hanford Reach from the I-182 Bridge to Snyder Boat Launch is closed to salmon retention from May 1 to June 30, 2026.",
        effective_from=date(2026, 5, 1),
        effective_to=date(2026, 6, 30),
        modified_at=datetime(2026, 5, 1, 12, 0),
    )


def _mock_anthropic_response(text: str) -> MagicMock:
    """Build a fake Anthropic Messages API response with content[0].text == text."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


@patch("regs.emergency_classifier._anthropic_client")
def test_classify_rule_parses_json_payload(mock_client_factory, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_response(
        json.dumps({
            "projections": [
                {
                    "section_id": "hanford_lower_i182_to_snyder",
                    "status": "closed",
                    "effective_from": "2026-05-01",
                    "effective_to": "2026-06-30",
                    "reason": "Rule mentions Hanford Reach lower from I-182 to Snyder.",
                }
            ],
            "confidence": 0.95,
            "reasoning": "Rule mentions Hanford Reach lower from I-182 to Snyder.",
        })
    )
    mock_client_factory.return_value = fake_client

    result = classify_rule(_rule(), pamphlet_sections=[
        {"id": "hanford_lower_i182_to_snyder", "description": "From the I-182 Bridge to a line between the Snyder Boat Launch..."}
    ])

    assert result is not None
    assert len(result.projections) == 1
    assert result.projections[0].section_id == "hanford_lower_i182_to_snyder"
    assert result.projections[0].status == "closed"
    assert result.projections[0].authority == "WDFW"
    assert result.confidence == 0.95


@patch("regs.emergency_classifier._anthropic_client")
def test_classify_rule_low_confidence_returns_none(mock_client_factory, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_response(
        json.dumps({
            "projections": [
                {
                    "section_id": "hanford_lower_i182_to_snyder",
                    "status": "closed",
                    "effective_from": "2026-05-01",
                    "effective_to": "2026-06-30",
                    "reason": "Vague language.",
                }
            ],
            "confidence": 0.4,
            "reasoning": "Vague language.",
        })
    )
    mock_client_factory.return_value = fake_client

    result = classify_rule(_rule(), pamphlet_sections=[])
    assert result is None  # below 0.7 threshold


@patch("regs.emergency_classifier._anthropic_client")
def test_classify_rule_empty_projections_returns_none(mock_client_factory, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_response(
        json.dumps({
            "projections": [],
            "confidence": 0.95,
            "reasoning": "No matching pamphlet section.",
        })
    )
    mock_client_factory.return_value = fake_client

    result = classify_rule(_rule(), pamphlet_sections=[])
    assert result is None


@patch("regs.emergency_classifier._anthropic_client")
def test_classify_rule_uses_cache_on_second_call(mock_client_factory, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _mock_anthropic_response(
        json.dumps({
            "projections": [
                {
                    "section_id": "hanford_lower_i182_to_snyder",
                    "status": "closed",
                    "effective_from": "2026-05-01",
                    "effective_to": "2026-06-30",
                    "reason": "Match.",
                }
            ],
            "confidence": 0.95,
            "reasoning": "Match.",
        })
    )
    mock_client_factory.return_value = fake_client

    sections = [{"id": "hanford_lower_i182_to_snyder", "description": "..."}]
    classify_rule(_rule(), pamphlet_sections=sections)
    classify_rule(_rule(), pamphlet_sections=sections)

    assert fake_client.messages.create.call_count == 1, "second call should hit cache, not Anthropic"


def test_classify_rule_no_api_key_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = classify_rule(_rule(), pamphlet_sections=[])
    assert result is None
