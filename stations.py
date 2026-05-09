"""All boat launches, sub-spots, and per-launch metadata.

Coordinates are starter values from public sources; verify against satellite imagery
during launch testing. ref_dams empty + flow_source set means the launch isn't on a
dam-controlled reach (currently only salmon_mouth).
"""
from __future__ import annotations
from typing import Any


def _s(**kw) -> dict[str, Any]:
    """Build a station dict with sensible defaults; raises if required fields missing."""
    defaults = {
        "ref_dams": [],
        "flow_source": None,
        "usgs_site": None,
        "tide_station": None,
        "parent_key": None,
        "wdfw_url": None,
        "hero_photo": None,
        "pamphlet_section": None,  # slug into wdfw_pamphlet.yaml; if set, overrides regs_section for seasonal closures
    }
    return {**defaults, **kw}


STATIONS: list[dict[str, Any]] = [
    # ===== Mid-Columbia (5) =====
    _s(
        key="drano", name="Drano Lake", region="mid_col",
        lat=45.7299, lon=-121.6589,
        ref_dams=["BON"], usgs_site="14123500",
        species=["spring_chinook", "summer_chinook", "summer_steelhead"],
        reach_type="reservoir-side",
        regs_section="WDFW_DRANO", regs_authority="WDFW",
        creel_district="wdfw_drano",
        pamphlet_section="drano_lake",
    ),
    _s(
        key="wind_mouth", name="Wind River Mouth (Home Valley)", region="mid_col",
        lat=45.7236, lon=-121.7937,
        ref_dams=["BON"], usgs_site="14128870",
        species=["spring_chinook", "summer_chinook", "summer_steelhead"],
        reach_type="reservoir-trib",
        regs_section="WDFW_WIND", regs_authority="WDFW",
        creel_district="wdfw_wind",
        pamphlet_section="wind_river_mouth_to_hwy14",
    ),
    _s(
        key="klickitat_mouth", name="Klickitat Mouth (Lyle)", region="mid_col",
        lat=45.6969, lon=-121.2902,
        ref_dams=["TDA"], usgs_site="14113000",
        species=["spring_chinook", "fall_chinook", "summer_steelhead", "winter_steelhead"],
        reach_type="reservoir-trib",
        regs_section="WDFW_KLICKITAT_MOUTH", regs_authority="WDFW",
        creel_district="wdfw_klickitat",
        pamphlet_section="klickitat_mouth_to_fisher_hill",
    ),
    _s(
        key="maryhill", name="Maryhill State Park", region="mid_col",
        lat=45.6711, lon=-120.8329,
        ref_dams=["TDA", "JDA"], usgs_site=None,
        species=["fall_chinook", "summer_chinook", "summer_steelhead"],
        reach_type="reservoir",
        regs_section="WDFW_MID_COL_POOL", regs_authority="WDFW",
        creel_district="wdfw_mid_columbia",
        pamphlet_section="dalles_dam_to_jda_pool",
    ),
    _s(
        key="umatilla_marina", name="Umatilla Marina", region="mid_col",
        lat=45.9223, lon=-119.3434,
        ref_dams=["JDA", "MCN"], usgs_site=None,
        species=["fall_chinook", "summer_chinook"],
        reach_type="reservoir",
        regs_section="ODFW_MID_COL", regs_authority="ODFW",
        creel_district="odfw_mid_columbia",
    ),

    # ===== Hanford Reach (7 primary + 1 sub-spot) =====
    _s(
        key="priest_rapids_tail", name="Priest Rapids Tailrace", region="hanford",
        lat=46.6444, lon=-119.9097,
        ref_dams=["PRD"], usgs_site="12472800",
        species=["fall_chinook", "summer_chinook", "sockeye", "summer_steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="priest_rapids_to_wanapum",
    ),
    _s(
        key="vernita", name="Vernita Bridge", region="hanford",
        lat=46.6483, lon=-119.8833,
        ref_dams=["PRD", "MCN"], usgs_site="12472800",
        species=["fall_chinook", "summer_chinook", "sockeye", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="hanford_powerline_to_vernita",  # Vernita is the upper boundary of this section
    ),
    _s(
        key="white_bluffs", name="White Bluffs Landing", region="hanford",
        lat=46.6711, lon=-119.4408,
        ref_dams=["PRD", "MCN"], usgs_site="12472800",
        species=["fall_chinook", "summer_chinook", "sockeye"],
        reach_type="freeflowing",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="hanford_powerline_to_vernita",
    ),
    _s(
        key="wahluke", name="Wahluke (100F slough)", region="hanford",
        lat=46.6517, lon=-119.5436,
        ref_dams=["PRD", "MCN"], usgs_site="12472800",
        species=["fall_chinook", "summer_chinook"],
        reach_type="freeflowing",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        parent_key="white_bluffs",  # SUB-SPOT
        pamphlet_section="hanford_powerline_to_vernita",
    ),
    _s(
        key="ringold", name="Ringold Springs", region="hanford",
        lat=46.4951, lon=-119.1773,
        ref_dams=["PRD", "MCN"], usgs_site="12472800",
        species=["fall_chinook", "summer_chinook", "sockeye"],
        reach_type="freeflowing",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="hanford_ringold_wasteway_to_ringold_hatchery",
    ),
    _s(
        key="hanford_townsite", name="Hanford Town Site", region="hanford",
        lat=46.6225, lon=-119.5378,
        ref_dams=["PRD", "MCN"], usgs_site="12472800",
        species=["fall_chinook", "summer_chinook"],
        reach_type="freeflowing",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="hanford_ringold_hatchery_to_powerline",
    ),
    _s(
        key="mcnary_tail_pasco", name="McNary Tailrace / Pasco Boat Basin", region="hanford",
        lat=46.2247, lon=-119.0961,
        ref_dams=["MCN"], usgs_site="14019240",
        species=["fall_chinook", "summer_chinook", "sockeye"],
        reach_type="tailrace",
        regs_section="WDFW_MCNARY_POOL", regs_authority="WDFW",
        creel_district="wdfw_mcnary",
        pamphlet_section="mcnary_tailrace",  # Closed Jan 1 - Jun 15 per pamphlet
    ),
    _s(
        key="sacajawea", name="Sacajawea State Park (Snake/Col confluence)", region="hanford",
        lat=46.2014, lon=-118.9961,
        ref_dams=["MCN", "IHR"], usgs_site="14019240",
        species=["fall_chinook", "summer_chinook"],
        reach_type="confluence",
        regs_section="WDFW_MCNARY_POOL", regs_authority="WDFW",
        creel_district="wdfw_mcnary",
        pamphlet_section="mcnary_tailrace",  # Snake/Col confluence is below McNary Dam
    ),

    # ===== Upper Columbia (5) =====
    _s(
        key="wells_tail", name="Wells Dam Tailrace (Pateros)", region="upper_col",
        lat=47.9486, lon=-119.8650,
        ref_dams=["WEL"], usgs_site="12449950",
        species=["summer_chinook", "sockeye", "summer_steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_UPPER_COL", regs_authority="WDFW",
        creel_district="wdfw_upper_columbia",
        pamphlet_section="rocky_reach_to_wells",
    ),
    _s(
        key="methow_mouth", name="Methow Mouth (Pateros)", region="upper_col",
        lat=48.0506, lon=-119.9111,
        ref_dams=["WEL"], usgs_site="12449950",
        species=["summer_chinook", "summer_steelhead"],
        reach_type="confluence",
        regs_section="WDFW_UPPER_COL", regs_authority="WDFW",
        creel_district="wdfw_upper_columbia",
        pamphlet_section="wells_to_brewster",
    ),
    _s(
        key="brewster", name="Brewster Flats", region="upper_col",
        lat=48.0975, lon=-119.7811,
        ref_dams=["WEL", "CHJ"], usgs_site=None,
        species=["sockeye", "summer_chinook"],
        reach_type="reservoir",
        regs_section="WDFW_UPPER_COL", regs_authority="WDFW",
        creel_district="wdfw_upper_columbia",
        pamphlet_section="brewster_to_hwy17",
    ),
    _s(
        key="rocky_reach_tail", name="Rocky Reach Tailrace", region="upper_col",
        lat=47.5311, lon=-120.2939,
        ref_dams=["RRH"], usgs_site="12462500",
        species=["summer_chinook", "sockeye", "summer_steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_UPPER_COL", regs_authority="WDFW",
        creel_district="wdfw_upper_columbia",
        pamphlet_section="rock_island_to_rocky_reach",
    ),
    _s(
        key="wenatchee_mouth", name="Wenatchee Mouth", region="upper_col",
        lat=47.4623, lon=-120.3289,
        ref_dams=["RRH", "RIS"], usgs_site="12462500",
        species=["summer_chinook", "sockeye", "summer_steelhead"],
        reach_type="confluence",
        regs_section="WDFW_UPPER_COL", regs_authority="WDFW",
        creel_district="wdfw_upper_columbia",
        pamphlet_section="rock_island_to_rocky_reach",
    ),

    # ===== Snake / Clearwater (13) =====
    _s(
        key="ice_harbor_tail", name="Ice Harbor Tailrace", region="snake",
        lat=46.2542, lon=-118.8800,
        ref_dams=["IHR"], usgs_site="13353200",
        species=["fall_chinook", "spring_chinook", "summer_steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_goose_island_to_ice_harbor",
    ),
    _s(
        key="lyons_ferry", name="Lyons Ferry (Snake/Palouse)", region="snake",
        lat=46.5917, lon=-118.2306,
        ref_dams=["LMN"], usgs_site="13353200",
        species=["fall_chinook", "spring_chinook", "summer_steelhead"],
        reach_type="reservoir",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_lower_monumental_to_little_goose",
    ),
    _s(
        key="boyer_park", name="Boyer Park (above Lower Granite)", region="snake",
        lat=46.6750, lon=-117.7361,
        ref_dams=["LGS", "LGR"], usgs_site="13334300",
        species=["fall_chinook", "spring_chinook", "summer_steelhead"],
        reach_type="reservoir",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_little_goose_to_lower_granite",
    ),
    _s(
        key="wawawai", name="Wawawai / Lower Granite Tailrace", region="snake",
        lat=46.6614, lon=-117.4194,
        ref_dams=["LGR"], usgs_site="13334300",
        species=["fall_chinook", "spring_chinook", "summer_steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_little_goose_to_lower_granite",
    ),
    _s(
        key="clarkston_greenbelt", name="Greenbelt (Clarkston)", region="snake",
        lat=46.4275, lon=-117.0244,
        ref_dams=["LGR"], usgs_site="13334300",
        species=["fall_chinook", "spring_chinook", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_lower_granite_to_wa_id_clarkston",
    ),
    _s(
        key="lewiston_hellsgate", name="Hells Gate SP (Lewiston)", region="snake",
        lat=46.3811, lon=-117.0392,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["fall_chinook", "spring_chinook", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_LOWER", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="clearwater_park", name="Clearwater Park (Lewiston)", region="snake",
        lat=46.4192, lon=-117.0389,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["spring_chinook", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_LOWER", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="wild_goose", name="Wild Goose (mid-Clearwater)", region="snake",
        lat=46.4297, lon=-116.6928,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["spring_chinook", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_MID", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="cherrylane", name="Cherrylane (Clearwater)", region="snake",
        lat=46.4631, lon=-116.7425,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["spring_chinook", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_MID", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="lenore", name="Lenore Boat Ramp (Clearwater)", region="snake",
        lat=46.5267, lon=-116.5511,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["spring_chinook", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_MID", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="asotin", name="Asotin", region="snake",
        lat=46.3375, lon=-117.0489,
        ref_dams=["LGR"], usgs_site="13334300",
        species=["fall_chinook", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_blue_bridge_to_or_id_border",
    ),
    _s(
        key="heller_bar", name="Heller Bar (mouth of Grande Ronde)", region="snake",
        lat=46.0938, lon=-116.9772,
        ref_dams=["LGR"], usgs_site="13334300",
        species=["fall_chinook", "spring_chinook", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_blue_bridge_to_or_id_border",
    ),
    _s(
        key="salmon_mouth", name="Salmon River Mouth (Riggins area)", region="snake",
        lat=45.3833, lon=-116.3333,
        ref_dams=[], flow_source="usgs:13317000", usgs_site="13317000",
        species=["spring_chinook", "summer_steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_SALMON", regs_authority="IDFG",
        creel_district="idfg_salmon",
    ),
]


def get_station(key: str) -> dict[str, Any] | None:
    return next((s for s in STATIONS if s["key"] == key), None)


def primary_stations() -> list[dict[str, Any]]:
    return [s for s in STATIONS if s["parent_key"] is None]


def stations_by_region() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for s in STATIONS:
        if s["parent_key"] is not None:
            continue  # exclude sub-spots from region grouping
        out.setdefault(s["region"], []).append(s)
    return out
