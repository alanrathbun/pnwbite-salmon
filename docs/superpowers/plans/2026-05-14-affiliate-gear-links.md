# Affiliate Gear Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inline Amazon Associates + Sportsman's Warehouse (AvantLink) affiliate links to every gear bullet in the salmon report's technique panel, with FTC-compliant disclosure, gracefully degrading when env vars are unset.

**Architecture:** One new pure-Python module `engines/affiliate.py` exposes `AffiliateLink` and `links_for(query, *, launch_key, species)`. The renderer's `_species_block` calls a new `_gear_bullets(gear, *, launch_key, species)` helper that emits `<li>` items with inline `<a class="aff">` badges per vendor. Credentials read from env vars at call time so tests can manipulate them via `monkeypatch`. No changes to `bait_rules.yaml`, no JS changes, no payload changes — affiliate URLs are baked into the static HTML at cron time.

**Tech Stack:** Python stdlib only (`dataclasses`, `urllib.parse`, `os`). Existing pytest test runner.

**Spec:** `docs/superpowers/specs/2026-05-14-affiliate-gear-links-design.md`

**Env vars (configured on Railway service `pnwbite-salmon` in Task 5):**
- `AMAZON_AFFILIATE_TAG`
- `AVANTLINK_AFFILIATE_ID`
- `AVANTLINK_SPWH_MERCHANT_ID`

---

## File Map

- **Create:** `engines/affiliate.py` — pure function `links_for()` + `AffiliateLink` dataclass.
- **Create:** `tests/engines/test_affiliate.py` — unit tests for `links_for`.
- **Modify:** `render.py` — add `_gear_bullets` helper, extend `_species_block` signature, add `_disclosure_banner` helper, extend `_launch_card` call site, add CSS for `.aff` and `.aff-disclosure`.
- **Modify:** `tests/test_render.py` — add render-layer tests for affiliate links + disclosure banner.

---

## Task 1: Create `engines/affiliate.py` with failing tests

**Files:**
- Create: `engines/affiliate.py`
- Create: `tests/engines/test_affiliate.py`

- [ ] **Step 1.1: Create the test file with the full test suite**

Create `tests/engines/test_affiliate.py`:

```python
"""Tests for engines.affiliate.links_for."""
from __future__ import annotations

import urllib.parse

import pytest

from engines.affiliate import AffiliateLink, links_for


def _set_all(monkeypatch):
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "mid-456")


def _clear_all(monkeypatch):
    for k in (
        "AMAZON_AFFILIATE_TAG",
        "AVANTLINK_AFFILIATE_ID",
        "AVANTLINK_SPWH_MERCHANT_ID",
    ):
        monkeypatch.delenv(k, raising=False)


def test_both_vendors_returns_two_links_in_order(monkeypatch):
    _set_all(monkeypatch)
    out = links_for("hot pink flasher", launch_key="brewster", species="chinook")
    assert len(out) == 2
    assert out[0].vendor == "amzn"
    assert out[1].vendor == "spwh"
    assert all(isinstance(l, AffiliateLink) for l in out)


def test_no_credentials_returns_empty(monkeypatch):
    _clear_all(monkeypatch)
    assert links_for("anything", launch_key="x", species="y") == []


def test_only_amazon_set_returns_one_link(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    out = links_for("hot pink flasher", launch_key="b", species="c")
    assert len(out) == 1
    assert out[0].vendor == "amzn"


def test_only_avantlink_set_returns_one_link(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "mid-456")
    out = links_for("hot pink flasher", launch_key="b", species="c")
    assert len(out) == 1
    assert out[0].vendor == "spwh"


def test_avantlink_requires_both_vars(monkeypatch):
    """If only one of the AvantLink pair is set, drop spwh entirely."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    # AVANTLINK_SPWH_MERCHANT_ID intentionally unset
    out = links_for("anything", launch_key="b", species="c")
    assert out == []


def test_amazon_url_has_tag_and_subtag(monkeypatch):
    _set_all(monkeypatch)
    out = links_for("hot pink flasher", launch_key="brewster", species="chinook")
    amzn = next(l for l in out if l.vendor == "amzn")
    parsed = urllib.parse.urlparse(amzn.url)
    qs = urllib.parse.parse_qs(parsed.query)
    assert parsed.netloc == "www.amazon.com"
    assert parsed.path == "/s"
    assert qs["k"] == ["hot pink flasher"]
    assert qs["tag"] == ["pnwbite-20"]
    assert qs["ascsubtag"] == ["brewster__chinook"]


def test_spwh_url_wraps_sportsmans_target(monkeypatch):
    _set_all(monkeypatch)
    out = links_for("hot pink flasher", launch_key="brewster", species="chinook")
    spwh = next(l for l in out if l.vendor == "spwh")
    parsed = urllib.parse.urlparse(spwh.url)
    qs = urllib.parse.parse_qs(parsed.query)
    assert parsed.netloc == "www.avantlink.com"
    assert parsed.path == "/click.php"
    assert qs["tt"] == ["cl"]
    assert qs["merchant_id"] == ["mid-456"]
    assert qs["affiliate_id"] == ["aff-123"]
    assert qs["pat"] == ["brewster__chinook"]
    # The wrapped target URL must point at Sportsman's Warehouse search.
    target = qs["url"][0]
    target_parsed = urllib.parse.urlparse(target)
    target_qs = urllib.parse.parse_qs(target_parsed.query)
    assert target_parsed.netloc == "www.sportsmans.com"
    assert target_parsed.path == "/search"
    assert target_qs["query"] == ["hot pink flasher"]


def test_query_with_special_chars_is_safely_encoded(monkeypatch):
    _set_all(monkeypatch)
    # Apostrophe, ampersand, double-quote — all common in tackle names.
    query = 'Brad\'s "Super Bait" & roe wrap'
    out = links_for(query, launch_key="b", species="chinook")
    for link in out:
        parsed = urllib.parse.urlparse(link.url)
        qs = urllib.parse.parse_qs(parsed.query)
        # Round-trip: parsing the encoded URL should yield the original query.
        if link.vendor == "amzn":
            assert qs["k"] == [query]
        else:
            target_qs = urllib.parse.parse_qs(urllib.parse.urlparse(qs["url"][0]).query)
            assert target_qs["query"] == [query]


def test_link_label_and_title_are_present(monkeypatch):
    _set_all(monkeypatch)
    out = links_for("anything", launch_key="b", species="c")
    by_v = {l.vendor: l for l in out}
    assert by_v["amzn"].label == "amzn"
    assert by_v["spwh"].label == "spwh"
    assert "Amazon" in by_v["amzn"].title
    assert "affiliate" in by_v["amzn"].title.lower()
    assert "Sportsman" in by_v["spwh"].title
    assert "affiliate" in by_v["spwh"].title.lower()
```

- [ ] **Step 1.2: Run the test file to verify all tests fail with ImportError**

Run: `.venv/bin/python -m pytest tests/engines/test_affiliate.py -v`

Expected: All tests fail with `ImportError: cannot import name 'AffiliateLink'` or `ModuleNotFoundError: No module named 'engines.affiliate'`.

- [ ] **Step 1.3: Create `engines/affiliate.py` with the minimal implementation**

Create `engines/affiliate.py`:

```python
"""Affiliate-link URL builder.

Pure function. Reads credentials from environment variables at call time
so tests can manipulate them with monkeypatch. Returns zero, one, or two
AffiliateLink entries depending on which vendors are configured. When
both vendors are configured, Amazon comes first, then Sportsman's
Warehouse via AvantLink — the order is deterministic so render-layer
snapshots are stable.

Vendor: 'amzn' (Amazon Associates) | 'spwh' (Sportsman's Warehouse via
AvantLink). AvantLink requires BOTH `AVANTLINK_AFFILIATE_ID` and
`AVANTLINK_SPWH_MERCHANT_ID`; if either is missing the spwh link is
omitted.

Sub-tag format: `<launch_key>__<species>` — double underscore avoids
collisions with launch keys that contain a single underscore.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass(frozen=True)
class AffiliateLink:
    vendor: str   # "amzn" | "spwh"
    url: str
    label: str    # short text shown in the badge
    title: str    # tooltip / aria text


_AMAZON_BASE = "https://www.amazon.com/s"
_AVANTLINK_BASE = "https://www.avantlink.com/click.php"
_SPWH_SEARCH_BASE = "https://www.sportsmans.com/search"


def _amazon_link(query: str, *, tag: str, subtag: str) -> AffiliateLink:
    qs = urlencode({"k": query, "tag": tag, "ascsubtag": subtag})
    return AffiliateLink(
        vendor="amzn",
        url=f"{_AMAZON_BASE}?{qs}",
        label="amzn",
        title="Search Amazon (affiliate link)",
    )


def _spwh_link(
    query: str, *, affiliate_id: str, merchant_id: str, subtag: str,
) -> AffiliateLink:
    target = f"{_SPWH_SEARCH_BASE}?{urlencode({'query': query})}"
    qs = urlencode({
        "tt": "cl",
        "merchant_id": merchant_id,
        "affiliate_id": affiliate_id,
        "url": target,
        "pat": subtag,
    })
    return AffiliateLink(
        vendor="spwh",
        url=f"{_AVANTLINK_BASE}?{qs}",
        label="spwh",
        title="Search Sportsman's Warehouse (affiliate link)",
    )


def links_for(query: str, *, launch_key: str, species: str) -> list[AffiliateLink]:
    """Build affiliate links for a gear search phrase.

    Caller composes the search phrase (e.g. f"{value} {key}" from a gear
    dict entry → "hot pink size 4 flasher"). Returns a list ordered
    [amzn, spwh]; either vendor may be omitted when its credentials are
    not configured.
    """
    subtag = f"{launch_key}__{species}"
    out: list[AffiliateLink] = []

    amazon_tag = os.environ.get("AMAZON_AFFILIATE_TAG")
    if amazon_tag:
        out.append(_amazon_link(query, tag=amazon_tag, subtag=subtag))

    aid = os.environ.get("AVANTLINK_AFFILIATE_ID")
    mid = os.environ.get("AVANTLINK_SPWH_MERCHANT_ID")
    if aid and mid:
        out.append(_spwh_link(query, affiliate_id=aid, merchant_id=mid, subtag=subtag))

    return out
```

- [ ] **Step 1.4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/engines/test_affiliate.py -v`

Expected: All 9 tests pass.

- [ ] **Step 1.5: Run the full test suite to verify nothing else broke**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: All previously-passing tests still pass (560 + 9 new = 569 passing, 1 skipped).

- [ ] **Step 1.6: Commit**

```bash
git add engines/affiliate.py tests/engines/test_affiliate.py
git commit -m "feat(affiliate): add links_for() URL builder for Amazon + Sportsman's Warehouse

Pure function, reads credentials from env vars at call time. Returns
zero, one, or two AffiliateLink entries depending on which vendors are
configured. Sub-tag format is <launch_key>__<species> for
vendor-dashboard attribution.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Wire affiliate links into `_species_block`

**Files:**
- Modify: `render.py` — add `_gear_bullets` helper, change `_species_block` signature, change `_launch_card` call site (around lines 387, 400-435).
- Modify: `tests/test_render.py` — add 3 tests for the new render behavior.

- [ ] **Step 2.1: Write failing render-layer tests**

Append to `tests/test_render.py` (after the last existing test):

```python
def test_species_block_gear_bullets_include_affiliate_links(monkeypatch):
    """When env vars are set, each gear bullet gets two <a class='aff'> badges."""
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    monkeypatch.setenv("AVANTLINK_AFFILIATE_ID", "aff-123")
    monkeypatch.setenv("AVANTLINK_SPWH_MERCHANT_ID", "mid-456")
    from render import _species_block
    days = [{
        "date": "2026-07-01",
        "score": 0.9, "verdict": "GREAT", "open": True,
        "no_run_data": False,
        "techniques": [{
            "rank": 1, "method": "trolling", "label": "Spinner & roe",
            "gear": {"flasher": "hot pink size 4", "bait": "cured roe"},
            "notes": "fish the deep slot",
        }],
    }]
    out = _species_block("chinook", days, True, launch_key="brewster")
    # Two affiliate <a> tags per gear bullet × 2 gear items = 4 total.
    assert out.count('class="aff aff-amzn"') == 2
    assert out.count('class="aff aff-spwh"') == 2
    # All affiliate <a> tags carry the required rel attributes.
    assert out.count('rel="sponsored nofollow noopener"') == 4
    # Sub-tag attribution is launch_key + species.
    assert "brewster__chinook" in out


def test_species_block_gear_bullets_have_no_links_without_credentials(monkeypatch):
    """With no env vars set, gear bullets render as plain <li> with no <a>."""
    for k in ("AMAZON_AFFILIATE_TAG", "AVANTLINK_AFFILIATE_ID",
              "AVANTLINK_SPWH_MERCHANT_ID"):
        monkeypatch.delenv(k, raising=False)
    from render import _species_block
    days = [{
        "date": "2026-07-01",
        "score": 0.9, "verdict": "GREAT", "open": True,
        "no_run_data": False,
        "techniques": [{
            "rank": 1, "method": "trolling", "label": "Spinner & roe",
            "gear": {"flasher": "hot pink size 4"},
            "notes": "fish the deep slot",
        }],
    }]
    out = _species_block("chinook", days, True, launch_key="brewster")
    assert 'class="aff' not in out
    # Plain bullet text still present.
    assert "flasher" in out and "hot pink size 4" in out


def test_species_block_gear_query_combines_value_and_key(monkeypatch):
    """Search query is '<value> <key>' so it reads naturally on the vendor."""
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    from render import _species_block
    days = [{
        "date": "2026-07-01",
        "score": 0.9, "verdict": "GREAT", "open": True,
        "no_run_data": False,
        "techniques": [{
            "rank": 1, "method": "trolling", "label": "x",
            "gear": {"flasher": "hot pink size 4"},
            "notes": "",
        }],
    }]
    out = _species_block("chinook", days, True, launch_key="brewster")
    # urlencode replaces spaces with '+': "hot+pink+size+4+flasher"
    assert "k=hot+pink+size+4+flasher" in out
```

- [ ] **Step 2.2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_render.py::test_species_block_gear_bullets_include_affiliate_links tests/test_render.py::test_species_block_gear_bullets_have_no_links_without_credentials tests/test_render.py::test_species_block_gear_query_combines_value_and_key -v`

Expected: All 3 tests fail with `TypeError: _species_block() got an unexpected keyword argument 'launch_key'`.

- [ ] **Step 2.3: Add the import to `render.py`**

In `render.py`, locate the existing imports near the top of the file. Add this import after the other internal imports:

```python
from engines.affiliate import links_for as _aff_links_for
```

- [ ] **Step 2.4: Add the `_gear_bullets` helper above `_species_block` in `render.py`**

Insert immediately before the `def _species_block(...)` line (currently line 400):

```python
def _gear_bullets(gear: dict, *, launch_key: str, species: str) -> str:
    """Render the gear dict as a series of <li> bullets, each with inline
    affiliate-link badges. When no affiliate env vars are set, the badges
    are omitted and bullets render as plain text.
    """
    out = []
    for k, v in gear.items():
        key_html = html.escape(str(k))
        val_html = html.escape(str(v))
        query = f"{v} {k}"  # e.g. "hot pink size 4 flasher"
        badges = "".join(
            f' <a class="aff aff-{l.vendor}" href="{html.escape(l.url, quote=True)}"'
            f' target="_blank" rel="sponsored nofollow noopener"'
            f' title="{html.escape(l.title, quote=True)}">{html.escape(l.label)}</a>'
            for l in _aff_links_for(query, launch_key=launch_key, species=species)
        )
        out.append(f"<li>{key_html}: {val_html}{badges}</li>")
    return "".join(out)
```

- [ ] **Step 2.5: Extend `_species_block` signature and replace the inline gear_html assignment**

Replace the existing `_species_block` function (lines 400-435) with:

```python
def _species_block(
    sp: str, days: list[dict], section_open: bool, *, launch_key: str,
) -> str:
    if not days:
        return ""
    cells = []
    # Day-strip is anchored to today's 7-day window; the rest of the 366-day
    # forecast lives in the JSON payload and is consumed by planner.js.
    for i, d in enumerate(days[:7]):
        klass = d["verdict"]
        future = "future-dim" if i >= 4 else ""
        no_run = (
            '<br><span class="muted">(no run data)</span>'
            if d.get("no_run_data")
            else ""
        )
        cells.append(
            f'<div class="day-cell {klass} {future}">'
            f'<strong>{d["date"][-5:]}</strong><br>{d["verdict"]}<br>'
            f'<span class="muted">{d["score"]:.2f}</span>{no_run}</div>'
        )
    today = days[0]
    techs = today.get("techniques") or []
    tech_html = ""
    if techs:
        primary = techs[0]
        gear = primary.get("gear") or {}
        gear_html = _gear_bullets(gear, launch_key=launch_key, species=sp)
        tech_html = (
            f'<div><strong>★ {html.escape(primary["label"])}</strong>'
            f'<ul>{gear_html}</ul>'
            f'<div class="muted">{html.escape(primary.get("notes",""))}</div></div>'
        )
    return f"""<details data-species-block="{sp}" {"open" if section_open else ""}>
<summary>{html.escape(SPECIES_LABEL.get(sp, sp))}</summary>
<div class="day-strip">{"".join(cells)}</div>
{tech_html}
</details>"""
```

- [ ] **Step 2.6: Update the only caller (`_launch_card`)**

In `render.py`, locate line 387 which currently reads:

```python
species_blocks.append(_species_block(sp, days, is_open))
```

Replace with:

```python
species_blocks.append(_species_block(sp, days, is_open, launch_key=launch["key"]))
```

- [ ] **Step 2.7: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_render.py::test_species_block_gear_bullets_include_affiliate_links tests/test_render.py::test_species_block_gear_bullets_have_no_links_without_credentials tests/test_render.py::test_species_block_gear_query_combines_value_and_key -v`

Expected: All 3 tests pass.

- [ ] **Step 2.8: Run the full test suite to verify the signature change didn't break other render tests**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: All tests pass (569 + 3 new = 572 passing, 1 skipped). If any existing render test fails because it called `_species_block` with positional args, those tests would need to pass `launch_key=` as a kwarg — check the failure and update accordingly.

- [ ] **Step 2.9: Commit**

```bash
git add render.py tests/test_render.py
git commit -m "feat(render): inline affiliate badges on every gear bullet

Each <li> in the technique block now carries optional [amzn] [spwh]
badges (when their env vars are configured). Sub-tag attribution =
<launch_key>__<species> so vendor dashboards reveal which fishing
recommendations drive clicks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Add the FTC disclosure banner

**Files:**
- Modify: `render.py` — add `_disclosure_banner` helper, render it inside `_header_bar` (around line 233-254).
- Modify: `tests/test_render.py` — add 2 tests for banner presence/absence.

- [ ] **Step 3.1: Write failing tests**

Append to `tests/test_render.py`:

```python
def test_disclosure_banner_renders_when_amazon_configured(monkeypatch):
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    monkeypatch.delenv("AVANTLINK_AFFILIATE_ID", raising=False)
    monkeypatch.delenv("AVANTLINK_SPWH_MERCHANT_ID", raising=False)
    from render import render_html
    data = _minimal_data()
    out = render_html(data)
    assert 'class="aff-disclosure muted"' in out
    assert "affiliate" in out.lower()


def test_disclosure_banner_omitted_with_no_credentials(monkeypatch):
    for k in ("AMAZON_AFFILIATE_TAG", "AVANTLINK_AFFILIATE_ID",
              "AVANTLINK_SPWH_MERCHANT_ID"):
        monkeypatch.delenv(k, raising=False)
    from render import render_html
    data = _minimal_data()
    out = render_html(data)
    assert 'class="aff-disclosure' not in out
```

- [ ] **Step 3.2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_render.py::test_disclosure_banner_renders_when_amazon_configured tests/test_render.py::test_disclosure_banner_omitted_with_no_credentials -v`

Expected: Both fail with `AssertionError` (`aff-disclosure` not found / unexpectedly found).

- [ ] **Step 3.3: Add `_disclosure_banner` helper above `_header_bar` in `render.py`**

Insert immediately before the `def _header_bar(data: dict)` line (currently line 233):

```python
def _disclosure_banner() -> str:
    """One-line FTC disclosure rendered when at least one affiliate vendor
    is configured. When unset, returns empty string so dev/test renders
    don't show a misleading disclosure with no actual affiliate links.
    """
    import os
    if not any(os.environ.get(k) for k in (
        "AMAZON_AFFILIATE_TAG",
        "AVANTLINK_AFFILIATE_ID",
    )):
        return ""
    return (
        '<aside class="aff-disclosure muted">'
        'Gear links are affiliate links — we earn a small commission if you '
        'buy, at no cost to you.'
        '</aside>'
    )
```

- [ ] **Step 3.4: Insert the banner inside `_header_bar`**

Locate the existing `_header_bar` body (lines 239-254). Replace the return value with:

```python
    return f"""<header class="card">
  <h1>Salmon &amp; Steelhead Report</h1>
  <div class="muted">Forecast week starting <span id="picker-caption">{today_iso}</span> · generated {html.escape(data['generated_at'])}</div>
  {_disclosure_banner()}
  <div class="picker">
    <label>View date: <input type="date" id="date-picker" min="{today_iso}" max="{html.escape(max_iso)}" value="{today_iso}"></label>
    <span class="muted" id="picker-note"></span>
  </div>
  <details class="score-help">
    <summary class="muted">What does the score mean?</summary>
    <div class="muted">
      Scores combine open/closed status, run-timing pace, weather conditions, and recent creel.
      <strong>0.9+ GREAT</strong> · <strong>0.7+ GOOD</strong> · <strong>0.5+ FAIR</strong> · <strong>below 0.5 POOR</strong>.
      Scores past day 7 use only run-timing pace and regulations (weather isn't predicted).
    </div>
  </details>
</header>"""
```

- [ ] **Step 3.5: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_render.py::test_disclosure_banner_renders_when_amazon_configured tests/test_render.py::test_disclosure_banner_omitted_with_no_credentials -v`

Expected: Both tests pass.

- [ ] **Step 3.6: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: All tests pass (572 + 2 new = 574 passing, 1 skipped).

- [ ] **Step 3.7: Commit**

```bash
git add render.py tests/test_render.py
git commit -m "feat(render): FTC affiliate-disclosure banner under report header

Renders only when at least one affiliate vendor env var is set, so test
and dev environments don't show a misleading disclosure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Add CSS for `.aff` badges and `.aff-disclosure`

**Files:**
- Modify: `render.py` — append rules to the `<style>` block (located between lines ~190-228, search for `.heat-cell.NA` to find the surrounding context).

- [ ] **Step 4.1: Add a regression test for the CSS rules**

Append to `tests/test_render.py`:

```python
def test_css_includes_aff_badge_styles():
    """The rendered <style> block carries the .aff and .aff-disclosure rules."""
    from render import render_html
    data = _minimal_data()
    out = render_html(data)
    assert ".aff {" in out
    assert ".aff-disclosure {" in out
    # Badge attributes that should always be styled:
    assert "font-size: 0.7rem" in out  # smaller than gear text
```

- [ ] **Step 4.2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_render.py::test_css_includes_aff_badge_styles -v`

Expected: Fails — neither `.aff {` nor `.aff-disclosure {` is in the CSS yet.

- [ ] **Step 4.3: Locate the CSS block end**

In `render.py`, find the line `.aff-disclosure` would naturally follow — search for `.heat-legend .heat-cell` (around line 223). The line immediately after `.aff-disclosure` should be `.picker { margin-top: 0.5rem; }` (around line 224).

- [ ] **Step 4.4: Insert the new CSS rules**

Insert these rules immediately before the `.picker { margin-top: 0.5rem; }` line:

```css
.aff {
    display: inline-block;
    margin-left: 0.25rem;
    padding: 0 0.25rem;
    font-size: 0.7rem;
    line-height: 1.4;
    border: 1px solid var(--border);
    border-radius: 3px;
    color: var(--muted);
    text-decoration: none;
    vertical-align: middle;
}
.aff:hover { color: var(--fg); background: #2a2a2a; }
.aff-disclosure {
    font-size: 0.75rem;
    margin: 0.25rem 0;
}
```

- [ ] **Step 4.5: Run the test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_render.py::test_css_includes_aff_badge_styles -v`

Expected: Passes.

- [ ] **Step 4.6: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: All tests pass (574 + 1 new = 575 passing, 1 skipped).

- [ ] **Step 4.7: Manual visual check**

Generate a local report with credentials set and open it in a browser:

```bash
DATA_DIR=/tmp/aff_test_data \
AMAZON_AFFILIATE_TAG=test-tag \
AVANTLINK_AFFILIATE_ID=test-aff \
AVANTLINK_SPWH_MERCHANT_ID=test-mid \
.venv/bin/python -c "
import os; os.makedirs('/tmp/aff_test_data', exist_ok=True)
from datetime import date
from storage import FileStorage
from fishing_report import build_report_data, render_html
from tests.test_build_report_data_long_range import _minimal_inputs
storage = FileStorage(root='/tmp/aff_test_data')
data = build_report_data(_minimal_inputs(date(2026, 5, 13)), storage=storage)
open('/tmp/aff_test.html','w').write(render_html(data))
print('wrote /tmp/aff_test.html')
"
```

Open `/tmp/aff_test.html` in a browser. Confirm:
- Disclosure banner appears under the header
- Every gear bullet shows two small `[amzn]` `[spwh]` badges
- Hovering each badge shows the tooltip
- Clicking each badge opens a search results page (Amazon search or AvantLink → Sportsman's Warehouse redirect with the test tag values)

- [ ] **Step 4.8: Commit**

```bash
git add render.py tests/test_render.py
git commit -m "style(render): CSS for affiliate badges and disclosure banner

Small bordered pills (.aff), readable but unobtrusive. Hover state
highlights the badge. Disclosure styled muted at 0.75rem.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Deploy and regenerate

**Files:**
- (none in repo) — Railway env-var configuration + regen.

**Prerequisite:** You need real affiliate credentials. Sign up for:
- Amazon Associates → get your tracking tag (looks like `pnwbite-20`).
- AvantLink → apply to the Sportsman's Warehouse merchant program, get your affiliate ID and the SpWh merchant ID.

If credentials aren't ready, this task can wait — Tasks 1-4 deployed without env vars will leave the report unchanged (graceful degradation).

- [ ] **Step 5.1: Push the commits to GitHub**

```bash
git push origin master
```

Expected: Railway auto-deploy triggers. Wait until status shows `● Online` without a `Building` suffix.

- [ ] **Step 5.2: Configure the three env vars on Railway**

```bash
export RAILWAY_API_TOKEN=$(grep '=' /home/alan/arath/fishing_reports/no_git_commit-RAILWAY_API_TOKEN.txt | cut -d= -f2)
export PATH=$HOME/.railway/bin:$PATH
cd /home/alan/arath/fishing_reports/salmon
railway variables --set "AMAZON_AFFILIATE_TAG=<your-amazon-tag>"
railway variables --set "AVANTLINK_AFFILIATE_ID=<your-avantlink-aff-id>"
railway variables --set "AVANTLINK_SPWH_MERCHANT_ID=<spwh-merchant-id>"
```

Replace each placeholder with the real value. Railway redeploys after each `--set` — wait until status is Online between each one, or use one combined `--set` invocation if the CLI supports it.

- [ ] **Step 5.3: Regenerate `report.html` on Railway**

```bash
railway ssh "cd /app && DATA_DIR=/data python -u fishing_report.py 2>&1 | tail -5"
```

Expected: `INFO report.html written: ~21MB bytes` and `INFO Cloudflare cache purged`.

- [ ] **Step 5.4: Verify on the live site**

```bash
curl -sS 'https://salmon.pnwbite.com/' -H 'Cache-Control: no-cache' -o /tmp/salmon_live.html
grep -c 'class="aff aff-amzn"' /tmp/salmon_live.html
grep -c 'class="aff aff-spwh"' /tmp/salmon_live.html
grep -c 'aff-disclosure' /tmp/salmon_live.html
grep -c '<your-amazon-tag>' /tmp/salmon_live.html
```

Expected:
- aff-amzn count > 0 (one per gear bullet times number of open launches with techniques)
- aff-spwh count = same as aff-amzn
- aff-disclosure count = 1
- Your real amazon tag appears in the URLs

- [ ] **Step 5.5: Manual click-through verification**

Open https://salmon.pnwbite.com in a browser:
- Disclosure banner visible under the report header.
- Open any launch card → expand a species block → confirm gear bullets show `[amzn]` `[spwh]` badges.
- Click an `[amzn]` badge in a fresh tab → confirm it opens an Amazon search results page with your real affiliate tag in the URL.
- Click an `[spwh]` badge in a fresh tab → confirm it redirects through AvantLink to a Sportsman's Warehouse search results page.

- [ ] **Step 5.6: (Optional) Update HANDOFF.md**

Add a one-line entry under "Out-of-repo (Railway env vars)" listing the three new env vars, so the next person sees them when reading the handoff.

---

## Done criteria

- All 575 tests pass.
- `engines/affiliate.py` covers the URL-building logic in isolation.
- Renderer emits affiliate badges + disclosure when env vars are set, plain bullets + no banner when unset.
- Live site shows badges + disclosure, click-through lands on real Amazon and Sportsman's Warehouse search pages with your affiliate identifiers in the URL.
