"""Facilities router — CRUD with org-scoped access."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.rbac import get_current_user, require_permission
from app.models.facility import Facility
from app.models.user import User

router = APIRouter()


class FacilityResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    facility_type: str | None
    address: str | None
    city: str | None
    state: str | None
    zip: str | None
    phone: str | None
    npi: str | None
    tax_id: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class FacilityCreate(BaseModel):
    name: str
    facility_type: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    phone: str | None = None
    npi: str | None = None
    tax_id: str | None = None


class FacilityUpdate(BaseModel):
    name: str | None = None
    facility_type: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    phone: str | None = None
    npi: str | None = None
    tax_id: str | None = None
    is_active: bool | None = None


@router.get("/", response_model=list[FacilityResponse])
async def list_facilities(
    current_user: User = Depends(require_permission("facilities:read")),
    db: AsyncSession = Depends(get_db),
    is_active: bool = Query(True),
):
    """List facilities scoped to the user's organization."""
    query = select(Facility).where(
        Facility.deleted_at.is_(None),
        Facility.is_active == is_active,
    )
    # Non-super-admins only see their own org's facilities
    if current_user.role != "super_admin":
        query = query.where(Facility.organization_id == current_user.organization_id)

    result = await db.execute(query.order_by(Facility.name))
    return result.scalars().all()


@router.post("/", response_model=FacilityResponse, status_code=status.HTTP_201_CREATED)
async def create_facility(
    body: FacilityCreate,
    current_user: User = Depends(require_permission("facilities:write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a facility in the user's organization."""
    if current_user.role == "super_admin" and current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin must specify organization context",
        )

    facility = Facility(
        organization_id=current_user.organization_id,
        **body.model_dump(exclude_unset=True),
    )
    db.add(facility)
    await db.commit()
    await db.refresh(facility)
    return facility


@router.get("/{facility_id}", response_model=FacilityResponse)
async def get_facility(
    facility_id: uuid.UUID,
    current_user: User = Depends(require_permission("facilities:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single facility by ID, scoped to org."""
    query = select(Facility).where(
        Facility.id == facility_id,
        Facility.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Facility.organization_id == current_user.organization_id)

    result = await db.execute(query)
    facility = result.scalar_one_or_none()
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found")
    return facility


@router.patch("/{facility_id}", response_model=FacilityResponse)
async def update_facility(
    facility_id: uuid.UUID,
    body: FacilityUpdate,
    current_user: User = Depends(require_permission("facilities:write")),
    db: AsyncSession = Depends(get_db),
):
    """Update a facility, scoped to org."""
    query = select(Facility).where(
        Facility.id == facility_id,
        Facility.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Facility.organization_id == current_user.organization_id)

    result = await db.execute(query)
    facility = result.scalar_one_or_none()
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(facility, field, value)

    await db.commit()
    await db.refresh(facility)
    return facility
