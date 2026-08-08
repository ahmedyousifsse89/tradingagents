"""Process entry point: the API plus, optionally, the cron scheduler.

Railway runs this. One process serves HTTP and owns the scheduler thread, so
a scheduled run and an API-triggered run contend for the same runner lock and
can never overlap. Splitting them into separate services would lose that.

    python -m tradingagents.server.main
"""

from __future__ import annotations

import logging
import os

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.runner.runner import TradingRunner

from .app import create_app

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


_APP = None


def build():
    """Assemble runner, scheduler, and app from the environment-driven config.

    Memoised: a second call must not start a second scheduler thread, which
    would fire two runs per cron tick against the same account.
    """
    global _APP
    if _APP is not None:
        return _APP

    config = DEFAULT_CONFIG.copy()
    runner = TradingRunner(config)

    scheduler = None
    if config.get("schedule_enabled", False):
        from tradingagents.runner.scheduler import RunScheduler

        scheduler = RunScheduler(runner)
        scheduler.start()
    else:
        logger.info("scheduler disabled (set TRADINGAGENTS_SCHEDULE_ENABLED=true)")

    logger.info(
        "execution_enabled=%s execution_dry_run=%s alpaca_live=%s",
        config.get("execution_enabled"),
        config.get("execution_dry_run"),
        config.get("alpaca_live"),
    )
    _APP = create_app(config, runner=runner, scheduler=scheduler)
    return _APP


app = build()


def main() -> None:
    import uvicorn

    # Railway injects PORT; default matches the local docker-compose mapping.
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
