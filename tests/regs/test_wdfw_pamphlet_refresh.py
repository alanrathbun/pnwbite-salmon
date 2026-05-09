"""Tests for the pamphlet-refresh detector — filename change + email."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from regs.wdfw_pamphlet_refresh import (
    extract_filename,
    check_for_new_pamphlet,
)


def _head_response(content_disposition: str | None = None, url: str = "https://wdfw.wa.gov/sites/default/files/publications/02559/25WAFW_LR7.pdf"):
    r = MagicMock()
    r.status_code = 200
    r.url = url
    r.headers = {}
    if content_disposition:
        r.headers["Content-Disposition"] = content_disposition
    return r


def test_extract_filename_from_content_disposition():
    r = _head_response(content_disposition='attachment; filename="26WAFW_LR1.pdf"')
    assert extract_filename(r) == "26WAFW_LR1.pdf"


def test_extract_filename_from_url_when_no_header():
    r = _head_response(content_disposition=None)
    assert extract_filename(r) == "25WAFW_LR7.pdf"


def test_check_for_new_pamphlet_first_run_initializes_cache(tmp_path, monkeypatch):
    """First run: no cache file. Should NOT email; should write current_filename.txt."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email:
        mock_head.return_value = _head_response(content_disposition='attachment; filename="25WAFW_LR7.pdf"')
        check_for_new_pamphlet()

    assert (cache_dir / "current_filename.txt").read_text(encoding="utf-8").strip() == "25WAFW_LR7.pdf"
    mock_email.assert_not_called()


def test_check_for_new_pamphlet_emails_on_change(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    (cache_dir / "current_filename.txt").write_text("25WAFW_LR7.pdf", encoding="utf-8")

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email:
        mock_head.return_value = _head_response(content_disposition='attachment; filename="26WAFW_LR1.pdf"')
        mock_email.return_value = True
        check_for_new_pamphlet()

    mock_email.assert_called_once()
    args, kwargs = mock_email.call_args
    subject, body = args
    assert "26WAFW_LR1.pdf" in subject
    assert "25WAFW_LR7.pdf" in body  # old filename for context
    assert "26WAFW_LR1.pdf" in body
    assert (cache_dir / "STALE_PAMPHLET").read_text(encoding="utf-8").strip() == "26WAFW_LR1.pdf"
    assert (cache_dir / "current_filename.txt").read_text(encoding="utf-8").strip() == "26WAFW_LR1.pdf"


def test_check_for_new_pamphlet_idempotent_on_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    (cache_dir / "current_filename.txt").write_text("25WAFW_LR7.pdf", encoding="utf-8")

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email:
        mock_head.return_value = _head_response(content_disposition='attachment; filename="25WAFW_LR7.pdf"')
        check_for_new_pamphlet()
        check_for_new_pamphlet()

    mock_email.assert_not_called()


def test_check_for_new_pamphlet_clears_stale_flag_when_yaml_caught_up(tmp_path, monkeypatch):
    """If STALE_PAMPHLET exists with content matching YAML's pamphlet_filename, clear it."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    (cache_dir / "current_filename.txt").write_text("26WAFW_LR1.pdf", encoding="utf-8")
    (cache_dir / "STALE_PAMPHLET").write_text("26WAFW_LR1.pdf", encoding="utf-8")

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email, \
         patch("regs.wdfw_pamphlet_refresh.pamphlet_filename") as mock_yaml_filename:
        mock_head.return_value = _head_response(content_disposition='attachment; filename="26WAFW_LR1.pdf"')
        mock_yaml_filename.return_value = "26WAFW_LR1.pdf"  # YAML matches flag
        check_for_new_pamphlet()

    assert not (cache_dir / "STALE_PAMPHLET").exists(), "stale flag should be cleared once YAML caught up"
    mock_email.assert_not_called()


def test_check_for_new_pamphlet_email_failure_keeps_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    (cache_dir / "current_filename.txt").write_text("25WAFW_LR7.pdf", encoding="utf-8")

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email:
        mock_head.return_value = _head_response(content_disposition='attachment; filename="26WAFW_LR1.pdf"')
        mock_email.return_value = False  # SendGrid failed
        check_for_new_pamphlet()

    # Flag still gets written, current_filename gets bumped — next cron retries email
    assert (cache_dir / "STALE_PAMPHLET").exists()
