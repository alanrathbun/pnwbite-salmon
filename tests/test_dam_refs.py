from dam_refs import FPC_DAMS, get_dam, all_dam_keys

EXPECTED_DAMS = {
    "BON", "TDA", "JDA", "MCN",
    "IHR", "LMN",
    "PRD", "WEL", "RRH", "RIS", "LGR",
}
SPECIES_KEYS = {
    "spring_chinook", "summer_chinook", "sockeye", "fall_chinook",
    "coho", "summer_steelhead", "winter_steelhead",
}


def test_all_expected_dams_present():
    assert set(FPC_DAMS.keys()) == EXPECTED_DAMS


def test_each_dam_has_required_fields():
    required = {"name", "river_mile", "fpc_section", "flow_col", "species_count_cols"}
    for key, d in FPC_DAMS.items():
        assert required <= set(d.keys()), f"{key} missing: {required - set(d.keys())}"


def test_species_count_cols_keyed_by_known_species():
    for key, d in FPC_DAMS.items():
        for sp in d["species_count_cols"]:
            assert sp in SPECIES_KEYS, f"{key}: unknown species column {sp}"


def test_get_dam_returns_match_or_none():
    assert get_dam("BON")["name"] == "Bonneville"
    assert get_dam("TDA")["name"] == "The Dalles"
    assert get_dam("JDA")["name"] == "John Day"
    assert get_dam("IHR")["name"] == "Ice Harbor"
    assert get_dam("LMN")["name"] == "Lower Monumental"
    assert get_dam("FAKE") is None


def test_all_dam_keys_returns_all_expected():
    assert sorted(all_dam_keys()) == sorted(EXPECTED_DAMS)
