from fastapi import APIRouter

router = APIRouter()


@router.get("/claims-summary")
async def claims_summary():
    """Aggregate claim stats by status, facility, date range."""
    ...


@router.get("/productivity")
async def productivity_report():
    """Biller/coder throughput metrics."""
    ...


@router.get("/credentials-status")
async def credentials_status():
    """Credential expiry overview across org."""
    ...


@router.get("/export")
async def export_report():
    """Generate CSV/txt export for billing software ingest."""
    ...
