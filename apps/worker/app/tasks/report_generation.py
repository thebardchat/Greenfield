"""Report generation task.

Generates CSV/txt exports for billing software ingest
and summary reports for client dashboards.
"""


async def generate_report(ctx, report_type: str, organization_id: str, params: dict):
    """Generate a report and store the output file."""
    ...
