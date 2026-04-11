from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_credentials():
    ...


@router.post("/")
async def create_credential():
    ...


@router.get("/expiring")
async def list_expiring():
    """Credentials expiring within N days."""
    ...


@router.get("/{credential_id}")
async def get_credential(credential_id: str):
    ...


@router.patch("/{credential_id}")
async def update_credential(credential_id: str):
    ...
