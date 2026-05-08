"""Bait/technique rules engine.

Loads `bait_rules.yaml` (a list of rules with selector + ranked techniques) and
matches a context (species, reach_type, flow_band, clarity_band) to a rule.

Match algorithm: score each rule by specificity (count of non-"*" selectors that
match the context), filter to rules where all non-"*" selectors match, return
the highest-specificity rule. Wildcards (`"*"`) match anything.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def _specificity(rule: dict[str, Any]) -> int:
    return sum(1 for f in _SELECTOR_FIELDS if rule["when"].get(f, "*") != "*")


def match_rule(
    rules: list[dict[str, Any]],
    *,
    species: str,
    reach_type: str,
    flow_band: str,
    clarity_band: str,
) -> dict[str, Any] | None:
    ctx = {
        "species": species,
        "reach_type": reach_type,
        "flow_band": flow_band,
        "clarity_band": clarity_band,
    }
    eligible = []
    for r in rules:
        if all(_selector_matches(r["when"].get(f, "*"), ctx[f]) for f in _SELECTOR_FIELDS):
            eligible.append(r)
    if not eligible:
        return None
    return max(eligible, key=_specificity)


def techniques_from_rule(rule: dict[str, Any]) -> list[Technique]:
    return [
        Technique(
            rank=int(t.get("rank", i + 1)),
            method=t["method"],
            label=t.get("label", t["method"]),
            gear=dict(t.get("gear") or {}),
            notes=t.get("notes", ""),
        )
        for i, t in enumerate(sorted(rule["techniques"], key=lambda x: x.get("rank", 99)))
    ]
