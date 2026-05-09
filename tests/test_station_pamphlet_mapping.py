"""Verify every WA-side launch maps to an encoded pamphlet section."""
from regs.wdfw_pamphlet import load_pamphlet
from stations import STATIONS


WA_SIDE_KEYS = {
    "drano", "wind_mouth", "klickitat_mouth", "maryhill",
    "priest_rapids_tail", "vernita", "white_bluffs", "wahluke", "ringold",
    "hanford_townsite", "mcnary_tail_pasco", "sacajawea",
    "wells_tail", "methow_mouth", "brewster", "rocky_reach_tail", "wenatchee_mouth",
    "ice_harbor_tail", "lyons_ferry", "boyer_park", "wawawai",
    "clarkston_greenbelt", "asotin", "heller_bar",
}


def test_every_wa_launch_has_pamphlet_section():
    encoded = {s["id"] for s in load_pamphlet()}
    missing = []
    for st in STATIONS:
        if st["key"] not in WA_SIDE_KEYS:
            continue
        if not st.get("pamphlet_section"):
            missing.append(st["key"])
            continue
        if st["pamphlet_section"] not in encoded:
            missing.append(f"{st['key']}->{st['pamphlet_section']} (not in YAML)")
    assert not missing, f"WA-side launches without valid pamphlet_section: {missing}"
