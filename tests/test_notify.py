"""Tests for the SendGrid wrapper. Network is mocked."""
from unittest.mock import MagicMock, patch

import pytest

from notify import send_admin_email


def test_send_admin_email_calls_sendgrid_with_expected_args(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "alan@pe-prep-engine.com")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")

    with patch("notify.SendGridAPIClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.send.return_value = MagicMock(status_code=202)
        mock_client_cls.return_value = mock_client

        ok = send_admin_email("test subject", "test body")

    assert ok is True
    mock_client_cls.assert_called_once_with("SG.test")
    mock_client.send.assert_called_once()
    sent = mock_client.send.call_args[0][0]
    assert "admin@example.com" in str(sent.get())


def test_send_admin_email_no_op_when_api_key_missing(monkeypatch, caplog):
    monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
    ok = send_admin_email("subj", "body")
    assert ok is False
    assert any("SENDGRID_API_KEY" in r.message for r in caplog.records)


def test_send_admin_email_returns_false_on_5xx(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "alan@pe-prep-engine.com")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")

    with patch("notify.SendGridAPIClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.send.side_effect = RuntimeError("503 server error")
        mock_client_cls.return_value = mock_client

        ok = send_admin_email("subj", "body")

    assert ok is False
