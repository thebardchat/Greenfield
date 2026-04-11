from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_patients():
    ...


@router.post("/")
async def create_patient():
    ...


@router.get("/{patient_id}")
async def get_patient(patient_id: str):
    ...


@router.patch("/{patient_id}")
async def update_patient(patient_id: str):
    ...
