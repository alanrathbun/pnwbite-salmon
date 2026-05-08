# Public Deploy Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate both pikeminnow and salmon fishing-report apps from local Tailscale-only deployment to public web availability under `pnwbite.com`. Each app becomes a Railway service with in-process APScheduler + HTTP server, fronted by Cloudflare. A small landing page goes live at the apex.

**Architecture:** Single-process containerized Python services. APScheduler runs cron jobs in a background thread; the HTTP server runs in the main thread. State persists on per-service Railway volumes mounted at `/data`. Cloudflare proxies DNS for both subdomains with 24h edge cache + cron-driven purge for sub-hour freshness on the salmon midday regs refresh.

**Tech Stack:** Python 3.12, APScheduler 3.10, `requests`, Docker, Railway (containers + volumes), Cloudflare (DNS + proxy + Pages), GitHub.

---

## Spec reference

This plan implements `/home/alan/arath/fishing_reports/salmon/docs/superpowers/specs/2026-05-08-public-deploy-phase-1-design.md`. When in doubt, the spec is the source of truth.

## Project layout

Touches three repos:

- **`pnwbite/salmon`** (existing, currently `/home/alan/arath/fishing_reports/salmon`) — adds containerization, env-var-aware Storage root, cache purge, robots.txt/sitemap.xml routes, OG meta.
- **`pnwbite/pikeminnow`** (new GitHub repo from `/home/alan/arath/fishing_reports/pikeminnow`) — adds containerization, L1 path retrofit (DATA_DIR env var), robots.txt/sitemap.xml routes, OG meta. Pikeminnow has no test suite; manual smoke test only.
- **`pnwbite/landing`** (new GitHub repo) — single static HTML page with live status badges, deployed to Cloudflare Pages.

## Manual setup steps (user, not in this plan)

These happen on migration day, mostly via dashboards. The plan's Task 12 has the runbook. Listed here for reference:

1. Create GitHub repos `pnwbite/pikeminnow`, `pnwbite/salmon`, `pnwbite/landing` (public).
2. Push current local state to `pnwbite/salmon` and `pnwbite/pikeminnow`.
3. In Railway project `pnwbite` (id `77a2a9f0-38b4-4937-979f-cab2edad57e3`): add 2 services from those GitHub repos.
4. Mount 5GB volumes at `/data` on each service.
5. Set service env vars: `DATA_DIR=/data`, `CLOUDFLARE_PURGE_TOKEN=<token>`, `CLOUDFLARE_ZONE_ID=<id>` (salmon only; pikeminnow has no midday refresh so cache purge is optional there).
6. Add custom domains in Railway → CNAMEs in Cloudflare → SSL Full(strict).
7. Cloudflare Cache Rules for both subdomains: 24h edge TTL, 1h browser cache.
8. Deploy `pnwbite/landing` to Cloudflare Pages → wire to apex `pnwbite.com`.
9. Submit each subdomain to Google Search Console.

## Test approach

- **Salmon** has 130 unit tests. New code lands behind tests; container/Docker bits are smoke-tested via `docker build` + `docker run` locally.
- **Pikeminnow** has zero unit tests. We DO NOT add a test suite in Phase 1 (out of scope per the L1 vs L2 decision). Verification is manual smoke testing: render output should match the pre-migration version.
- **Landing page** is static HTML; verification is `curl` + visual check + JS console for badge fetches.

---

# Phase A: Salmon containerization

Goal: salmon ready to deploy to Railway. All changes contained to `/home/alan/arath/fishing_reports/salmon`.

## Task 1: APScheduler dependency + scheduler.py + entrypoint.py

**Files:**
- Modify: `/home/alan/arath/fishing_reports/salmon/requirements.txt`
- Create: `/home/alan/arath/fishing_reports/salmon/scheduler.py`
- Create: `/home/alan/arath/fishing_reports/salmon/entrypoint.py`
- Create: `/home/alan/arath/fishing_reports/salmon/tests/test_scheduler.py`

- [ ] **Step 1: Add apscheduler to requirements.txt**

```bash
cd /home/alan/arath/fishing_reports/salmon
.venv/bin/pip install apscheduler==3.10.4
echo "apscheduler==3.10.4" >> requirements.txt
sort -o requirements.txt requirements.txt
```

- [ ] **Step 2: Write the failing test**

`tests/test_scheduler.py`:

```python
"""scheduler.py registers APScheduler jobs and exposes a maybe_warmup hook."""
from unittest.mock import MagicMock, patch
from pathlib import Path

import scheduler


def test_register_jobs_adds_daily_and_regs():
    sched = MagicMock()
    scheduler.register_jobs(sched)
    # Two add_job calls expected: daily report + regs refresh
    assert sched.add_job.call_count == 2
    job_ids = [c.kwargs.get("id") or c.args[-1] for c in sched.add_job.call_args_list]
    # Job ids should include "daily_report" and "regs_refresh"
    flat = " ".join(str(c) for c in sched.add_job.call_args_list)
    assert "daily_report" in flat
    assert "regs_refresh" in flat


def test_maybe_warmup_runs_daily_when_no_report(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with patch.object(scheduler, "_run_daily") as mock_daily:
        scheduler.maybe_warmup()
        mock_daily.assert_called_once()


def test_maybe_warmup_skips_when_report_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "report.html").write_text("<html></html>")
    with patch.object(scheduler, "_run_daily") as mock_daily:
        scheduler.maybe_warmup()
        mock_daily.assert_not_called()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_scheduler.py -v
```
Expected: ImportError on `import scheduler`.

- [ ] **Step 4: Implement scheduler.py**

`scheduler.py`:

```python
"""APScheduler job registration for the salmon report.

Two jobs:
  - daily_report: 05:35 Pacific. Runs fishing_report.main() then purges Cloudflare cache.
  - regs_refresh: 12:00 Pacific. Runs regs_refresh.main() then purges Cloudflare cache.

maybe_warmup() runs the daily job once at startup if no report.html exists yet,
so a fresh deploy serves a real page on first GET instead of 503.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger("scheduler")


def register_jobs(sched) -> None:
    sched.add_job(_run_daily, CronTrigger(hour=5, minute=35), id="daily_report")
    sched.add_job(_run_regs, CronTrigger(hour=12, minute=0), id="regs_refresh")


def _run_daily() -> None:
    log.info("Running daily report job")
    from fishing_report import main as run_report
    run_report()
    _safe_purge()


def _run_regs() -> None:
    log.info("Running regs refresh job")
    from regs_refresh import main as run_regs
    run_regs()
    _safe_purge()


def _safe_purge() -> None:
    try:
        from cloudflare import purge_cache
        purge_cache()
    except Exception as e:
        log.warning("cache purge failed: %s", e)


def maybe_warmup() -> None:
    """Run the daily job once if no report.html exists in DATA_DIR."""
    data_dir = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent)))
    report = data_dir / "report.html"
    if not report.exists():
        log.info("No report at %s; running warmup daily job", report)
        _run_daily()
    else:
        log.info("Report exists at %s; skipping warmup", report)
```

- [ ] **Step 5: Implement entrypoint.py**

`entrypoint.py`:

```python
"""Entry point for Railway: APScheduler in background thread + HTTP server in main thread."""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

import scheduler
import fishing_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("entrypoint")

PACIFIC = ZoneInfo("America/Los_Angeles")


def main() -> None:
    sched = BackgroundScheduler(timezone=PACIFIC)
    scheduler.register_jobs(sched)
    sched.start()
    log.info("Scheduler started; jobs: %s", [j.id for j in sched.get_jobs()])

    scheduler.maybe_warmup()

    fishing_server.main()  # blocks


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_scheduler.py -v
```
Expected: 3 passed.

- [ ] **Step 7: Run full suite to verify no regressions**

```bash
.venv/bin/pytest -q 2>&1 | tail -3
```
Expected: 133 passed (was 130 + 3 new).

- [ ] **Step 8: Commit**

```bash
git add requirements.txt scheduler.py entrypoint.py tests/test_scheduler.py
git commit -m "feat: APScheduler + entrypoint for in-process cron + server"
```

---

## Task 2: Storage DATA_DIR env var support

**Files:**
- Modify: `/home/alan/arath/fishing_reports/salmon/storage.py`
- Modify: `/home/alan/arath/fishing_reports/salmon/fishing_report.py`
- Modify: `/home/alan/arath/fishing_reports/salmon/fishing_server.py`
- Modify: `/home/alan/arath/fishing_reports/salmon/regs_refresh.py`
- Modify: `/home/alan/arath/fishing_reports/salmon/tests/test_storage.py`

The `Storage` already accepts `root` in `__init__`. We add a helper `default_root()` that reads `DATA_DIR` env var, and update callers to use it.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_storage.py`:

```python
def test_default_root_uses_data_dir_env(tmp_path, monkeypatch):
    """default_root() returns DATA_DIR if set, otherwise the project root."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from storage import default_root
    assert default_root() == tmp_path


def test_default_root_falls_back_to_project_root(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    from pathlib import Path
    from storage import default_root
    # Should be the salmon project root
    assert default_root() == Path(__file__).resolve().parent.parent
```

- [ ] **Step 2: Run, verify failure**

```bash
.venv/bin/pytest tests/test_storage.py -v
```
Expected: ImportError on `from storage import default_root`.

- [ ] **Step 3: Add default_root to storage.py**

Append to `storage.py`:

```python
def default_root() -> Path:
    """Return DATA_DIR env var if set, otherwise the project root.

    On Railway, DATA_DIR is set to /data (a mounted volume). Locally, falls
    back to the directory containing this storage.py file.
    """
    env = os.environ.get("DATA_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent
```

- [ ] **Step 4: Update callers**

Modify `fishing_report.py` — find the line that creates `FileStorage`:

Before:
```python
storage = FileStorage(root=PROJECT_ROOT)
```

After:
```python
from storage import FileStorage, default_root
storage = FileStorage(root=default_root())
```

Modify `fishing_server.py` — wherever it reads `report.html`. Replace any `PROJECT_ROOT` references in the report-serving path with `default_root()`. Specifically, find this section in `main()`:

```python
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    handler = build_handler(root=PROJECT_ROOT)
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
```

Replace with:

```python
def main():
    import os
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from storage import default_root
    bind_host = os.environ.get("BIND_HOST", "127.0.0.1")
    bind_port = int(os.environ.get("PORT", str(PORT)))
    handler = build_handler(root=default_root())
    httpd = ThreadingHTTPServer((bind_host, bind_port), handler)
    log.info("salmon report server listening on %s:%d", bind_host, bind_port)
    httpd.serve_forever()
```

(This also adds env-var support for `BIND_HOST` and `PORT` so Railway can override.)

Modify `regs_refresh.py` similarly — replace `FileStorage(root=PROJECT_ROOT)` with `FileStorage(root=default_root())`.

- [ ] **Step 5: Run tests to verify all pass**

```bash
.venv/bin/pytest -q 2>&1 | tail -3
```
Expected: 135 passed.

- [ ] **Step 6: Commit**

```bash
git add storage.py fishing_report.py fishing_server.py regs_refresh.py tests/test_storage.py
git commit -m "feat: Storage default_root reads DATA_DIR env; server respects PORT/BIND_HOST"
```

---

## Task 3: Cloudflare cache purge helper

**Files:**
- Create: `/home/alan/arath/fishing_reports/salmon/cloudflare.py`
- Create: `/home/alan/arath/fishing_reports/salmon/tests/test_cloudflare.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cloudflare.py`:

```python
"""cloudflare.purge_cache hits the Cloudflare API; gracefully no-ops without env vars."""
import requests_mock
import pytest

from cloudflare import purge_cache, MissingCloudflareConfig


def test_purge_cache_no_config_silent_noop(monkeypatch):
    """Without env vars, purge_cache returns False and does NOT raise."""
    monkeypatch.delenv("CLOUDFLARE_PURGE_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ZONE_ID", raising=False)
    assert purge_cache() is False


def test_purge_cache_raises_when_strict_and_no_config(monkeypatch):
    """Strict mode raises MissingCloudflareConfig instead of silently no-op."""
    monkeypatch.delenv("CLOUDFLARE_PURGE_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ZONE_ID", raising=False)
    with pytest.raises(MissingCloudflareConfig):
        purge_cache(strict=True)


def test_purge_cache_calls_api(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_PURGE_TOKEN", "test-token")
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "test-zone-123")
    with requests_mock.Mocker() as m:
        m.post(
            "https://api.cloudflare.com/client/v4/zones/test-zone-123/purge_cache",
            json={"success": True, "result": {"id": "abc"}},
            status_code=200,
        )
        result = purge_cache()
        assert result is True
        # Verify the Authorization header was sent
        history = m.request_history
        assert history[0].headers["Authorization"] == "Bearer test-token"
        # Verify body is purge_everything
        assert history[0].json() == {"purge_everything": True}


def test_purge_cache_swallows_api_errors(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_PURGE_TOKEN", "test-token")
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "test-zone-123")
    with requests_mock.Mocker() as m:
        m.post(
            "https://api.cloudflare.com/client/v4/zones/test-zone-123/purge_cache",
            status_code=500,
        )
        # Should not raise
        result = purge_cache()
        assert result is False
```

- [ ] **Step 2: Run, verify failure**

```bash
.venv/bin/pytest tests/test_cloudflare.py -v
```
Expected: ImportError on `from cloudflare import purge_cache`.

- [ ] **Step 3: Implement cloudflare.py**

`cloudflare.py`:

```python
"""Cloudflare cache-purge helper.

Called after each cron run to invalidate the edge cache for the report.
Token + zone-id come from env vars; if either is missing, the function returns
False (silent no-op). API errors are also swallowed (logged, not raised) so a
purge failure never breaks a cron run.
"""
from __future__ import annotations

import logging
import os

import requests

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"

log = logging.getLogger("cloudflare")


class MissingCloudflareConfig(RuntimeError):
    """Raised when strict=True and CLOUDFLARE_PURGE_TOKEN or CLOUDFLARE_ZONE_ID is unset."""


def purge_cache(*, strict: bool = False, timeout: int = 10) -> bool:
    """Purge all cached files for the configured Cloudflare zone.

    Returns True on success, False on missing-config or API failure.
    If strict=True, raises MissingCloudflareConfig when env vars are missing.
    """
    token = os.environ.get("CLOUDFLARE_PURGE_TOKEN")
    zone = os.environ.get("CLOUDFLARE_ZONE_ID")
    if not (token and zone):
        if strict:
            raise MissingCloudflareConfig(
                "CLOUDFLARE_PURGE_TOKEN and CLOUDFLARE_ZONE_ID must both be set"
            )
        log.info("Cloudflare config not set; skipping cache purge")
        return False

    try:
        r = requests.post(
            f"{CLOUDFLARE_API_BASE}/zones/{zone}/purge_cache",
            headers={"Authorization": f"Bearer {token}"},
            json={"purge_everything": True},
            timeout=timeout,
        )
        r.raise_for_status()
        log.info("Cloudflare cache purged for zone %s", zone)
        return True
    except Exception as e:
        log.warning("Cloudflare cache purge failed: %s", e)
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_cloudflare.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/pytest -q 2>&1 | tail -3
```
Expected: 139 passed.

- [ ] **Step 6: Commit**

```bash
git add cloudflare.py tests/test_cloudflare.py
git commit -m "feat: Cloudflare cache purge helper with env-var config"
```

---

## Task 4: robots.txt + sitemap.xml routes in fishing_server.py

**Files:**
- Modify: `/home/alan/arath/fishing_reports/salmon/fishing_server.py`
- Modify: `/home/alan/arath/fishing_reports/salmon/tests/test_server.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_server.py`:

```python
def test_robots_txt(server):
    body = urllib.request.urlopen(server + "/robots.txt").read().decode()
    assert "User-agent: *" in body
    assert "Allow: /" in body
    assert "Disallow: /health" in body
    assert "Sitemap:" in body


def test_sitemap_xml(server):
    body = urllib.request.urlopen(server + "/sitemap.xml").read().decode()
    assert "<urlset" in body
    assert "<loc>" in body
    assert "<priority>1.0</priority>" in body
```

- [ ] **Step 2: Run, verify failure**

```bash
.venv/bin/pytest tests/test_server.py -v
```
Expected: 2 new tests fail with 404.

- [ ] **Step 3: Add routes to fishing_server.py**

Modify `fishing_server.py` — extend `Handler.do_GET` to handle `/robots.txt` and `/sitemap.xml`. Find the existing dispatcher:

```python
def do_GET(self):
    try:
        if self.path in ("/", "/index.html", "/report.html"):
            return self._serve_report(root)
        if self.path == "/health":
            return self._serve_health(root)
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self.send_error(404)
    except BrokenPipeError:
        pass
```

Replace with:

```python
def do_GET(self):
    try:
        if self.path in ("/", "/index.html", "/report.html"):
            return self._serve_report(root)
        if self.path == "/health":
            return self._serve_health(root)
        if self.path == "/robots.txt":
            return self._serve_robots()
        if self.path == "/sitemap.xml":
            return self._serve_sitemap()
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self.send_error(404)
    except BrokenPipeError:
        pass
```

Add the two helper methods inside `Handler`:

```python
def _serve_robots(self):
    host = self.headers.get("Host", "salmon.pnwbite.com")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /health\n\n"
        f"Sitemap: https://{host}/sitemap.xml\n"
    ).encode()
    self.send_response(200)
    self.send_header("Content-Type", "text/plain; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    try:
        self.wfile.write(body)
    except BrokenPipeError:
        pass

def _serve_sitemap(self):
    host = self.headers.get("Host", "salmon.pnwbite.com")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url>\n'
        f'    <loc>https://{host}/</loc>\n'
        '    <changefreq>daily</changefreq>\n'
        '    <priority>1.0</priority>\n'
        '  </url>\n'
        '</urlset>\n'
    ).encode()
    self.send_response(200)
    self.send_header("Content-Type", "application/xml; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    try:
        self.wfile.write(body)
    except BrokenPipeError:
        pass
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_server.py -v
```
Expected: 6 passed (4 original + 2 new).

- [ ] **Step 5: Commit**

```bash
git add fishing_server.py tests/test_server.py
git commit -m "feat: serve /robots.txt and /sitemap.xml from the salmon server"
```

---

## Task 5: Open Graph + Twitter card meta tags in render.py

**Files:**
- Modify: `/home/alan/arath/fishing_reports/salmon/render.py`
- Modify: `/home/alan/arath/fishing_reports/salmon/tests/test_render.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_render.py`:

```python
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
```

- [ ] **Step 2: Run, verify failure**

```bash
.venv/bin/pytest tests/test_render.py -v
```
Expected: 2 new tests fail (no `og:` tags in output).

- [ ] **Step 3: Update render.py `_head()` function**

Modify `render.py` — find `_head()`:

```python
def _head() -> str:
    return """<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Salmon &amp; Steelhead Report</title>
<style>
...
</style>
</head>"""
```

Replace with:

```python
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
...""" + _existing_style_block_continues_here
```

(Keep the existing `<style>...` block; just insert the meta tags before `<style>`.)

The full updated `_head()`:

```python
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
.banner-warn { background: var(--fair); color: #000; padding: 0.4rem; border-radius: 4px; }
.muted { color: var(--muted); font-size: 0.85rem; }
[hidden] { display: none !important; }
@media (max-width: 600px) {
  .now-strip { grid-template-columns: 1fr; }
}
</style>
</head>"""
```

(Note: this preserves the existing CSS exactly. The only change is the addition of the 6 `<meta>` tags between `<title>` and `<style>`.)

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_render.py -v
```
Expected: All previous render tests + 2 new = pass.

- [ ] **Step 5: Run full suite**

```bash
.venv/bin/pytest -q 2>&1 | tail -3
```
Expected: 141 passed.

- [ ] **Step 6: Commit**

```bash
git add render.py tests/test_render.py
git commit -m "feat: Open Graph + Twitter card + description meta tags"
```

---

## Task 6: Hook cache purge into salmon's report jobs

**Files:**
- Modify: `/home/alan/arath/fishing_reports/salmon/fishing_report.py`
- Modify: `/home/alan/arath/fishing_reports/salmon/regs_refresh.py`

The cache purge already happens through `scheduler.py` (Task 1), which calls `_safe_purge()` after each job. No changes needed to `fishing_report.main()` or `regs_refresh.main()` — they don't need to know about the cache. But we should ensure that local manual runs also purge if env vars are set. Add the call to `main()` in both files.

- [ ] **Step 1: Update fishing_report.py main()**

Modify `fishing_report.main()` — append cache purge at the end:

```python
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    storage = FileStorage(root=default_root())
    today = datetime.now(LOCAL_TZ).date()
    log.info("salmon report run starting; today=%s", today)
    inputs = fetch_all(storage=storage, today=today)
    data = build_report_data(inputs, storage=storage)
    from render import render_html
    html = render_html(data)
    storage.write("report_html", html)
    log.info("report.html written: %d bytes", len(html))

    # Purge Cloudflare cache so the new report is immediately visible at the edge.
    try:
        from cloudflare import purge_cache
        purge_cache()
    except Exception as e:
        log.warning("cache purge failed: %s", e)
```

- [ ] **Step 2: Update regs_refresh.py main() similarly**

```python
def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    storage = FileStorage(root=default_root())
    data = storage.read_json("report_data")
    if data is None:
        log.error("no report_data cached; skipping regs refresh")
        return
    log.info("regs refresh starting")
    new_regs, new_meta = regs_fetch_all()
    updated = refresh_regs_in_data(data, new_regs, new_meta)
    storage.write_json("report_data", updated)
    from render import render_html
    html = render_html(updated)
    storage.write("report_html", html)
    log.info("regs refresh complete; report.html re-rendered (%d bytes)", len(html))

    try:
        from cloudflare import purge_cache
        purge_cache()
    except Exception as e:
        log.warning("cache purge failed: %s", e)
```

(Note: scheduler.py also calls `_safe_purge()` after each job, so the purge happens twice when running on Railway — once from `main()`, once from the scheduler. That's idempotent and fine. The duplication is intentional: it makes manual `python fishing_report.py` runs from the command line also purge.)

- [ ] **Step 3: Run full suite**

```bash
.venv/bin/pytest -q 2>&1 | tail -3
```
Expected: 141 passed (no test changes; just code paths now wire purge).

- [ ] **Step 4: Commit**

```bash
git add fishing_report.py regs_refresh.py
git commit -m "feat: trigger Cloudflare cache purge after each report regeneration"
```

---

## Task 7: Dockerfile + railway.toml for salmon

**Files:**
- Create: `/home/alan/arath/fishing_reports/salmon/Dockerfile`
- Create: `/home/alan/arath/fishing_reports/salmon/railway.toml`
- Create: `/home/alan/arath/fishing_reports/salmon/.dockerignore`

- [ ] **Step 1: Create .dockerignore**

`/home/alan/arath/fishing_reports/salmon/.dockerignore`:

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.git/
.gitignore
*.log
report.html
.report_data.json
.nws_grid_cache.json
.dart_runtiming_cache.json
.creel_cache.json
.regs_cache.json
docs/
ops/
tests/fixtures/
HANDOFF.md
README.md
*.md
```

- [ ] **Step 2: Create Dockerfile**

`/home/alan/arath/fishing_reports/salmon/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install lxml/pdfplumber system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Volume for state
ENV DATA_DIR=/data
VOLUME /data

# Railway sets PORT
ENV PORT=8080
ENV BIND_HOST=0.0.0.0
EXPOSE 8080

# Single-process: APScheduler + HTTP server
CMD ["python", "-u", "entrypoint.py"]
```

- [ ] **Step 3: Create railway.toml**

`/home/alan/arath/fishing_reports/salmon/railway.toml`:

```toml
[build]
builder = "DOCKERFILE"

[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
numReplicas = 1
```

- [ ] **Step 4: Verify the Docker build works locally**

```bash
cd /home/alan/arath/fishing_reports/salmon
docker build -t salmon-test:latest .
```

Expected: image builds successfully. If you don't have docker installed, skip this verification — Railway will run the build during deploy.

- [ ] **Step 5: Verify the container runs locally (if docker available)**

```bash
docker run -d --name salmon-test \
  -p 18080:8080 \
  -e DATA_DIR=/data \
  -v salmon-test-data:/data \
  salmon-test:latest

sleep 5
curl -s http://127.0.0.1:18080/health
```

Expected: JSON with size/mtime fields. The first request may show `report_html_size: 0` if warmup is still in progress; wait 30 seconds and curl again.

```bash
docker stop salmon-test && docker rm salmon-test
docker volume rm salmon-test-data
```

- [ ] **Step 6: Commit**

```bash
git add Dockerfile railway.toml .dockerignore
git commit -m "feat: Dockerfile + railway.toml for Railway deployment"
```

---

# Phase B: Pikeminnow containerization + L1 retrofit

Goal: pikeminnow ready to deploy to Railway. Pikeminnow has no test suite; verification is manual smoke testing. The L1 retrofit replaces hardcoded paths with `DATA_DIR`-aware constants.

## Task 8: Pikeminnow path constants retrofit

**Files:**
- Modify: `/home/alan/arath/fishing_reports/pikeminnow/fishing_report.py`
- Modify: `/home/alan/arath/fishing_reports/pikeminnow/fishing_server.py`

Pikeminnow uses several hardcoded paths. We replace them with `DATA_DIR`-aware versions. No tests exist; verify by running the report locally and confirming output matches pre-retrofit.

- [ ] **Step 1: Inventory hardcoded paths**

```bash
cd /home/alan/arath/fishing_reports/pikeminnow
grep -nE "(report\.html|cpue.*cache|nws.*cache|fishing\.log|\.report_data)" fishing_report.py fishing_server.py | head -30
```

Expected: shows all path references that need updating. There should be ~6-10 hits across the files.

- [ ] **Step 2: Add DATA_DIR helper near top of fishing_report.py**

Find the top of `fishing_report.py` (after imports):

```python
import os
from pathlib import Path

# DATA_DIR: state location. /data on Railway; project dir locally.
DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent)))
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_HTML = DATA_DIR / "report.html"
NWS_GRID_CACHE = DATA_DIR / ".nws_grid_cache.json"
CPUE_CACHE = DATA_DIR / ".cpue_2025_cache.json"
```

(Adapt the variable names to match what pikeminnow actually uses — inspect the existing constants first via the grep above.)

- [ ] **Step 3: Replace all in-file hardcoded path references**

Find every reference to `report.html`, `.cpue_2025_cache.json`, `.nws_grid_cache.json` (and any others surfaced by the grep) and replace with the new constants.

For example, find:
```python
with open("report.html", "w") as f:
```

Replace with:
```python
with open(OUTPUT_HTML, "w") as f:
```

(Pikeminnow's atomic write probably uses `tempfile.mkstemp` + `os.replace` — make sure the tempfile is created in `OUTPUT_HTML.parent`, not the project dir. Update accordingly.)

- [ ] **Step 4: Add DATA_DIR helper to fishing_server.py**

Top of `fishing_server.py`:

```python
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent)))
PORT = int(os.environ.get("PORT", "7070"))
BIND_HOST = os.environ.get("BIND_HOST", "127.0.0.1")
```

Then replace the hardcoded `report.html` reference and bind config in `main()` with the new constants. The existing pikeminnow server probably looks like:

```python
def main():
    server_address = ("0.0.0.0", 7070)  # or 127.0.0.1
    httpd = ThreadingHTTPServer(server_address, Handler)
    httpd.serve_forever()
```

Replace with:

```python
def main():
    server_address = (BIND_HOST, PORT)
    httpd = ThreadingHTTPServer(server_address, Handler)
    print(f"pikeminnow server listening on {BIND_HOST}:{PORT}")
    httpd.serve_forever()
```

The handler reading `report.html` should reference `DATA_DIR / "report.html"` instead.

- [ ] **Step 5: Manual smoke test — run before/after diff**

Before retrofit (snapshot prior output):

```bash
cd /home/alan/arath/fishing_reports/pikeminnow
cp report.html /tmp/report-before.html  # snapshot existing output
```

After applying changes, regenerate:

```bash
DATA_DIR=. /usr/bin/python3 fishing_report.py
diff -q /tmp/report-before.html report.html
```

Expected: no diff (or only the `generated_at` timestamp differs). If structural differences appear, the retrofit broke something — investigate before committing.

- [ ] **Step 6: Verify server still serves**

```bash
DATA_DIR=. PORT=7088 BIND_HOST=127.0.0.1 /usr/bin/python3 fishing_server.py &
SERVER_PID=$!
sleep 1
curl -s http://127.0.0.1:7088/ | head -c 100
curl -s http://127.0.0.1:7088/health
kill $SERVER_PID
```

Expected: report HTML head + JSON health.

- [ ] **Step 7: Initialize git for pikeminnow if needed**

Check if pikeminnow has a git repo:

```bash
cd /home/alan/arath/fishing_reports/pikeminnow
git status 2>&1 | head -3
```

If "not a git repository," initialize:

```bash
git init
cat > .gitignore <<'EOF'
.venv/
__pycache__/
*.pyc
*.log
report.html
.report_data.json
.nws_grid_cache.json
.cpue_2025_cache.json
.tmp
*.tmp
fishing.log
fishing_server.log
EOF
git add .gitignore fishing_report.py fishing_server.py HANDOFF.md
git commit -m "chore: initial commit (pre-public-deploy migration)"
```

If already a git repo, skip the init.

- [ ] **Step 8: Commit the retrofit**

```bash
git add fishing_report.py fishing_server.py
git commit -m "feat: L1 retrofit — DATA_DIR + PORT + BIND_HOST env vars"
```

---

## Task 9: Pikeminnow scheduler.py + entrypoint.py + requirements.txt

**Files:**
- Create: `/home/alan/arath/fishing_reports/pikeminnow/requirements.txt`
- Create: `/home/alan/arath/fishing_reports/pikeminnow/scheduler.py`
- Create: `/home/alan/arath/fishing_reports/pikeminnow/entrypoint.py`

- [ ] **Step 1: Create requirements.txt**

Pikeminnow currently has no requirements.txt. Inspect what it imports:

```bash
cd /home/alan/arath/fishing_reports/pikeminnow
grep -hE "^import |^from " fishing_report.py fishing_server.py | sort -u | head -30
```

Based on the imports, create `requirements.txt` (typical pikeminnow deps):

```
requests==2.31.0
beautifulsoup4==4.12.3
lxml==5.1.0
apscheduler==3.10.4
```

(Adjust based on what pikeminnow actually imports — for example if it uses `pdfplumber`, add it.)

- [ ] **Step 2: Create scheduler.py**

`/home/alan/arath/fishing_reports/pikeminnow/scheduler.py`:

```python
"""APScheduler job registration for the pikeminnow report.

One job: daily report at 05:30 Pacific.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger("scheduler")


def register_jobs(sched) -> None:
    sched.add_job(_run_daily, CronTrigger(hour=5, minute=30), id="daily_report")


def _run_daily() -> None:
    log.info("Running pikeminnow daily report job")
    from fishing_report import main as run_report
    run_report()
    # Pikeminnow has no midday refresh; skip cache purge unless desired.
    # The 24h Cloudflare TTL plus daily cron is sufficient for pikeminnow's
    # cadence. If you want the same purge-after-cron pattern as salmon,
    # uncomment:
    # _safe_purge()


def maybe_warmup() -> None:
    """Run the daily job once if no report.html exists in DATA_DIR."""
    data_dir = Path(os.environ.get("DATA_DIR", str(Path(__file__).resolve().parent)))
    report = data_dir / "report.html"
    if not report.exists():
        log.info("No report at %s; running warmup daily job", report)
        _run_daily()
    else:
        log.info("Report exists at %s; skipping warmup", report)
```

- [ ] **Step 3: Create entrypoint.py**

`/home/alan/arath/fishing_reports/pikeminnow/entrypoint.py`:

```python
"""Entry point for Railway: APScheduler in background + HTTP server in main thread."""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

import scheduler
import fishing_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("entrypoint")

PACIFIC = ZoneInfo("America/Los_Angeles")


def main() -> None:
    sched = BackgroundScheduler(timezone=PACIFIC)
    scheduler.register_jobs(sched)
    sched.start()
    log.info("Scheduler started; jobs: %s", [j.id for j in sched.get_jobs()])

    scheduler.maybe_warmup()

    fishing_server.main()  # blocks


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Manual smoke test**

```bash
cd /home/alan/arath/fishing_reports/pikeminnow
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
DATA_DIR=. PORT=7089 .venv/bin/python entrypoint.py &
ENTRYPOINT_PID=$!
sleep 5
curl -s http://127.0.0.1:7089/health
curl -s http://127.0.0.1:7089/ | head -c 200
kill $ENTRYPOINT_PID
```

Expected: scheduler logs jobs registered; warmup may take 30-60 seconds (it actually runs the report). Then server responds with JSON health + HTML.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt scheduler.py entrypoint.py
git commit -m "feat: APScheduler + entrypoint for pikeminnow Railway deployment"
```

---

## Task 10: Pikeminnow Dockerfile + railway.toml + robots.txt + sitemap.xml routes + OG meta

**Files:**
- Create: `/home/alan/arath/fishing_reports/pikeminnow/Dockerfile`
- Create: `/home/alan/arath/fishing_reports/pikeminnow/railway.toml`
- Create: `/home/alan/arath/fishing_reports/pikeminnow/.dockerignore`
- Modify: `/home/alan/arath/fishing_reports/pikeminnow/fishing_server.py`
- Modify: `/home/alan/arath/fishing_reports/pikeminnow/fishing_report.py` (OG meta in render path)

- [ ] **Step 1: Create .dockerignore**

`/home/alan/arath/fishing_reports/pikeminnow/.dockerignore`:

```
.venv/
__pycache__/
*.pyc
.git/
.gitignore
*.log
report.html
.cpue_2025_cache.json
.nws_grid_cache.json
.tmp
*.tmp
docs/
*.md
pikeminnow.zip
```

- [ ] **Step 2: Create Dockerfile**

`/home/alan/arath/fishing_reports/pikeminnow/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATA_DIR=/data
VOLUME /data

ENV PORT=8080
ENV BIND_HOST=0.0.0.0
EXPOSE 8080

CMD ["python", "-u", "entrypoint.py"]
```

- [ ] **Step 3: Create railway.toml**

`/home/alan/arath/fishing_reports/pikeminnow/railway.toml`:

```toml
[build]
builder = "DOCKERFILE"

[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
numReplicas = 1
```

- [ ] **Step 4: Add robots.txt + sitemap.xml routes to fishing_server.py**

In pikeminnow's `fishing_server.py`, find the `do_GET` handler. Add the same 2 routes used in salmon (Task 4). The exact code structure may differ (pikeminnow's server is older), but the pattern is:

```python
elif self.path == "/robots.txt":
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /health\n\n"
        "Sitemap: https://pikeminnow.pnwbite.com/sitemap.xml\n"
    ).encode()
    self.send_response(200)
    self.send_header("Content-Type", "text/plain; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)
elif self.path == "/sitemap.xml":
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url>\n'
        '    <loc>https://pikeminnow.pnwbite.com/</loc>\n'
        '    <changefreq>daily</changefreq>\n'
        '    <priority>1.0</priority>\n'
        '  </url>\n'
        '</urlset>\n'
    ).encode()
    self.send_response(200)
    self.send_header("Content-Type", "application/xml; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)
```

(Add this within the `do_GET` method, before the catch-all 404.)

- [ ] **Step 5: Add OG meta tags to pikeminnow's HTML output**

Pikeminnow's HTML rendering happens inside `fishing_report.py` (likely in a function like `render_html()` or directly inline). Find where the `<head>` section is generated (search for `<head>`). Insert these meta tags right after the `<title>` tag:

```html
<meta property="og:title" content="Pikeminnow Sport-Reward Report" />
<meta property="og:description" content="Daily fishing forecast for 21 NPSRP check-in stations on the Columbia River." />
<meta property="og:url" content="https://pikeminnow.pnwbite.com/" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary" />
<meta name="description" content="Daily Northern Pikeminnow Sport-Reward Program fishing forecast across 21 check-in stations on the Columbia River." />
```

Use the same f-string approach pikeminnow already uses for HTML generation; just insert the meta tags into the existing `<head>` block.

- [ ] **Step 6: Manual smoke test the complete pikeminnow container**

```bash
cd /home/alan/arath/fishing_reports/pikeminnow

# Local docker test (if docker available)
docker build -t pikeminnow-test:latest .
docker run -d --name pikeminnow-test \
  -p 18081:8080 \
  -e DATA_DIR=/data \
  -v pikeminnow-test-data:/data \
  pikeminnow-test:latest

sleep 60  # wait for warmup
curl -s http://127.0.0.1:18081/robots.txt
curl -s http://127.0.0.1:18081/sitemap.xml
curl -s http://127.0.0.1:18081/ | grep -E 'og:title|og:url'

docker stop pikeminnow-test && docker rm pikeminnow-test
docker volume rm pikeminnow-test-data
```

Expected: robots.txt + sitemap.xml visible; OG meta tags present in HTML.

- [ ] **Step 7: Commit**

```bash
git add Dockerfile railway.toml .dockerignore fishing_server.py fishing_report.py
git commit -m "feat: pikeminnow container, robots.txt, sitemap.xml, OG meta"
```

---

# Phase C: Landing page

## Task 11: pnwbite/landing repo

**Files (in a NEW separate repo):**
- Create: `index.html`
- Create: `robots.txt`
- Create: `sitemap.xml`
- Optional: `favicon.ico`

This is a separate GitHub repo, deployed via Cloudflare Pages.

- [ ] **Step 1: Initialize the landing repo**

```bash
mkdir -p /home/alan/arath/fishing_reports/landing
cd /home/alan/arath/fishing_reports/landing
git init
```

- [ ] **Step 2: Create index.html**

`/home/alan/arath/fishing_reports/landing/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PNW Bite — Pacific Northwest Fishing Reports</title>
<meta property="og:title" content="PNW Bite" />
<meta property="og:description" content="Daily Pacific Northwest fishing reports for pikeminnow and salmon/steelhead." />
<meta property="og:url" content="https://pnwbite.com/" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary" />
<meta name="description" content="Daily Pacific Northwest fishing reports — pikeminnow sport-reward stations, salmon and steelhead launches across the upper Columbia and Snake river systems." />
<style>
:root {
  --bg: #0d1117; --fg: #e6edf3; --muted: #8b949e;
  --card: #161b22; --border: #30363d;
  --good: #3fb950; --fair: #d29922; --poor: #f85149;
}
* { box-sizing: border-box; }
body {
  background: var(--bg); color: var(--fg);
  font: 16px/1.5 system-ui, -apple-system, sans-serif;
  margin: 0; padding: 2rem 1rem;
  display: flex; align-items: center; justify-content: center;
  min-height: 100vh;
}
.wrap { max-width: 700px; width: 100%; }
header { text-align: center; margin-bottom: 2rem; }
h1 { font-size: 2.5rem; margin: 0 0 0.25rem; letter-spacing: -0.02em; }
.tagline { color: var(--muted); font-size: 1rem; margin: 0; }
.grid { display: grid; gap: 1rem; grid-template-columns: 1fr 1fr; }
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: 8px;
  padding: 1.25rem; text-decoration: none; color: var(--fg);
  display: flex; flex-direction: column; gap: 0.5rem;
  transition: border-color 0.15s;
}
.card:hover { border-color: var(--good); }
.card h2 { margin: 0; font-size: 1.25rem; }
.card .desc { color: var(--muted); font-size: 0.9rem; flex: 1; margin: 0; }
.status { display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; }
.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--muted);
}
.dot.fresh { background: var(--good); }
.dot.stale { background: var(--fair); }
.dot.error { background: var(--poor); }
.cta { color: var(--good); font-weight: 500; font-size: 0.95rem; margin-top: auto; }
footer { text-align: center; color: var(--muted); font-size: 0.85rem; margin-top: 2rem; }
@media (max-width: 600px) {
  .grid { grid-template-columns: 1fr; }
  h1 { font-size: 2rem; }
}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>PNW Bite</h1>
  <p class="tagline">Daily Pacific Northwest fishing reports.</p>
</header>

<div class="grid">
  <a class="card" href="https://pikeminnow.pnwbite.com/" data-app="pikeminnow" data-host="pikeminnow.pnwbite.com">
    <h2>Pikeminnow Sport-Reward</h2>
    <p class="desc">21 NPSRP check-in stations on the Columbia. CPUE-driven station rankings, flow + weather forecast.</p>
    <div class="status">
      <span class="dot" data-dot></span>
      <span data-status>Loading…</span>
    </div>
    <span class="cta">Open report →</span>
  </a>

  <a class="card" href="https://salmon.pnwbite.com/" data-app="salmon" data-host="salmon.pnwbite.com">
    <h2>Salmon &amp; Steelhead</h2>
    <p class="desc">30 boat launches across the upper Columbia and Snake. Run-timing, regulations, bait recommendations.</p>
    <div class="status">
      <span class="dot" data-dot></span>
      <span data-status>Loading…</span>
    </div>
    <span class="cta">Open report →</span>
  </a>
</div>

<footer>Built by Alan · v1 (2026)</footer>
</div>

<script>
async function refresh() {
  for (const card of document.querySelectorAll('[data-app]')) {
    const host = card.dataset.host;
    const dot = card.querySelector('[data-dot]');
    const txt = card.querySelector('[data-status]');
    try {
      const r = await fetch(`https://${host}/health`, { cache: 'no-cache' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      const mtime = j.report_html_mtime || j.report_data_mtime;
      if (!mtime) throw new Error('no mtime');
      const ageMs = Date.now() - (mtime * 1000);
      const ageHours = Math.floor(ageMs / 3.6e6);
      if (ageHours < 25) {
        dot.className = 'dot fresh';
        txt.textContent = ageHours < 1
          ? 'Fresh (< 1h ago)'
          : `Updated ${ageHours}h ago`;
      } else {
        dot.className = 'dot stale';
        txt.textContent = `Stale (${Math.floor(ageHours/24)}d ago)`;
      }
    } catch (e) {
      dot.className = 'dot error';
      txt.textContent = 'Unreachable';
    }
  }
}
refresh();
setInterval(refresh, 60000);
</script>
</body>
</html>
```

- [ ] **Step 3: Create robots.txt**

`/home/alan/arath/fishing_reports/landing/robots.txt`:

```
User-agent: *
Allow: /

Sitemap: https://pnwbite.com/sitemap.xml
```

- [ ] **Step 4: Create sitemap.xml**

`/home/alan/arath/fishing_reports/landing/sitemap.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://pnwbite.com/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://pikeminnow.pnwbite.com/</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://salmon.pnwbite.com/</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
</urlset>
```

- [ ] **Step 5: Create .gitignore**

```
.DS_Store
*.swp
node_modules/
```

- [ ] **Step 6: Smoke test locally**

```bash
cd /home/alan/arath/fishing_reports/landing
python3 -m http.server 18000 &
SERVER_PID=$!
sleep 1
curl -s http://127.0.0.1:18000/ | grep -E 'PNW Bite|data-host'
curl -s http://127.0.0.1:18000/robots.txt
kill $SERVER_PID
```

Expected: HTML loads, robots.txt loads. Open http://127.0.0.1:18000/ in a browser; confirm both cards show "Unreachable" (the apps aren't on pnwbite.com yet) — that's fine for now.

- [ ] **Step 7: Commit**

```bash
cd /home/alan/arath/fishing_reports/landing
git add index.html robots.txt sitemap.xml .gitignore
git commit -m "feat: landing page for pnwbite.com with live status badges"
```

---

# Phase D: Migration day runbook

## Task 12: Migration day execution

This task is the runbook for cutover day. It's mostly manual dashboard work; we run through it sequentially. Each step has a verification.

- [ ] **Step 1: Push GitHub repos**

```bash
# salmon
cd /home/alan/arath/fishing_reports/salmon
git remote add origin https://github.com/<user>/salmon.git
git push -u origin master

# pikeminnow
cd /home/alan/arath/fishing_reports/pikeminnow
git remote add origin https://github.com/<user>/pikeminnow.git
git push -u origin master

# landing
cd /home/alan/arath/fishing_reports/landing
git remote add origin https://github.com/<user>/landing.git
git push -u origin master
```

(Replace `<user>` with the actual GitHub user/org name. The user supplied that the repos are public.)

Expected: 3 successful pushes to GitHub. Verify each repo is visible at github.com.

- [ ] **Step 2: Add salmon service to Railway**

In the `pnwbite` Railway project (id `77a2a9f0-38b4-4937-979f-cab2edad57e3`):

1. Click **+ New** → **GitHub Repo**.
2. Select the salmon repo.
3. Service name: `salmon`.
4. Wait for build to complete (Dockerfile build). ~2-3 minutes.
5. Once green, click on the service → **Variables** → add:
   - `DATA_DIR` = `/data`
   - `CLOUDFLARE_PURGE_TOKEN` = `<token>` (created in Cloudflare dashboard with `Cache Purge` scope on `pnwbite.com` zone)
   - `CLOUDFLARE_ZONE_ID` = `<id>` (visible in Cloudflare dashboard for `pnwbite.com`)
6. **Settings** → **Volumes** → add a 5GB volume mounted at `/data`.
7. Trigger a redeploy (so the new env vars + volume take effect).

Verify: service shows green status, logs show "Scheduler started; jobs: ['daily_report', 'regs_refresh']".

- [ ] **Step 3: Add pikeminnow service to Railway**

Same as Step 2 but for pikeminnow:

1. **+ New** → **GitHub Repo** → pikeminnow.
2. Service name: `pikeminnow`.
3. Variables: `DATA_DIR=/data`. (Cloudflare purge env vars optional; pikeminnow doesn't have a midday refresh.)
4. Volumes: 5GB at `/data`.
5. Redeploy.

Verify: service green, logs show scheduler started.

- [ ] **Step 4: First warmup runs**

The `maybe_warmup()` call in each `entrypoint.py` triggers an immediate report generation if `report.html` doesn't exist. Wait 1-2 minutes after first deploy and check:

```bash
# Get each service's preview URL from the Railway dashboard,
# e.g. salmon-production-abc.up.railway.app

curl -s https://salmon-production-XXX.up.railway.app/health
curl -s https://pikeminnow-production-YYY.up.railway.app/health
```

Expected: JSON with `report_html_size > 0` for both.

If `report_html_size == 0`, check Railway logs for errors. Common issue: source scrapers fail because of cold-start outbound network restrictions (rare).

- [ ] **Step 5: Add custom domains in Railway + Cloudflare DNS**

For each service in Railway:

1. **Settings** → **Domains** → **Custom Domain**.
2. Enter `salmon.pnwbite.com` (or `pikeminnow.pnwbite.com`).
3. Railway shows a CNAME target (e.g. `salmon-production-abc.up.railway.app`).
4. Copy the CNAME target.

In Cloudflare dashboard for `pnwbite.com` zone → **DNS** → **Records**:

```
Type: CNAME
Name: salmon
Target: salmon-production-abc.up.railway.app
Proxy status: Proxied (orange cloud ON)
TTL: Auto
```

Same for `pikeminnow`.

- [ ] **Step 6: Set Cloudflare SSL/TLS to Full (strict)**

In Cloudflare dashboard → **SSL/TLS** → **Overview** → set encryption mode to **Full (strict)**.

Wait 5-15 minutes for Universal SSL cert to provision for the new subdomains.

- [ ] **Step 7: Add Cloudflare Cache Rule**

In Cloudflare dashboard → **Caching** → **Cache Rules** → **Create Rule**:

```
Rule name: pnwbite app caching
If: hostname is in [pikeminnow.pnwbite.com, salmon.pnwbite.com]
Then:
  - Cache eligibility: Eligible for cache
  - Edge TTL: Override origin → 24 hours
  - Browser TTL: Override origin → 1 hour
```

Save and deploy.

- [ ] **Step 8: Verify subdomain HTTPS works**

```bash
curl -sSL https://salmon.pnwbite.com/ -o /tmp/salmon-prod.html -w "HTTP %{http_code} · %{size_download} bytes\n"
curl -sSL https://pikeminnow.pnwbite.com/ -o /tmp/pm-prod.html -w "HTTP %{http_code} · %{size_download} bytes\n"
grep -oE '<title>[^<]+</title>' /tmp/salmon-prod.html /tmp/pm-prod.html
curl -sSL https://salmon.pnwbite.com/health
curl -sSL https://pikeminnow.pnwbite.com/health
curl -sSL https://salmon.pnwbite.com/robots.txt
curl -sSL https://salmon.pnwbite.com/sitemap.xml
```

Expected: HTTP 200 from each, titles match, JSON health, robots.txt + sitemap.xml correct.

- [ ] **Step 9: Deploy landing page to Cloudflare Pages**

In Cloudflare dashboard → **Workers & Pages** → **Pages** → **Create a project** → **Connect to Git** → select the `landing` repo.

Build settings:
- Framework preset: None
- Build command: (leave empty)
- Build output directory: `/`

Click **Save and Deploy**. Wait for deployment (usually 30-60 seconds).

After deploy, click on the project → **Custom domains** → **Set up a custom domain** → `pnwbite.com`. Cloudflare auto-wires it (since the domain is registered through them).

Also add `www.pnwbite.com` and configure as a redirect to apex.

- [ ] **Step 10: Verify apex landing page**

```bash
curl -sSL https://pnwbite.com/ -o /tmp/landing.html -w "HTTP %{http_code} · %{size_download} bytes\n"
grep -oE 'PNW Bite|data-host' /tmp/landing.html | head -5
curl -sSL https://pnwbite.com/robots.txt
curl -sSL https://pnwbite.com/sitemap.xml
```

Expected: HTTP 200, landing markup present, robots.txt + sitemap.xml correct.

- [ ] **Step 11: Mobile smoke test**

Open these on iPhone Safari and Android Chrome:

```
https://pnwbite.com/
https://salmon.pnwbite.com/
https://pikeminnow.pnwbite.com/
```

Verify:
- Landing page status badges show "Fresh (Xh ago)".
- Salmon report: tabs are tappable, dropdown works, day-strip horizontally scrolls without overflowing the viewport, font is readable.
- Pikeminnow report: dropdown works, hourly table fits or scrolls, font is readable.

If any layout is broken: file a follow-up; do CSS-only patches and re-push to redeploy.

- [ ] **Step 12: Submit subdomains to Google Search Console**

Visit https://search.google.com/search-console.

For each property — `https://pnwbite.com/`, `https://salmon.pnwbite.com/`, `https://pikeminnow.pnwbite.com/`:

1. Click **Add property** → **URL prefix** → enter the URL.
2. Verify ownership via DNS TXT record (Cloudflare-easy) or HTML file upload.
3. Once verified, submit the sitemap: **Sitemaps** → enter `sitemap.xml` → **Submit**.

Expected: each property is verified and the sitemap shows "Success" within a few hours.

- [ ] **Step 13: Tailscale parallel run note**

Don't change anything on the local NUC yet. Tailscale Serve continues to expose the local versions. Set a calendar reminder for Day 7 to re-evaluate.

- [ ] **Step 14: Final commit (HANDOFF updates)**

Update both `HANDOFF.md` files (salmon and pikeminnow) with a "Phase 1 deployment" section noting:
- Live URLs: https://salmon.pnwbite.com, https://pikeminnow.pnwbite.com
- Apex: https://pnwbite.com
- Railway project ID
- Cron times stay the same; APScheduler in-process now
- Tailscale parallel for ~1 week
- Phase 2 starts Day 7+

```bash
cd /home/alan/arath/fishing_reports/salmon
# Edit HANDOFF.md to add the Phase 1 section
git add HANDOFF.md
git commit -m "docs: Phase 1 public deployment shipped"
git push

cd /home/alan/arath/fishing_reports/pikeminnow
# Same
git add HANDOFF.md
git commit -m "docs: Phase 1 public deployment shipped"
git push
```

Phase 1 complete.

---

## Plan self-review

Looking at the plan against the spec:

**Spec coverage:**
- §2 In Phase 1 → all items mapped:
  - Containerize both apps → Tasks 7, 10
  - Deploy to Railway services → Task 12 (manual)
  - Volumes at /data → Tasks 7, 10 + Task 12
  - Custom domains → Task 12 step 5
  - Cloudflare proxy + SSL Full(strict) → Task 12 steps 5-6
  - Cache Rules + cron-driven purge → Tasks 3, 6, 12 step 7
  - Landing page on Cloudflare Pages → Tasks 11, 12 step 9
  - Mobile review/fixes → Task 12 step 11
  - Pikeminnow L1 retrofit → Task 8
  - robots.txt, sitemap.xml → Tasks 4, 10, 11
  - OG meta tags → Tasks 5, 10
  - Search Console submission → Task 12 step 12
  - Tailscale parallel run → Task 12 step 13 (and beyond plan scope on Day 7+)
- §10 Risks: addressed implicitly via verification steps in Task 12.
- §12 Acceptance criteria: covered by Task 12's verification steps.

**Placeholder scan:** No "TBD/TODO/handle edge cases." Each step has concrete code or commands.

**Type consistency:** `default_root()` defined in Task 2 used in subsequent tasks. `purge_cache()` defined in Task 3 used in Tasks 1, 6. `register_jobs()` and `maybe_warmup()` consistent across Tasks 1 and 9.

**Two notes for executors:**

1. **Task 8 (pikeminnow retrofit)** is the riskiest task — no test suite, working production code. Snapshot output before changes; diff after; only commit if the diff is timestamps-only.

2. **Task 12 (migration day)** assumes manual dashboard access. The dashboard steps can't be fully automated by an agent; user does these. Each agent-runnable step has a `curl` verification.

---

## Execution choice

Plan complete and saved to `docs/superpowers/plans/2026-05-08-public-deploy-phase-1.md`.

Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration. Good fit since most tasks are mechanical.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
