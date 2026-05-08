"""HTML renderer.

Single big f-string approach (matches pikeminnow). Splits into helpers per
section: header, species tabs, top-picks card, launch detail card. JS at the
bottom handles tab switching and dropdown selection via URL hash + localStorage.
"""
from __future__ import annotations

import html
from typing import Any

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
DAM_LABEL = {"BON": "Bonneville", "MCN": "McNary", "PRD": "Priest Rapids",
             "WEL": "Wells", "RRH": "Rocky Reach", "RIS": "Rock Island", "LGR": "Lower Granite"}


def render_html(data: dict[str, Any]) -> str:
    launches = [l for l in data["launches"] if l["parent_key"] is None]

    head = _head()
    header_bar = _header_bar(data)
    species_summary = _all_species_summary(data)
    species_tabs_html = _species_tabs(data)
    top_picks_html = _all_top_picks_cards(data)
    launch_detail_html = _launch_detail_section(data, launches)
    js = _js()

    return f"""<!doctype html>
<html lang="en">
{head}
<body>
{header_bar}
{species_summary}
{species_tabs_html}
{top_picks_html}
{launch_detail_html}
{js}
</body>
</html>"""


def _head() -> str:
    return """<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Salmon &amp; Steelhead Report</title>
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
.muted { color: var(--muted); font-size: 0.85rem; }
[hidden] { display: none !important; }
@media (max-width: 600px) {
  .now-strip { grid-template-columns: 1fr; }
}
</style>
</head>"""


def _header_bar(data: dict) -> str:
    return f"""<header class="card">
  <h1>Salmon &amp; Steelhead Report</h1>
  <div class="muted">Forecast week starting {html.escape(data['today'])} · generated {html.escape(data['generated_at'])}</div>
</header>"""


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
        rows.append(
            f'<li>'
            f'<strong>{i}.</strong> '
            f'<a href="#species={p.get("species", sp_key)}&launch={launch["key"]}">'
            f'{html.escape(launch["name"])}</a> '
            f'· day +{p["day_offset"]} · score {p["score"]:.2f} · '
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
    regs = data["regs"].get(launch["regs_section"]) or {"open": True, "reason": "default-open"}
    is_open = regs["open"]
    banner = (
        f'<div class="banner-open">OPEN · {html.escape(regs.get("reason",""))}</div>'
        if is_open else
        f'<div class="banner-closed">CLOSED — {html.escape(regs.get("reason",""))}</div>'
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
<div class="muted">Regs source: {html.escape(regs.get('authority',''))} · last checked {html.escape(regs.get('last_checked',''))}</div>
</div>"""


def _species_block(sp: str, days: list[dict], section_open: bool) -> str:
    if not days:
        return ""
    cells = []
    for i, d in enumerate(days):
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
