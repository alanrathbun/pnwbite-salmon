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
