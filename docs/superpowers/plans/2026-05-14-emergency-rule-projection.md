# Emergency Rule Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** WDFW emergency rules (and ODFW/IDFG) currently apply only to today — future dates fall back to the pamphlet baseline, so the user can pick June 15 in the date picker and see "closed" even when a published emergency rule opens that exact date. Fix by carrying date-bounded `Projection`s through the regs pipeline so the per-day forecast loop sees emergency overlays for any day in the 365-day forecast horizon.

**Architecture:** Replace `emergency_layer: dict[str, RegStatus]` (today-only) with `emergency_projections: dict[str, list[Projection]]` (per-section list of date-bounded projections, one per open/closed window). The Claude classifier now returns `list[Projection]` from a single rule — supporting one rule with different dates for different sections (the Snake Spring Chinook rule's structure: "Little Goose section open May 15+19, Ice Harbor section open May 20+21"). A new `resolve_for_day(emergency_projections, section_id, day)` function does the per-day lookup; the per-day forecast loop in `fishing_report.py` calls it uniformly for all 365 offsets, replacing the current today-vs-future dual-path.

**Tech Stack:** Python stdlib + existing Anthropic SDK already in use.

**Spec context:** Discrete dates are represented as projections with `effective_from == effective_to`. A continuous range is `effective_from <= effective_to`. A projection with both fields `None` means "always active" (used for legacy ODFW/IDFG wrappers).

---

## File Map

- **Modify:** `regs/emergency_types.py` — add `Projection` dataclass; replace `Classification.{section_ids,status,effective_from,effective_to}` with `Classification.projections: list[Projection]`.
- **Modify:** `regs/emergency_classifier.py` — rewrite prompt to emit projections; update cache serialization.
- **Modify:** `regs/__init__.py` — `fetch_all` returns `emergency_projections: dict[str, list[Projection]]` instead of `emergency_layer: dict[str, RegStatus]`; add `resolve_for_day(emergency_projections, section_id, day) -> RegStatus | None`. Wrap ODFW/IDFG output as Projections. Keep `resolve()` as a today-only back-compat wrapper.
- **Modify:** `fishing_report.py` — change `regs.fetch_all` unpacking; replace per-day dual-branch with `resolve_for_day` for all 366 offsets.
- **Modify:** Several test files — `tests/regs/test_emergency_types.py`, `tests/regs/test_emergency_classifier.py`, `tests/regs/test_aggregator.py`, `tests/regs/test_aggregator_resolve.py`, `tests/test_build_report_data_long_range.py`, `tests/test_fetch_all.py`.

---

## Task 1: Add `Projection` and refactor `Classification`

**Files:**
- Modify: `regs/emergency_types.py`
- Modify: `tests/regs/test_emergency_types.py`

- [ ] **Step 1.1: Write failing tests**

Append to `tests/regs/test_emergency_types.py`:

```python
def test_projection_carries_date_bounded_status():
    """A Projection represents one open/closed window for one section."""
    from datetime import date
    from regs.emergency_types import Projection
    p = Projection(
        section_id="snake_lower_monumental_to_little_goose",
        status="open",
        effective_from=date(2026, 5, 15),
        effective_to=date(2026, 5, 15),
        reason="Snake Spring Chinook one-day opener",
        authority="WDFW",
    )
    assert p.section_id == "snake_lower_monumental_to_little_goose"
    assert p.status == "open"
    assert p.effective_from == p.effective_to == date(2026, 5, 15)


def test_classification_carries_projections_list():
    """Classification now carries a list of Projections (one rule -> many)."""
    from datetime import date
    from regs.emergency_types import Classification, Projection
    p1 = Projection(
        section_id="snake_lower_monumental_to_little_goose",
        status="open",
        effective_from=date(2026, 5, 15), effective_to=date(2026, 5, 15),
        reason="x", authority="WDFW",
    )
    p2 = Projection(
        section_id="snake_goose_island_to_ice_harbor",
        status="open",
        effective_from=date(2026, 5, 20), effective_to=date(2026, 5, 21),
        reason="y", authority="WDFW",
    )
    c = Classification(
        projections=[p1, p2],
        confidence=0.9,
        reasoning="snake river spring chinook fishery change",
    )
    assert len(c.projections) == 2
    assert {p.section_id for p in c.projections} == {
        "snake_lower_monumental_to_little_goose",
        "snake_goose_island_to_ice_harbor",
    }
```

- [ ] **Step 1.2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/regs/test_emergency_types.py -v -k "projection or projections_list"`

Expected: Both tests fail with `ImportError: cannot import name 'Projection'` and a `TypeError` for the Classification constructor.

- [ ] **Step 1.3: Update `regs/emergency_types.py`**

Replace the entire file contents with:

```python
"""Shared types for the emergency-rule fetch + classify + apply pipeline.

Kept in a separate module so wdfw_emergency.py and emergency_classifier.py can
import them without depending on each other (avoids circular imports).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal


@dataclass(frozen=True)
class EmergencyRule:
    """A single WDFW emergency rule entry as fetched from the advanced-search page."""
    url: str
    title: str
    body: str
    effective_from: date | None
    effective_to: date | None
    modified_at: datetime


@dataclass(frozen=True)
class Projection:
    """A single date-bounded open/closed window for one pamphlet section.

    Discrete dates: ``effective_from == effective_to``.
    Continuous range: ``effective_from <= effective_to``.
    Always-active: both fields None — used for legacy today-only scrapers
    (ODFW, IDFG) until they grow date-projection support.
    """
    section_id: str
    status: Literal["open", "closed"]
    effective_from: date | None
    effective_to: date | None
    reason: str
    authority: str


@dataclass(frozen=True)
class Classification:
    """Claude-API output for a single emergency rule.

    One rule may produce N projections — supports the common case where a
    single notice covers multiple sections with different open dates each
    (e.g. Snake Spring Chinook: Little Goose May 15+19, Ice Harbor May 20+21).
    """
    projections: list[Projection]
    confidence: float
    reasoning: str
```

- [ ] **Step 1.4: Run the new tests + the rest of the suite**

Run: `.venv/bin/python -m pytest tests/regs/test_emergency_types.py -v`

Expected: New tests pass. Older tests may break if they referenced the old `Classification.section_ids` shape — leave them failing for now; Task 2 will fix `emergency_classifier.py` which is the next consumer.

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -10
```

Expect several failures in `test_emergency_classifier.py`, `test_aggregator*`, and `test_fetch_all.py`. These will all be fixed in Tasks 2-4.

- [ ] **Step 1.5: Commit (schema-only, full suite not yet green)**

```bash
git add regs/emergency_types.py tests/regs/test_emergency_types.py
git commit -m "refactor(regs): add Projection; Classification now carries list of projections

Replaces the today-only (section_ids, status, effective_from, effective_to)
shape with a list of date-bounded Projections so a single emergency rule
can describe multiple sections each with their own open dates (the Snake
Spring Chinook rule's actual structure).

Downstream consumers (classifier, aggregator, fishing_report) wired up in
the next commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Rewrite classifier to emit Projection lists

**Files:**
- Modify: `regs/emergency_classifier.py` — prompt, parser, cache serialization, `_filter`.
- Modify: `tests/regs/test_emergency_classifier.py`.

- [ ] **Step 2.1: Write failing tests**

Look at the existing `tests/regs/test_emergency_classifier.py` to see what fixtures + patterns exist (use `.venv/bin/python -m pytest tests/regs/test_emergency_classifier.py --collect-only -q` to list tests). Then add these tests at the end:

```python
def test_classify_rule_produces_projection_per_section(monkeypatch, tmp_path):
    """The classifier returns a Classification with projections covering each
    (section_id, date-window) pair found in the rule body."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from datetime import date, datetime
    from regs.emergency_classifier import classify_rule
    from regs.emergency_types import EmergencyRule

    # Stub the Anthropic client to return a deterministic JSON response.
    class _StubResponse:
        def __init__(self, text):
            self.content = [type("M", (), {"text": text})()]
    class _StubMessages:
        def create(self, **_kwargs):
            return _StubResponse('{\n'
                '  "projections": [\n'
                '    {"section_id": "snake_lower_monumental_to_little_goose",\n'
                '     "status": "open",\n'
                '     "effective_from": "2026-05-15", "effective_to": "2026-05-15",\n'
                '     "reason": "Little Goose 1-day opener"},\n'
                '    {"section_id": "snake_lower_monumental_to_little_goose",\n'
                '     "status": "open",\n'
                '     "effective_from": "2026-05-19", "effective_to": "2026-05-19",\n'
                '     "reason": "Little Goose 1-day opener"},\n'
                '    {"section_id": "snake_goose_island_to_ice_harbor",\n'
                '     "status": "open",\n'
                '     "effective_from": "2026-05-20", "effective_to": "2026-05-21",\n'
                '     "reason": "Ice Harbor 2-day opener"}\n'
                '  ],\n'
                '  "confidence": 0.95,\n'
                '  "reasoning": "snake spring chinook fishery change"\n'
                '}')
    class _StubClient:
        messages = _StubMessages()

    monkeypatch.setattr("regs.emergency_classifier._anthropic_client", lambda: _StubClient())

    rule = EmergencyRule(
        url="https://wdfw.wa.gov/x", title="Snake Spring Chinook Fishery Change",
        body="Snake from Texas Rapids to Little Goose: open May 15 and 19. "
             "Below Ice Harbor: open May 20-21.",
        effective_from=date(2026, 5, 13), effective_to=date(2026, 7, 1),
        modified_at=datetime.now(),
    )
    sections = [
        {"id": "snake_lower_monumental_to_little_goose",
         "description": "Snake R, Texas Rapids to Little Goose Dam"},
        {"id": "snake_goose_island_to_ice_harbor",
         "description": "Snake R, Goose Island to Ice Harbor Dam"},
    ]
    c = classify_rule(rule, sections)
    assert c is not None
    assert len(c.projections) == 3
    # Each projection carries authority "WDFW" (set by classifier post-process).
    assert all(p.authority == "WDFW" for p in c.projections)
    # Discrete-date projections survive (from == to).
    discrete = [p for p in c.projections if p.effective_from == p.effective_to]
    assert len(discrete) == 2


def test_classify_rule_returns_none_for_irrelevant_rule(monkeypatch, tmp_path):
    """Empty projections list — rule unrelated to salmon retention — returns None."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from datetime import date, datetime
    from regs.emergency_classifier import classify_rule
    from regs.emergency_types import EmergencyRule

    class _StubResponse:
        def __init__(self, text):
            self.content = [type("M", (), {"text": text})()]
    class _StubMessages:
        def create(self, **_kwargs):
            return _StubResponse('{"projections": [], "confidence": 0.9, "reasoning": "halibut"}')
    class _StubClient:
        messages = _StubMessages()
    monkeypatch.setattr("regs.emergency_classifier._anthropic_client", lambda: _StubClient())

    rule = EmergencyRule(
        url="https://wdfw.wa.gov/halibut",
        title="Marine area halibut", body="halibut rules",
        effective_from=date(2026, 5, 1), effective_to=None,
        modified_at=datetime.now(),
    )
    assert classify_rule(rule, []) is None


def test_classify_rule_caches_projections_to_disk(monkeypatch, tmp_path):
    """The cache survives across calls — second call doesn't hit the API."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from datetime import date, datetime
    from regs.emergency_classifier import classify_rule
    from regs.emergency_types import EmergencyRule

    call_count = {"n": 0}
    class _StubResponse:
        def __init__(self, text): self.content = [type("M", (), {"text": text})()]
    class _StubMessages:
        def create(self, **_kwargs):
            call_count["n"] += 1
            return _StubResponse('{"projections": ['
                '{"section_id": "x", "status": "open",'
                ' "effective_from": "2026-06-01", "effective_to": "2026-06-15",'
                ' "reason": "test"}'
                '], "confidence": 0.9, "reasoning": "test"}')
    class _StubClient:
        messages = _StubMessages()
    monkeypatch.setattr("regs.emergency_classifier._anthropic_client", lambda: _StubClient())

    rule = EmergencyRule(
        url="https://w/x", title="t", body="b",
        effective_from=None, effective_to=None, modified_at=datetime.now(),
    )
    c1 = classify_rule(rule, [{"id": "x", "description": "y"}])
    c2 = classify_rule(rule, [{"id": "x", "description": "y"}])
    assert call_count["n"] == 1  # second call hit the cache
    assert c1 == c2
    assert c1.projections[0].section_id == "x"
```

- [ ] **Step 2.2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/regs/test_emergency_classifier.py -v -k "projection or projections or caches_projections or irrelevant_rule"`

Expected: Failures (the classifier still produces old-shape Classification objects).

- [ ] **Step 2.3: Rewrite `regs/emergency_classifier.py`**

Replace the file contents with:

```python
"""Claude-API classifier for WDFW emergency rules.

Returns a Classification carrying a list of Projection entries — one per
(section_id, status, date-window) tuple. Results cached on disk by
(url, title, body[:500]) so re-classification only fires when WDFW edits
the rule text.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict
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
    """Stable key on url + title + body[:500] — survives cron runs; invalidates
    only when WDFW edits the rule text."""
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
    _cache_path(rule).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_cached_classification(rule: EmergencyRule) -> Classification | None:
    path = _cache_path(rule)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _deserialize_classification(payload["classification"])
    except (json.JSONDecodeError, KeyError, ValueError) as e:
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


def _serialize_projection(p: Projection) -> dict:
    return {
        "section_id": p.section_id,
        "status": p.status,
        "effective_from": p.effective_from.isoformat() if p.effective_from else None,
        "effective_to": p.effective_to.isoformat() if p.effective_to else None,
        "reason": p.reason,
        "authority": p.authority,
    }


def _serialize_classification(c: Classification) -> dict:
    return {
        "projections": [_serialize_projection(p) for p in c.projections],
        "confidence": c.confidence,
        "reasoning": c.reasoning,
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


def _deserialize_classification(d: dict) -> Classification:
    return Classification(
        projections=[_deserialize_projection(p) for p in d.get("projections", [])],
        confidence=float(d.get("confidence", 0.0)),
        reasoning=str(d.get("reasoning", "")),
    )


_CLIENT = None
CONFIDENCE_THRESHOLD = 0.7
MODEL = "claude-sonnet-4-6"


def _anthropic_client():
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
    return f"""You are classifying a WDFW emergency fishing-rule notice into pamphlet section ids.

PAMPHLET SECTIONS (id: description):
{sections_text}

EMERGENCY RULE:
Title: {rule.title}
Body: {rule.body}
Effective: {rule.effective_from} to {rule.effective_to}

A single rule may impose different open dates on different sections, and may
list discrete dates rather than continuous ranges. Output ONE JSON object
(no surrounding prose) with these fields:

- projections: list of objects, each describing one open/closed window for
  one section. Use one projection per (section_id, status, date-window)
  tuple. A discrete date is a projection where effective_from == effective_to.
  Fields per projection:
    - section_id: a pamphlet section id from the list above
    - status: "open" or "closed"
    - effective_from: "YYYY-MM-DD" (or null)
    - effective_to: "YYYY-MM-DD" (or null)
    - reason: one short phrase suitable for display
- confidence: 0.0-1.0 (your certainty in the projections)
- reasoning: one short sentence

Examples:

  "Open May 15 and 19, 2026, only" on a single section produces TWO
  projections — one with effective_from=effective_to=2026-05-15, another
  with effective_from=effective_to=2026-05-19.

  "Open June 1 through June 30" on two sections produces TWO projections
  — one per section_id — each with the same date range.

If the rule is NOT about salmon retention (or maps to no listed section),
return projections=[] with a reasoning explaining why.

Output JSON only."""


def classify_rule(rule: EmergencyRule, pamphlet_sections: list[dict]) -> Classification | None:
    """Classify a rule. Cache-hit returns the cached value; cache-miss calls API.

    Returns None when:
      - Cache miss AND API key/SDK unavailable
      - Confidence below threshold
      - projections list is empty (irrelevant rule)
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
            max_tokens=2048,
            messages=[{"role": "user", "content": _build_prompt(rule, pamphlet_sections)}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = "\n".join(line for line in text.splitlines() if not line.startswith("```"))
        payload = json.loads(text)
    except Exception as e:
        log.warning("classify_rule failed for %s: %s", rule.url, e)
        return None

    projections = []
    for p in (payload.get("projections") or []):
        try:
            projections.append(Projection(
                section_id=str(p["section_id"]),
                status=p.get("status", "open"),
                effective_from=date.fromisoformat(p["effective_from"]) if p.get("effective_from") else None,
                effective_to=date.fromisoformat(p["effective_to"]) if p.get("effective_to") else None,
                reason=str(p.get("reason", ""))[:240],
                authority="WDFW",
            ))
        except (KeyError, ValueError) as e:
            log.warning("dropping malformed projection in %s: %s", rule.url, e)
            continue

    classification = Classification(
        projections=projections,
        confidence=float(payload.get("confidence", 0.0)),
        reasoning=str(payload.get("reasoning", "")),
    )
    save_cached_classification(rule, classification)
    return _filter(classification)


def _filter(c: Classification) -> Classification | None:
    if c.confidence < CONFIDENCE_THRESHOLD:
        return None
    if not c.projections:
        return None
    return c
```

- [ ] **Step 2.4: Run the classifier tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/regs/test_emergency_classifier.py -v`

Expected: New tests pass. Older tests in that file may fail if they referenced the old Classification.section_ids shape — go through each failure and either delete the obsolete test (if it was redundantly testing the old shape) or rewrite it to use Projections. Re-run until the file is green.

- [ ] **Step 2.5: Commit**

```bash
git add regs/emergency_classifier.py tests/regs/test_emergency_classifier.py
git commit -m "feat(regs): classifier emits Projections; supports discrete dates per section

The new prompt explicitly handles discrete-date lists ('open May 15 and
19') and rules that open multiple sections on different dates — the
Snake Spring Chinook rule's actual shape. Cache serialization updated
for the new schema (old cache entries are auto-invalidated by JSON
parse failure).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Aggregator emits projections; add `resolve_for_day`

**Files:**
- Modify: `regs/__init__.py`
- Modify: `tests/regs/test_aggregator.py`, `tests/regs/test_aggregator_resolve.py`

- [ ] **Step 3.1: Write failing tests**

Append to `tests/regs/test_aggregator_resolve.py`:

```python
def test_resolve_for_day_closure_window_overrides_pamphlet_open(monkeypatch):
    """Emergency closure projection wins over pamphlet baseline-open for any day in range."""
    from datetime import date
    from regs import resolve_for_day
    from regs.emergency_types import Projection
    em = {"x": [Projection(
        section_id="x", status="closed",
        effective_from=date(2026, 6, 1), effective_to=date(2026, 6, 15),
        reason="emergency closure", authority="WDFW",
    )]}
    # Stub pamphlet to say "open" for any date.
    def _stub_pamphlet(section_id, *, today, species="salmon_hatchery_steelhead"):
        from datetime import datetime
        from regs.wdfw_pamphlet import RegStatus
        return RegStatus(authority="WDFW", section_key=section_id, open=True,
                         reason="pamphlet says open", last_checked=datetime.now())
    monkeypatch.setattr("regs.pamphlet_status_for_section", _stub_pamphlet)

    # Inside the closure window -> closed
    rs = resolve_for_day(em, "x", date(2026, 6, 7))
    assert rs is not None and rs.open is False
    # Outside the closure window -> pamphlet baseline (open)
    rs = resolve_for_day(em, "x", date(2026, 7, 1))
    assert rs is not None and rs.open is True


def test_resolve_for_day_discrete_date_open(monkeypatch):
    """Discrete-date open projection (from==to) applies only on that exact day."""
    from datetime import date
    from regs import resolve_for_day
    from regs.emergency_types import Projection
    em = {"snake_lower_monumental_to_little_goose": [
        Projection(
            section_id="snake_lower_monumental_to_little_goose", status="open",
            effective_from=date(2026, 5, 15), effective_to=date(2026, 5, 15),
            reason="Little Goose one-day opener", authority="WDFW",
        ),
    ]}
    def _stub_pamphlet(section_id, *, today, species="salmon_hatchery_steelhead"):
        from datetime import datetime
        from regs.wdfw_pamphlet import RegStatus
        # pamphlet says CLOSED (no salmon row -> default-closed)
        return RegStatus(authority="WDFW", section_key=section_id, open=False,
                         reason="Closed (no salmon row)", last_checked=datetime.now())
    monkeypatch.setattr("regs.pamphlet_status_for_section", _stub_pamphlet)

    # On the open date -> open
    rs = resolve_for_day(em, "snake_lower_monumental_to_little_goose", date(2026, 5, 15))
    assert rs is not None and rs.open is True
    # Day before -> pamphlet baseline (closed)
    rs = resolve_for_day(em, "snake_lower_monumental_to_little_goose", date(2026, 5, 14))
    assert rs is not None and rs.open is False
    # Day after -> pamphlet baseline (closed)
    rs = resolve_for_day(em, "snake_lower_monumental_to_little_goose", date(2026, 5, 16))
    assert rs is not None and rs.open is False


def test_resolve_for_day_closures_win_over_opens_on_same_day(monkeypatch):
    """When two projections overlap on the same day, a closure overrides an open."""
    from datetime import date
    from regs import resolve_for_day
    from regs.emergency_types import Projection
    em = {"y": [
        Projection(section_id="y", status="open",
                   effective_from=date(2026, 6, 1), effective_to=date(2026, 6, 30),
                   reason="seasonal open", authority="WDFW"),
        Projection(section_id="y", status="closed",
                   effective_from=date(2026, 6, 10), effective_to=date(2026, 6, 12),
                   reason="emergency closure", authority="WDFW"),
    ]}
    def _stub_pamphlet(section_id, *, today, species="salmon_hatchery_steelhead"):
        return None
    monkeypatch.setattr("regs.pamphlet_status_for_section", _stub_pamphlet)

    # Inside closure window -> closed (closures win)
    rs = resolve_for_day(em, "y", date(2026, 6, 11))
    assert rs is not None and rs.open is False
    assert "emergency" in rs.reason.lower()
    # Inside seasonal open window, outside closure -> open
    rs = resolve_for_day(em, "y", date(2026, 6, 5))
    assert rs is not None and rs.open is True


def test_resolve_for_day_no_projections_falls_back_to_pamphlet(monkeypatch):
    """No emergency projections for the section -> pamphlet result is returned."""
    from datetime import date
    from regs import resolve_for_day
    from datetime import datetime
    from regs.wdfw_pamphlet import RegStatus
    def _stub_pamphlet(section_id, *, today, species="salmon_hatchery_steelhead"):
        return RegStatus(authority="WDFW", section_key=section_id, open=True,
                         reason="pamphlet", last_checked=datetime.now())
    monkeypatch.setattr("regs.pamphlet_status_for_section", _stub_pamphlet)

    rs = resolve_for_day({}, "z", date(2026, 7, 1))
    assert rs is not None and rs.open is True


def test_resolve_for_day_returns_none_when_no_data(monkeypatch):
    """No emergency AND pamphlet returns None -> overall None (caller treats as default-open)."""
    from datetime import date
    from regs import resolve_for_day
    monkeypatch.setattr("regs.pamphlet_status_for_section", lambda *args, **kw: None)
    assert resolve_for_day({}, "unknown_section", date(2026, 7, 1)) is None


def test_fetch_all_returns_emergency_projections_shape(monkeypatch, tmp_path):
    """fetch_all's middle return is now dict[str, list[Projection]], not dict[str, RegStatus]."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    # Stub all the network/LLM dependencies to keep this test offline.
    monkeypatch.setattr("regs.fetch_active_rules", lambda today: [])
    monkeypatch.setattr("regs.odfw_fetch", lambda: [])
    monkeypatch.setattr("regs.idfg_fetch", lambda: [])
    from regs import fetch_all
    from datetime import date
    pam, em, meta = fetch_all(date(2026, 5, 14))
    assert isinstance(em, dict)
    # Each value should be a list (empty if no rules), not a RegStatus.
    for v in em.values():
        assert isinstance(v, list)
```

- [ ] **Step 3.2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/regs/test_aggregator_resolve.py -v -k "resolve_for_day or fetch_all_returns_emergency_projections"`

Expected: All 6 tests fail (`resolve_for_day` doesn't exist; `fetch_all` returns the old shape).

- [ ] **Step 3.3: Update `regs/__init__.py`**

Replace the file contents with:

```python
"""3-layer regs aggregator.

Layer 0 (default)  : OPEN
Layer 1 (baseline) : WDFW pamphlet YAML — fine-grained, per pamphlet section_id
Layer 2 (overlay)  : Emergency projections (WDFW classifier + ODFW + IDFG scrapers)

resolve_for_day(emergency_projections, section_id, day) consults Layer 2's
date-bounded projections, then falls back to the pamphlet for `day`, returning
None when neither layer has an entry for `section_id` on `day` (caller defaults
to OPEN).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Iterable

from regs.emergency_classifier import classify_rule
from regs.emergency_types import Classification, EmergencyRule, Projection
from regs.idfg import fetch_status as idfg_fetch
from regs.odfw import fetch_status as odfw_fetch
from regs.wdfw import RegStatus
from regs.wdfw_emergency import fetch_active_rules
from regs.wdfw_pamphlet import load_pamphlet
from regs.wdfw_pamphlet import status_for_all_sections as pamphlet_statuses
from regs.wdfw_pamphlet import status_for_section as pamphlet_status_for_section

log = logging.getLogger("regs")


def fetch_all(today: date | None = None) -> tuple[
    dict[str, RegStatus],          # pamphlet_layer (today-only snapshot)
    dict[str, list[Projection]],   # emergency_projections (date-bounded, projects forward)
    dict[str, dict],               # agency_meta
]:
    """Build the pamphlet snapshot (today) + emergency projections (date-bounded) + agency meta."""
    if today is None:
        today = date.today()

    # Layer 1 — pamphlet (still a today-only snapshot for the legacy `resolve` path)
    pamphlet_layer: dict[str, RegStatus] = {}
    try:
        pamphlet_layer = pamphlet_statuses(today=today)
        agency_meta_pamphlet = {"ok": True, "last_successful_check": datetime.now().isoformat(), "error": None}
    except Exception as e:  # noqa: BLE001
        log.exception("pamphlet load failed")
        agency_meta_pamphlet = {"ok": False, "last_successful_check": None, "error": str(e)[:200]}

    # Layer 2 — emergency projections
    emergency_projections: dict[str, list[Projection]] = {}
    agency_meta: dict[str, dict] = {"WDFW_PAMPHLET": agency_meta_pamphlet}

    # WDFW emergency via advanced-search + Claude classifier
    try:
        rules = fetch_active_rules(today)
        sections_for_prompt = [
            {"id": s["id"], "description": s.get("description", "")}
            for s in load_pamphlet()
        ]
        for rule in rules:
            classification = classify_rule(rule, sections_for_prompt)
            if classification is None:
                continue
            for p in classification.projections:
                emergency_projections.setdefault(p.section_id, []).append(p)
        agency_meta["WDFW"] = {"ok": True, "last_successful_check": datetime.now().isoformat(), "error": None}
    except Exception as e:  # noqa: BLE001
        log.exception("WDFW emergency fetch failed")
        agency_meta["WDFW"] = {"ok": False, "last_successful_check": None, "error": str(e)[:200]}

    # ODFW + IDFG keep their existing today-only RegStatus output; we wrap each
    # as a single Projection with effective_from=effective_to=None ("always
    # active for this run"). The per-day caller filters by date, so a None/None
    # range means "this projection applies on every day of the forecast".
    for name, fn in (("ODFW", odfw_fetch), ("IDFG", idfg_fetch)):
        try:
            for s in fn():
                emergency_projections.setdefault(s.section_key, []).append(Projection(
                    section_id=s.section_key,
                    status=("open" if s.open else "closed"),
                    effective_from=None,
                    effective_to=None,
                    reason=s.reason,
                    authority=s.authority,
                ))
            agency_meta[name] = {"ok": True, "last_successful_check": datetime.now().isoformat(), "error": None}
        except Exception as e:  # noqa: BLE001
            log.exception("%s fetch failed", name)
            agency_meta[name] = {"ok": False, "last_successful_check": None, "error": str(e)[:200]}

    return pamphlet_layer, emergency_projections, agency_meta


def _projection_applies_on(p: Projection, day: date) -> bool:
    if p.effective_from is not None and day < p.effective_from:
        return False
    if p.effective_to is not None and day > p.effective_to:
        return False
    return True


def resolve_for_day(
    emergency_projections: dict[str, list[Projection]],
    section_id: str,
    day: date,
) -> RegStatus | None:
    """Per-day 3-layer precedence lookup.

    1. Find emergency projections matching section_id with day in range.
       Closures win over opens on the same day.
    2. Otherwise, fall back to the pamphlet's per-day status_for_section.
    3. Return None if neither layer has an entry (caller defaults to OPEN).
    """
    matching = [p for p in emergency_projections.get(section_id, []) if _projection_applies_on(p, day)]
    closures = [p for p in matching if p.status == "closed"]
    if closures:
        p = closures[0]
        return RegStatus(authority=p.authority, section_key=section_id, open=False,
                         reason=p.reason, last_checked=datetime.now())
    opens = [p for p in matching if p.status == "open"]
    if opens:
        p = opens[0]
        return RegStatus(authority=p.authority, section_key=section_id, open=True,
                         reason=p.reason, last_checked=datetime.now())
    return pamphlet_status_for_section(section_id, today=day)


def resolve(
    pamphlet_layer: dict[str, RegStatus],
    emergency_projections: dict[str, list[Projection]],
    section_id: str,
    today: date,
) -> RegStatus | None:
    """Back-compat shim — today-only resolution via resolve_for_day."""
    return resolve_for_day(emergency_projections, section_id, today)


def is_open(
    pamphlet_layer: dict[str, RegStatus],
    emergency_projections: dict[str, list[Projection]],
    section_id: str,
    today: date,
) -> bool:
    """Convenience: True if the section is open per the 3-layer resolution
    on `today`. Default-OPEN when neither layer has data."""
    rs = resolve_for_day(emergency_projections, section_id, today)
    return True if rs is None else rs.open
```

- [ ] **Step 3.4: Run the aggregator tests + fix any old tests that broke**

Run: `.venv/bin/python -m pytest tests/regs/ -v 2>&1 | tail -25`

Expected: The 6 new tests in `test_aggregator_resolve.py` pass. Old tests in `test_aggregator.py` / `test_aggregator_resolve.py` that referenced the old shape (`emergency_layer: dict[str, RegStatus]`, the old `resolve(pamphlet_layer, emergency_layer, ...)` signature) need updating. Walk each failure: update fixture dicts to lists of Projections, and update `resolve()` callers to pass `emergency_projections` (same semantics, new name) — the shim keeps the signature working but the second argument's contents must be the new shape.

- [ ] **Step 3.5: Commit**

```bash
git add regs/__init__.py tests/regs/test_aggregator.py tests/regs/test_aggregator_resolve.py
git commit -m "feat(regs): fetch_all emits emergency_projections; add resolve_for_day

emergency_projections is dict[str, list[Projection]] (was today-only
dict[str, RegStatus]). resolve_for_day(em_projections, section_id, day)
does per-day lookup: closures-win over opens, fall back to pamphlet
status_for_section for the same day, return None when neither layer
has an entry. resolve() retained as a today-only shim for back-compat.

ODFW/IDFG scrapers are wrapped as always-active Projections
(effective_from=effective_to=None) since those agencies don't publish
date-bounded rules yet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `fishing_report.py` uses `resolve_for_day` uniformly

**Files:**
- Modify: `fishing_report.py`
- Modify: `tests/test_build_report_data_long_range.py`, `tests/test_fetch_all.py`

- [ ] **Step 4.1: Write failing test**

Append to `tests/test_build_report_data_long_range.py`:

```python
def test_build_report_data_emergency_projection_opens_future_day(tmp_path, monkeypatch):
    """An emergency Projection with status=open on a future day flips that day
    from default-CLOSED (pamphlet) to OPEN in the forecast."""
    from datetime import date
    from regs.emergency_types import Projection

    storage = FileStorage(root=tmp_path)
    today = date(2026, 5, 14)
    inputs = _minimal_inputs(today)
    # Pretend the first primary launch maps to a pamphlet section that is
    # default-CLOSED, with an emergency Projection opening day +6.
    from stations import primary_stations
    target_launch_key = primary_stations()[0]["key"]

    def _stub_pamphlet_status(section_id, *, today, species="salmon_hatchery_steelhead"):
        """Pretend the section is default-CLOSED for every day."""
        from datetime import datetime
        from regs.wdfw_pamphlet import RegStatus
        if section_id != "test_section_id":
            return None
        return RegStatus(authority="WDFW", section_key=section_id, open=False,
                         reason="default-closed", last_checked=datetime.now())

    real_primary = primary_stations()
    patched_stations = []
    for s in real_primary:
        if s["key"] == target_launch_key:
            patched_stations.append({**s, "pamphlet_section": "test_section_id"})
        else:
            patched_stations.append(s)

    # Stub fetch_all so the emergency_projections fixture contains our test rule.
    open_day = today.replace(day=20)  # offset 6
    em_projections = {"test_section_id": [Projection(
        section_id="test_section_id", status="open",
        effective_from=open_day, effective_to=open_day,
        reason="test opener", authority="WDFW",
    )]}

    from unittest.mock import patch
    with patch("fishing_report.primary_stations", return_value=patched_stations), \
         patch("fishing_report.STATIONS", patched_stations), \
         patch("fishing_report.pamphlet_status_for_section", side_effect=_stub_pamphlet_status), \
         patch("regs.pamphlet_status_for_section", side_effect=_stub_pamphlet_status), \
         patch("regs.fetch_all", return_value=({}, em_projections, {})):
        out = build_report_data(inputs, storage=storage)

    fkey = next(k for k in out["forecasts"] if k.endswith(f"::{target_launch_key}"))
    days = out["forecasts"][fkey]
    # Day +5 should still be closed (pamphlet baseline).
    assert days[5]["open"] is False, "day before opener should be closed"
    # Day +6 (the open Projection date) should be open.
    assert days[6]["date"] == open_day.isoformat()
    assert days[6]["open"] is True, "emergency-opened day should be open"
    # Day +7 should be closed again (back to pamphlet baseline).
    assert days[7]["open"] is False, "day after opener should be closed"
```

- [ ] **Step 4.2: Run the new test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_build_report_data_long_range.py::test_build_report_data_emergency_projection_opens_future_day -v`

Expected: Fails — current code uses `pamphlet_status_for_section` directly for offset > 0, never sees the emergency projection.

- [ ] **Step 4.3: Update `fishing_report.py` per-day loop**

Locate the per-day regs resolution block (currently lines ~399-422 inside the `for offset in range(366):` loop). It currently has a dual-branch `if offset == 0 ... else ...`. Replace the entire block with:

```python
                # Per-day 3-layer regs resolution. emergency_projections carries
                # date-bounded windows (WDFW classifier + ODFW + IDFG), with the
                # pamphlet's per-day status_for_section as the baseline.
                pamphlet_section = launch.get("pamphlet_section")
                section_id = pamphlet_section or launch.get("regs_section")
                if section_id:
                    rs_day = regs_resolve_for_day(emergency_projections, section_id, day)
                    open_today = bool(rs_day.open) if rs_day is not None else True
                    reason_today = (rs_day.reason if rs_day is not None else "")
                    authority_today = (rs_day.authority if rs_day is not None else "")
                else:
                    open_today = True
                    reason_today = ""
                    authority_today = ""
                open_status_day = 1.0 if open_today else 0.0
```

Update the imports at the top of `fishing_report.py` — the file currently imports `regs.resolve as regs_resolve`. Replace with:

```python
from regs import fetch_all as regs_fetch_all, resolve_for_day as regs_resolve_for_day
```

(Find the existing `from regs import ...` line and replace it with this; also remove now-unused `regs_resolve` if it's imported under that alias.)

And the `fetch_all` unpacking at the top of `build_report_data` — the middle return value is now `emergency_projections`, not `emergency_layer`. Rename the variable:

```python
pamphlet_layer, emergency_projections, agency_meta = regs_fetch_all(today=today)
```

Also update the `launch_status` computation block (still uses `regs_resolve(pamphlet_layer, emergency_layer, ...)` shape). Replace each call to `regs_resolve(pamphlet_layer, emergency_layer, x, today)` with `regs_resolve_for_day(emergency_projections, x, today)`.

- [ ] **Step 4.4: Run the new test + full suite**

Run: `.venv/bin/python -m pytest tests/test_build_report_data_long_range.py -v -k "emergency_projection"`

Expected: New test passes.

```bash
.venv/bin/python -m pytest tests/ -q 2>&1 | tail -10
```

Expect a handful of failures in `test_fetch_all.py` and any other tests still using the old `emergency_layer` shape. Update each: rename the variable in fixtures from `emergency_layer` to `emergency_projections`, and change RegStatus-valued fixtures to lists of single Projections. Re-run until green.

- [ ] **Step 4.5: Commit**

```bash
git add fishing_report.py tests/test_build_report_data_long_range.py tests/test_fetch_all.py
git commit -m "feat(report): per-day loop uses resolve_for_day uniformly

Replaces the today-vs-future dual-branch with a single
resolve_for_day(emergency_projections, section_id, day) call for all 366
offsets. Emergency rules now project forward — the Snake Spring Chinook
'May 15+19 open' shape applies correctly in the forecast.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Deploy, invalidate cache, verify on Snake

**Files:** none.

- [ ] **Step 5.1: Push to GitHub**

```bash
git push origin master
```

Railway auto-deploys.

- [ ] **Step 5.2: Wait for deploy, invalidate the emergency cache (old shape), regen**

The cache schema changed. Existing cache files won't deserialize correctly — `load_cached_classification` will return None and the classifier will re-run for each rule. We can rely on that, but it's tidier to flush the cache explicitly.

```bash
export RAILWAY_API_TOKEN=$(grep '=' /home/alan/arath/fishing_reports/no_git_commit-RAILWAY_API_TOKEN.txt | cut -d= -f2)
for i in 1 2 3 4 5 6 7 8; do
  status=$($HOME/.railway/bin/railway status 2>&1 | grep -E "status:" | head -1)
  echo "[$i] $status"
  if echo "$status" | grep -q "Online" && ! echo "$status" | grep -qE "Building|Deploying"; then
    break
  fi
  sleep 15
done
$HOME/.railway/bin/railway ssh "rm -rf /data/emergency-cache && cd /app && DATA_DIR=/data python -u fishing_report.py 2>&1 | tail -6"
```

Expect a longer-than-usual run (~30s instead of 5s) because every active WDFW emergency rule is being re-classified.

- [ ] **Step 5.3: Verify the Snake emergency projection is live**

```bash
curl -sS -m 30 'https://salmon.pnwbite.com/' -H 'Cache-Control: no-cache' -o /tmp/salmon_snake_live.html
.venv/bin/python - <<'PY'
import json, re
html = open('/tmp/salmon_snake_live.html').read()
m = re.search(r'<script id="report-payload" type="application/json">(.*?)</script>', html, re.DOTALL)
payload = json.loads(m.group(1))
# Pick a Snake launch in the Little Goose section: lyons_ferry or texas_rapids.
for key in ("chinook::lyons_ferry", "chinook::texas_rapids", "chinook::ice_harbor_tail"):
    days = payload["forecasts"].get(key, [])
    print(f"\n=== {key} ===")
    for d in days:
        if d["date"] in ("2026-05-15", "2026-05-19", "2026-05-20", "2026-05-21"):
            print(f"  {d['date']} open={d.get('open')} score={d.get('score')} reason={(d.get('closure_reason') or '')[:80]}")
PY
```

Expected:
- `chinook::lyons_ferry` or `chinook::texas_rapids` shows `open=True` on 2026-05-15 and 2026-05-19.
- `chinook::ice_harbor_tail` shows `open=True` on 2026-05-20 and 2026-05-21.
- Adjacent dates (e.g. 2026-05-16, 2026-05-17) remain `open=False`.

- [ ] **Step 5.4: Manual UI check**

Open https://salmon.pnwbite.com, change the date picker to 2026-05-15, find Lyons Ferry or Texas Rapids — should show OPEN with the emergency reason text. Switch to 2026-05-16 — should show CLOSED again.

---

## Done criteria

- All tests pass.
- The classifier returns date-bounded Projection lists; cache holds them.
- A WDFW emergency Projection opening section X on day +N flips that one day in the report from default-CLOSED to OPEN; days N-1 and N+1 stay CLOSED.
- Snake launches in the Little Goose / Ice Harbor sections show OPEN on the rule's discrete dates and CLOSED on adjacent dates.
