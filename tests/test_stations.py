import pytest
from stations import STATIONS, get_station, stations_by_region, primary_stations


REGIONS = {"mid_col", "hanford", "upper_col", "snake"}
SPECIES_KEYS = {
    "spring_chinook", "summer_chinook", "sockeye", "fall_chinook",
    "coho", "summer_steelhead", "winter_steelhead",
}
REGS_AUTHORITIES = {"WDFW", "ODFW", "IDFG"}
REACH_TYPES = {"tailrace", "reservoir", "freeflowing", "confluence", "reservoir-side", "reservoir-trib"}


def test_30_primary_launches_and_1_subspot():
    primary = [s for s in STATIONS if s["parent_key"] is None]
    sub = [s for s in STATIONS if s["parent_key"] is not None]
    assert len(primary) == 30, f"expected 30 primary launches, got {len(primary)}"
    assert len(sub) == 1, f"expected 1 sub-spot, got {len(sub)}"
    assert sub[0]["key"] == "wahluke"
    assert sub[0]["parent_key"] == "white_bluffs"


def test_region_breakdown():
    by_region = {r: [s for s in STATIONS if s["region"] == r and s["parent_key"] is None] for r in REGIONS}
    assert len(by_region["mid_col"]) == 5
    assert len(by_region["hanford"]) == 7
    assert len(by_region["upper_col"]) == 5
    assert len(by_region["snake"]) == 13


def test_required_fields():
    required = {
        "key", "name", "region", "lat", "lon", "ref_dams", "flow_source",
        "usgs_site", "species", "reach_type", "tide_station", "regs_section",
        "regs_authority", "creel_district", "parent_key", "wdfw_url", "hero_photo",
    }
    for s in STATIONS:
        missing = required - set(s.keys())
        assert not missing, f"{s.get('key')} missing fields: {missing}"


def test_keys_unique():
    keys = [s["key"] for s in STATIONS]
    assert len(keys) == len(set(keys)), "duplicate keys"


def test_keys_url_safe():
    import re
    for s in STATIONS:
        assert re.fullmatch(r"[a-z0-9_]+", s["key"]), f"bad key: {s['key']}"


def test_lat_lon_in_pnw_range():
    for s in STATIONS:
        assert 45.0 < s["lat"] < 49.0, f"{s['key']} lat out of range: {s['lat']}"
        assert -122.5 < s["lon"] < -116.0, f"{s['key']} lon out of range: {s['lon']}"


def test_ref_dams_or_flow_source_set():
    """Every launch must have either ref_dams populated OR flow_source set."""
    for s in STATIONS:
        if not s["ref_dams"]:
            assert s["flow_source"], f"{s['key']} has neither ref_dams nor flow_source"


def test_regs_authority_valid():
    for s in STATIONS:
        assert s["regs_authority"] in REGS_AUTHORITIES, f"{s['key']}: bad regs_authority"


def test_species_subset_of_known():
    for s in STATIONS:
        assert set(s["species"]) <= SPECIES_KEYS, f"{s['key']}: unknown species"


def test_get_station_returns_match_or_none():
    assert get_station("vernita")["name"] == "Vernita Bridge"
    assert get_station("nonsense") is None


def test_stations_by_region_groups_correctly():
    grouped = stations_by_region()
    assert set(grouped.keys()) == REGIONS
    assert all(s["region"] == "hanford" for s in grouped["hanford"])


def test_primary_stations_excludes_subspots():
    assert all(s["parent_key"] is None for s in primary_stations())
