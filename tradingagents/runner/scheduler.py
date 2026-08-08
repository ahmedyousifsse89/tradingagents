"""Cron scheduling for unattended runs.

APScheduler is an optional dependency (``pip install -e ".[server]"``). The
scheduler holds a single job; ``coalesce`` and ``max_instances=1`` mean a
backlog of missed fires collapses into one run rather than stampeding the
broker after an outage.

A scheduled fire that arrives while a run is in flight is dropped and logged.
That is deliberate — see :class:`~tradingagents.runner.runner.TradingRunner`.
"""

from __future__ import annotations

import logging
from typing import Optional

from .runner import RunnerBusy, TradingRunner

logger = logging.getLogger(__name__)


class RunScheduler:
    """Wraps an APScheduler background scheduler around a :class:`TradingRunner`."""

    JOB_ID = "tradingagents-scheduled-run"

    def __init__(self, runner: TradingRunner, scheduler=None):
        self.runner = runner
        self.config = runner.config
        self._scheduler = scheduler
        self._started = False

    def _build_scheduler(self):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise ImportError(
                "APScheduler is required for scheduled runs. "
                'Install it with: pip install -e ".[server]"'
            ) from exc
        return BackgroundScheduler(timezone=self.config.get("schedule_timezone", "UTC"))

    def start(self) -> bool:
        """Start the cron job. Returns False when scheduling is disabled."""
        if not self.config.get("schedule_enabled", False):
            logger.info("scheduler not started: schedule_enabled is False")
            return False
        if self._started:
            return True

        from apscheduler.triggers.cron import CronTrigger

        if self._scheduler is None:
            self._scheduler = self._build_scheduler()

        cron = self.config.get("schedule_cron", "30 13 * * 1-5")
        self._scheduler.add_job(
            self._fire,
            CronTrigger.from_crontab(
                cron, timezone=self.config.get("schedule_timezone", "UTC")
            ),
            id=self.JOB_ID,
            replace_existing=True,
            # Collapse a backlog of missed fires into one, and never let two
            # runs overlap.
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600,
        )
        self._scheduler.start()
        self._started = True
        logger.info(
            "scheduler started: cron %r in %s",
            cron,
            self.config.get("schedule_timezone", "UTC"),
        )
        return True

    def shutdown(self, wait: bool = False) -> None:
        if self._scheduler is not None and self._started:
            self._scheduler.shutdown(wait=wait)
            self._started = False

    @property
    def running(self) -> bool:
        return self._started

    def next_run_time(self) -> Optional[str]:
        if self._scheduler is None or not self._started:
            return None
        job = self._scheduler.get_job(self.JOB_ID)
        if job is None or job.next_run_time is None:
            return None
        return job.next_run_time.isoformat()

    def _fire(self) -> None:
        try:
            record = self.runner.run_once(trigger="schedule")
            logger.info(
                "scheduled run %s finished with status %s", record.run_id, record.status
            )
        except RunnerBusy as exc:
            logger.warning("scheduled run skipped: %s", exc)
        except Exception:
            # Never let an exception escape into APScheduler's thread — it
            # would kill the job and stop all future fires silently.
            logger.exception("scheduled run raised")
