"""Claude-API classifier for WDFW emergency rules.

Maps each WDFW emergency-rule entry to a list of pamphlet section ids plus an
open/closed verdict. Results are cached on disk by (rule_url, modified_at) so
we re-classify only when WDFW updates a rule.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from regs.emergency_types import Classification, EmergencyRule

log = logging.getLogger("emergency_classifier")


def _cache_dir() -> Path:
    root = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent.parent)))
    d = root / "emergency-cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key_for(rule: EmergencyRule) -> str:
    """Stable key incorporating url + modified_at — re-classify when WDFW edits a rule."""
    h = hashlib.sha256()
    h.update(rule.url.encode("utf-8"))
    h.update(b"\n")
    h.update(rule.modified_at.isoformat().encode("utf-8"))
    return h.hexdigest()[:32]


def _cache_path(rule: EmergencyRule) -> Path:
    return _cache_dir() / f"{cache_key_for(rule)}.json"


def save_cached_classification(rule: EmergencyRule, classification: Classification) -> None:
    payload = {
        "rule": _serialize_rule(rule),
        "classification": _serialize_classification(classification),
    }
    path = _cache_path(rule)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_cached_classification(rule: EmergencyRule) -> Classification | None:
    path = _cache_path(rule)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _deserialize_classification(payload["classification"])
    except (json.JSONDecodeError, KeyError) as e:
        log.warning("cache read failed for %s: %s", path, e)
        return None


def _serialize_rule(r: EmergencyRule) -> dict:
    d = asdict(r)
    if d["effective_from"]:
        d["effective_from"] = d["effective_from"].isoformat()
    if d["effective_to"]:
        d["effective_to"] = d["effective_to"].isoformat()
    d["modified_at"] = d["modified_at"].isoformat()
    return d


def _serialize_classification(c: Classification) -> dict:
    d = asdict(c)
    if d["effective_from"]:
        d["effective_from"] = d["effective_from"].isoformat()
    if d["effective_to"]:
        d["effective_to"] = d["effective_to"].isoformat()
    return d


def _deserialize_classification(d: dict) -> Classification:
    return Classification(
        section_ids=list(d["section_ids"]),
        status=d["status"],
        effective_from=date.fromisoformat(d["effective_from"]) if d.get("effective_from") else None,
        effective_to=date.fromisoformat(d["effective_to"]) if d.get("effective_to") else None,
        confidence=float(d["confidence"]),
        reasoning=str(d.get("reasoning", "")),
    )
