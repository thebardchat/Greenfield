"""Patients router — CRUD with org-scoped access."""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.rbac import get_current_user, require_permission
from app.models.patient import Patient
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PatientResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date
    mrn: str | None
    ssn_last_four: str | None
    gender: str | None
    primary_insurance_name: str | None
    primary_insurance_id: str | None
    secondary_insurance_name: str | None
    secondary_insurance_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: date
    mrn: str | None = None
    ssn_last_four: str | None = None
    gender: str | None = None
    primary_insurance_name: str | None = None
    primary_insurance_id: str | None = None
    secondary_insurance_name: str | None = None
    secondary_insurance_id: str | None = None


class PatientUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    mrn: str | None = None
    ssn_last_four: str | None = None
    gender: str | None = None
    primary_insurance_name: str | None = None
    primary_insurance_id: str | None = None
    secondary_insurance_name: str | None = None
    secondary_insurance_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[PatientResponse])
async def list_patients(
    current_user: User = Depends(require_permission("patients:read")),
    db: AsyncSession = Depends(get_db),
    last_name: str | None = Query(None),
    mrn: str | None = Query(None),
):
    """List patients scoped to the user's organization, searchable by last_name and mrn."""
    query = select(Patient).where(Patient.deleted_at.is_(None))

    # Non-super-admins only see their own org's patients
    if current_user.role != "super_admin":
        query = query.where(Patient.organization_id == current_user.organization_id)

    if last_name is not None:
        query = query.where(Patient.last_name.ilike(f"%{last_name}%"))
    if mrn is not None:
        query = query.where(Patient.mrn == mrn)

    result = await db.execute(query.order_by(Patient.last_name, Patient.first_name))
    return result.scalars().all()


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    body: PatientCreate,
    current_user: User = Depends(require_permission("patients:write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a patient in the user's organization."""
    if current_user.role == "super_admin" and current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin must specify organization context",
        )

    patient = Patient(
        organization_id=current_user.organization_id,
        **body.model_dump(exclude_unset=True),
    )
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: uuid.UUID,
    current_user: User = Depends(require_permission("patients:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single patient by ID, scoped to org."""
    query = select(Patient).where(
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Patient.organization_id == current_user.organization_id)

    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: uuid.UUID,
    body: PatientUpdate,
    current_user: User = Depends(require_permission("patients:write")),
    db: AsyncSession = Depends(get_db),
):
    """Update a patient, scoped to org."""
    query = select(Patient).where(
        Patient.id == patient_id,
        Patient.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Patient.organization_id == current_user.organization_id)

    result = await db.execute(query)
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(patient, field, value)

    await db.commit()
    await db.refresh(patient)
    return patient
