"""Tests for the Cloudflare Worker mailer relay. Network is mocked."""
from unittest.mock import MagicMock, patch

import pytest

from notify import send_admin_email


def test_send_admin_email_posts_to_relay_with_bearer(monkeypatch):
    monkeypatch.setenv("MAILER_SHARED_SECRET", "test-secret")
    monkeypatch.setenv("MAILER_URL", "https://pnwbite.com/send-email")

    with patch("notify.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text='{"ok":true}')
        ok = send_admin_email("test subject", "test body")

    assert ok is True
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"] == {"subject": "test subject", "body": "test body"}
    assert call_kwargs["headers"]["Authorization"] == "Bearer test-secret"
    assert mock_post.call_args.args[0] == "https://pnwbite.com/send-email"


def test_send_admin_email_no_op_when_secret_missing(monkeypatch, caplog):
    monkeypatch.delenv("MAILER_SHARED_SECRET", raising=False)
    ok = send_admin_email("subj", "body")
    assert ok is False
    assert any("MAILER_SHARED_SECRET" in r.message for r in caplog.records)


def test_send_admin_email_returns_false_on_5xx(monkeypatch):
    monkeypatch.setenv("MAILER_SHARED_SECRET", "test-secret")

    with patch("notify.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=502, text="Bad gateway")
        ok = send_admin_email("subj", "body")

    assert ok is False


def test_send_admin_email_returns_false_on_request_exception(monkeypatch):
    monkeypatch.setenv("MAILER_SHARED_SECRET", "test-secret")

    with patch("notify.requests.post") as mock_post:
        import requests as _requests
        mock_post.side_effect = _requests.RequestException("connection refused")
        ok = send_admin_email("subj", "body")

    assert ok is False


def test_send_admin_email_uses_default_url_when_unset(monkeypatch):
    monkeypatch.setenv("MAILER_SHARED_SECRET", "test-secret")
    monkeypatch.delenv("MAILER_URL", raising=False)

    with patch("notify.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text='{"ok":true}')
        send_admin_email("s", "b")

    assert mock_post.call_args.args[0] == "https://pnwbite.com/send-email"
