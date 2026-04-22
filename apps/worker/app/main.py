"""
arq worker entry point.

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

from .tasks.ocr_pipeline import process_document

log = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")

# ─────────────────────── Worker settings ─────────────────────────────


class WorkerSettings:
    """
    arq WorkerSettings class.  arq discovers this by module path.

    Tasks registered here:
      - process_document: OCR pipeline (enqueued by document upload endpoint)
    """

    # Task functions
    functions = [process_document]

    # Redis connection
    redis_settings = RedisSettings.from_dsn(REDIS_URL)

    # Concurrency — keep low on Pi 5 (CPU-bound OCR)
    max_jobs = int(os.getenv("WORKER_MAX_JOBS", "4"))

    # Retry settings
    max_tries = 3
    retry_jobs = True

    # Job timeout (seconds) — 300s for large multi-page PDFs
    job_timeout = int(os.getenv("WORKER_JOB_TIMEOUT", "300"))

    # Health poll interval
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
