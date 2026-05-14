"""Claude-API classifier for WDFW emergency rules.

Maps each WDFW emergency-rule entry to a list of Projections — one per
(section_id, status, date-window) tuple. Results are cached on disk by
(url, title, body) so we re-classify only when WDFW updates a rule's text.

A single rule may impose different open dates on different sections (e.g.
Snake Spring Chinook: Little Goose May 15+19, Ice Harbor May 20–21). The
new prompt explicitly handles this shape; old cache entries with the
pre-Projection schema are auto-invalidated by JSON parse failure.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

from regs.emergency_types import Classification, EmergencyRule, Projection

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


def _serialize_rule(r: EmergencyRule) -> dict:
    return {
        "url": r.url,
        "title": r.title,
        "body": r.body,
        "effective_from": r.effective_from.isoformat() if r.effective_from else None,
        "effective_to": r.effective_to.isoformat() if r.effective_to else None,
        "modified_at": r.modified_at.isoformat(),
    }


def _serialize_projection(p: Projection) -> dict:
    return {
        "section_id": p.section_id,
        "status": p.status,
        "effective_from": p.effective_from.isoformat() if p.effective_from else None,
        "effective_to": p.effective_to.isoformat() if p.effective_to else None,
        "reason": p.reason,
        "authority": p.authority,
    }


def _deserialize_projection(d: dict) -> Projection:
    return Projection(
        section_id=str(d["section_id"]),
        status=d["status"],
        effective_from=date.fromisoformat(d["effective_from"]) if d.get("effective_from") else None,
        effective_to=date.fromisoformat(d["effective_to"]) if d.get("effective_to") else None,
        reason=str(d.get("reason", "")),
        authority=str(d.get("authority", "WDFW")),
    )


def _serialize_classification(c: Classification) -> dict:
    return {
        "projections": [_serialize_projection(p) for p in c.projections],
        "confidence": c.confidence,
        "reasoning": c.reasoning,
    }


def _deserialize_classification(d: dict) -> Classification:
    return Classification(
        projections=[_deserialize_projection(p) for p in d["projections"]],
        confidence=float(d["confidence"]),
        reasoning=str(d.get("reasoning", "")),
    )


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
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        log.warning("cache read failed for %s: %s", path, e)
        return None


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

CRITICAL INSTRUCTIONS:

1. PARSE THE BODY TEXT for specific open or closed date windows. Each section may have
   multiple discrete dates (e.g. "open May 15 and 19, 2026, only") OR a continuous range
   (e.g. "open July 1 through August 31"). Discrete dates produce one projection each;
   continuous ranges produce one projection with effective_from <= effective_to.

2. DO NOT use any "rule effective" metadata if not stated in the body. The dates that go
   into projections come from the BODY TEXT describing salmon open/closed windows.

3. SECTION ID MATCHING: only include section_ids whose description matches a geographic
   reach explicitly named in the body. If the body names "below Little Goose Dam" and one
   pamphlet section maps to that reach, that is THE section. Do not also include adjacent
   upstream/downstream sections unless the body separately names them too.

4. STATUS: "open" if the rule grants salmon retention for that section on those dates;
   "closed" if the rule prohibits retention.

OUTPUT: a single JSON object (no surrounding text) with these fields:
- projections: list of objects, each with:
    - section_id: a pamphlet section id from the list above
    - status: "open" or "closed"
    - effective_from: ISO "YYYY-MM-DD" (or null if unspecified)
    - effective_to: ISO "YYYY-MM-DD" (or null if unspecified)
    - reason: one short phrase describing this specific date window
- confidence: 0.0-1.0 — your certainty in (a) the section_ids mapping and (b) the
  open/closed status/date windows. Be honest: if the body text is ambiguous about which
  pamphlet section, lower confidence accordingly.
- reasoning: one short sentence

WORKED EXAMPLE:

  Body: "Below Little Goose Dam (from Texas Rapids upstream to Little Goose Dam):
         Salmon open May 15 and 19, 2026, only.
         Below Ice Harbor Dam (from Hwy 12 bridge upstream to Ice Harbor Dam):
         Salmon open May 20 and 21, 2026, only."

  Pamphlet sections include:
    - snake_lower_monumental_to_little_goose: "Snake R, Texas Rapids to Little Goose Dam"
    - snake_goose_island_to_ice_harbor: "Snake R, Goose Island to Ice Harbor Dam"

  Correct output:
    projections: [
      {{"section_id": "snake_lower_monumental_to_little_goose", "status": "open",
        "effective_from": "2026-05-15", "effective_to": "2026-05-15",
        "reason": "Little Goose 1-day opener"}},
      {{"section_id": "snake_lower_monumental_to_little_goose", "status": "open",
        "effective_from": "2026-05-19", "effective_to": "2026-05-19",
        "reason": "Little Goose 1-day opener"}},
      {{"section_id": "snake_goose_island_to_ice_harbor", "status": "open",
        "effective_from": "2026-05-20", "effective_to": "2026-05-20",
        "reason": "Ice Harbor 1-day opener"}},
      {{"section_id": "snake_goose_island_to_ice_harbor", "status": "open",
        "effective_from": "2026-05-21", "effective_to": "2026-05-21",
        "reason": "Ice Harbor 1-day opener"}}
    ]
    confidence: 0.95
    reasoning: "snake spring chinook fishery change - 2 sections, 4 discrete dates"

If the rule's geographic scope cannot be matched to any pamphlet section above, return
projections=[]. If the rule is not about salmon retention (e.g. halibut, sturgeon, marine
areas), return projections=[].

Output JSON only.
"""


def classify_rule(rule: EmergencyRule, pamphlet_sections: list[dict]) -> Classification | None:
    """Classify a rule. Returns cached result if present; calls Anthropic API otherwise.

    Returns None when:
      - Cache miss AND API key/SDK unavailable
      - Confidence below threshold
      - projections list is empty (rule doesn't map to any pamphlet section)
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
            max_tokens=1024,
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

    raw_projections = payload.get("projections") or []
    projections = [
        Projection(
            section_id=str(p.get("section_id", "")),
            status=p.get("status", "open"),
            effective_from=date.fromisoformat(p["effective_from"]) if p.get("effective_from") else None,
            effective_to=date.fromisoformat(p["effective_to"]) if p.get("effective_to") else None,
            reason=str(p.get("reason", "")),
            authority="WDFW",
        )
        for p in raw_projections
    ]

    classification = Classification(
        projections=projections,
        confidence=float(payload.get("confidence", 0.0)),
        reasoning=str(payload.get("reasoning", "")),
    )
    save_cached_classification(rule, classification)
    return _filter(classification)


def _filter(c: Classification) -> Classification | None:
    """Drop classifications that are too low-confidence or empty."""
    if c.confidence < CONFIDENCE_THRESHOLD:
        return None
    if not c.projections:
        return None
    return c
