"""Daily detector for new WDFW pamphlet editions.

Steps each run:
  1. HEAD-request the WDFW pamphlet PDF URL.
  2. Compare filename (Content-Disposition or URL) against /data/pamphlet-cache/current_filename.txt.
  3. On change: write STALE_PAMPHLET flag + email admin.
  4. On unchanged: if STALE_PAMPHLET exists with content matching YAML's pamphlet_filename, clear it
     (admin completed YAML review).

Module is import-safe: missing env vars / deps result in no-op + warning, not crashes.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import requests

from notify import send_admin_email
from regs.wdfw_pamphlet import pamphlet_filename
from utils import USER_AGENT

log = logging.getLogger("pamphlet_refresh")

WDFW_PAMPHLET_URL = "https://wdfw.wa.gov/sites/default/files/publications/02559/wdfw02559.pdf"


def _cache_dir() -> Path:
    root = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent.parent)))
    d = root / "pamphlet-cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_filename(response) -> str:
    """Return the PDF filename from Content-Disposition, falling back to URL path."""
    cd = response.headers.get("Content-Disposition", "")
    m = re.search(r'filename="?([^"]+)"?', cd)
    if m:
        return m.group(1)
    return response.url.rsplit("/", 1)[-1]


def check_for_new_pamphlet() -> None:
    """Run the full detector pass. Idempotent."""
    cache = _cache_dir()
    current_file = cache / "current_filename.txt"
    stale_flag = cache / "STALE_PAMPHLET"

    try:
        resp = requests.head(
            WDFW_PAMPHLET_URL,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        log.warning("HEAD request failed: %s — skipping refresh check", e)
        return

    new_filename = extract_filename(resp)
    if not new_filename:
        log.warning("could not determine pamphlet filename from HEAD response")
        return

    cached = current_file.read_text(encoding="utf-8").strip() if current_file.exists() else ""

    if cached == new_filename:
        if stale_flag.exists():
            flag_filename = stale_flag.read_text(encoding="utf-8").strip()
            if flag_filename == pamphlet_filename():
                stale_flag.unlink()
                log.info("STALE_PAMPHLET cleared — YAML pamphlet_filename matches %s", flag_filename)
        return

    if not cached:
        # First run — initialize cache without emailing.
        current_file.write_text(new_filename, encoding="utf-8")
        log.info("first-run initialization: cached pamphlet filename = %s", new_filename)
        return

    log.info("new pamphlet detected: %s -> %s", cached, new_filename)
    stale_flag.write_text(new_filename, encoding="utf-8")
    current_file.write_text(new_filename, encoding="utf-8")

    body = (
        f"A new WDFW Sport Fishing Pamphlet has been detected.\n\n"
        f"Old filename: {cached}\n"
        f"New filename: {new_filename}\n"
        f"URL: {WDFW_PAMPHLET_URL}\n\n"
        f"Action required:\n"
        f"1. Download the new PDF.\n"
        f"2. Diff your encoded sections against the new prose.\n"
        f"3. Update wdfw_pamphlet.yaml — set pamphlet_filename to '{new_filename}' "
        f"and bump pamphlet_version once changes are reviewed.\n"
        f"4. The 'rules may be stale' banner clears at the next 07:00 cron after "
        f"the YAML update.\n"
    )
    sent = send_admin_email(
        f"WDFW pamphlet changed: {new_filename}",
        body,
    )
    if not sent:
        log.warning("admin email failed; STALE_PAMPHLET flag still set, will retry next cron")
