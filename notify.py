"""SendGrid wrapper for admin notifications.

Reads three env vars:
  - SENDGRID_API_KEY      — SendGrid API key
  - SENDGRID_FROM_EMAIL   — verified sender address (default: alan@pe-prep-engine.com)
  - ADMIN_EMAIL           — recipient (default: arathbun.pdm@gmail.com)

No-op + warning log if SENDGRID_API_KEY is missing. Used for pamphlet-refresh
alerts now; intended as the shared admin-alert channel for future scraper-failure
notifications.
"""
from __future__ import annotations

import logging
import os

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

log = logging.getLogger("notify")


def send_admin_email(subject: str, body: str) -> bool:
    """Send a plain-text email to ADMIN_EMAIL. Returns True on success."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        log.warning("SENDGRID_API_KEY not set; skipping admin email: %s", subject)
        return False

    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "alan@pe-prep-engine.com")
    to_email = os.environ.get("ADMIN_EMAIL", "arathbun.pdm@gmail.com")

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )
    try:
        client = SendGridAPIClient(api_key)
        resp = client.send(message)
        if 200 <= getattr(resp, "status_code", 0) < 300:
            log.info("admin email sent: %s", subject)
            return True
        log.warning("SendGrid returned status %s for: %s", resp.status_code, subject)
        return False
    except Exception as e:  # noqa: BLE001
        log.exception("SendGrid send failed: %s", e)
        return False
