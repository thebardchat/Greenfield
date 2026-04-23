"""arq worker entry point.

Start with:
    cd apps/worker
    arq app.main.WorkerSettings

Or via docker-compose (see docker-compose.yml):
    docker-compose up worker
"""

import logging
import os

from arq import cron
from arq.connections import RedisSettings

from .tasks.credential_expiry import check_credential_expiry
from .tasks.ocr_pipeline import process_document
from .tasks.report_generation import generate_report

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")


class WorkerSettings:
    """arq WorkerSettings — task registry and scheduling.

    Tasks:
      process_document       — OCR pipeline (enqueued per upload)
      check_credential_expiry — Daily credential expiry scan + alerts
      generate_report        — On-demand CSV/summary report generation
    """

    functions = [process_document, check_credential_expiry, generate_report]

    cron_jobs = [
        # Run credential expiry check daily at 07:00 UTC
        cron(check_credential_expiry, hour=7, minute=0),
    ]

    redis_settings = RedisSettings.from_dsn(REDIS_URL)

    # Keep concurrency low on Pi 5 (OCR is CPU-bound)
    max_jobs = int(os.getenv("WORKER_MAX_JOBS", "4"))

    max_tries = 3
    retry_jobs = True

    # OCR can take up to 5 min for large multi-page PDFs
    job_timeout = int(os.getenv("WORKER_JOB_TIMEOUT", "300"))

    health_check_interval = 30
    health_check_key = "claim-cruncher:worker:health"

    @staticmethod
    async def on_startup(ctx: dict) -> None:
        log.info("Worker started. Redis: %s", REDIS_URL)

    @staticmethod
    async def on_shutdown(ctx: dict) -> None:
        log.info("Worker shutting down.")

    @staticmethod
    async def on_job_start(ctx: dict) -> None:
        log.debug("Job started: %s args=%s", ctx.get("job_id"), ctx.get("args"))

    @staticmethod
    async def on_job_end(ctx: dict) -> None:
        log.debug("Job ended: %s", ctx.get("job_id"))
