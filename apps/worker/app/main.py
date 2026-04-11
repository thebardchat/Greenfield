"""arq worker entry point.

Run with: arq app.main.WorkerSettings
"""

from arq.connections import RedisSettings

from app.tasks.credential_expiry import check_credential_expiry
from app.tasks.ocr_pipeline import process_document
from app.tasks.report_generation import generate_report


async def startup(ctx):
    """Initialize DB connection pool for worker."""
    pass


async def shutdown(ctx):
    """Clean up resources."""
    pass


class WorkerSettings:
    functions = [process_document, check_credential_expiry, generate_report]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings()
    max_jobs = 4
    job_timeout = 600  # 10 minutes
