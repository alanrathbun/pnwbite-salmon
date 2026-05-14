"""Bait/technique rules engine.

Loads `bait_rules.yaml` (a list of rules with selector + ranked techniques) and
matches a context (species, reach_type, flow_band, clarity_band, optional date)
to a rule.

Match algorithm: filter rules whose `when` clause matches the context (all
non-"*" selectors equal the context value; if the rule has a `dates` field and
`today` is supplied, today must fall in the MM-DD..MM-DD range). Among
eligible rules, return the one with the highest specificity (count of
non-wildcard selectors, with `dates` counting as one). Wildcards (`"*"`) match
anything.

Date ranges follow the pamphlet YAML convention: "MM-DD..MM-DD"; if the start
date is after the end date, the range wraps around year-end (e.g.
"11-01..03-31" matches Nov-Dec or Jan-Mar).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


_SELECTOR_FIELDS = ("species", "reach_type", "flow_band", "clarity_band")


@dataclass(frozen=True)
class Technique:
    rank: int
    method: str
    label: str
    gear: dict[str, Any]
    notes: str


def load_rules_text(text: str) -> list[dict[str, Any]]:
    rules = yaml.safe_load(text) or []
    if not isinstance(rules, list):
        raise ValueError("bait_rules.yaml must be a top-level list")
    for r in rules:
        if "when" not in r or "techniques" not in r:
            raise ValueError(f"rule missing required keys: {r}")
        for f in _SELECTOR_FIELDS:
            r["when"].setdefault(f, "*")
    return rules


def load_rules_file(path: str | Path) -> list[dict[str, Any]]:
    return load_rules_text(Path(path).read_text(encoding="utf-8"))


def _selector_matches(selector_value: str, context_value: str) -> bool:
    return selector_value == "*" or selector_value == context_value


def _parse_mmdd(s: str, year: int) -> date:
    m, d = s.split("-")
    return date(year, int(m), int(d))


def _date_in_range(today: date, range_str: str) -> bool:
    """MM-DD..MM-DD range. Handles year wraparound (e.g. 11-01..03-31)."""
    try:
        start_str, end_str = range_str.split("..")
    except ValueError:
        return False
    start = _parse_mmdd(start_str.strip(), today.year)
    end = _parse_mmdd(end_str.strip(), today.year)
    if start <= end:
        return start <= today <= end
    return today >= start or today <= end


def _specificity(rule: dict[str, Any]) -> int:
    n = sum(1 for f in _SELECTOR_FIELDS if rule["when"].get(f, "*") != "*")
    if rule["when"].get("dates"):
        n += 1
    return n


def match_rule(
    rules: list[dict[str, Any]],
    *,
    species: str,
    reach_type: str,
    flow_band: str,
    clarity_band: str,
    today: date | None = None,
) -> dict[str, Any] | None:
    ctx = {
        "species": species,
        "reach_type": reach_type,
        "flow_band": flow_band,
        "clarity_band": clarity_band,
    }
    eligible = []
    for r in rules:
        if not all(_selector_matches(r["when"].get(f, "*"), ctx[f]) for f in _SELECTOR_FIELDS):
            continue
        dates_spec = r["when"].get("dates")
        if dates_spec:
            # When the caller doesn't supply `today`, a dated rule is skipped
            # rather than treated as universal — otherwise a fallback caller
            # would silently grab a seasonal rule.
            if today is None or not _date_in_range(today, dates_spec):
                continue
        eligible.append(r)
    if not eligible:
        return None
    return max(eligible, key=_specificity)


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
