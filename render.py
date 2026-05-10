"""HTML renderer.

Single big f-string approach (matches pikeminnow). Splits into helpers per
section: header, species tabs, top-picks card, launch detail card. JS at the
bottom handles tab switching and dropdown selection via URL hash + localStorage.
"""
from __future__ import annotations

import html
import os
from datetime import date as _date, timedelta as _timedelta
from pathlib import Path
from typing import Any

from regs.wdfw_pamphlet import pamphlet_expires, pamphlet_version

ALL_SPECIES = [
    "spring_chinook", "summer_chinook", "sockeye", "fall_chinook",
    "coho", "summer_steelhead", "winter_steelhead",
]
SPECIES_LABEL = {
    "spring_chinook": "Spring Chinook",
    "summer_chinook": "Summer Chinook",
    "sockeye": "Sockeye",
    "fall_chinook": "Fall Chinook",
    "coho": "Coho",
    "summer_steelhead": "Summer Steelhead",
    "winter_steelhead": "Winter Steelhead",
}
DAM_LABEL = {
    "BON": "Bonneville",
    "TDA": "The Dalles",
    "JDA": "John Day",
    "MCN": "McNary",
    "IHR": "Ice Harbor",
    "LMN": "Lower Monumental",
    "PRD": "Priest Rapids",
    "WEL": "Wells",
    "RRH": "Rocky Reach",
    "RIS": "Rock Island",
    "LGR": "Lower Granite",
}


def render_html(data: dict[str, Any]) -> str:
    launches = [l for l in data["launches"] if l["parent_key"] is None]

    head = _head()
    header_bar = _header_bar(data)
    expiration_banner = _pamphlet_expiration_banner()
    pamphlet_banner = _pamphlet_staleness_banner()
    staleness_banner = _agency_staleness_banner(data.get("regs_agency_meta") or {})
    species_summary = _all_species_summary(data)
    species_tabs_html = _species_tabs(data)
    top_picks_html = _all_top_picks_cards(data)
    launch_detail_html = _launch_detail_section(data, launches)
    planner_html = _planner_section(data)
    heatmap_html = _season_heatmap_section(data)
    payload = _payload_script(data)
    js = _js()
    planner_js = '<script src="/static/planner.js" defer></script>'

    return f"""<!doctype html>
<html lang="en">
{head}
<body>
{header_bar}
{expiration_banner}
{pamphlet_banner}
{staleness_banner}
{species_summary}
{species_tabs_html}
{top_picks_html}
{launch_detail_html}
{planner_html}
{heatmap_html}
{payload}
{js}
{planner_js}
</body>
</html>"""


def _agency_staleness_banner(agency_meta: dict) -> str:
    """Yellow warning banner shown when a regs scraper failed this run.

    A silent default-open during a WDFW outage produces dangerously
    permissive verdicts; surface it so the user knows to verify directly.
    """
    failures = [name for name, meta in agency_meta.items() if not meta.get("ok")]
    if not failures:
        return ""
    names = ", ".join(failures)
    return (
        f'<div class="banner-warn">'
        f'Regulations check failed for {html.escape(names)} '
        f'&mdash; verify directly with the agency before fishing.'
        f'</div>'
    )


def _pamphlet_stale_flag_value() -> str | None:
    """Return the Last-Modified value in /data/pamphlet-cache/STALE_PAMPHLET, or None if absent.

    The flag is written by regs/wdfw_pamphlet_refresh.py when WDFW publishes a
    pamphlet PDF whose Last-Modified header differs from the cached value.
    """
    root = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent)))
    flag = root / "pamphlet-cache" / "STALE_PAMPHLET"
    if not flag.exists():
        return None
    try:
        return flag.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _pamphlet_expired_message() -> str | None:
    """Return banner text if today is past pamphlet_expires, else None."""
    expires = pamphlet_expires()
    if expires is None:
        return None
    today = _date.today()
    if today <= expires:
        return None
    return (
        f"WDFW pamphlet ({pamphlet_version()}) expired on {expires.isoformat()} "
        f"and may no longer reflect current regulations. Please verify rules "
        f"at https://wdfw.wa.gov/fishing/regulations before fishing."
    )


def _pamphlet_expiration_banner() -> str:
    """Strong warning banner shown when today is past the pamphlet expiration
    date encoded in wdfw_pamphlet.yaml.

    Distinct from `_pamphlet_staleness_banner` (which fires when the WDFW PDF
    has been updated since the last admin review): this one fires purely on
    calendar date — no Resend/email path required. Both can coexist; this one
    sits visually on top.
    """
    msg = _pamphlet_expired_message()
    if not msg:
        return ""
    return (
        f'<div class="banner-warn"><strong>'
        f'{html.escape(msg)}'
        f'</strong></div>'
    )


def _pamphlet_staleness_banner() -> str:
    """Yellow warning banner shown when the WDFW pamphlet PDF has been updated
    since the last admin review (STALE_PAMPHLET flag file is present).

    Sits visually above the regs-agency staleness banner: pamphlet updates can
    silently invalidate seasonal rules baked into wdfw_pamphlet.yaml until an
    admin diffs the new PDF and clears the flag manually.
    """
    last_modified = _pamphlet_stale_flag_value()
    if not last_modified:
        return ""
    return (
        f'<div class="banner-warn">'
        f'&#9888;&#65039; Pamphlet may be out of date &mdash; WDFW PDF updated since last review '
        f'(Last-Modified: <strong>{html.escape(last_modified)}</strong>). '
        f'Some seasonal rules may be incorrect until reviewed.'
        f'</div>'
    )


def _head() -> str:
    return """<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Salmon &amp; Steelhead Report</title>
<meta property="og:title" content="Salmon &amp; Steelhead Report" />
<meta property="og:description" content="Daily fishing forecast for 30 launches in the upper Columbia and Snake systems." />
<meta property="og:url" content="https://salmon.pnwbite.com/" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary" />
<meta name="description" content="Daily salmon &amp; steelhead fishing forecast for 30 launches across the upper Columbia and Snake river systems. Run timing, regulations, bait recommendations." />
<style>
:root {
  --bg: #0d1117; --fg: #e6edf3; --muted: #8b949e;
  --card: #161b22; --border: #30363d;
  --good: #3fb950; --great: #2ea043; --fair: #d29922; --poor: #f85149;
  --dawn: #f0a04b; --dusk: #c46210; --night: #4a4e8f;
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--fg); font: 14px/1.4 system-ui, sans-serif; margin: 0; padding: 1rem; }
h1, h2, h3 { margin: 0.5em 0; }
.tabs { display: flex; flex-wrap: wrap; gap: 0.25rem; margin: 0.5rem 0; }
.tab { padding: 0.4rem 0.7rem; border: 1px solid var(--border); border-radius: 4px;
       background: var(--card); color: var(--fg); cursor: pointer; font-size: 0.9rem; }
.tab.active { background: var(--great); border-color: var(--great); }
.tab.dim { opacity: 0.45; }
.card { border: 1px solid var(--border); border-radius: 6px; padding: 0.75rem 1rem; margin: 0.75rem 0; background: var(--card); }
.day-strip { display: flex; gap: 0.25rem; overflow-x: auto; }
.day-cell { flex: 0 0 auto; min-width: 80px; padding: 0.5rem; border-radius: 4px; text-align: center; }
.day-cell.GREAT { background: var(--great); }
.day-cell.GOOD  { background: var(--good); }
.day-cell.FAIR  { background: var(--fair); color: #000; }
.day-cell.POOR  { background: var(--poor); color: #000; }
.day-cell.future-dim { background-image: repeating-linear-gradient(45deg, transparent, transparent 5px, rgba(255,255,255,0.05) 5px, rgba(255,255,255,0.05) 10px); }
.now-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; }
.now-strip > div { background: rgba(255,255,255,0.03); padding: 0.5rem; border-radius: 4px; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
th, td { padding: 0.3rem 0.5rem; text-align: left; border-bottom: 1px solid var(--border); }
.banner-closed { background: var(--poor); color: #000; padding: 0.5rem; border-radius: 4px; font-weight: bold; }
.banner-open { background: var(--good); color: #000; padding: 0.4rem; border-radius: 4px; }
.banner-warn { background: var(--fair); color: #000; padding: 0.5rem; border-radius: 4px; margin: 0.5rem 0; font-weight: bold; }
.muted { color: var(--muted); font-size: 0.85rem; }
[hidden] { display: none !important; }
@media (max-width: 600px) {
  .now-strip { grid-template-columns: 1fr; }
}
.heat-row { display: grid; grid-template-columns: 140px 1fr; align-items: center; gap: 0.5rem; margin: 0.25rem 0; }
.heat-label { font-size: 0.85rem; color: var(--muted); }
.heat-cells { display: flex; gap: 1px; }
.heat-cell { flex: 1 1 0; min-height: 14px; display: inline-block; }
.heat-cell.GREAT { background: var(--great); }
.heat-cell.GOOD { background: #58a6ff; } /* light blue: distinguishable from GREAT (dark green) */
.heat-cell.FAIR { background: var(--fair); }
.heat-cell.POOR { background: var(--poor); }
.heat-month-row { margin-bottom: 0.25rem; }
.heat-month-label { font-size: 0.7rem; color: var(--muted); text-align: center; min-height: 12px; line-height: 12px; border-left: 1px solid var(--border); padding-left: 2px; overflow: hidden; }
.heat-legend { font-size: 0.85rem; margin: 0.25rem 0 0.75rem; }
.heat-legend .heat-cell { width: 16px; min-height: 12px; vertical-align: middle; flex: none; display: inline-block; }
.picker { margin-top: 0.5rem; }
.score-help { margin-top: 0.5rem; }
.score-help summary { cursor: pointer; }
.planner-inputs label { margin-right: 1rem; }
</style>
</head>"""


def _header_bar(data: dict) -> str:
    today_iso = html.escape(data["today"])
    # max = today + 365 days (computed in Python, not JS, so it survives no-JS)
    from datetime import date as _d, timedelta as _td
    today_dt = _d.fromisoformat(data["today"])
    max_iso = (today_dt + _td(days=365)).isoformat()
    return f"""<header class="card">
  <h1>Salmon &amp; Steelhead Report</h1>
  <div class="muted">Forecast week starting <span id="picker-caption">{today_iso}</span> · generated {html.escape(data['generated_at'])}</div>
  <div class="picker">
    <label>View date: <input type="date" id="date-picker" min="{today_iso}" max="{html.escape(max_iso)}" value="{today_iso}"></label>
    <span class="muted" id="picker-note"></span>
  </div>
  <details class="score-help">
    <summary class="muted">What does the score mean?</summary>
    <div class="muted">
      Scores combine open/closed status, run-timing pace, weather conditions, and recent creel.
      <strong>0.9+ GREAT</strong> · <strong>0.7+ GOOD</strong> · <strong>0.5+ FAIR</strong> · <strong>below 0.5 POOR</strong>.
      Scores past day 7 use only run-timing pace and regulations (weather isn't predicted).
    </div>
  </details>
</header>"""


def _payload_script(data: dict) -> str:
    """Embed the full report data as a JSON script tag for the client."""
    import json
    # Avoid `</script>` injection in any string fields by escaping `<` in JSON.
    payload = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
    return f'<script id="report-payload" type="application/json">{payload}</script>'


def _all_species_summary(data: dict) -> str:
    lines = []
    for sp in ALL_SPECIES:
        front_dam = data["runtiming"].get(f"front_{sp}")
        # Use Bonneville pace as the headline if present
        bon_state = data["runtiming"].get(f"BON_{sp}")
        if not bon_state:
            continue
        pace = bon_state.get("pace_ratio")
        peak_est = bon_state.get("peak_date_estimated")
        front_label = DAM_LABEL.get(front_dam, "—") if front_dam else "—"
        peak_str = peak_est or "—"
        pace_str = f"{pace:.2f}×" if pace is not None else "—"
        lines.append(
            f'<div data-species-summary="{sp}" hidden>'
            f'{html.escape(SPECIES_LABEL[sp])} · '
            f'{pace_str} of 10-yr at Bonneville · Front of run at {html.escape(front_label)} · '
            f'Peak est. {html.escape(peak_str)}</div>'
        )
    return '<div class="card">' + "\n".join(lines) + '</div>'


def _species_tabs(data: dict) -> str:
    tabs = ['<div class="tabs">']
    tabs.append(f'<button class="tab active" data-tab="all">All</button>')
    for sp in ALL_SPECIES:
        # Tab dimmed if Bonneville pace ratio is below 0.4 (proxy for out-of-season)
        st = data["runtiming"].get(f"BON_{sp}")
        dim = "dim" if (st and (st.get("pace_ratio") or 0) < 0.4) else ""
        tabs.append(f'<button class="tab {dim}" data-tab="{sp}">{html.escape(SPECIES_LABEL[sp])}</button>')
    tabs.append("</div>")
    return "\n".join(tabs)


def _all_top_picks_cards(data: dict) -> str:
    cards = []
    for sp in ALL_SPECIES + ["all"]:
        if sp == "all":
            picks = []
            for s in ALL_SPECIES:
                p = (data["top_picks"].get(s) or [])[:1]
                for x in p:
                    picks.append({**x, "species": s})
            cards.append(_top_card("all", picks, data))
        else:
            picks = data["top_picks"].get(sp) or []
            cards.append(_top_card(sp, picks, data))
    return "\n".join(cards)


def _pick_date(data: dict, day_offset: int) -> str:
    """Convert a pick's day_offset to an ISO date relative to the run's today."""
    today_dt = _date.fromisoformat(data["today"])
    return (today_dt + _timedelta(days=day_offset)).isoformat()


def _top_card(sp_key: str, picks: list[dict], data: dict) -> str:
    title = "Top Picks (All Species)" if sp_key == "all" else f"Top 3 Picks — {SPECIES_LABEL.get(sp_key, sp_key)}"
    rows = []
    if not picks:
        rows.append('<li class="muted">No open recommendations for this species this week.</li>')
    for i, p in enumerate(picks, 1):
        launch = next((l for l in data["launches"] if l["key"] == p["launch"]), None)
        if not launch:
            continue
        sp_label = SPECIES_LABEL.get(p.get("species", sp_key), sp_key)
        pick_date = _pick_date(data, p["day_offset"])
        rows.append(
            f'<li>'
            f'<strong>{i}.</strong> '
            f'<a href="#species={p.get("species", sp_key)}&launch={launch["key"]}">'
            f'{html.escape(launch["name"])}</a> '
            f'· {pick_date} · score {p["score"]:.2f} · '
            f'<em>{html.escape(p.get("technique", ""))}</em>'
            f' · <span class="muted">{html.escape(sp_label)}</span>'
            f'</li>'
        )
    return f'<div class="card" data-toppicks="{sp_key}" hidden>' \
           f'<h2>{html.escape(title)}</h2>' \
           f'<ul>{"".join(rows)}</ul></div>'


def _launch_detail_section(data: dict, launches: list[dict]) -> str:
    options = "\n".join(
        f'<option value="{l["key"]}">{html.escape(l["name"])} ({l["region"]})</option>'
        for l in sorted(launches, key=lambda x: (x["region"], x["name"]))
    )
    cards = "\n".join(_launch_card(l, data) for l in launches)
    return f"""<div class="card">
<label>Launch: <select id="launch-select">{options}</select></label>
</div>
<div id="launch-cards">{cards}</div>"""


def _launch_card(launch: dict, data: dict) -> str:
    # Read closure state directly off the launch — build_report_data resolves
    # this per-launch using the same 3-layer (pamphlet + emergency) logic that
    # drives the 7-day grid. Older serialized data (pre-decoration) may lack
    # these keys; fall back to the legacy ``data["regs"]`` lookup so we can
    # still render archived report_data.json files.
    if "closed_today" in launch:
        is_closed = bool(launch.get("closed_today"))
        reason = launch.get("closure_reason") or ("default-open" if not is_closed else "")
        authority = launch.get("closure_authority") or ""
        last_checked = launch.get("closure_last_checked") or ""
    else:
        regs = data["regs"].get(launch["regs_section"]) or {"open": True, "reason": "default-open"}
        is_closed = not regs["open"]
        reason = regs.get("reason", "")
        authority = regs.get("authority", "")
        last_checked = regs.get("last_checked", "")
    is_open = not is_closed
    banner = (
        f'<div class="banner-open">OPEN · {html.escape(reason)}</div>'
        if is_open else
        f'<div class="banner-closed">CLOSED — {html.escape(reason)}</div>'
    )

    species_blocks = []
    for sp in launch["species"]:
        key = f"{sp}::{launch['key']}"
        days = data["forecasts"].get(key, [])
        species_blocks.append(_species_block(sp, days, is_open))

    map_url = f"https://www.google.com/maps?q={launch['lat']:.4f},{launch['lon']:.4f}"

    return f"""<div class="card" data-launch="{html.escape(launch['key'])}" hidden>
<h2>{html.escape(launch['name'])}</h2>
<div class="muted">{launch['lat']:.4f}°N, {abs(launch['lon']):.4f}°W · {html.escape(launch['region'])} · <a href="{map_url}" target="_blank">map</a></div>
{banner}
{"".join(species_blocks)}
<div class="muted">Regs source: {html.escape(authority)} · last checked {html.escape(last_checked)}</div>
</div>"""


def _species_block(sp: str, days: list[dict], section_open: bool) -> str:
    if not days:
        return ""
    cells = []
    # Day-strip is anchored to today's 7-day window; the rest of the 366-day
    # forecast lives in the JSON payload and is consumed by planner.js.
    for i, d in enumerate(days[:7]):
        klass = d["verdict"]
        future = "future-dim" if i >= 4 else ""
        no_run = (
            '<br><span class="muted">(no run data)</span>'
            if d.get("no_run_data")
            else ""
        )
        cells.append(
            f'<div class="day-cell {klass} {future}">'
            f'<strong>{d["date"][-5:]}</strong><br>{d["verdict"]}<br>'
            f'<span class="muted">{d["score"]:.2f}</span>{no_run}</div>'
        )
    today = days[0]
    techs = today.get("techniques") or []
    tech_html = ""
    if techs:
        primary = techs[0]
        gear = primary.get("gear") or {}
        gear_html = "".join(f"<li>{html.escape(str(k))}: {html.escape(str(v))}</li>" for k, v in gear.items())
        tech_html = (
            f'<div><strong>★ {html.escape(primary["label"])}</strong>'
            f'<ul>{gear_html}</ul>'
            f'<div class="muted">{html.escape(primary.get("notes",""))}</div></div>'
        )
    return f"""<details data-species-block="{sp}" {"open" if section_open else ""}>
<summary>{html.escape(SPECIES_LABEL.get(sp, sp))}</summary>
<div class="day-strip">{"".join(cells)}</div>
{tech_html}
</details>"""


def _heatmap_month_labels(heatmap: dict) -> str:
    """Render a month-label row aligned to the heatmap cells below.

    Uses the first species' date list as the reference axis. Each month label
    gets a flex weight equal to its day count so labels align (approximately)
    to the cell columns underneath.
    """
    first_species = next(iter(heatmap.values()), None)
    if not first_species:
        return ""
    from collections import OrderedDict
    months: "OrderedDict[str, int]" = OrderedDict()
    for d in first_species:
        ym = d["date"][:7]  # "YYYY-MM"
        months[ym] = months.get(ym, 0) + 1
    cells = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for ym, count in months.items():
        mm = int(ym.split("-")[1])
        label = month_names[mm - 1]
        cells.append(
            f'<span class="heat-month-label" style="flex: {count} 1 0">{label}</span>'
        )
    return (
        f'<div class="heat-row heat-month-row">'
        f'<span class="heat-label"></span>'
        f'<span class="heat-cells">{"".join(cells)}</span>'
        f'</div>'
    )


def _season_heatmap_section(data: dict) -> str:
    heatmap = data.get("season_heatmap") or {}
    if not heatmap:
        return ""
    launch_names = {l["key"]: l["name"] for l in (data.get("launches") or [])}
    rows = [_heatmap_month_labels(heatmap)]
    for sp in ALL_SPECIES:
        days = heatmap.get(sp) or []
        if not days:
            continue
        cells = []
        for d in days:
            score = float(d.get("score") or 0.0)
            verdict = ("GREAT" if score >= 0.9 else "GOOD" if score >= 0.7
                       else "FAIR" if score >= 0.5 else "POOR")
            launch_key = d.get("launch") or ""
            launch_name = launch_names.get(launch_key, launch_key)
            tip = f'{d["date"]} · {launch_name} · {score:.2f}' if launch_name else f'{d["date"]}: {score:.2f}'
            cells.append(
                f'<span class="heat-cell {verdict}" data-heat-date="{html.escape(d["date"])}" '
                f'title="{html.escape(tip)}"></span>'
            )
        rows.append(
            f'<div class="heat-row" data-heat-species="{sp}">'
            f'<span class="heat-label">{html.escape(SPECIES_LABEL[sp])}</span>'
            f'<span class="heat-cells">{"".join(cells)}</span>'
            f'</div>'
        )
    legend = (
        '<div class="heat-legend muted">'
        '<span class="heat-cell GREAT"></span>&nbsp;GREAT (≥0.9) &nbsp;·&nbsp; '
        '<span class="heat-cell GOOD"></span>&nbsp;GOOD (≥0.7) &nbsp;·&nbsp; '
        '<span class="heat-cell FAIR"></span>&nbsp;FAIR (≥0.5) &nbsp;·&nbsp; '
        '<span class="heat-cell POOR"></span>&nbsp;POOR (&lt;0.5)'
        '</div>'
    )
    subtitle = (
        '<p class="muted" style="margin-top: 0; font-size: 0.85rem;">'
        'Each cell shows the <strong>best score across all open launches</strong> for that species on that day. '
        'A green cell means at least one launch is firing — to see <em>which</em> launch, '
        'use the Trip Planner\'s "Best places" mode below.'
        '</p>'
    )
    return f'<section id="season-heatmap" class="card"><h2>Season Heatmap</h2>{subtitle}{legend}{"".join(rows)}</section>'


def _planner_section(data: dict) -> str:
    species_options = "\n".join(
        f'<option value="{sp}">{html.escape(SPECIES_LABEL[sp])}</option>'
        for sp in ALL_SPECIES
    )
    launch_options = "\n".join(
        f'<option value="{l["key"]}">{html.escape(l["name"])} ({html.escape(l["region"])})</option>'
        for l in sorted(
            (l for l in data["launches"] if l.get("parent_key") is None),
            key=lambda x: (x["region"], x["name"]),
        )
    )
    today_iso = html.escape(data["today"])
    from datetime import date as _d, timedelta as _td
    max_iso = (_d.fromisoformat(data["today"]) + _td(days=365)).isoformat()
    return f"""<section id="planner" class="card">
  <h2>Trip Planner</h2>
  <div class="tabs">
    <button class="tab active" data-planner-mode="best-places">Best places</button>
    <button class="tab" data-planner-mode="best-dates">Best dates</button>
    <button class="tab" data-planner-mode="best-mix">Best mix</button>
  </div>
  <div class="planner-inputs">
    <div data-planner-form="best-places">
      <label>Species: <select data-planner-input="bp-species">{species_options}</select></label>
      <label>Date: <input type="date" data-planner-input="bp-date" min="{today_iso}" max="{html.escape(max_iso)}" value="{today_iso}"></label>
    </div>
    <div data-planner-form="best-dates" hidden>
      <label>Launch: <select data-planner-input="bd-launch">{launch_options}</select></label>
      <label>Species: <select data-planner-input="bd-species">{species_options}</select></label>
    </div>
    <div data-planner-form="best-mix" hidden>
      <label>Date: <input type="date" data-planner-input="bm-date" min="{today_iso}" max="{html.escape(max_iso)}" value="{today_iso}"></label>
    </div>
  </div>
  <div id="planner-results"></div>
  <button id="planner-ics" class="tab" hidden>Download .ics</button>
</section>"""


def _js() -> str:
    return """<script>
(function(){
  function getHash() {
    const h = location.hash.replace(/^#/, '');
    const out = {};
    h.split('&').forEach(p => { const [k,v] = p.split('='); if (k) out[k] = decodeURIComponent(v||''); });
    return out;
  }
  function setHash(o) {
    location.hash = Object.entries(o).map(([k,v]) => `${k}=${encodeURIComponent(v)}`).join('&');
  }
  function selectSpecies(sp) {
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === sp));
    document.querySelectorAll('[data-toppicks]').forEach(el => el.hidden = (el.dataset.toppicks !== sp));
    document.querySelectorAll('[data-species-summary]').forEach(el => el.hidden = (sp === 'all' || el.dataset.speciesSummary !== sp));
    document.querySelectorAll('[data-species-block]').forEach(el => el.hidden = (sp !== 'all' && el.dataset.speciesBlock !== sp));
  }
  function selectLaunch(key) {
    document.querySelectorAll('[data-launch]').forEach(el => el.hidden = (el.dataset.launch !== key));
    const sel = document.getElementById('launch-select');
    if (sel && sel.value !== key) sel.value = key;
    try { localStorage.setItem('salmon.last_launch', key); } catch(e) {}
  }
  function applyHash() {
    const h = getHash();
    const sp = h.species || 'all';
    let lk = h.launch;
    if (!lk) {
      try { lk = localStorage.getItem('salmon.last_launch'); } catch(e) {}
    }
    if (!lk) {
      const first = document.querySelector('[data-launch]');
      lk = first ? first.dataset.launch : null;
    }
    selectSpecies(sp);
    if (lk) selectLaunch(lk);
  }
  document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', () => {
    setHash({ species: t.dataset.tab, launch: getHash().launch || '' });
  }));
  const sel = document.getElementById('launch-select');
  if (sel) sel.addEventListener('change', () => {
    const h = getHash();
    setHash({ species: h.species || 'all', launch: sel.value });
  });
  window.addEventListener('hashchange', applyHash);
  applyHash();
})();
</script>"""
