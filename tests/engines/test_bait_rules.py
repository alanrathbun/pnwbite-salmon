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


DATED_YAML = textwrap.dedent("""
- when:
    species: chinook
    dates: "03-01..06-15"
    reach_type: "*"
    flow_band: "*"
    clarity_band: "*"
  techniques:
    - rank: 1
      method: spring_eggs
      label: "Spring eggs"
      gear: {}
      notes: ""
- when:
    species: chinook
    dates: "08-01..12-31"
    reach_type: "*"
    flow_band: "*"
    clarity_band: "*"
  techniques:
    - rank: 1
      method: fall_kwikfish
      label: "Fall Kwikfish"
      gear: {}
      notes: ""
- when:
    species: chinook
    reach_type: "*"
    flow_band: "*"
    clarity_band: "*"
  techniques:
    - rank: 1
      method: year_round_fallback
      label: "Year-round fallback"
      gear: {}
      notes: ""
""").strip()


def test_dated_rule_matches_inside_window():
    from datetime import date
    rules = load_rules_text(DATED_YAML)
    match = match_rule(
        rules, species="chinook", reach_type="freeflowing",
        flow_band="normal", clarity_band="clear",
        today=date(2026, 5, 15),
    )
    assert match["techniques"][0]["method"] == "spring_eggs"


def test_dated_rule_falls_back_outside_window():
    from datetime import date
    rules = load_rules_text(DATED_YAML)
    # July 1 is between spring (03-01..06-15) and fall (08-01..12-31) windows.
    match = match_rule(
        rules, species="chinook", reach_type="freeflowing",
        flow_band="normal", clarity_band="clear",
        today=date(2026, 7, 1),
    )
    assert match["techniques"][0]["method"] == "year_round_fallback"


def test_dated_rule_matches_fall_window():
    from datetime import date
    rules = load_rules_text(DATED_YAML)
    match = match_rule(
        rules, species="chinook", reach_type="freeflowing",
        flow_band="normal", clarity_band="clear",
        today=date(2026, 10, 1),
    )
    assert match["techniques"][0]["method"] == "fall_kwikfish"


def test_dated_rule_with_year_wraparound():
    """Winter window 11-01..03-31 should match both Nov-Dec and Jan-Mar."""
    from datetime import date
    rules = load_rules_text(textwrap.dedent("""
    - when:
        species: steelhead
        dates: "11-01..03-31"
        reach_type: "*"
        flow_band: "*"
        clarity_band: "*"
      techniques:
        - rank: 1
          method: winter_plugs
          label: "Winter plugs"
          gear: {}
          notes: ""
    """).strip())
    for d in (date(2026, 12, 15), date(2026, 1, 15), date(2026, 3, 31), date(2026, 11, 1)):
        assert match_rule(
            rules, species="steelhead", reach_type="freeflowing",
            flow_band="normal", clarity_band="clear", today=d,
        )["techniques"][0]["method"] == "winter_plugs", f"failed for {d}"
    # May should NOT match
    assert match_rule(
        rules, species="steelhead", reach_type="freeflowing",
        flow_band="normal", clarity_band="clear", today=date(2026, 5, 15),
    ) is None


def test_dated_rule_skipped_when_today_not_supplied():
    """Without today, a seasonal rule should be skipped, falling to the
    dateless fallback. Prevents silently shipping a wrong seasonal pick."""
    rules = load_rules_text(DATED_YAML)
    match = match_rule(
        rules, species="chinook", reach_type="freeflowing",
        flow_band="normal", clarity_band="clear",
    )
    assert match["techniques"][0]["method"] == "year_round_fallback"


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
