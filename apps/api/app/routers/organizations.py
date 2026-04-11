from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_organizations():
    ...


@router.post("/")
async def create_organization():
    ...


@router.get("/{org_id}")
async def get_organization(org_id: str):
    ...


@router.patch("/{org_id}")
async def update_organization(org_id: str):
    ...
