from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_claims():
    """List claims with filtering by status, facility, assignee, date range."""
    ...


@router.post("/")
async def create_claim():
    ...


@router.get("/{claim_id}")
async def get_claim(claim_id: str):
    ...


@router.patch("/{claim_id}")
async def update_claim(claim_id: str):
    ...


@router.post("/{claim_id}/transition")
async def transition_claim_status(claim_id: str):
    """Transition claim status with validation."""
    ...


@router.get("/{claim_id}/lines")
async def list_claim_lines(claim_id: str):
    ...


@router.post("/{claim_id}/lines")
async def add_claim_line(claim_id: str):
    ...
