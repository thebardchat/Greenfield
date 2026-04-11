from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_facilities():
    ...


@router.post("/")
async def create_facility():
    ...


@router.get("/{facility_id}")
async def get_facility(facility_id: str):
    ...


@router.patch("/{facility_id}")
async def update_facility(facility_id: str):
    ...


@router.get("/{facility_id}/assignments")
async def list_assignments(facility_id: str):
    ...


@router.post("/{facility_id}/assignments")
async def create_assignment(facility_id: str):
    ...
