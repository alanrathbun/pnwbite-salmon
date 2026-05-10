"""Per-launch climatology cache.

Cache file shape (one file per launch under ``<DATA_DIR>/climatology-cache/``):

    {
      "fetched_at": "2026-05-10T12:34:56-07:00",
      "source": "open-meteo-archive-v1",
      "lat": 46.6483, "lon": -119.8833,
      "years": [2016, 2017, ..., 2025],
      "daily": {"01-01": {"high_f": 41, "low_f": 28}, ...}
    }

Refresh policy: if ``fetched_at`` is more than 365 days old (or the file is
missing), re-fetch. On fetch failure, fall back to the prior-good cache
contents; if no prior cache exists, return ``None`` and let the caller treat
long-range entries as climatology-less.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sources.climatology import fetch_climatology
from storage import FileStorage

log = logging.getLogger(__name__)

CACHE_DIR_NAME = "climatology-cache"
MAX_AGE_DAYS = 365


def _cache_path(launch: dict, *, storage: FileStorage) -> Path:
    return Path(storage.root) / CACHE_DIR_NAME / f"{launch['key']}.json"


def _read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _is_fresh(blob: dict[str, Any]) -> bool:
    fetched = blob.get("fetched_at")
    if not fetched:
        return False
    try:
        when = datetime.fromisoformat(fetched)
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when) <= timedelta(days=MAX_AGE_DAYS)


def _atomic_write(path: Path, blob: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(blob, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_or_refresh(launch: dict, *, storage: FileStorage) -> dict[str, dict[str, float]] | None:
    """Return the per-mm-dd climatology dict for *launch*.

    Reads cache; refreshes via ``fetch_climatology`` if stale or missing.
    On fetch failure, returns the last-good cache (even if stale). Returns
    ``None`` when no cache exists and the fetch also fails.
    """
    path = _cache_path(launch, storage=storage)
    cached = _read_cache(path)
    if cached and _is_fresh(cached):
        return cached.get("daily") or {}

    try:
        daily = fetch_climatology(launch["lat"], launch["lon"], years=10)
    except Exception as e:  # noqa: BLE001
        log.warning("climatology fetch failed for %s: %s", launch["key"], e)
        if cached:
            return cached.get("daily") or {}
        return None

    blob = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "open-meteo-archive-v1",
        "lat": launch["lat"],
        "lon": launch["lon"],
        "daily": daily,
    }
    _atomic_write(path, blob)
    return daily
