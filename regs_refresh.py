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
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from regs import fetch_all as regs_fetch_all, resolve_for_day as regs_resolve_for_day
from regs.emergency_types import Projection
from regs.wdfw import RegStatus
from storage import FileStorage, default_root

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
PROJECT_ROOT = Path(__file__).parent

log = logging.getLogger("regs_refresh")


def _normalize_emergency_projections(
    emergency_input: dict,
    today: date,
) -> dict[str, list[Projection]]:
    """Normalize emergency_input to dict[str, list[Projection]].

    Accepts both the new shape (dict[str, list[Projection]]) and the legacy
    shape (dict[str, RegStatus]) produced by old callers or test fixtures.
    Legacy RegStatus entries are wrapped as today-only Projections.
    """
    result: dict[str, list[Projection]] = {}
    for section_id, value in emergency_input.items():
        if isinstance(value, list):
            result[section_id] = value
        elif isinstance(value, RegStatus):
            # Legacy shape: wrap as always-active Projection
            result[section_id] = [Projection(
                section_id=section_id,
                status=("open" if value.open else "closed"),
                effective_from=None,
                effective_to=None,
                reason=value.reason,
                authority=value.authority,
            )]
    return result


def refresh_regs_in_data(
    data: dict,
    new_regs,
    agency_meta: dict | None = None,
    *,
    pamphlet_layer: dict[str, RegStatus] | None = None,
    emergency_layer: dict | None = None,
    today: date | None = None,
) -> dict:
    """Patch ``data`` with refreshed regs; preserves prior status for any
    agency whose scrape failed this round.

    Two call shapes are accepted:

    * Preferred: pass ``pamphlet_layer`` and ``emergency_layer``
      (the layered dicts returned by ``regs.fetch_all``). Per-launch open/closed
      decisions go through ``regs_resolve_for_day()``, so the emergency overlay
      can flip a pamphlet-closed section open (and vice versa).
    * Legacy: pass a single ``new_regs`` dict positionally — treated as the
      emergency layer with no pamphlet baseline. This keeps the old test
      contract working.

    ``agency_meta`` is the per-agency success map returned alongside the layers.
    """
    out = deepcopy(data)
    agency_meta = agency_meta or {}
    today = today or date.today()
    # Build the two layers from whichever shape we got.
    if pamphlet_layer is None and emergency_layer is None:
        # Legacy positional shape: new_regs is the only layer we have.
        pamphlet_layer = {}
        raw_emergency = dict(new_regs or {})
    else:
        pamphlet_layer = pamphlet_layer or {}
        raw_emergency = dict(emergency_layer or {})
    # Normalize emergency input to the new dict[str, list[Projection]] shape.
    emergency_projections = _normalize_emergency_projections(raw_emergency, today)

    # Identify which agencies failed this round; their existing entries in
    # the cached regs dict should *not* be wiped out by the dict-merge.
    failed_agencies = {a for a, m in agency_meta.items() if not m.get("ok")}

    # Serialize the pamphlet layer into the flat shape report_data uses.
    serialized: dict[str, dict] = {}
    for k, st in pamphlet_layer.items():
        serialized[k] = {
            "open": st.open, "reason": st.reason, "authority": st.authority,
            "last_checked": st.last_checked.isoformat(),
        }
    # Serialize emergency projections: for each section, use the resolution
    # for today so the merged dict stays consistent with per-launch decisions.
    for section_id, projections in emergency_projections.items():
        rs = regs_resolve_for_day(emergency_projections, section_id, today)
        if rs is not None:
            serialized[section_id] = {
                "open": rs.open, "reason": rs.reason, "authority": rs.authority,
                "last_checked": rs.last_checked.isoformat(),
            }

    # Merge rules:
    #   - Prior entry from a *failed* agency: keep as-is (don't lose closure).
    #   - Prior entry overwritten by a fresh status with same key: take fresh.
    #   - Prior entry from a *successful* agency without a fresh re-emit:
    #     keep prior (conservative — the scrape may simply not have re-listed
    #     an unchanged section).
    #   - Fresh status with no prior: insert.
    merged: dict[str, dict] = {}
    prior = out.get("regs", {})
    for k, v in prior.items():
        if v.get("authority") in failed_agencies:
            merged[k] = v
        elif k in serialized:
            merged[k] = serialized[k]
        else:
            merged[k] = v
    for k, v in serialized.items():
        merged.setdefault(k, v)
    out["regs"] = merged

    # Surface agency staleness so the renderer can display a banner.
    if agency_meta:
        out["regs_agency_meta"] = agency_meta

    # Build a per-launch closed lookup using resolve_for_day so the
    # emergency-projection precedence applies. Falls back to the legacy
    # regs_section when the launch has no pamphlet_section mapping.
    launches_by_key = {l["key"]: l for l in out["launches"]}

    def _launch_is_closed(launch: dict) -> bool:
        section = launch.get("pamphlet_section") or launch.get("regs_section")
        if not section:
            return False
        rs = regs_resolve_for_day(emergency_projections, section, today)
        if rs is not None:
            return not rs.open
        # No fresh layer entry for this section — fall back to the merged cache
        # so previously-known closures (e.g. from a failed-agency carryover)
        # still gate scores.
        cached = out["regs"].get(section)
        if cached is not None:
            return not cached.get("open", True)
        return False

    # Zero out scores in forecasts for closed launches
    for forecast_key, days in out.get("forecasts", {}).items():
        species, launch_key = forecast_key.split("::", 1)
        launch = launches_by_key.get(launch_key)
        if launch and _launch_is_closed(launch):
            for d in days:
                d["score"] = 0.0
                d["verdict"] = "POOR"

    # Filter top_picks to remove closed launches
    for sp, picks in list(out.get("top_picks", {}).items()):
        kept = []
        for p in picks:
            launch = launches_by_key.get(p["launch"])
            if launch and _launch_is_closed(launch):
                continue
            kept.append(p)
        out["top_picks"][sp] = kept

    out["regs_refreshed_at"] = datetime.now(LOCAL_TZ).isoformat()
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    storage = FileStorage(root=default_root())
    data = storage.read_json("report_data")
    if data is None:
        log.error("no report_data cached; skipping regs refresh")
        return
    log.info("regs refresh starting")
    today = datetime.now(LOCAL_TZ).date()
    pamphlet_layer, emergency_projections, agency_meta = regs_fetch_all(today=today)
    updated = refresh_regs_in_data(
        data,
        new_regs=None,
        agency_meta=agency_meta,
        pamphlet_layer=pamphlet_layer,
        emergency_layer=emergency_projections,
        today=today,
    )
    storage.write_json("report_data", updated)
    from render import render_html
    html = render_html(updated)
    storage.write("report_html", html)
    log.info("regs refresh complete; report.html re-rendered (%d bytes)", len(html))
    # Purge Cloudflare cache so the updated report is immediately visible at the edge.
    try:
        from cloudflare import purge_cache
        purge_cache()
    except Exception as e:
        log.warning("cache purge failed: %s", e)


if __name__ == "__main__":
    main()
