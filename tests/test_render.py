from datetime import date

from render import render_html


def _minimal_data():
    return {
        "generated_at": "2026-04-27T05:35:00-07:00",
        "today": "2026-04-27",
        "launches": [
            {"key": "vernita", "name": "Vernita Bridge", "region": "hanford",
             "lat": 46.6483, "lon": -119.8833,
             "species": ["spring_chinook", "fall_chinook"],
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
            "spring_chinook::vernita": [
                {"date": "2026-04-27", "score": 0.82, "verdict": "GOOD",
                 "techniques": [{"rank": 1, "method": "bobber_eggs",
                                 "label": "Bobber + cured eggs", "gear": {}, "notes": "..."}],
                 "wind_mph": 8.0, "water_temp_f": 52.0, "flow_cfs": 130000},
            ] + [
                {"date": f"2026-04-{27+i}", "score": 0.5, "verdict": "FAIR",
                 "techniques": [], "wind_mph": 5.0, "water_temp_f": 53.0, "flow_cfs": 130000}
                for i in range(1, 4)
            ] + [
                {"date": f"2026-05-{i-3:02d}", "score": 0.4, "verdict": "POOR",
                 "techniques": [], "wind_mph": 5.0, "water_temp_f": 53.0, "flow_cfs": 130000}
                for i in range(4, 7)
            ],
        },
        "runtiming": {
            "BON_spring_chinook": {"species": "spring_chinook", "dam_key": "BON",
                                   "pace_ratio": 0.92, "cumulative_count": 5000.0,
                                   "cumulative_avg": 5435.0,
                                   "peak_date_10yr": "2026-05-10",
                                   "peak_date_estimated": "2026-05-11"},
            "front_spring_chinook": "MCN",
        },
        "top_picks": {
            "spring_chinook": [
                {"launch": "vernita", "day_offset": 0, "score": 0.82,
                 "technique": "Bobber + cured eggs"},
            ],
        },
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
    assert "Spring Chinook" in html
    assert "Fall Chinook" in html
    assert "Summer Steelhead" in html


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
