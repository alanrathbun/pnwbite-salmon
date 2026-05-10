"""Planner engine: top-N pivots over the per-launch forecast dict."""
import pytest

from engines.planner import (
    top_launches_by_species_date,
    top_dates_by_launch_species,
    top_pairs_by_date,
    season_heatmap_for_species,
)


def _make_entry(date_iso: str, score: float, *, open_=True, technique="Plunking", long_range=False):
    base = {
        "date": date_iso, "score": score, "verdict": "GOOD",
        "open": open_, "long_range": long_range,
    }
    if not long_range:
        base["techniques"] = [{"label": technique}]
    return base


@pytest.fixture
def forecasts():
    return {
        "spring_chinook::mcnary_tailrace": [
            _make_entry("2026-05-10", 0.84),
            _make_entry("2026-05-11", 0.70),
            _make_entry("2026-05-12", 0.30),
        ],
        "spring_chinook::umatilla_marina": [
            _make_entry("2026-05-10", 0.92),
            _make_entry("2026-05-11", 0.40),
            _make_entry("2026-05-12", 0.10),
        ],
        "spring_chinook::closed_launch": [
            _make_entry("2026-05-10", 0.95, open_=False),
        ],
        "fall_chinook::mcnary_tailrace": [
            _make_entry("2026-05-10", 0.20),
            _make_entry("2026-05-11", 0.25),
            _make_entry("2026-05-12", 0.30),
        ],
    }


def test_top_launches_by_species_date_ranks_open_only(forecasts):
    out = top_launches_by_species_date(forecasts, "spring_chinook", "2026-05-10", k=5)
    assert [(p["launch"], p["score"]) for p in out] == [
        ("umatilla_marina", 0.92),
        ("mcnary_tailrace", 0.84),
    ]
    # The closed launch is excluded even though its score is highest
    assert all(p["launch"] != "closed_launch" for p in out)


def test_top_launches_includes_technique_when_present(forecasts):
    out = top_launches_by_species_date(forecasts, "spring_chinook", "2026-05-10", k=5)
    assert out[0]["technique"] == "Plunking"


def test_top_launches_returns_empty_when_no_entries(forecasts):
    out = top_launches_by_species_date(forecasts, "coho", "2026-05-10", k=5)
    assert out == []


def test_top_launches_caps_at_k(forecasts):
    out = top_launches_by_species_date(forecasts, "spring_chinook", "2026-05-10", k=1)
    assert len(out) == 1
    assert out[0]["launch"] == "umatilla_marina"


def test_top_dates_by_launch_species_returns_best_dates(forecasts):
    out = top_dates_by_launch_species(forecasts, "mcnary_tailrace", "spring_chinook", k=2)
    assert [(d["date"], d["score"]) for d in out] == [
        ("2026-05-10", 0.84),
        ("2026-05-11", 0.70),
    ]


def test_top_dates_excludes_closed_dates(forecasts):
    forecasts["spring_chinook::mcnary_tailrace"][0]["open"] = False
    out = top_dates_by_launch_species(forecasts, "mcnary_tailrace", "spring_chinook", k=5)
    assert all(d["date"] != "2026-05-10" for d in out)


def test_top_dates_returns_empty_for_unknown_pair(forecasts):
    out = top_dates_by_launch_species(forecasts, "nonexistent", "coho", k=5)
    assert out == []


def test_top_pairs_by_date_ranks_across_species(forecasts):
    out = top_pairs_by_date(forecasts, "2026-05-10", k=5)
    # umatilla spring_chinook (0.92) > mcnary spring_chinook (0.84) > mcnary fall_chinook (0.20)
    assert [(p["launch"], p["species"], p["score"]) for p in out] == [
        ("umatilla_marina", "spring_chinook", 0.92),
        ("mcnary_tailrace", "spring_chinook", 0.84),
        ("mcnary_tailrace", "fall_chinook", 0.20),
    ]


def test_top_pairs_excludes_closed(forecasts):
    out = top_pairs_by_date(forecasts, "2026-05-10", k=5)
    assert all(p["launch"] != "closed_launch" for p in out)


def test_season_heatmap_for_species_returns_best_open_score_per_date(forecasts):
    out = season_heatmap_for_species(forecasts, "spring_chinook")
    by_date = {d["date"]: d["score"] for d in out}
    assert by_date["2026-05-10"] == 0.92  # max(0.84, 0.92), closed excluded
    assert by_date["2026-05-11"] == 0.70  # max(0.70, 0.40)
    assert by_date["2026-05-12"] == 0.30  # max(0.30, 0.10)


def test_season_heatmap_returns_empty_for_unknown_species(forecasts):
    out = season_heatmap_for_species(forecasts, "coho")
    assert out == []


def test_top_n_breaks_ties_alphabetically(forecasts):
    # Force a tie: two launches both at 0.50 on the same date
    forecasts["spring_chinook::aaa_launch"] = [_make_entry("2026-05-13", 0.50)]
    forecasts["spring_chinook::bbb_launch"] = [_make_entry("2026-05-13", 0.50)]
    out = top_launches_by_species_date(forecasts, "spring_chinook", "2026-05-13", k=2)
    assert [p["launch"] for p in out] == ["aaa_launch", "bbb_launch"]
