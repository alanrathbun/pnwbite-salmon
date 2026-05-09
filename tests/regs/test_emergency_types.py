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
    c = Classification(
        section_ids=["hanford_lower_i182_to_snyder"],
        status="closed",
        effective_from=date(2026, 5, 1),
        effective_to=date(2026, 6, 30),
        confidence=0.95,
        reasoning="Rule explicitly mentions Hanford Reach lower section.",
    )
    assert c.status == "closed"
    assert c.confidence == 0.95
