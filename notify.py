"""HTTP relay to the Cloudflare Worker mailer at https://pnwbite.com/send-email.

The Worker authenticates with a shared secret (Authorization: Bearer ...) and
calls Cloudflare's SendEmail binding. We can't call SendEmail directly from
Railway because the binding is only available inside a Worker.

Reads four env vars:
  - MAILER_URL              — full URL of the relay endpoint (default: https://pnwbite.com/send-email)
  - MAILER_SHARED_SECRET    — Bearer token used by the relay to authenticate us
  - FROM_EMAIL              — informational only; the Worker hard-codes the From: header
  - ADMIN_EMAIL             — informational only; the Worker hard-codes the To: header

No-op + warning log if MAILER_SHARED_SECRET is missing.
"""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger("notify")

DEFAULT_MAILER_URL = "https://pnwbite.com/send-email"


def send_admin_email(subject: str, body: str) -> bool:
    """POST to the Cloudflare mailer relay. Returns True on 2xx."""
    secret = os.environ.get("MAILER_SHARED_SECRET")
    if not secret:
        log.warning("MAILER_SHARED_SECRET not set; skipping admin email: %s", subject)
        return False

    url = os.environ.get("MAILER_URL", DEFAULT_MAILER_URL)

    try:
        resp = requests.post(
            url,
            json={"subject": subject, "body": body},
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
    except requests.RequestException as e:
        log.exception("mailer request failed: %s", e)
        return False

    if 200 <= resp.status_code < 300:
        log.info("admin email sent via relay: %s", subject)
        return True

    log.warning("mailer returned %s for %s: %s", resp.status_code, subject, resp.text[:200])
    return False
