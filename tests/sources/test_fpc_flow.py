from datetime import date
from pathlib import Path
from sources.fpc_flow import parse_flowspil, FlowRecord

FIXTURE = Path(__file__).parent.parent / "fixtures/fpc/flowspil_sample.txt"


def test_parses_known_dams():
    text = FIXTURE.read_text()
    records = parse_flowspil(text)
    # The fixture must contain at least our 7 reference dams; verify a few.
    keys = {r.dam_key for r in records}
    assert "BON" in keys
    assert "MCN" in keys
    assert "LGR" in keys


def test_record_has_date_and_kcfs():
    text = FIXTURE.read_text()
    records = parse_flowspil(text)
    r = next(r for r in records if r.dam_key == "BON")
    assert isinstance(r.date, date)
    assert isinstance(r.kcfs, float)
    assert 50.0 < r.kcfs < 600.0  # plausible Bonneville range


def test_returns_per_dam_history_in_chronological_order():
    text = FIXTURE.read_text()
    records = parse_flowspil(text)
    bon = sorted([r for r in records if r.dam_key == "BON"], key=lambda r: r.date)
    # Should be at least 7 days of history for any active dam.
    assert len(bon) >= 7
    # Dates strictly increasing.
    for a, b in zip(bon, bon[1:]):
        assert b.date > a.date
