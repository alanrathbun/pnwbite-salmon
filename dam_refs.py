"""FPC dam reference data: section names + column indices for the daily files.

The FPC publishes flow at fpc.org/currentdaily/flowspil.txt and adult counts at
fpc.org/adults/adult_count.htm. Each dam has a fixed section header and column
ordering; the species_count_cols dict maps our species keys to the column index
in the adult_count rows for that dam.

Column indices below are placeholders to verify against current FPC pages during
implementation of the FPC scrapers (see Tasks 5 and 6) — they may shift if FPC
reorders. The scraper tests use captured fixtures to lock indices.
"""
from __future__ import annotations
from typing import Any


FPC_DAMS: dict[str, dict[str, Any]] = {
    "BON": {
        "name": "Bonneville",
        "river_mile": 146.1,
        "fpc_section": "BON",
        "flow_col": 1,
        "species_count_cols": {
            "spring_chinook": "Chin",
            "summer_chinook": "Chin",
            "fall_chinook": "Chin",
            "sockeye": "Sock",
            "coho": "Coho",
            "summer_steelhead": "Stlhd",
            "winter_steelhead": "Stlhd",
        },
    },
    "MCN": {
        "name": "McNary",
        "river_mile": 292.0,
        "fpc_section": "MCN",
        "flow_col": 1,
        "species_count_cols": {
            "spring_chinook": "Chin",
            "summer_chinook": "Chin",
            "fall_chinook": "Chin",
            "sockeye": "Sock",
            "coho": "Coho",
            "summer_steelhead": "Stlhd",
            "winter_steelhead": "Stlhd",
        },
    },
    "PRD": {
        "name": "Priest Rapids",
        "river_mile": 397.1,
        "fpc_section": "PRD",
        "flow_col": 1,
        "species_count_cols": {
            "summer_chinook": "Chin",
            "fall_chinook": "Chin",
            "sockeye": "Sock",
            "summer_steelhead": "Stlhd",
        },
    },
    "WEL": {
        "name": "Wells",
        "river_mile": 515.6,
        "fpc_section": "WEL",
        "flow_col": 1,
        "species_count_cols": {
            "summer_chinook": "Chin",
            "sockeye": "Sock",
            "summer_steelhead": "Stlhd",
        },
    },
    "RRH": {
        "name": "Rocky Reach",
        "river_mile": 473.7,
        "fpc_section": "RRH",
        "flow_col": 1,
        "species_count_cols": {
            "summer_chinook": "Chin",
            "sockeye": "Sock",
            "summer_steelhead": "Stlhd",
        },
    },
    "RIS": {
        "name": "Rock Island",
        "river_mile": 453.4,
        "fpc_section": "RIS",
        "flow_col": 1,
        "species_count_cols": {
            "summer_chinook": "Chin",
            "sockeye": "Sock",
            "summer_steelhead": "Stlhd",
        },
    },
    "LGR": {
        "name": "Lower Granite",
        "river_mile": 522.2,
        "fpc_section": "LGR",
        "flow_col": 1,
        "species_count_cols": {
            "spring_chinook": "Chin",
            "fall_chinook": "Chin",
            "summer_steelhead": "Stlhd",
        },
    },
}


def get_dam(key: str) -> dict[str, Any] | None:
    return FPC_DAMS.get(key)


def all_dam_keys() -> list[str]:
    return list(FPC_DAMS.keys())
