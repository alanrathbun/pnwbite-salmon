"""Daily detector for new WDFW pamphlet editions.

Detection signal: HTTP Last-Modified header on the WDFW pamphlet PDF URL.
The URL itself is a permanent container path that never changes between
editions, and the response has no Content-Disposition header. Last-Modified
is the only stable change indicator.

Steps each run:
  1. HEAD-request the WDFW pamphlet PDF URL.
  2. Read the Last-Modified header.
  3. Compare against /data/pamphlet-cache/last_modified.txt.
  4. On change: write STALE_PAMPHLET flag (content = new Last-Modified) +
     email admin. Update last_modified.txt to the new value.
  5. STALE_PAMPHLET stays in place until admin manually removes it after
     reviewing the new pamphlet and updating the YAML.

Module is import-safe: missing env vars / deps result in no-op + warning, not crashes.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

from notify import send_admin_email
from utils import USER_AGENT

log = logging.getLogger("pamphlet_refresh")

WDFW_PAMPHLET_URL = "https://wdfw.wa.gov/sites/default/files/publications/02559/wdfw02559.pdf"


def _cache_dir() -> Path:
    root = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent.parent)))
    d = root / "pamphlet-cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_last_modified(response) -> str | None:
    """Return the Last-Modified header value, or None if absent."""
    return response.headers.get("Last-Modified")


def check_for_new_pamphlet() -> None:
    """Run the full detector pass. Idempotent on unchanged Last-Modified."""
    cache = _cache_dir()
    last_mod_file = cache / "last_modified.txt"
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

    new_lm = extract_last_modified(resp)
    if not new_lm:
        log.warning("could not determine pamphlet Last-Modified from HEAD response")
        return

    cached = last_mod_file.read_text(encoding="utf-8").strip() if last_mod_file.exists() else ""

    if cached == new_lm:
        # Unchanged. Leave STALE_PAMPHLET in place if present (admin clears manually).
        return

    if not cached:
        # First run — initialize cache without emailing.
        last_mod_file.write_text(new_lm, encoding="utf-8")
        log.info("first-run initialization: cached pamphlet Last-Modified = %s", new_lm)
        return

    log.info("pamphlet Last-Modified changed: %s -> %s", cached, new_lm)
    stale_flag.write_text(new_lm, encoding="utf-8")
    last_mod_file.write_text(new_lm, encoding="utf-8")

    body = (
        f"The WDFW Sport Fishing Pamphlet PDF has been updated.\n\n"
        f"Previous Last-Modified: {cached}\n"
        f"New Last-Modified:      {new_lm}\n"
        f"URL: {WDFW_PAMPHLET_URL}\n\n"
        f"The URL is a permanent container path; the file at that URL has\n"
        f"changed. This usually means a new pamphlet edition has been published.\n\n"
        f"Action required:\n"
        f"1. Download the PDF from the URL above.\n"
        f"2. Open it and confirm whether this is a new edition or just a minor\n"
        f"   correction within the same edition.\n"
        f"3. If a new edition: derive a new filename label from the cover sheet\n"
        f"   (e.g., 26WAFW_LR1.pdf), then diff your encoded sections against the\n"
        f"   new prose and update wdfw_pamphlet.yaml (sections + pamphlet_filename\n"
        f"   + pamphlet_version).\n"
        f"4. Once review is complete, clear the stale-pamphlet banner manually:\n"
        f"   rm /data/pamphlet-cache/STALE_PAMPHLET\n"
        f"5. The 'rules may be stale' banner stays on the report until that flag\n"
        f"   file is removed.\n"
    )
    sent = send_admin_email(
        f"WDFW pamphlet may have updated (Last-Modified: {new_lm})",
        body,
    )
    if not sent:
        log.warning("admin email failed; STALE_PAMPHLET flag still set, will retry next cron")
