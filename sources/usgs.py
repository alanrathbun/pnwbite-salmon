"""USGS Instantaneous Values for flow (00060) and water temp (00010).

Parameter codes:
  - 00060: discharge, cfs
  - 00010: temperature, water, °C (we convert to °F)

Note: a site may *list* a parameter but return zero values when the sensor is
offline. We filter to only readings where len(values) > 0 (lesson from
pikeminnow's HANDOFF.md, item: USGS site 14019240 sensor offline).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from utils import fetch

URL_TEMPLATE = (
    "https://waterservices.usgs.gov/nwis/iv/"
    "?format=json&sites={sites}&parameterCd=00060,00010&period=P3D"
)


@dataclass(frozen=True)
class GaugeReading:
    site: str
    parameter: str  # "flow_cfs" or "water_temp_f"
    dt: datetime
    value: float


def parse_iv_response(doc: dict[str, Any]) -> list[GaugeReading]:
    out: list[GaugeReading] = []
    series = (doc.get("value") or {}).get("timeSeries") or []
    for ts in series:
        site_code = ts.get("sourceInfo", {}).get("siteCode", [{}])[0].get("value")
        if not site_code:
            continue
        var = ts.get("variable", {}).get("variableCode", [{}])[0].get("value")
        if var not in {"00060", "00010"}:
            continue
        param = "flow_cfs" if var == "00060" else "water_temp_f"

        for value_block in ts.get("values", []):
            for v in value_block.get("value", []):
                raw = v.get("value")
                dt_str = v.get("dateTime")
                if raw is None or dt_str is None:
                    continue
                try:
                    val = float(raw)
                except ValueError:
                    continue
                if val < -100:  # USGS uses -999999 as no-data sentinel
                    continue
                if param == "water_temp_f":
                    val = val * 9 / 5 + 32  # °C → °F
                    if val < 28 or val > 90:  # clamp implausible
                        continue
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                out.append(GaugeReading(site=site_code, parameter=param, dt=dt, value=val))
    return out


def get_latest(readings: list[GaugeReading], parameter: str) -> GaugeReading | None:
    matches = [r for r in readings if r.parameter == parameter]
    if not matches:
        return None
    return max(matches, key=lambda r: r.dt)


def fetch_for_site(site: str) -> list[GaugeReading]:
    import json
    raw = fetch(URL_TEMPLATE.format(sites=site))
    return parse_iv_response(json.loads(raw))
