"""Tests for the Resend wrapper. Network is mocked."""
from unittest.mock import patch

import pytest

from notify import send_admin_email


def test_send_admin_email_calls_resend_with_expected_args(monkeypatch):
    monkeypatch.setenv("FISHING_REPORTS", "re_test_key")
    monkeypatch.setenv("FROM_EMAIL", "from@example.com")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")

    with patch("notify.resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "abc-123"}
        ok = send_admin_email("test subject", "test body")

    assert ok is True
    mock_send.assert_called_once()
    params = mock_send.call_args[0][0]
    assert params["from"] == "from@example.com"
    assert params["to"] == ["admin@example.com"]
    assert params["subject"] == "test subject"
    assert params["text"] == "test body"


def test_send_admin_email_no_op_when_api_key_missing(monkeypatch, caplog):
    monkeypatch.delenv("FISHING_REPORTS", raising=False)
    ok = send_admin_email("subj", "body")
    assert ok is False
    assert any("FISHING_REPORTS" in r.message for r in caplog.records)


def test_send_admin_email_returns_false_on_exception(monkeypatch):
    monkeypatch.setenv("FISHING_REPORTS", "re_test_key")
    monkeypatch.setenv("FROM_EMAIL", "from@example.com")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")

    with patch("notify.resend.Emails.send") as mock_send:
        mock_send.side_effect = RuntimeError("API error")
        ok = send_admin_email("subj", "body")

    assert ok is False


def test_send_admin_email_returns_false_when_no_id_returned(monkeypatch):
    monkeypatch.setenv("FISHING_REPORTS", "re_test_key")
    monkeypatch.setenv("FROM_EMAIL", "from@example.com")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")

    with patch("notify.resend.Emails.send") as mock_send:
        mock_send.return_value = {}  # No id field
        ok = send_admin_email("subj", "body")

    assert ok is False
