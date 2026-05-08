# Public Deployment — Phase 1 Design

**Status:** Draft for implementation
**Date:** 2026-05-08
**Project root for spec:** `/home/alan/arath/fishing_reports/salmon/docs/superpowers/specs/`
**Apps in scope:** `/home/alan/arath/fishing_reports/pikeminnow/`, `/home/alan/arath/fishing_reports/salmon/`
**Successor of:** `2026-04-27-salmon-report-design.md` (salmon v1)

## 1. Goal

Migrate both fishing-report apps (pikeminnow and salmon) from local Tailscale-only deployment to public web availability under the `pnwbite.com` parent domain. Phase 1 deploys both apps as-is (no new app features, no auth, no AI, no photos) on Railway, fronted by Cloudflare for CDN/TLS/DDoS protection, with a small static landing page at the apex. Tailscale stays running for ~1 week as a parallel safety net before being torn down.

## 2. Scope

### In Phase 1
- Containerize both apps with single-process architecture (in-process APScheduler + HTTP server).
- Deploy each app as its own Railway service inside the existing `pnwbite` Railway project (`77a2a9f0-38b4-4937-979f-cab2edad57e3`).
- Mount per-service Railway volumes at `/data` for state persistence.
- Custom domains via Cloudflare DNS: `pikeminnow.pnwbite.com`, `salmon.pnwbite.com`.
- Cloudflare proxy enabled (orange cloud) on both subdomains; SSL Full (strict).
- Cloudflare Cache Rules: 24h edge TTL on report HTML, 1h browser cache.
- Cron-driven Cloudflare cache purge after each report regeneration.
- Apex landing page at `pnwbite.com` (Cloudflare Pages from `pnwbite/landing` repo) with live status badges fetched from each subdomain's `/health` endpoint.
- Mobile layout review on iPhone Safari and Android Chrome with in-place CSS fixes.
- Pikeminnow L1 retrofit: respect `DATA_DIR` env var around hardcoded paths.
- `robots.txt` (allow all, disallow `/health`) and `sitemap.xml` per subdomain + apex.
- Open Graph + Twitter card meta tags in each app's `<head>`.
- Submit each subdomain to Google Search Console on cutover day.
- Tailscale parallel run for ~1 week, then teardown of local cron + tailscale serve config.

### Out of scope (deferred)
- **Phase 2:** Email-code auth (passwordless login), user accounts, user preferences (favorites), Postgres database, Resend or equivalent email sender, salmon launch hero photos via Cloudinary, full L2/L3 pikeminnow retrofit.
- **Phase 3:** AI features — forecast explanation ("why POOR?"), natural-language query, personalized weekend summary. Anthropic API integration.
- **Phase 4:** Trip planner, bait-rule reasoning, catch logging.
- **Phase 5+ (or never):** Pikeminnow photos, mobile redesign beyond fixes, additional fishing-report apps (`bank.pnwbite.com`, walleye), shared backend extraction.

### Out of scope (won't do)
- Beta gates / invite codes / domain-restricted signups (decided against; the data is informational and public).
- Auth in Phase 1 (Phase 2 only).
- Static-only hosting via Cloudflare Pages (rejected because Phase 2 needs a real backend; static-only would force a rebuild).

## 3. Architecture overview

```
                     pnwbite.com (Cloudflare DNS + proxy + free CDN)
                     ┌───────────────────────────────────────────────┐
                     │  Apex landing page (Cloudflare Pages, free)   │
                     │  Live status badges fetch each app's /health  │
                     └───────────────────────────────────────────────┘
                                │                      │
                       Cloudflare proxy        Cloudflare proxy
                                │                      │
                                ▼                      ▼
                     ┌─────────────────────┐  ┌─────────────────────┐
                     │ Railway: pikeminnow │  │ Railway: salmon     │
                     │  ├─ APScheduler     │  │  ├─ APScheduler     │
                     │  │   05:30 daily    │  │  │   05:35 daily    │
                     │  │                  │  │  │   12:00 regs     │
                     │  └─ HTTP server     │  │  └─ HTTP server     │
                     │     :$PORT          │  │     :$PORT          │
                     │  Volume: /data      │  │  Volume: /data      │
                     └─────────────────────┘  └─────────────────────┘
```

**Key changes from local v1:**

1. **No more Tailscale Serve.** Apps bind to `0.0.0.0:$PORT` (Railway-provided). Public traffic flows through Cloudflare → Railway over HTTPS.
2. **In-process cron via APScheduler.** Single Python process per service handles both schedule and serving. No external cron daemon; no separate Railway services for cron.
3. **State on Railway volumes** (`/data`, default 5GB tier). The `Storage` shim's root becomes `/data` instead of the project directory.
4. **Logs to stdout** (Railway captures); no file-based logs.
5. **Cloudflare** handles TLS, edge caching, DDoS, DNS. Cache TTL is 24h with cron-driven purge for sub-hour updates after the salmon 12:00 regs refresh.
6. **`numReplicas = 1`** is required because the scheduler is in-process. Multiple replicas would double-run cron jobs.

## 4. File structure changes (per app)

```
fishing_reports/<app>/
├── Dockerfile               # NEW
├── railway.toml             # NEW
├── entrypoint.py            # NEW: launches scheduler + server in one process
├── scheduler.py             # NEW: APScheduler job registration
├── ...                      # existing code, plus DATA_DIR env-var handling
```

### Dockerfile (template, swap names for each app)

```dockerfile
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATA_DIR=/data
VOLUME /data
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-u", "entrypoint.py"]
```

### railway.toml

```toml
[build]
builder = "DOCKERFILE"

[deploy]
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
numReplicas = 1
```

### entrypoint.py

```python
"""Entry point for Railway: APScheduler in background + HTTP server in main thread."""
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from zoneinfo import ZoneInfo

import scheduler
import fishing_server

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("entrypoint")

PACIFIC = ZoneInfo("America/Los_Angeles")


def main():
    sched = BackgroundScheduler(timezone=PACIFIC)
    scheduler.register_jobs(sched)
    sched.start()
    log.info("Scheduler started; jobs: %s", [j.id for j in sched.get_jobs()])

    scheduler.maybe_warmup()  # run daily job once if no report yet

    fishing_server.main()  # blocks


if __name__ == "__main__":
    main()
```

### scheduler.py (per app — schedules differ)

**Salmon:**
```python
from apscheduler.triggers.cron import CronTrigger

def register_jobs(sched):
    sched.add_job(_run_daily, CronTrigger(hour=5, minute=35), id="daily_report")
    sched.add_job(_run_regs, CronTrigger(hour=12, minute=0), id="regs_refresh")

def _run_daily():
    from fishing_report import main
    main()
    _purge_cloudflare_cache()

def _run_regs():
    from regs_refresh import main
    main()
    _purge_cloudflare_cache()

def maybe_warmup():
    import os
    from pathlib import Path
    data_dir = Path(os.environ.get("DATA_DIR", "."))
    if not (data_dir / "report.html").exists():
        _run_daily()
```

**Pikeminnow:** same shape, single daily job at 05:30, no regs refresh.

### Pikeminnow L1 retrofit

In `fishing_report.py` and `fishing_server.py`, replace hardcoded paths with:

```python
import os
from pathlib import Path
DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent)))

OUTPUT_HTML = DATA_DIR / "report.html"
NWS_GRID_CACHE = DATA_DIR / ".nws_grid_cache.json"
CPUE_CACHE = DATA_DIR / ".cpue_2025_cache.json"
# ...etc for every cache file
```

No structural refactor; just env-var-aware path constants. ~30 minutes of work.

## 5. DNS + Railway setup

### One-time manual setup (user)

1. **Create GitHub repos** — `pnwbite/pikeminnow`, `pnwbite/salmon`, `pnwbite/landing` (public).
2. **Push current local state** to each app repo.
3. **Empty Railway project** `pnwbite` already created (`77a2a9f0-38b4-4937-979f-cab2edad57e3`).
4. **Add 2 services** to the project (after Dockerfiles land in repos):
   - `pikeminnow` linked to GitHub `pnwbite/pikeminnow`
   - `salmon` linked to GitHub `pnwbite/salmon`
   - For each, set env: `DATA_DIR=/data`, `CLOUDFLARE_PURGE_TOKEN=<token>` (token created in step 7).
   - Mount volume at `/data` (5GB default).
5. **Custom domains in Railway** for each service: enter `<app>.pnwbite.com`, copy the CNAME target.
6. **Cloudflare DNS records** in `pnwbite.com` zone:
   ```
   pikeminnow  CNAME  <pikeminnow>.up.railway.app  Proxied
   salmon      CNAME  <salmon>.up.railway.app      Proxied
   ```
7. **Cloudflare API token** with `Cache Purge` scope on `pnwbite.com` zone. Add to Railway env as `CLOUDFLARE_PURGE_TOKEN`. Add zone ID to env as `CLOUDFLARE_ZONE_ID`.
8. **Cloudflare SSL/TLS mode**: Full (strict).
9. **Cloudflare Cache Rules** (one rule covering both subdomains):
   - Match: `Hostname` matches `pikeminnow.pnwbite.com OR salmon.pnwbite.com`
   - Edge Cache TTL: 24 hours
   - Browser Cache TTL: 1 hour
10. **Cloudflare Pages** for `pnwbite/landing` repo. Apex `pnwbite.com` auto-wires (Cloudflare-registered domain).
11. **Submit each subdomain to Google Search Console** post-launch.

### Cache purge implementation (~15 lines)

```python
import os
import requests

def _purge_cloudflare_cache():
    token = os.environ.get("CLOUDFLARE_PURGE_TOKEN")
    zone = os.environ.get("CLOUDFLARE_ZONE_ID")
    if not (token and zone):
        return
    try:
        r = requests.post(
            f"https://api.cloudflare.com/client/v4/zones/{zone}/purge_cache",
            headers={"Authorization": f"Bearer {token}"},
            json={"purge_everything": True},
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:
        # Log but don't fail the cron run.
        import logging
        logging.getLogger("cache_purge").warning("purge failed: %s", e)
```

## 6. Mobile layout review

Phase 1 is "make it work," not redesign. Test on iPhone Safari + Android Chrome at 390/412/768px widths. Fix:

- Tables overflowing without horizontal scroll
- Touch targets <44px
- Body text <16px (causes Safari auto-zoom)
- Tab/button rows wrapping awkwardly
- Salmon's day-strip overflowing horizontally on small screens

Estimated 2-4 hours per app, mostly CSS adjustments. Done during or shortly after migration day cutover.

## 7. Landing page (`pnwbite.com`)

Repo: `pnwbite/landing`. Single `index.html` with embedded CSS + ~30 lines JS. Cloudflare Pages auto-deploys on push to main.

Content (Option B — live status badges):

```
┌────────────────────────────────────────────────┐
│           PNW Bite                             │
│   Daily Pacific Northwest fishing reports      │
│                                                │
│  ┌──────────────────┐  ┌──────────────────┐   │
│  │  Pikeminnow      │  │  Salmon &        │   │
│  │  Sport-Reward    │  │  Steelhead       │   │
│  │                  │  │                  │   │
│  │  ● Fresh         │  │  ● Fresh         │   │
│  │  Updated 3h ago  │  │  Updated 5h ago  │   │
│  │                  │  │                  │   │
│  │  Open report →   │  │  Open report →   │   │
│  └──────────────────┘  └──────────────────┘   │
│                                                │
│  Made by Alan · alan@pnwbite.com (or none)    │
└────────────────────────────────────────────────┘
```

JS fetches each subdomain's `/health` JSON every 60s, derives "Fresh / Updated Nh ago / Stale" from `report_html_mtime`. Stale = >25 hours old (one missed cron).

Files: `index.html`, `robots.txt`, `sitemap.xml`, optional `favicon.ico`.

## 8. SEO

### robots.txt (per subdomain + apex, server-rendered for subdomains)

```
User-agent: *
Allow: /
Disallow: /health

Sitemap: https://<host>/sitemap.xml
```

### sitemap.xml (per subdomain + apex)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://<host>/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
```

### Open Graph + Twitter card meta (in each app's `<head>`)

```html
<meta property="og:title" content="<App Name>" />
<meta property="og:description" content="<one-line description>" />
<meta property="og:url" content="https://<host>/" />
<meta property="og:type" content="website" />
<meta name="twitter:card" content="summary" />
```

No `og:image` in Phase 1 (photos deferred to Phase 2).

## 9. Cutover plan

### Migration day (~3-4 hours)

```
T+0:00  Push GitHub commits with Dockerfile, entrypoint.py, scheduler.py,
        path retrofits, robots.txt + sitemap.xml in server, OG meta in renderer,
        Cloudflare cache-purge integration. Push pnwbite/landing repo content.

T+0:30  In Railway pnwbite project: add 2 services from GitHub repos.
        Verify both build and serve report.html on .up.railway.app preview URLs.

T+1:00  First warmup runs complete; /data populated on each service.

T+1:30  Add custom domains in Railway → CNAMEs in Cloudflare → SSL Full(strict)
        → Cache Rules → CLOUDFLARE_PURGE_TOKEN + CLOUDFLARE_ZONE_ID set.

T+2:00  Deploy landing page (Cloudflare Pages, auto-wires apex pnwbite.com).

T+2:30  External smoke tests:
        - https://pnwbite.com loads landing page with live status badges
        - https://pikeminnow.pnwbite.com loads report
        - https://salmon.pnwbite.com loads report
        - Mobile devices verify layout
        - Submit each subdomain to Google Search Console

T+3:00  Mobile fixes if needed (CSS-only push, auto-redeploy).

T+3:30  Phase 1 shipped.
```

### Parallel run + Tailscale teardown

- **Days 1-7:** Both routes work. Public URL is the new front door; Tailscale URLs continue as backup.
- **Day 7 checkpoint:** confirm Railway crons ran every day, no error spikes in Cloudflare analytics or Railway logs.
- **Day 8+:** remove crontab entries, stop local servers, remove `tailscale serve` configs.

If anything is flaky at Day 7, extend parallel run another week.

## 10. Risks

1. **Cron timing / timezone.** Railway containers are UTC. APScheduler's `BackgroundScheduler(timezone=PACIFIC)` handles conversion. Verify by inspecting first scheduled-run log entries for correct local time.
2. **Volume persistence.** Railway volumes are persistent across deploys but lost on service deletion. Don't delete the service.
3. **First-time TLS.** Cloudflare Universal SSL provisioning takes 5-15 minutes for new subdomains. Expect TLS errors during this window.
4. **DNS propagation.** Usually 5 minutes for Cloudflare-registered domains; can be up to 24h.
5. **Pikeminnow path retrofit regression.** No test suite. Mitigation: keep local Tailscale running; compare outputs side-by-side post-deploy.
6. **Cache purge token leak.** Restricted-scope token (`Cache Purge` only on `pnwbite.com` zone). Worst case if leaked: someone purges your cache, no real damage. Rotate quarterly.
7. **APScheduler missed run on container restart.** APScheduler doesn't persist missed runs; if Railway restarts the container during a scheduled time, that run is skipped. Mitigation: warmup-on-startup catches missed daily runs but not missed regs refreshes. Acceptable for v1.
8. **Cloudflare cache rules conflict.** If existing zone-wide rules exist, the new app-specific rule may not apply as expected. Verify cache headers via `curl -I` after deploy.

## 11. Phase 2 hooks

Architectural seams left for Phase 2 (auth + DB + photos):

- **`Storage` shim ready for `read_user_pref(uid, key)` extension** — same atomic-write semantics, swap implementation to Postgres.
- **Two-tier storage path:** `/data` for caches (NWS, FPC, DART), Postgres for users/sessions/preferences.
- **AI integration point:** the renderer separates `report_data.json` from HTML output. Phase 3's `/ai` endpoint reads `report_data.json` as Claude context.
- **Auth-free routes today; cookie middleware added in Phase 2 doesn't change existing routes.**

## 12. Acceptance criteria

- [ ] Both apps containerized and deployed to Railway services in the `pnwbite` project.
- [ ] Both apps reachable at `https://pikeminnow.pnwbite.com` and `https://salmon.pnwbite.com` over HTTPS via Cloudflare.
- [ ] Apex `https://pnwbite.com` shows landing page with two app links and live status badges.
- [ ] Mobile (iPhone Safari, Android Chrome) renders both reports legibly without pinch-zoom.
- [ ] Daily cron runs at 05:30 (pikeminnow) and 05:35 (salmon) in Pacific time, observed in logs.
- [ ] Salmon's 12:00 regs refresh runs and triggers Cloudflare cache purge.
- [ ] `robots.txt`, `sitemap.xml` accessible per subdomain.
- [ ] Each subdomain submitted to Google Search Console.
- [ ] Tailscale URLs continue working in parallel for ~1 week.
- [ ] Volumes survive a redeploy (push a no-op change; verify `/data/report.html` not regenerated unexpectedly).
- [ ] No regression in pikeminnow output content vs pre-migration local version.

## 13. File structure (final shape after Phase 1)

```
pikeminnow/
├── Dockerfile                # NEW
├── railway.toml              # NEW
├── entrypoint.py             # NEW
├── scheduler.py              # NEW
├── fishing_report.py         # MODIFIED: DATA_DIR env var
├── fishing_server.py         # MODIFIED: DATA_DIR env var, robots.txt, sitemap.xml routes
├── requirements.txt          # NEW (pikeminnow has none today): apscheduler, requests
├── HANDOFF.md                # MODIFIED: post-migration update
└── docs/superpowers/specs/   # NEW: link to this spec
    └── README.md             # cross-reference

salmon/
├── Dockerfile                # NEW
├── railway.toml              # NEW
├── entrypoint.py             # NEW
├── scheduler.py              # NEW
├── fishing_report.py         # MODIFIED: cache-purge call after main()
├── regs_refresh.py           # MODIFIED: cache-purge call after main()
├── fishing_server.py         # MODIFIED: bind 0.0.0.0:$PORT, robots.txt, sitemap.xml routes
├── render.py                 # MODIFIED: OG meta tags
├── storage.py                # MODIFIED: root from DATA_DIR env
├── requirements.txt          # MODIFIED: add apscheduler
├── HANDOFF.md                # MODIFIED: post-migration update
└── docs/superpowers/specs/2026-05-08-public-deploy-phase-1-design.md  # this spec

pnwbite/landing/  (new repo)
├── index.html                # NEW (with embedded CSS + JS)
├── robots.txt                # NEW
├── sitemap.xml               # NEW
└── favicon.ico               # NEW (optional)
```
