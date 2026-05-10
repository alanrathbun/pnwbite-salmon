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
        species=["chinook", "steelhead"],
        reach_type="reservoir-side",
        regs_section="WDFW_DRANO", regs_authority="WDFW",
        creel_district="wdfw_drano",
        pamphlet_section="drano_lake",
    ),
    _s(
        key="wind_mouth", name="Wind River Mouth (Home Valley)", region="mid_col",
        lat=45.7236, lon=-121.7937,
        ref_dams=["BON"], usgs_site="14128870",
        species=["chinook", "steelhead"],
        reach_type="reservoir-trib",
        regs_section="WDFW_WIND", regs_authority="WDFW",
        creel_district="wdfw_wind",
        pamphlet_section="wind_river_mouth_to_hwy14",
    ),
    _s(
        key="klickitat_mouth", name="Klickitat Mouth (Lyle)", region="mid_col",
        lat=45.6969, lon=-121.2902,
        ref_dams=["TDA"], usgs_site="14113000",
        species=["chinook", "steelhead"],
        reach_type="reservoir-trib",
        regs_section="WDFW_KLICKITAT_MOUTH", regs_authority="WDFW",
        creel_district="wdfw_klickitat",
        pamphlet_section="klickitat_mouth_to_fisher_hill",
    ),
    _s(
        key="maryhill", name="Maryhill State Park", region="mid_col",
        lat=45.6711, lon=-120.8329,
        ref_dams=["TDA", "JDA"], usgs_site=None,
        species=["chinook", "steelhead"],
        reach_type="reservoir",
        regs_section="WDFW_MID_COL_POOL", regs_authority="WDFW",
        creel_district="wdfw_mid_columbia",
        pamphlet_section="dalles_dam_to_jda_pool",
    ),
    _s(
        key="umatilla_marina", name="Umatilla Marina", region="mid_col",
        lat=45.9223, lon=-119.3434,
        ref_dams=["JDA", "MCN"], usgs_site=None,
        species=["chinook"],
        reach_type="reservoir",
        pamphlet_section="mcnary_pool",
        regs_section="ODFW_MID_COL", regs_authority="ODFW",
        creel_district="odfw_mid_columbia",
    ),

    # ===== Hanford Reach (7 primary + 1 sub-spot) =====
    _s(
        key="priest_rapids_tail", name="Priest Rapids Tailrace", region="hanford",
        lat=46.6444, lon=-119.9097,
        ref_dams=["PRD"], usgs_site="12472800",
        species=["chinook", "sockeye", "steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="priest_rapids_to_wanapum",
    ),
    _s(
        key="vernita", name="Vernita Bridge", region="hanford",
        lat=46.6483, lon=-119.8833,
        ref_dams=["PRD", "MCN"], usgs_site="12472800",
        species=["chinook", "sockeye", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="hanford_powerline_to_vernita",  # Vernita is the upper boundary of this section
    ),
    _s(
        key="white_bluffs", name="White Bluffs Landing", region="hanford",
        lat=46.6711, lon=-119.4408,
        ref_dams=["PRD", "MCN"], usgs_site="12472800",
        species=["chinook", "sockeye"],
        reach_type="freeflowing",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="hanford_powerline_to_vernita",
    ),
    _s(
        key="wahluke", name="Wahluke (100F slough)", region="hanford",
        lat=46.6517, lon=-119.5436,
        ref_dams=["PRD", "MCN"], usgs_site="12472800",
        species=["chinook"],
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
        species=["chinook", "sockeye"],
        reach_type="freeflowing",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="hanford_ringold_wasteway_to_ringold_hatchery",
    ),
    _s(
        key="hanford_townsite", name="Hanford Town Site", region="hanford",
        lat=46.6225, lon=-119.5378,
        ref_dams=["PRD", "MCN"], usgs_site="12472800",
        species=["chinook"],
        reach_type="freeflowing",
        regs_section="WDFW_HANFORD_REACH", regs_authority="WDFW",
        creel_district="wdfw_hanford",
        pamphlet_section="hanford_ringold_hatchery_to_powerline",
    ),
    _s(
        key="mcnary_tail_pasco", name="McNary Tailrace / Pasco Boat Basin", region="hanford",
        lat=46.2247, lon=-119.0961,
        ref_dams=["MCN"], usgs_site="14019240",
        species=["chinook", "sockeye"],
        reach_type="tailrace",
        regs_section="WDFW_MCNARY_POOL", regs_authority="WDFW",
        creel_district="wdfw_mcnary",
        pamphlet_section="mcnary_tailrace",  # Closed Jan 1 - Jun 15 per pamphlet
    ),
    _s(
        key="sacajawea", name="Sacajawea State Park (Snake/Col confluence)", region="hanford",
        lat=46.2014, lon=-118.9961,
        ref_dams=["MCN", "IHR"], usgs_site="14019240",
        species=["chinook"],
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
        species=["chinook", "sockeye", "steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_UPPER_COL", regs_authority="WDFW",
        creel_district="wdfw_upper_columbia",
        pamphlet_section="rocky_reach_to_wells",
    ),
    _s(
        key="methow_mouth", name="Methow Mouth (Pateros)", region="upper_col",
        lat=48.0506, lon=-119.9111,
        ref_dams=["WEL"], usgs_site="12449950",
        species=["chinook", "steelhead"],
        reach_type="confluence",
        regs_section="WDFW_UPPER_COL", regs_authority="WDFW",
        creel_district="wdfw_upper_columbia",
        pamphlet_section="wells_to_brewster",
    ),
    _s(
        key="brewster", name="Brewster Flats", region="upper_col",
        lat=48.0975, lon=-119.7811,
        ref_dams=["WEL", "CHJ"], usgs_site=None,
        species=["sockeye", "chinook"],
        reach_type="reservoir",
        regs_section="WDFW_UPPER_COL", regs_authority="WDFW",
        creel_district="wdfw_upper_columbia",
        pamphlet_section="brewster_to_hwy17",
    ),
    _s(
        key="rocky_reach_tail", name="Rocky Reach Tailrace", region="upper_col",
        lat=47.5311, lon=-120.2939,
        ref_dams=["RRH"], usgs_site="12462500",
        species=["chinook", "sockeye", "steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_UPPER_COL", regs_authority="WDFW",
        creel_district="wdfw_upper_columbia",
        pamphlet_section="rock_island_to_rocky_reach",
    ),
    _s(
        key="wenatchee_mouth", name="Wenatchee Mouth", region="upper_col",
        lat=47.4623, lon=-120.3289,
        ref_dams=["RRH", "RIS"], usgs_site="12462500",
        species=["chinook", "sockeye", "steelhead"],
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
        species=["chinook", "steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_goose_island_to_ice_harbor",
    ),
    _s(
        key="lyons_ferry", name="Lyons Ferry (Snake/Palouse)", region="snake",
        lat=46.5917, lon=-118.2306,
        ref_dams=["LMN"], usgs_site="13353200",
        species=["chinook", "steelhead"],
        reach_type="reservoir",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_lower_monumental_to_little_goose",
    ),
    _s(
        key="boyer_park", name="Boyer Park (above Lower Granite)", region="snake",
        lat=46.6750, lon=-117.7361,
        ref_dams=["LGS", "LGR"], usgs_site="13334300",
        species=["chinook", "steelhead"],
        reach_type="reservoir",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_little_goose_to_lower_granite",
    ),
    _s(
        key="wawawai", name="Wawawai / Lower Granite Tailrace", region="snake",
        lat=46.6614, lon=-117.4194,
        ref_dams=["LGR"], usgs_site="13334300",
        species=["chinook", "steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_little_goose_to_lower_granite",
    ),
    _s(
        key="clarkston_greenbelt", name="Greenbelt (Clarkston)", region="snake",
        lat=46.4275, lon=-117.0244,
        ref_dams=["LGR"], usgs_site="13334300",
        species=["chinook", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_lower_granite_to_wa_id_clarkston",
    ),
    _s(
        key="lewiston_hellsgate", name="Hells Gate SP (Lewiston)", region="snake",
        lat=46.3811, lon=-117.0392,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["chinook", "steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_LOWER", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="clearwater_park", name="Clearwater Park (Lewiston)", region="snake",
        lat=46.4192, lon=-117.0389,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["chinook", "steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_LOWER", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="wild_goose", name="Wild Goose (mid-Clearwater)", region="snake",
        lat=46.4297, lon=-116.6928,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["chinook", "steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_MID", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="cherrylane", name="Cherrylane (Clearwater)", region="snake",
        lat=46.4631, lon=-116.7425,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["chinook", "steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_MID", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="lenore", name="Lenore Boat Ramp (Clearwater)", region="snake",
        lat=46.5267, lon=-116.5511,
        ref_dams=["LGR"], usgs_site="13342500",
        species=["chinook", "steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_CLEARWATER_MID", regs_authority="IDFG",
        creel_district="idfg_clearwater",
    ),
    _s(
        key="asotin", name="Asotin", region="snake",
        lat=46.3375, lon=-117.0489,
        ref_dams=["LGR"], usgs_site="13334300",
        species=["chinook", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_blue_bridge_to_or_id_border",
    ),
    _s(
        key="heller_bar", name="Heller Bar (mouth of Grande Ronde)", region="snake",
        lat=46.0938, lon=-116.9772,
        ref_dams=["LGR"], usgs_site="13334300",
        species=["chinook", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_blue_bridge_to_or_id_border",
    ),
    _s(
        key="salmon_mouth", name="Salmon River Mouth (Riggins area)", region="snake",
        lat=45.3833, lon=-116.3333,
        ref_dams=[], flow_source="usgs:13317000", usgs_site="13317000",
        species=["chinook", "steelhead"],
        reach_type="freeflowing",
        regs_section="IDFG_SALMON", regs_authority="IDFG",
        creel_district="idfg_salmon",
    ),

    # ===== Lower Columbia mainstem (WA side, Pacific to Bonneville Dam) =====
    # Geographic order: downstream (Buoy 10) -> upstream (Bonneville tailrace).
    # All launches below Bonneville use ref_dams=["BON"] because Bonneville
    # discharge dominates the dam-controlled flow signal at all of these
    # locations; tide_station is added for the four downstream-most launches
    # below the tide line at Wauna/Skamokawa.
    _s(
        key="ilwaco", name="Port of Ilwaco", region="lower_col",
        lat=46.3047, lon=-124.0383,
        ref_dams=["BON"], usgs_site=None,
        tide_station="9440083",  # Cape Disappointment NOAA station (Pacific tides)
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="confluence",  # mouth of Columbia / Baker Bay
        regs_section="WDFW_BUOY10", regs_authority="WDFW",
        creel_district="wdfw_buoy10",
        pamphlet_section="buoy10_to_megler_astoria",
    ),
    _s(
        key="chinook_port", name="Port of Chinook (Baker Bay)", region="lower_col",
        lat=46.2699, lon=-123.9460,
        ref_dams=["BON"], usgs_site=None,
        tide_station="9439040",  # Astoria
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="confluence",
        regs_section="WDFW_BUOY10", regs_authority="WDFW",
        creel_district="wdfw_buoy10",
        pamphlet_section="buoy10_to_megler_astoria",
    ),
    _s(
        key="skamokawa_vista", name="Skamokawa Vista Park", region="lower_col",
        lat=46.2693, lon=-123.4569,  # 5 Vista Park Rd, Skamokawa WA
        ref_dams=["BON"], usgs_site=None,
        tide_station="9439099",  # Skamokawa
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_TONGUE_PUGET", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="tongue_point_to_puget_island",
    ),
    _s(
        key="elochoman_marina", name="Elochoman Slough Marina (Cathlamet)", region="lower_col",
        lat=46.2050, lon=-123.3871,
        ref_dams=["BON"], usgs_site=None,
        tide_station="9439099",  # Skamokawa
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_TONGUE_PUGET", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="tongue_point_to_puget_island",
    ),
    _s(
        key="county_line_park", name="County Line Park (Cathlamet)", region="lower_col",
        lat=46.2024, lon=-123.2486,  # 2076 East SR 4, Cathlamet WA - approx from address
        ref_dams=["BON"], usgs_site=None,
        tide_station="9439099",
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_PUGET_LONGVIEW", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="puget_island_to_longview",
    ),
    _s(
        key="willow_grove", name="Willow Grove Park (Longview)", region="lower_col",
        lat=46.1700, lon=-123.0728,  # 7141 Willow Grove Rd, Longview WA - RM ~58
        ref_dams=["BON"], usgs_site=None,
        tide_station="9439201",  # Wauna
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_PUGET_LONGVIEW", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="puget_island_to_longview",
    ),
    _s(
        key="kalama_marina", name="Port of Kalama Marina", region="lower_col",
        lat=46.0083, lon=-122.8470,  # 110 W Marine Drive, Kalama WA - RM ~73
        # Kalama at RM 73 sits upstream of the Longview Bridge (RM ~66) so the
        # applicable Compact Zone is CRC 523 (longview_to_warrior_rock), not
        # CRC 521 (puget_island_to_longview).
        ref_dams=["BON"], usgs_site=None,
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_LONGVIEW_WARRIOR", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="longview_to_warrior_rock",
    ),
    _s(
        key="woodland_bar", name="Woodland Bar (Lewis River mouth)", region="lower_col",
        lat=45.9191, lon=-122.8026,
        # Woodland is at RM ~87, well upstream of the Longview Bridge.
        ref_dams=["BON"], usgs_site=None,
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="confluence",
        regs_section="WDFW_LOWER_COL_LONGVIEW_WARRIOR", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="longview_to_warrior_rock",
    ),
    _s(
        key="ridgefield", name="Ridgefield Boat Ramp (Lake River)", region="lower_col",
        lat=45.8160, lon=-122.7440,  # foot of S Mill St, Ridgefield WA
        ref_dams=["BON"], usgs_site=None,
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_LONGVIEW_WARRIOR", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="longview_to_warrior_rock",
    ),
    _s(
        key="frenchmans_bar", name="Frenchman's Bar Park (Vancouver)", region="lower_col",
        lat=45.6855, lon=-122.7614,  # 9612 NW Lower River Rd, Vancouver WA
        ref_dams=["BON"], usgs_site=None,
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_WARRIOR_I5", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="warrior_rock_to_i5",
    ),
    _s(
        key="port_camas_washougal", name="Port of Camas-Washougal Marina", region="lower_col",
        lat=45.5703, lon=-122.3837,  # 24 S A St, Washougal WA - RM ~122
        ref_dams=["BON"], usgs_site=None,
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_I5_BEACONROCK", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="i5_to_nav_marker_82",
    ),
    _s(
        key="captain_william_clark", name="Captain William Clark Park (Cottonwood Beach)",
        region="lower_col",
        lat=45.5680, lon=-122.3620,  # 32nd St, Washougal WA
        ref_dams=["BON"], usgs_site=None,
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_I5_BEACONROCK", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="i5_to_nav_marker_82",
    ),
    _s(
        key="beacon_rock", name="Beacon Rock State Park", region="lower_col",
        lat=45.6213, lon=-122.0232,
        ref_dams=["BON"], usgs_site=None,
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LOWER_COL_BEACON_HAMILTON", regs_authority="WDFW",
        creel_district="wdfw_lower_columbia",
        pamphlet_section="beacon_rock_to_hamilton_island",
    ),
    _s(
        key="hamilton_island", name="Hamilton Island Boat Ramp (Bonneville tailrace)",
        region="lower_col",
        lat=45.6444, lon=-121.9606,  # below Bonneville Dam, North Bonneville WA
        ref_dams=["BON"], usgs_site="14128870",  # Wind River near Carson (closest gauge)
        species=["chinook", "sockeye", "coho", "steelhead"],
        reach_type="tailrace",
        regs_section="WDFW_BONNEVILLE_TAILRACE", regs_authority="WDFW",
        creel_district="wdfw_bonneville_tailrace",
        pamphlet_section="hamilton_island_to_bradford_island_4000",
    ),

    # ===== Lower Columbia WA tributaries =====
    # Cowlitz River (downstream -> upstream): mouth -> Lexington -> Mill Creek
    # -> Barrier Dam. Two USGS gauges drive the lower (Castle Rock, 14243000)
    # and upper (below Mayfield, 14238000) reaches.
    _s(
        key="gerhart_gardens", name="Gerhart Gardens (Cowlitz mouth area, Longview)",
        region="lower_col",
        lat=46.1531, lon=-122.9078,  # off Pacific Way / Westside Hwy, Longview WA
        ref_dams=[], flow_source="usgs:14243000", usgs_site="14243000",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_COWLITZ_LOWER", regs_authority="WDFW",
        creel_district="wdfw_cowlitz",
        pamphlet_section="cowlitz_mouth_to_lexington",
    ),
    _s(
        key="olequa_crossing", name="Olequa Crossing (Cowlitz, Vader)", region="lower_col",
        lat=46.3678, lon=-122.9342,
        ref_dams=[], flow_source="usgs:14243000", usgs_site="14243000",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_COWLITZ_LEXINGTON_MILL", regs_authority="WDFW",
        creel_district="wdfw_cowlitz",
        pamphlet_section="cowlitz_lexington_to_mill_creek",
    ),
    _s(
        key="cowlitz_i5_launch", name="Cowlitz I-5 Bridge Launch", region="lower_col",
        lat=46.4134, lon=-122.8909,  # WDFW I-5 access site, Lewis Co.
        ref_dams=[], flow_source="usgs:14243000", usgs_site="14243000",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_COWLITZ_LEXINGTON_MILL", regs_authority="WDFW",
        creel_district="wdfw_cowlitz",
        pamphlet_section="cowlitz_lexington_to_mill_creek",
    ),
    _s(
        key="toledo_cowlitz", name="Toledo (Cowlitz)", region="lower_col",
        lat=46.4345, lon=-122.8478,
        ref_dams=[], flow_source="usgs:14243000", usgs_site="14243000",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_COWLITZ_LEXINGTON_MILL", regs_authority="WDFW",
        creel_district="wdfw_cowlitz",
        pamphlet_section="cowlitz_lexington_to_mill_creek",
    ),
    _s(
        key="massey_bar", name="Massey Bar (Cowlitz)", region="lower_col",
        lat=46.4588, lon=-122.8076,
        ref_dams=[], flow_source="usgs:14243000", usgs_site="14243000",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_COWLITZ_LEXINGTON_MILL", regs_authority="WDFW",
        creel_district="wdfw_cowlitz",
        pamphlet_section="cowlitz_lexington_to_mill_creek",
    ),
    _s(
        key="blue_creek_cowlitz", name="Blue Creek (Cowlitz)", region="lower_col",
        lat=46.4839, lon=-122.7311,
        ref_dams=[], flow_source="usgs:14238000", usgs_site="14238000",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_COWLITZ_MILL_BARRIER", regs_authority="WDFW",
        creel_district="wdfw_cowlitz",
        pamphlet_section="cowlitz_mill_creek_to_barrier_dam",
    ),
    _s(
        key="barrier_dam", name="Barrier Dam (Cowlitz, Salkum)", region="lower_col",
        lat=46.5159, lon=-122.6374,
        ref_dams=[], flow_source="usgs:14238000", usgs_site="14238000",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_COWLITZ_MILL_BARRIER", regs_authority="WDFW",
        creel_district="wdfw_cowlitz",
        pamphlet_section="cowlitz_mill_creek_to_barrier_dam",
    ),

    # Toutle River — major Cowlitz tributary devastated by Mt. St. Helens.
    # Mouth-to-forks reach uses Tower Road USGS gauge (14242580).
    _s(
        key="toutle_mouth", name="Mouth of Toutle (Castle Rock)", region="lower_col",
        lat=46.3098, lon=-122.9169,
        ref_dams=[], flow_source="usgs:14242580", usgs_site="14242580",
        species=["chinook", "coho", "steelhead"],
        reach_type="confluence",
        regs_section="WDFW_TOUTLE", regs_authority="WDFW",
        creel_district="wdfw_toutle",
        pamphlet_section="toutle_river_mouth_to_forks",
    ),
    _s(
        key="tower_bridge_toutle", name="Tower Bridge (Toutle)", region="lower_col",
        lat=46.3338, lon=-122.8408,
        ref_dams=[], flow_source="usgs:14242580", usgs_site="14242580",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_TOUTLE", regs_authority="WDFW",
        creel_district="wdfw_toutle",
        pamphlet_section="toutle_river_mouth_to_forks",
    ),

    # Kalama River — strong Spring/Fall Chinook + steelhead + coho fishery.
    _s(
        key="kalama_river_modrow", name="Modrow Bridge (Kalama)", region="lower_col",
        lat=46.0475, lon=-122.8367,
        ref_dams=[], flow_source="usgs:14223000", usgs_site="14223000",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_KALAMA_LOWER", regs_authority="WDFW",
        creel_district="wdfw_kalama",
        pamphlet_section="kalama_mouth_to_modrow",
    ),

    # Lewis River — strong Spring Chinook + Fall Chinook + coho fishery.
    _s(
        key="eagle_island_lewis", name="Island Boat Ramp (Lewis River, near Eagle Island)",
        region="lower_col",
        lat=45.8773, lon=-122.6720,  # ~5 mi east of Woodland on Lewis River Rd
        ref_dams=[], flow_source="usgs:14220500", usgs_site="14220500",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_LEWIS_EF_JOHNSON", regs_authority="WDFW",
        creel_district="wdfw_lewis",
        pamphlet_section="lewis_river_ef_to_johnson",
    ),

    # Washougal River — small Spring/Fall Chinook + coho + steelhead trib.
    _s(
        key="washougal_county_line", name="WDFW County Line Access (Washougal)",
        region="lower_col",
        lat=45.5917, lon=-122.2853,  # County Line Access, lower Washougal
        ref_dams=[], flow_source="usgs:14144100", usgs_site="14144100",
        species=["chinook", "coho", "steelhead"],
        reach_type="freeflowing",
        regs_section="WDFW_WASHOUGAL_LOWER", regs_authority="WDFW",
        creel_district="wdfw_washougal",
        pamphlet_section="washougal_mouth_to_county_line",
    ),

    # ===== Yakima system =====
    # Yakima River (mouth at Richland) — Salmon retention only Sept-Oct/Nov
    # in lower five reaches per pamphlet. Uses below-Horn-Rapids gauge for
    # the lowest reach and Kiona gauge for the upper retention reaches.
    _s(
        key="horn_rapids_park", name="Horn Rapids County Park (Yakima)", region="mid_col",
        lat=46.3799, lon=-119.4178,
        ref_dams=[], flow_source="usgs:12511520", usgs_site="12511520",
        species=["chinook", "coho"],
        reach_type="freeflowing",
        regs_section="WDFW_YAKIMA_LOWER", regs_authority="WDFW",
        creel_district="wdfw_yakima",
        pamphlet_section="yakima_lower_mouth_to_horn_rapids",
    ),
    _s(
        key="prosser_riverfront", name="Riverfront Park (Prosser, Yakima)", region="mid_col",
        lat=46.2042, lon=-119.7767,
        ref_dams=[], flow_source="usgs:12510500", usgs_site="12510500",
        species=["chinook", "coho"],
        reach_type="freeflowing",
        regs_section="WDFW_YAKIMA_PROSSER", regs_authority="WDFW",
        creel_district="wdfw_yakima",
        pamphlet_section="yakima_i82_to_grant_ave_prosser",
    ),

    # ===== Snake WA tributaries =====
    _s(
        key="texas_rapids", name="Texas Rapids (Snake near Tucannon mouth)",
        region="snake",
        lat=46.5631, lon=-118.0997,  # USACE site upstream of Tucannon mouth
        ref_dams=["LMN"], usgs_site="13344500",
        species=["chinook", "steelhead"],
        reach_type="reservoir",  # in Lower Monumental pool
        regs_section="WDFW_LOWER_SNAKE", regs_authority="WDFW",
        creel_district="wdfw_snake",
        pamphlet_section="snake_lower_monumental_to_little_goose",
    ),

    # ===== Walla Walla =====
    # Madame Dorion Memorial Park sits at the WW/Columbia confluence — primary
    # public access for the WW mouth (which is in McNary Pool / Lake Wallula).
    _s(
        key="madame_dorion", name="Madame Dorion Park (Walla Walla mouth, Wallula)",
        region="mid_col",
        lat=46.0622, lon=-118.9033,
        ref_dams=["MCN"], usgs_site="14018500",  # WW near Touchet
        species=["chinook", "steelhead"],
        reach_type="confluence",
        regs_section="WDFW_WALLA_WALLA_MOUTH", regs_authority="WDFW",
        creel_district="wdfw_walla_walla",
        pamphlet_section="mcnary_pool",  # WW mouth waters in McNary Pool
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
