import textwrap
import pytest
from engines.bait_rules import load_rules_text, match_rule, Technique


SAMPLE_YAML = textwrap.dedent("""
- when:
    species: chinook
    reach_type: freeflowing
    flow_band: normal
    clarity_band: clear
  techniques:
    - rank: 1
      method: back_bounce_eggs
      label: "Back-bounce cured eggs"
      gear: { weight: "2-4 oz cannonball" }
      notes: "Anchor at the head"
- when:
    species: chinook
    reach_type: freeflowing
    flow_band: "*"
    clarity_band: "*"
  techniques:
    - rank: 1
      method: troll_kwikfish
      label: "Wrapped Kwikfish"
      gear: {}
      notes: "fallback"
- when:
    species: "*"
    reach_type: "*"
    flow_band: "*"
    clarity_band: "*"
  techniques:
    - rank: 1
      method: any
      label: "Generic"
      gear: {}
      notes: "last resort"
""").strip()


def test_load_rules_returns_list_with_techniques():
    rules = load_rules_text(SAMPLE_YAML)
    assert len(rules) == 3
    assert rules[0]["when"]["species"] == "chinook"
    assert rules[0]["techniques"][0]["method"] == "back_bounce_eggs"


def test_match_picks_most_specific_first():
    rules = load_rules_text(SAMPLE_YAML)
    match = match_rule(
        rules,
        species="chinook",
        reach_type="freeflowing",
        flow_band="normal",
        clarity_band="clear",
    )
    assert match is not None
    assert match["techniques"][0]["method"] == "back_bounce_eggs"


def test_match_falls_back_to_wildcard():
    rules = load_rules_text(SAMPLE_YAML)
    match = match_rule(
        rules,
        species="chinook",
        reach_type="freeflowing",
        flow_band="high",
        clarity_band="muddy",
    )
    assert match is not None
    assert match["techniques"][0]["method"] == "troll_kwikfish"


def test_match_returns_universal_fallback_for_unknown_species():
    rules = load_rules_text(SAMPLE_YAML)
    match = match_rule(
        rules,
        species="snakehead",
        reach_type="tailrace",
        flow_band="low",
        clarity_band="clear",
    )
    assert match["techniques"][0]["method"] == "any"


def test_match_returns_none_when_no_universal_fallback():
    rules = load_rules_text(SAMPLE_YAML[: SAMPLE_YAML.index('- when:\n    species: "*"')])
    match = match_rule(
        rules,
        species="snakehead",
        reach_type="tailrace",
        flow_band="low",
        clarity_band="clear",
    )
    assert match is None
