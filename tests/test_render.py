from datetime import date

from render import render_html


def _minimal_data():
    return {
        "generated_at": "2026-04-27T05:35:00-07:00",
        "today": "2026-04-27",
        "launches": [
            {"key": "vernita", "name": "Vernita Bridge", "region": "hanford",
             "lat": 46.6483, "lon": -119.8833,
             "species": ["chinook", "chinook"],
             "regs_section": "WDFW_HANFORD_REACH",
             "parent_key": None,
             "ref_dams": ["PRD", "MCN"],
             "reach_type": "freeflowing",
             "regs_authority": "WDFW",
             "creel_district": "wdfw_hanford",
             "usgs_site": "12472800",
             "tide_station": None, "flow_source": None,
             "wdfw_url": None, "hero_photo": None},
        ],
        "forecasts": {
            "chinook::vernita": [
                {"date": "2026-04-27", "score": 0.82, "verdict": "GOOD",
                 "open": True, "long_range": False,
                 "techniques": [{"rank": 1, "method": "bobber_eggs",
                                 "label": "Bobber + cured eggs", "gear": {}, "notes": "..."}],
                 "wind_mph": 8.0, "water_temp_f": 52.0, "flow_cfs": 130000},
            ] + [
                {"date": f"2026-04-{27+i}", "score": 0.5, "verdict": "FAIR",
                 "open": True, "long_range": False,
                 "techniques": [], "wind_mph": 5.0, "water_temp_f": 53.0, "flow_cfs": 130000}
                for i in range(1, 4)
            ] + [
                {"date": f"2026-05-{i-3:02d}", "score": 0.4, "verdict": "POOR",
                 "open": True, "long_range": False,
                 "techniques": [], "wind_mph": 5.0, "water_temp_f": 53.0, "flow_cfs": 130000}
                for i in range(4, 7)
            ],
        },
        "runtiming": {
            "BON_chinook": {"species": "chinook", "dam_key": "BON",
                            "pace_ratio": 0.92, "cumulative_count": 5000.0,
                            "cumulative_avg": 5435.0,
                            "peak_date_10yr": "2026-05-10",
                            "peak_date_estimated": "2026-05-11"},
            "front_chinook": "MCN",
        },
        "top_picks": {
            "chinook": [
                {"launch": "vernita", "day_offset": 0, "score": 0.82,
                 "technique": "Bobber + cured eggs"},
            ],
        },
        "top_picks_by_date": {
            "2026-04-27": {
                "chinook": [
                    {"launch": "vernita", "score": 0.82, "technique": "Bobber + cured eggs"},
                ],
            },
        },
        "season_heatmap": {
            "chinook": [
                {"date": "2026-04-27", "score": 0.82},
                {"date": "2026-04-28", "score": 0.5},
            ],
        },
        "pamphlet_expires": "2026-06-30",
        "regs": {
            "WDFW_HANFORD_REACH": {"open": True, "reason": "Open through May 31",
                                   "authority": "WDFW", "last_checked": "2026-04-27T12:00:00"},
        },
        "creel": [],
    }


def test_render_returns_html():
    html = render_html(_minimal_data())
    assert "<html" in html.lower()
    assert "</html>" in html.lower()


def test_render_includes_species_tabs():
    html = render_html(_minimal_data())
    assert "Chinook" in html
    assert "Coho" in html
    assert "Steelhead" in html
    assert "Sockeye" in html


def test_render_includes_top_picks_card():
    html = render_html(_minimal_data())
    assert "Top 3 Picks" in html or "Top Picks" in html
    assert "Vernita Bridge" in html


def test_render_marks_launch_with_data_attribute():
    html = render_html(_minimal_data())
    assert 'data-launch="vernita"' in html


def test_render_includes_google_maps_link():
    html = render_html(_minimal_data())
    assert "google.com/maps" in html
    assert "46.6483,-119.8833" in html


def test_render_runtiming_summary_in_header():
    html = render_html(_minimal_data())
    assert "0.92" in html  # pace ratio
    assert "MCN" in html or "McNary" in html  # front of run


def test_render_closed_section_grays_out():
    data = _minimal_data()
    data["regs"]["WDFW_HANFORD_REACH"] = {
        "open": False, "reason": "Emergency closure", "authority": "WDFW",
        "last_checked": "2026-04-27T12:00:00",
    }
    html = render_html(data)
    assert "CLOSED" in html
    assert "Emergency closure" in html


def test_render_no_staleness_banner_when_all_agencies_ok(tmp_path, monkeypatch):
    """Normal run: every agency reports ok=True, no banner element appears.

    Pin DATA_DIR to a clean tmp_path so a developer's local STALE_PAMPHLET
    flag (which also emits a banner-warn div) cannot pollute this assertion.
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    data = _minimal_data()
    data["regs_agency_meta"] = {
        "WDFW": {"ok": True, "last_successful_check": "2026-04-27T05:35:00", "error": None},
        "ODFW": {"ok": True, "last_successful_check": "2026-04-27T05:35:00", "error": None},
        "IDFG": {"ok": True, "last_successful_check": "2026-04-27T05:35:00", "error": None},
    }
    html = render_html(data)
    # The class is defined in the stylesheet; check for the actual banner element.
    assert '<div class="banner-warn">' not in html
    assert "Regulations check failed" not in html


def test_render_staleness_banner_when_agency_failed():
    """An agency with ok=False surfaces a yellow staleness banner."""
    data = _minimal_data()
    data["regs_agency_meta"] = {
        "WDFW": {"ok": False, "last_successful_check": None, "error": "503 Service Unavailable"},
        "ODFW": {"ok": True, "last_successful_check": "2026-04-27T05:35:00", "error": None},
        "IDFG": {"ok": True, "last_successful_check": "2026-04-27T05:35:00", "error": None},
    }
    html = render_html(data)
    assert '<div class="banner-warn">' in html
    assert "WDFW" in html
    assert "Regulations check failed" in html


def test_render_staleness_banner_handles_missing_meta_gracefully(tmp_path, monkeypatch):
    """Older cached data without regs_agency_meta should still render.

    Pin DATA_DIR to a clean tmp_path so a developer's local STALE_PAMPHLET
    flag cannot trip this assertion.
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    data = _minimal_data()
    # No regs_agency_meta key at all
    html = render_html(data)
    assert '<div class="banner-warn">' not in html


def test_render_includes_open_graph_meta():
    html = render_html(_minimal_data())
    assert 'property="og:title"' in html
    assert 'property="og:description"' in html
    assert 'property="og:url"' in html
    assert 'property="og:type"' in html
    assert 'name="twitter:card"' in html


def test_render_og_url_uses_canonical_host():
    html = render_html(_minimal_data())
    assert "salmon.pnwbite.com" in html


def test_stale_pamphlet_banner_renders(tmp_path, monkeypatch):
    """When STALE_PAMPHLET flag exists, render emits the pamphlet warning banner."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    (cache_dir / "STALE_PAMPHLET").write_text(
        "Wed, 24 Jun 2026 12:00:00 GMT", encoding="utf-8"
    )

    html = render_html(_minimal_data())
    assert "Pamphlet may be out of date" in html
    assert "Wed, 24 Jun 2026 12:00:00 GMT" in html


def test_no_pamphlet_banner_when_flag_absent(tmp_path, monkeypatch):
    """No STALE_PAMPHLET flag in the cache dir => no pamphlet banner in HTML."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "pamphlet-cache").mkdir()
    # Deliberately no STALE_PAMPHLET file.

    html = render_html(_minimal_data())
    assert "Pamphlet may be out of date" not in html


def test_no_pamphlet_banner_when_flag_empty(tmp_path, monkeypatch):
    """An empty STALE_PAMPHLET file should be treated as absent (defensive)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    (cache_dir / "STALE_PAMPHLET").write_text("", encoding="utf-8")

    html = render_html(_minimal_data())
    assert "Pamphlet may be out of date" not in html


def test_pamphlet_expiration_banner_renders_when_today_past_expiration(
    tmp_path, monkeypatch
):
    """When today's date is past pamphlet_expires, the expiration banner appears.

    Pin DATA_DIR to a clean tmp_path so the STALE_PAMPHLET banner cannot
    pollute this assertion.
    """
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr("render.pamphlet_expires", lambda: date(2026, 6, 30))
    monkeypatch.setattr("render.pamphlet_version", lambda: "2025-2026")

    # Force the expiration check to see "today" as past 2026-06-30.
    class _FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 7, 15)

    monkeypatch.setattr("render._date", _FakeDate)

    html = render_html(_minimal_data())
    assert "expired on 2026-06-30" in html
    assert "2025-2026" in html
    assert "wdfw.wa.gov/fishing/regulations" in html


def test_pamphlet_expiration_banner_absent_when_today_before_expiration(
    tmp_path, monkeypatch
):
    """When today's date is on/before pamphlet_expires, the banner is absent."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr("render.pamphlet_expires", lambda: date(2026, 6, 30))
    monkeypatch.setattr("render.pamphlet_version", lambda: "2025-2026")

    class _FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 5, 9)  # before expiration

    monkeypatch.setattr("render._date", _FakeDate)

    html = render_html(_minimal_data())
    assert "expired on" not in html
    assert "may no longer reflect current regulations" not in html


def test_pamphlet_expiration_banner_absent_when_no_expires_field(
    tmp_path, monkeypatch
):
    """When pamphlet_expires() returns None, no expiration banner appears."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr("render.pamphlet_expires", lambda: None)

    html = render_html(_minimal_data())
    assert "expired on" not in html
    assert "may no longer reflect current regulations" not in html


def test_both_banners_can_coexist(tmp_path, monkeypatch):
    """STALE_PAMPHLET flag AND past-expiration date: both banners render."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache_dir = tmp_path / "pamphlet-cache"
    cache_dir.mkdir()
    (cache_dir / "STALE_PAMPHLET").write_text(
        "Wed, 24 Jun 2026 12:00:00 GMT", encoding="utf-8"
    )
    monkeypatch.setattr("render.pamphlet_expires", lambda: date(2026, 6, 30))
    monkeypatch.setattr("render.pamphlet_version", lambda: "2025-2026")

    class _FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 7, 15)

    monkeypatch.setattr("render._date", _FakeDate)

    html = render_html(_minimal_data())
    # Expiration banner.
    assert "expired on 2026-06-30" in html
    # STALE_PAMPHLET banner.
    assert "Pamphlet may be out of date" in html
    assert "Wed, 24 Jun 2026 12:00:00 GMT" in html


def test_mcnary_tailrace_label_shows_closed_from_pamphlet(tmp_path):
    """Regression for HANDOFF.md #9: per-launch banner must reflect pamphlet
    closures keyed by ``pamphlet_section`` (mcnary_tailrace), not just emergency
    rules keyed by the legacy ``regs_section`` (WDFW_MCNARY_POOL). The 7-day
    grid was already correct via resolve(); this test pins the banner.
    """
    from datetime import datetime, timezone
    from storage import FileStorage
    from fishing_report import build_report_data
    from sources.dart import RuntimingCurve
    from sources.fpc_counts import CountRecord
    from regs.wdfw import RegStatus

    today = date(2026, 5, 9)  # inside the Jan 1 – Jun 15 mcnary_tailrace closure
    flat_curve = lambda dam, sp: RuntimingCurve(
        dam_key=dam, species=sp, daily_avg={i: 100.0 for i in range(1, 367)},
    )
    inputs = {
        "today": today,
        "flows": [],
        "counts": [CountRecord("BON", "chinook", today, 5000)],
        "curves": {
            (d, s): flat_curve(d, s)
            for d in ("BON", "TDA", "JDA", "MCN", "IHR", "LMN", "PRD",
                       "WEL", "RRH", "RIS", "LGR")
            for s in ("chinook", "chinook", "sockeye",
                       "chinook", "coho", "steelhead",
                       "steelhead")
        },
        "usgs_by_site": {},
        "usgs_by_launch": {},
        "nws_by_launch": {},
        "creel": [],
        "pamphlet_regs": {
            "mcnary_tailrace": RegStatus(
                authority="WDFW", section_key="mcnary_tailrace", open=False,
                reason="Closed Jan 1 – Jun 15 (pamphlet)",
                last_checked=datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc),
            ),
        },
        "emergency_regs": {},
    }
    storage = FileStorage(root=tmp_path)
    data = build_report_data(inputs, storage=storage)
    html = render_html(data)

    # Locate the McNary Tailrace launch card and assert it shows CLOSED.
    marker = 'data-launch="mcnary_tail_pasco"'
    idx = html.find(marker)
    assert idx >= 0, "mcnary_tail_pasco card missing from rendered HTML"
    # Card runs until the next data-launch="..." or end.
    next_idx = html.find('data-launch="', idx + len(marker))
    card = html[idx:next_idx if next_idx > 0 else len(html)]
    assert "CLOSED" in card, f"expected CLOSED banner in mcnary_tail_pasco card, got: {card[:500]}"
    assert "OPEN · default-open" not in card
    assert "Closed Jan 1" in card

    # Sacajawea also points at pamphlet_section=mcnary_tailrace — same closure
    # should propagate without any per-launch hand-coding.
    marker2 = 'data-launch="sacajawea"'
    idx2 = html.find(marker2)
    assert idx2 >= 0
    next_idx2 = html.find('data-launch="', idx2 + len(marker2))
    card2 = html[idx2:next_idx2 if next_idx2 > 0 else len(html)]
    assert "CLOSED" in card2


def test_render_html_includes_date_picker_in_header():
    from render import render_html
    data = _minimal_data()
    html_out = render_html(data)
    # Native date input with id="date-picker" exists
    assert 'id="date-picker"' in html_out
    assert 'type="date"' in html_out
    # min and max attributes are set to today and today+365
    assert f'min="{data["today"]}"' in html_out
    # Caption span the JS will rewrite is present
    assert 'id="picker-caption"' in html_out


def test_render_html_embeds_full_payload_as_json_script():
    import json
    from render import render_html
    data = _minimal_data()
    html_out = render_html(data)
    # The payload script tag exists with the right id and type
    assert '<script id="report-payload" type="application/json">' in html_out
    # Extract the JSON between the tags and parse it
    start = html_out.index('<script id="report-payload" type="application/json">')
    start = html_out.index(">", start) + 1
    end = html_out.index("</script>", start)
    payload = json.loads(html_out[start:end])
    assert payload["today"] == data["today"]
    assert "forecasts" in payload
    assert "top_picks_by_date" in payload


def test_render_html_includes_planner_section():
    from render import render_html
    html_out = render_html(_minimal_data())
    # Planner card with mode toggles
    assert 'id="planner"' in html_out
    assert 'data-planner-mode="best-places"' in html_out
    assert 'data-planner-mode="best-dates"' in html_out
    assert 'data-planner-mode="best-mix"' in html_out
    # Result panel placeholder
    assert 'id="planner-results"' in html_out


def test_render_html_includes_season_heatmap():
    from render import render_html
    data = _minimal_data()
    # Inject a heatmap with two species, 3 dates each
    data["season_heatmap"] = {
        "chinook": [
            {"date": "2026-05-10", "score": 0.8},
            {"date": "2026-05-11", "score": 0.6},
            {"date": "2026-05-12", "score": 0.4},
        ],
        "coho": [
            {"date": "2026-05-10", "score": 0.2},
            {"date": "2026-05-11", "score": 0.3},
            {"date": "2026-05-12", "score": 0.5},
        ],
    }
    html_out = render_html(data)
    assert 'id="season-heatmap"' in html_out
    # One row per species
    assert 'data-heat-species="chinook"' in html_out
    assert 'data-heat-species="coho"' in html_out
    # 3 cells per row × 2 species = 6 cells with data-date
    assert html_out.count('data-heat-date=') == 6
