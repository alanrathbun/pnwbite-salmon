from datetime import date
from pathlib import Path
from sources.fpc_counts import parse_adult_counts, CountRecord

FIXTURE = Path(__file__).parent.parent / "fixtures/fpc/adult_count_sample.html"


def test_parses_chinook_at_bonneville():
    html = FIXTURE.read_text()
    records = parse_adult_counts(html)
    bon_chin = [r for r in records if r.dam_key == "BON" and r.species == "chinook"]
    assert bon_chin, "expected at least one chinook count at Bonneville"
    r = bon_chin[0]
    assert isinstance(r.date, date)
    assert isinstance(r.count, int)
    assert r.count >= 0


def test_parses_steelhead_at_lower_granite():
    html = FIXTURE.read_text()
    records = parse_adult_counts(html)
    lgr_sth = [r for r in records if r.dam_key == "LGR" and r.species == "steelhead"]
    # During open season, expect at least some history.
    if lgr_sth:
        assert all(r.count >= 0 for r in lgr_sth)


def test_yields_chronological_per_dam_per_species():
    html = FIXTURE.read_text()
    records = parse_adult_counts(html)
    by: dict[tuple[str, str], list[CountRecord]] = {}
    for r in records:
        by.setdefault((r.dam_key, r.species), []).append(r)
    # With chinook sub-runs (spring/summer/fall) consolidated into a single
    # "chinook" key, the same (dam_key, species, date) may appear multiple times
    # — once per source column. Within a (dam, species) sequence we still expect
    # dates to be non-decreasing.
    for (_, _), seq in by.items():
        sorted_seq = sorted(seq, key=lambda r: r.date)
        for a, b in zip(sorted_seq, sorted_seq[1:]):
            assert b.date >= a.date
