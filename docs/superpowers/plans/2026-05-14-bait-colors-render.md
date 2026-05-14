# Bait Rules: `colors_by_clarity` Resolution + Per-Color Bullets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Wind River Mouth (and 13 other techniques) where `colors_by_clarity: {clear: [...], stained: [...]}` was being rendered as a Python dict literal, producing unreadable text and useless Amazon searches like `{'clear': ['silver/red'...]} colors_by_clarity`.

**Architecture:** The bait-rule engine resolves `gear.colors_by_clarity` against the matched `clarity_band` at the engine layer, producing `gear["colors"]` as a list of strings (e.g. `["silver/red", "brass/red"]`). The render layer handles list gear values by emitting one bullet per item. Both the bullet text and the Amazon search query include the technique label for context so searches like `"silver/red R&B-style spinner"` return relevant tackle.

**Tech Stack:** Python stdlib. Existing pytest test runner.

---

## File Map

- **Modify:** `engines/bait_rules.py` — add `clarity_band` kwarg to `techniques_from_rule`; resolve `colors_by_clarity` to a `colors: list[str]` field.
- **Modify:** `fishing_report.py` — pass `clarity_band` through to `techniques_from_rule`.
- **Modify:** `render.py` — `_gear_bullets` now accepts a `technique_label`, handles list gear values (one bullet per item), and uses the label in Amazon search queries.
- **Modify:** `tests/engines/test_bait_rules.py` — tests for the new resolution.
- **Modify:** `tests/test_render.py` — tests for list-value rendering and label-in-query.

---

## Task 1: Engine resolves `colors_by_clarity` at match time

**Files:**
- Modify: `engines/bait_rules.py` — `techniques_from_rule`
- Modify: `tests/engines/test_bait_rules.py`

- [ ] **Step 1.1: Write failing tests**

Append to `tests/engines/test_bait_rules.py`:

```python
def test_techniques_from_rule_resolves_colors_by_clarity_clear():
    """Clear-water clarity band picks the 'clear' color list."""
    from engines.bait_rules import techniques_from_rule
    rule = {
        "techniques": [{
            "rank": 1, "method": "spinners", "label": "R&B-style spinner",
            "gear": {
                "size": "#5-6 R&B Spinglo",
                "colors_by_clarity": {
                    "clear": ["silver/red", "brass/red"],
                    "stained": ["chartreuse/orange", "fluor-pink"],
                },
            },
            "notes": "Cast and retrieve.",
        }],
    }
    techs = techniques_from_rule(rule, clarity_band="clear")
    assert len(techs) == 1
    gear = techs[0].gear
    # colors_by_clarity is dropped; replaced by a 'colors' list of strings.
    assert "colors_by_clarity" not in gear
    assert gear["colors"] == ["silver/red", "brass/red"]
    # Sibling keys still present
    assert gear["size"] == "#5-6 R&B Spinglo"


def test_techniques_from_rule_resolves_colors_by_clarity_stained():
    """Stained-water clarity band picks the 'stained' color list."""
    from engines.bait_rules import techniques_from_rule
    rule = {
        "techniques": [{
            "rank": 1, "method": "spinners", "label": "R&B-style spinner",
            "gear": {
                "colors_by_clarity": {
                    "clear": ["silver/red"],
                    "stained": ["chartreuse/orange", "fluor-pink"],
                },
            },
            "notes": "",
        }],
    }
    techs = techniques_from_rule(rule, clarity_band="stained")
    assert techs[0].gear["colors"] == ["chartreuse/orange", "fluor-pink"]


def test_techniques_from_rule_unknown_clarity_falls_back_to_clear():
    """If the rule has no entry for the matched clarity_band, fall back to 'clear'.
    Defensive: bait_rules.yaml might add new clarity bands the rule doesn't cover."""
    from engines.bait_rules import techniques_from_rule
    rule = {
        "techniques": [{
            "rank": 1, "method": "spinners", "label": "x",
            "gear": {
                "colors_by_clarity": {
                    "clear": ["silver/red"],
                    "stained": ["chartreuse/orange"],
                },
            },
            "notes": "",
        }],
    }
    techs = techniques_from_rule(rule, clarity_band="murky")  # not in dict
    assert techs[0].gear["colors"] == ["silver/red"]


def test_techniques_from_rule_no_colors_by_clarity_passes_through():
    """Gear without colors_by_clarity is unaffected — Kwikfish K15 plug stays as-is."""
    from engines.bait_rules import techniques_from_rule
    rule = {
        "techniques": [{
            "rank": 1, "method": "back_troll", "label": "Back-troll Kwikfish K15",
            "gear": {"plug": "Kwikfish K15", "wrap": "sardine wrap"},
            "notes": "",
        }],
    }
    techs = techniques_from_rule(rule, clarity_band="clear")
    assert techs[0].gear == {"plug": "Kwikfish K15", "wrap": "sardine wrap"}


def test_techniques_from_rule_handles_no_gear_dict():
    """Missing or null gear → empty dict, no crash."""
    from engines.bait_rules import techniques_from_rule
    rule = {"techniques": [{"rank": 1, "method": "x", "label": "x", "notes": ""}]}
    techs = techniques_from_rule(rule, clarity_band="clear")
    assert techs[0].gear == {}
```

- [ ] **Step 1.2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/engines/test_bait_rules.py -v -k "clarity or no_gear or no_colors"`

Expected: All 5 tests fail with `TypeError: techniques_from_rule() got an unexpected keyword argument 'clarity_band'`.

- [ ] **Step 1.3: Update `techniques_from_rule` signature and resolution logic**

In `engines/bait_rules.py`, replace the existing `techniques_from_rule` function (currently at the bottom of the file, ~10 lines) with:

```python
def techniques_from_rule(rule: dict[str, Any], *, clarity_band: str) -> list[Technique]:
    """Return resolved Technique entries for a matched rule.

    The bait rule's `gear` dict may include a `colors_by_clarity` sub-dict
    of the shape `{clarity_band: [color1, color2, ...], ...}`. This function
    resolves it against the caller's `clarity_band` and replaces it with a
    flat `colors: list[str]` field, dropping the nested key. If the band
    isn't represented in the dict, falls back to "clear" (defensive — keeps
    behavior sane if bait_rules.yaml ever introduces new clarity values
    that some techniques don't cover).
    """
    out = []
    for i, t in enumerate(sorted(rule["techniques"], key=lambda x: x.get("rank", 99))):
        gear = dict(t.get("gear") or {})
        cbc = gear.pop("colors_by_clarity", None)
        if isinstance(cbc, dict):
            gear["colors"] = list(cbc.get(clarity_band) or cbc.get("clear") or [])
        out.append(Technique(
            rank=int(t.get("rank", i + 1)),
            method=t["method"],
            label=t.get("label", t["method"]),
            gear=gear,
            notes=t.get("notes", ""),
        ))
    return out
```

- [ ] **Step 1.4: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/engines/test_bait_rules.py -v -k "clarity or no_gear or no_colors"`

Expected: All 5 tests pass.

- [ ] **Step 1.5: Run the full suite — existing callers of `techniques_from_rule` will now fail because `clarity_band` is required**

Run: `.venv/bin/python -m pytest tests/ -q 2>&1 | tail -20`

Expected: Several failures with `TypeError: techniques_from_rule() missing 1 required keyword-only argument: 'clarity_band'`. List the failing test files — they'll need to be updated in Step 1.6.

- [ ] **Step 1.6: Update existing callers of `techniques_from_rule`**

Search and update every test/production call site to pass `clarity_band=`. The known production caller is `fishing_report.py` at the per-day loop (search for `techniques_from_rule(rule)`). The fix there is Task 2. For now, update only the test callers so the existing tests pass.

For each test failure from Step 1.5, edit that test file to add `clarity_band="clear"` (or whatever band the test scenario is intended to exercise) to the `techniques_from_rule(...)` call.

Run: `.venv/bin/python -m pytest tests/engines/test_bait_rules.py -q`

Expected: All bait-rule tests pass (including the 5 new ones).

- [ ] **Step 1.7: Commit (defer full-suite green to Task 2)**

```bash
git add engines/bait_rules.py tests/engines/test_bait_rules.py
git commit -m "feat(bait): resolve colors_by_clarity to a flat colors list at match time

techniques_from_rule now requires clarity_band kwarg and resolves the
gear's colors_by_clarity dict into a single 'colors' list of strings,
falling back to 'clear' if the matched band isn't represented.

Production caller in fishing_report.py wired up in the next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Wire `clarity_band` through `fishing_report.py`

**Files:**
- Modify: `fishing_report.py` — the per-day loop that calls `techniques_from_rule`.

- [ ] **Step 2.1: Locate the call site**

In `fishing_report.py`, search for `techniques_from_rule(rule)` (currently around line 460-465 inside the per-day forecast loop). The matcher already computes `clarity_band = _clarity_band(latest_flow)` and passes it to `match_rule` a few lines above.

- [ ] **Step 2.2: Pass `clarity_band` through to `techniques_from_rule`**

Replace the existing call:

```python
techniques = (
    [
        {
            "rank": t.rank,
            "method": t.method,
            "label": t.label,
            "gear": t.gear,
            "notes": t.notes,
        }
        for t in techniques_from_rule(rule)
    ]
    if rule
    else []
)
```

with:

```python
techniques = (
    [
        {
            "rank": t.rank,
            "method": t.method,
            "label": t.label,
            "gear": t.gear,
            "notes": t.notes,
        }
        for t in techniques_from_rule(rule, clarity_band=_clarity_band(latest_flow))
    ]
    if rule
    else []
)
```

- [ ] **Step 2.3: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: All tests pass — should match the pre-existing count plus the 5 new bait-rule tests.

- [ ] **Step 2.4: Commit**

```bash
git add fishing_report.py
git commit -m "feat(report): pass clarity_band into techniques_from_rule

Production wires through the per-day clarity_band computed from the
launch's latest flow reading, completing the colors_by_clarity
resolution started in the previous commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Render layer handles list gear values + technique label in Amazon search

**Files:**
- Modify: `render.py` — `_gear_bullets` signature and body.
- Modify: `tests/test_render.py` — tests for list values and label-in-query.

- [ ] **Step 3.1: Write failing tests**

Append to `tests/test_render.py`:

```python
def test_gear_bullets_emit_one_li_per_list_item(monkeypatch):
    """Gear values that are lists produce one <li> per item."""
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    from render import _gear_bullets
    out = _gear_bullets(
        {"colors": ["silver/red", "brass/red"]},
        launch_key="wind_mouth", species="chinook",
        technique_label="R&B-style spinner",
    )
    assert out.count("<li>") == 2
    # Each list item rendered as its own bullet — no Python list literal text.
    assert "['silver/red'" not in out
    assert "silver/red" in out
    assert "brass/red" in out


def test_gear_bullets_search_query_uses_technique_label(monkeypatch):
    """Amazon search query is '<value> <technique_label>', dropping the
    bare gear-key word (e.g., 'colors') which is unhelpful for shopping."""
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    from render import _gear_bullets
    out = _gear_bullets(
        {"colors": ["silver/red"]},
        launch_key="wind_mouth", species="chinook",
        technique_label="R&B-style spinner",
    )
    # urlencode replaces spaces with '+'.
    assert "k=silver%2Fred+R%26B-style+spinner" in out


def test_gear_bullets_renders_scalar_unchanged(monkeypatch):
    """Scalar gear values still produce a single bullet, search uses label."""
    monkeypatch.setenv("AMAZON_AFFILIATE_TAG", "pnwbite-20")
    from render import _gear_bullets
    out = _gear_bullets(
        {"plug": "Kwikfish K15"},
        launch_key="drano", species="chinook",
        technique_label="Back-troll Kwikfish K15",
    )
    assert out.count("<li>") == 1
    assert "plug: Kwikfish K15" in out
    # Search uses label, not bare gear-key.
    assert "k=Kwikfish+K15+Back-troll+Kwikfish+K15" in out


def test_gear_bullets_without_credentials_still_emits_list_items(monkeypatch):
    """No-affiliate fallback path still expands list values to multiple bullets."""
    for k in ("AMAZON_AFFILIATE_TAG", "AVANTLINK_AFFILIATE_ID",
              "AVANTLINK_SPWH_MERCHANT_ID"):
        monkeypatch.delenv(k, raising=False)
    from render import _gear_bullets
    out = _gear_bullets(
        {"colors": ["silver/red", "brass/red"]},
        launch_key="wind_mouth", species="chinook",
        technique_label="R&B-style spinner",
    )
    assert out.count("<li>") == 2
    assert 'class="aff' not in out
```

- [ ] **Step 3.2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_render.py -v -k "gear_bullets" 2>&1 | tail -20`

Expected: All 4 new tests fail because `_gear_bullets` doesn't accept `technique_label=` and doesn't handle list values.

- [ ] **Step 3.3: Update `_gear_bullets` signature and body**

In `render.py`, replace the existing `_gear_bullets` function (currently in the helper section above `_species_block`):

```python
def _gear_bullets(
    gear: dict, *, launch_key: str, species: str, technique_label: str,
) -> str:
    """Render the gear dict as <li> bullets with inline affiliate badges.

    List gear values (e.g. `colors: [silver/red, brass/red]`) expand into
    one bullet per item. The Amazon search query is composed as
    `f"{value} {technique_label}"` so searches land on relevant tackle
    rather than the bare gear-key word.
    """
    out = []
    for k, v in gear.items():
        key_html = html.escape(str(k))
        values = v if isinstance(v, list) else [v]
        for individual in values:
            val_html = html.escape(str(individual))
            query = f"{individual} {technique_label}".strip()
            badges = "".join(
                f' <a class="aff aff-{html.escape(l.vendor)}" href="{html.escape(l.url, quote=True)}"'
                f' target="_blank" rel="sponsored nofollow noopener"'
                f' title="{html.escape(l.title, quote=True)}">{html.escape(l.label)}</a>'
                for l in _aff_links_for(query, launch_key=launch_key, species=species)
            )
            out.append(f"<li>{key_html}: {val_html}{badges}</li>")
    return "".join(out)
```

- [ ] **Step 3.4: Update the single caller (`_species_block`)**

In `render.py`, locate where `_species_block` calls `_gear_bullets` (currently passes `gear, launch_key=launch_key, species=sp`). Update to also pass `technique_label`:

```python
gear_html = _gear_bullets(
    gear,
    launch_key=launch_key,
    species=sp,
    technique_label=primary.get("label", ""),
)
```

- [ ] **Step 3.5: Run the new tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_render.py -v -k "gear_bullets"`

Expected: All 4 new tests pass.

- [ ] **Step 3.6: Run the full suite to verify no other render tests broke**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: All tests pass. If existing affiliate-render tests fail because the older fixture-data didn't include a technique label, update them to include `"label": "..."` on the test technique fixture, since `_gear_bullets` now requires `technique_label=`.

- [ ] **Step 3.7: Commit**

```bash
git add render.py tests/test_render.py
git commit -m "feat(render): list-valued gear emits one bullet per item; label in Amazon query

colors: [silver/red, brass/red] now renders as two bullets, each with
its own Amazon search using the technique label as context (e.g.
'silver/red R&B-style spinner') so links land on tackle, not generic
search results.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Deploy + verify on the live site

**Files:** none (push + regen).

- [ ] **Step 4.1: Push to GitHub**

```bash
git push origin master
```

Railway auto-deploys on push.

- [ ] **Step 4.2: Wait for deploy to finish + regenerate report**

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
$HOME/.railway/bin/railway ssh "cd /app && DATA_DIR=/data python -u fishing_report.py 2>&1 | tail -3"
```

- [ ] **Step 4.3: Verify on the live site**

```bash
curl -sS -m 30 'https://salmon.pnwbite.com/' -H 'Cache-Control: no-cache' -o /tmp/salmon_colors_live.html
# Confirm no Python dict literals leaked into the served HTML:
echo "raw dict literals: $(grep -c "{'clear':" /tmp/salmon_colors_live.html)"  # expect 0
echo "colors_by_clarity bullet text: $(grep -c 'colors_by_clarity' /tmp/salmon_colors_live.html)"  # expect 0
# Confirm color bullets render:
echo "color bullets: $(grep -c 'colors:' /tmp/salmon_colors_live.html)"  # expect > 0
# Spot-check a productive Amazon search URL:
grep -o 'k=silver%2Fred+[^&"]*' /tmp/salmon_colors_live.html | head -3
```

Expected:
- raw dict literals: 0
- colors_by_clarity in rendered text: 0
- color bullets > 0
- Sample search URLs include the technique label (not the literal word "colors")

Also manually open https://salmon.pnwbite.com, find the Wind River Mouth card, expand the chinook technique, confirm the bullet now reads `colors: silver/red [amzn] [spwh]` (one per color) and the Amazon link goes to a useful search.

---

## Done criteria

- All bait-rule and render tests pass.
- Production HTML has zero `{'clear':` or `colors_by_clarity` text.
- Wind River Mouth's chinook technique panel shows one bullet per color, each with productive Amazon search URLs containing the technique label.
