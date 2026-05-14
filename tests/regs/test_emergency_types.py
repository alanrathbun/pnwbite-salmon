from datetime import date, datetime

from regs.emergency_types import EmergencyRule, Classification


def test_emergency_rule_construction():
    r = EmergencyRule(
        url="https://wdfw.wa.gov/fishing/regulations/emergency-rules/abc",
        title="Hanford Reach closure",
        body="The Hanford Reach is closed to salmon...",
        effective_from=date(2026, 5, 1),
        effective_to=date(2026, 6, 30),
        modified_at=datetime(2026, 5, 1, 12, 0),
    )
    assert r.title == "Hanford Reach closure"


def test_classification_construction():
    from regs.emergency_types import Projection
    p = Projection(
        section_id="hanford_lower_i182_to_snyder",
        status="closed",
        effective_from=date(2026, 5, 1),
        effective_to=date(2026, 6, 30),
        reason="Rule explicitly mentions Hanford Reach lower section.",
        authority="WDFW",
    )
    c = Classification(
        projections=[p],
        confidence=0.95,
        reasoning="Rule explicitly mentions Hanford Reach lower section.",
    )
    assert c.projections[0].status == "closed"
    assert c.confidence == 0.95


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
