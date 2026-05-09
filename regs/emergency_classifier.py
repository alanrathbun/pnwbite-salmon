"""Claude-API classifier for WDFW emergency rules.

Maps each WDFW emergency-rule entry to a list of pamphlet section ids plus an
open/closed verdict. Results are cached on disk by (url, title, body) so
we re-classify only when WDFW updates a rule's text.
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
    """Stable key incorporating url + title + body — cache hits survive cron runs;
    cache misses trigger re-classification when WDFW edits a rule's text.

    Note: modified_at is intentionally NOT in the key. WDFW's advanced-search
    listing has no per-row modified timestamp, so modified_at often defaults to
    datetime.now() at parse time. Including it would defeat the cache.
    """
    h = hashlib.sha256()
    h.update(rule.url.encode("utf-8"))
    h.update(b"\n")
    h.update(rule.title.encode("utf-8"))
    h.update(b"\n")
    h.update(rule.body[:500].encode("utf-8"))
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


# Anthropic client constructed lazily so missing API key is non-fatal at import time.
_CLIENT = None
CONFIDENCE_THRESHOLD = 0.7
MODEL = "claude-sonnet-4-6"


def _anthropic_client():
    """Return a cached Anthropic client, or None if API key is missing."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set; emergency classifier disabled")
        return None
    try:
        from anthropic import Anthropic
        _CLIENT = Anthropic(api_key=api_key)
        return _CLIENT
    except ImportError:
        log.error("anthropic SDK not installed; emergency classifier disabled")
        return None


def _build_prompt(rule: EmergencyRule, pamphlet_sections: list[dict]) -> str:
    sections_text = "\n".join(
        f"- {s['id']}: {s.get('description', '')}"
        for s in pamphlet_sections
    )
    return f"""You are classifying a WDFW emergency fishing-rule notice into the pamphlet section namespace.

PAMPHLET SECTIONS (id: description):
{sections_text}

EMERGENCY RULE:
Title: {rule.title}
Body: {rule.body}
Effective: {rule.effective_from} to {rule.effective_to}

Output a single JSON object (no surrounding text) with these fields:
- section_ids: list of pamphlet section ids this rule affects (may be empty if rule covers an area not in the pamphlet)
- status: "open" or "closed" — the verdict this rule imposes on the listed sections
- effective_from: ISO date "YYYY-MM-DD" (or null)
- effective_to: ISO date "YYYY-MM-DD" (or null)
- confidence: 0.0-1.0 — how certain you are about the section_ids mapping AND the open/closed direction
- reasoning: one short sentence explaining the match

If the rule's geographic scope cannot be matched to any pamphlet section description above, return section_ids=[]. If the rule's open/closed direction is ambiguous, return confidence < 0.7.

Output JSON only.
"""


def classify_rule(rule: EmergencyRule, pamphlet_sections: list[dict]) -> Classification | None:
    """Classify a rule. Returns cached result if present; calls Anthropic API otherwise.

    Returns None when:
      - Cache miss AND API key/SDK unavailable
      - Confidence below threshold
      - section_ids is empty (rule doesn't map to any pamphlet section)
      - JSON parse fails
    """
    cached = load_cached_classification(rule)
    if cached is not None:
        return _filter(cached)

    client = _anthropic_client()
    if client is None:
        return None

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": _build_prompt(rule, pamphlet_sections)}],
        )
        text = resp.content[0].text.strip()
        # Strip optional code-fence
        if text.startswith("```"):
            text = "\n".join(line for line in text.splitlines() if not line.startswith("```"))
        payload = json.loads(text)
    except Exception as e:
        log.warning("classify_rule failed for %s: %s", rule.url, e)
        return None

    classification = Classification(
        section_ids=list(payload.get("section_ids") or []),
        status=payload.get("status", "open"),
        effective_from=date.fromisoformat(payload["effective_from"]) if payload.get("effective_from") else None,
        effective_to=date.fromisoformat(payload["effective_to"]) if payload.get("effective_to") else None,
        confidence=float(payload.get("confidence", 0.0)),
        reasoning=str(payload.get("reasoning", "")),
    )
    save_cached_classification(rule, classification)
    return _filter(classification)


def _filter(c: Classification) -> Classification | None:
    """Drop classifications that are too low-confidence or empty."""
    if c.confidence < CONFIDENCE_THRESHOLD:
        return None
    if not c.section_ids:
        return None
    return c
