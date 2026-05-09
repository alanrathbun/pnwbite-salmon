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
    sched.add_job(_run_pamphlet_refresh, CronTrigger(hour=7, minute=0), id="pamphlet_refresh")
    sched.add_job(_run_regs, CronTrigger(hour=12, minute=0), id="regs_refresh")


def _run_daily() -> None:
    log.info("Running daily report job")
    from fishing_report import main as run_report
    run_report()
    _safe_purge()


def _run_pamphlet_refresh() -> None:
    log.info("Running pamphlet refresh check")
    from regs.wdfw_pamphlet_refresh import check_for_new_pamphlet
    try:
        check_for_new_pamphlet()
    except Exception as e:
        log.exception("pamphlet refresh failed: %s", e)


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
