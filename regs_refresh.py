"""Midday regs-refresh job.

Re-runs the regs aggregator and patches the cached report_data:
  - regs section in report_data updated
  - any forecast under a now-closed regs_section gets score=0
  - top_picks filtered to drop newly-closed launches
  - report.html re-rendered

Does NOT re-fetch FPC, USGS, NWS, DART, or creel — those run at 05:35.
"""
from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from regs import fetch_all as regs_fetch_all
from storage import FileStorage

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
PROJECT_ROOT = Path(__file__).parent

log = logging.getLogger("regs_refresh")


def refresh_regs_in_data(data: dict, new_regs) -> dict:
    out = deepcopy(data)
    # Update regs section
    serialized = {}
    for k, st in new_regs.items():
        serialized[k] = {
            "open": st.open, "reason": st.reason, "authority": st.authority,
            "last_checked": st.last_checked.isoformat(),
        }
    out["regs"] = {**out.get("regs", {}), **serialized}

    # Build a per-launch closed lookup
    launches_by_key = {l["key"]: l for l in out["launches"]}
    closed_sections = {k for k, v in out["regs"].items() if not v["open"]}

    # Zero out scores in forecasts for closed launches
    for forecast_key, days in out.get("forecasts", {}).items():
        species, launch_key = forecast_key.split("::", 1)
        launch = launches_by_key.get(launch_key)
        if launch and launch["regs_section"] in closed_sections:
            for d in days:
                d["score"] = 0.0
                d["verdict"] = "POOR"

    # Filter top_picks to remove closed launches
    for sp, picks in list(out.get("top_picks", {}).items()):
        kept = []
        for p in picks:
            launch = launches_by_key.get(p["launch"])
            if launch and launch["regs_section"] in closed_sections:
                continue
            kept.append(p)
        out["top_picks"][sp] = kept

    out["regs_refreshed_at"] = datetime.now(LOCAL_TZ).isoformat()
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    storage = FileStorage(root=PROJECT_ROOT)
    data = storage.read_json("report_data")
    if data is None:
        log.error("no report_data cached; skipping regs refresh")
        return
    log.info("regs refresh starting")
    new_regs = regs_fetch_all()
    updated = refresh_regs_in_data(data, new_regs)
    storage.write_json("report_data", updated)
    from render import render_html
    html = render_html(updated)
    storage.write("report_html", html)
    log.info("regs refresh complete; report.html re-rendered (%d bytes)", len(html))


if __name__ == "__main__":
    main()
