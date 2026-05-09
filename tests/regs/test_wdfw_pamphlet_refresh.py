"""Tests for the pamphlet-refresh detector — Last-Modified change + email."""
from unittest.mock import MagicMock, patch

from regs.wdfw_pamphlet_refresh import (
    extract_last_modified,
    check_for_new_pamphlet,
    WDFW_PAMPHLET_URL,
)


def _head_response(last_modified: str | None = None, url: str = WDFW_PAMPHLET_URL):
    r = MagicMock()
    r.status_code = 200
    r.url = url
    r.headers = {}
    if last_modified:
        r.headers["Last-Modified"] = last_modified
    return r


def test_extract_last_modified_returns_header_value():
    r = _head_response(last_modified="Thu, 23 Jan 2025 18:42:11 GMT")
    assert extract_last_modified(r) == "Thu, 23 Jan 2025 18:42:11 GMT"


def test_extract_last_modified_returns_none_when_absent():
    r = _head_response(last_modified=None)
    assert extract_last_modified(r) is None


def test_check_for_new_pamphlet_first_run_initializes_cache(tmp_path, monkeypatch):
    """First run: no cache file. Should NOT email; should write last_modified.txt."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email:
        mock_head.return_value = _head_response(last_modified="Thu, 23 Jan 2025 18:42:11 GMT")
        check_for_new_pamphlet()

    assert (cache_dir / "last_modified.txt").read_text(encoding="utf-8").strip() == "Thu, 23 Jan 2025 18:42:11 GMT"
    mock_email.assert_not_called()


def test_check_for_new_pamphlet_emails_on_change(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    old_lm = "Thu, 23 Jan 2025 18:42:11 GMT"
    new_lm = "Mon, 29 Jun 2026 14:05:00 GMT"
    (cache_dir / "last_modified.txt").write_text(old_lm, encoding="utf-8")

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email:
        mock_head.return_value = _head_response(last_modified=new_lm)
        mock_email.return_value = True
        check_for_new_pamphlet()

    mock_email.assert_called_once()
    args, kwargs = mock_email.call_args
    subject, body = args
    assert "WDFW pamphlet may have updated" in subject
    assert new_lm in subject
    assert old_lm in body  # old Last-Modified for context
    assert new_lm in body
    assert WDFW_PAMPHLET_URL in body
    assert "rm /data/pamphlet-cache/STALE_PAMPHLET" in body
    assert (cache_dir / "STALE_PAMPHLET").read_text(encoding="utf-8").strip() == new_lm
    assert (cache_dir / "last_modified.txt").read_text(encoding="utf-8").strip() == new_lm


def test_check_for_new_pamphlet_idempotent_on_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    lm = "Thu, 23 Jan 2025 18:42:11 GMT"
    (cache_dir / "last_modified.txt").write_text(lm, encoding="utf-8")

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email:
        mock_head.return_value = _head_response(last_modified=lm)
        check_for_new_pamphlet()
        check_for_new_pamphlet()

    mock_email.assert_not_called()


def test_check_for_new_pamphlet_preserves_stale_flag_on_unchanged(tmp_path, monkeypatch):
    """Once STALE_PAMPHLET is set, subsequent unchanged runs must NOT clear it.

    Admin must `rm` the flag manually after updating YAML — the cron has no
    reliable signal to know review is complete.
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    lm = "Mon, 29 Jun 2026 14:05:00 GMT"
    (cache_dir / "last_modified.txt").write_text(lm, encoding="utf-8")
    (cache_dir / "STALE_PAMPHLET").write_text(lm, encoding="utf-8")

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email:
        mock_head.return_value = _head_response(last_modified=lm)
        check_for_new_pamphlet()

    assert (cache_dir / "STALE_PAMPHLET").exists(), "stale flag should persist until admin manually rm's it"
    assert (cache_dir / "STALE_PAMPHLET").read_text(encoding="utf-8").strip() == lm
    mock_email.assert_not_called()


def test_check_for_new_pamphlet_email_failure_keeps_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    old_lm = "Thu, 23 Jan 2025 18:42:11 GMT"
    new_lm = "Mon, 29 Jun 2026 14:05:00 GMT"
    (cache_dir / "last_modified.txt").write_text(old_lm, encoding="utf-8")

    with patch("regs.wdfw_pamphlet_refresh.requests.head") as mock_head, \
         patch("regs.wdfw_pamphlet_refresh.send_admin_email") as mock_email:
        mock_head.return_value = _head_response(last_modified=new_lm)
        mock_email.return_value = False  # SendGrid failed
        check_for_new_pamphlet()

    # Flag still gets written, last_modified gets bumped — next cron retries email
    assert (cache_dir / "STALE_PAMPHLET").exists()
