from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login():
    """Authenticate user, return JWT pair."""
    ...


@router.post("/refresh")
async def refresh():
    """Refresh access token."""
    ...


@router.post("/logout")
async def logout():
    """Invalidate refresh token."""
    ...
