from fastapi import APIRouter

router = APIRouter()


@router.post("/chat")
async def cruncher_chat():
    """Interactive AI assistant for claim Q&A and coder help."""
    ...


@router.post("/analyze-claim/{claim_id}")
async def analyze_claim(claim_id: str):
    """AI analysis of a specific claim — flag issues, suggest codes."""
    ...


@router.post("/denial-analysis/{claim_id}")
async def denial_analysis(claim_id: str):
    """Analyze denial reason and suggest appeal strategy."""
    ...
