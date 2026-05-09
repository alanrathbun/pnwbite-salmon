"""Resend wrapper for admin notifications.

Reads three env vars:
  - FISHING_REPORTS   — Resend API key (named after the project on Railway)
  - FROM_EMAIL        — verified sender address
  - ADMIN_EMAIL       — recipient (default: arathbun.pdm@gmail.com)

No-op + warning log if FISHING_REPORTS is missing. Used for pamphlet-refresh
alerts now; intended as the shared admin-alert channel for future scraper-failure
notifications.
"""
from __future__ import annotations

import logging
import os

import resend

log = logging.getLogger("notify")


def send_admin_email(subject: str, body: str) -> bool:
    """Send a plain-text email to ADMIN_EMAIL via Resend. Returns True on success."""
    api_key = os.environ.get("FISHING_REPORTS")
    if not api_key:
        log.warning("FISHING_REPORTS not set; skipping admin email: %s", subject)
        return False

    from_email = os.environ.get("FROM_EMAIL", "arathbun.pdm@gmail.com")
    to_email = os.environ.get("ADMIN_EMAIL", "arathbun.pdm@gmail.com")

    resend.api_key = api_key

    params = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }

    try:
        result = resend.Emails.send(params)
        if result and result.get("id"):
            log.info("admin email sent (id=%s): %s", result["id"], subject)
            return True
        log.warning("Resend returned no id for: %s (result=%r)", subject, result)
        return False
    except Exception as e:  # noqa: BLE001
        log.exception("Resend send failed: %s", e)
        return False
