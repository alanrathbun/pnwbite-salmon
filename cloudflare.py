"""Cloudflare cache-purge helper.

Called after each cron run to invalidate the edge cache for the report.
Token + zone-id come from env vars; if either is missing, the function returns
False (silent no-op). API errors are also swallowed (logged, not raised) so a
purge failure never breaks a cron run.
"""
from __future__ import annotations

import logging
import os

import requests

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"

log = logging.getLogger("cloudflare")


class MissingCloudflareConfig(RuntimeError):
    """Raised when strict=True and CLOUDFLARE_PURGE_TOKEN or CLOUDFLARE_ZONE_ID is unset."""


def purge_cache(*, strict: bool = False, timeout: int = 10) -> bool:
    """Purge all cached files for the configured Cloudflare zone.

    Returns True on success, False on missing-config or API failure.
    If strict=True, raises MissingCloudflareConfig when env vars are missing.
    """
    token = os.environ.get("CLOUDFLARE_PURGE_TOKEN")
    zone = os.environ.get("CLOUDFLARE_ZONE_ID")
    if not (token and zone):
        if strict:
            raise MissingCloudflareConfig(
                "CLOUDFLARE_PURGE_TOKEN and CLOUDFLARE_ZONE_ID must both be set"
            )
        log.info("Cloudflare config not set; skipping cache purge")
        return False

    try:
        r = requests.post(
            f"{CLOUDFLARE_API_BASE}/zones/{zone}/purge_cache",
            headers={"Authorization": f"Bearer {token}"},
            json={"purge_everything": True},
            timeout=timeout,
        )
        r.raise_for_status()
        log.info("Cloudflare cache purged for zone %s", zone)
        return True
    except Exception as e:
        log.warning("Cloudflare cache purge failed: %s", e)
        return False
