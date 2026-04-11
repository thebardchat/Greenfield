"""Claims router — CRUD with org-scoped access and status transitions."""

import os
import sys
import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.rbac import get_current_user, require_permission
from app.models.claim import Claim
from app.models.user import User

# Import claim_status from shared package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "packages"))
from shared.claim_status import ClaimStatus, can_transition

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ClaimResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    facility_id: uuid.UUID
    patient_id: uuid.UUID
    claim_number: str | None
    form_type: str | None
    status: str
    date_of_service_from: date | None
    date_of_service_to: date | None
    total_charges: Decimal | None
    total_paid: Decimal | None
    provider_npi: str | None
    referring_npi: str | None
    place_of_service: str | None
    assigned_coder_id: uuid.UUID | None
    assigned_biller_id: uuid.UUID | None
    submitted_by_id: uuid.UUID | None
    notes: str | None
    flagged: bool
    flag_reason: str | None
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClaimCreate(BaseModel):
    facility_id: uuid.UUID
    patient_id: uuid.UUID
    claim_number: str | None = None
    form_type: str | None = None
    date_of_service_from: date | None = None
    date_of_service_to: date | None = None
    total_charges: Decimal | None = None
    provider_npi: str | None = None
    referring_npi: str | None = None
    place_of_service: str | None = None
    assigned_coder_id: uuid.UUID | None = None
    assigned_biller_id: uuid.UUID | None = None
    notes: str | None = None
    flagged: bool = False
    flag_reason: str | None = None
    priority: int = 0


class ClaimUpdate(BaseModel):
    facility_id: uuid.UUID | None = None
    patient_id: uuid.UUID | None = None
    claim_number: str | None = None
    form_type: str | None = None
    date_of_service_from: date | None = None
    date_of_service_to: date | None = None
    total_charges: Decimal | None = None
    total_paid: Decimal | None = None
    provider_npi: str | None = None
    referring_npi: str | None = None
    place_of_service: str | None = None
    assigned_coder_id: uuid.UUID | None = None
    assigned_biller_id: uuid.UUID | None = None
    notes: str | None = None
    flagged: bool | None = None
    flag_reason: str | None = None
    priority: int | None = None


class ClaimTransition(BaseModel):
    target_status: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[ClaimResponse])
async def list_claims(
    current_user: User = Depends(require_permission("claims:read")),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    facility_id: uuid.UUID | None = Query(None),
    assigned_coder_id: uuid.UUID | None = Query(None),
    assigned_biller_id: uuid.UUID | None = Query(None),
    flagged: bool | None = Query(None),
):
    """List claims scoped to the user's organization with optional filters."""
    query = select(Claim).where(Claim.deleted_at.is_(None))

    # Non-super-admins only see their own org's claims
    if current_user.role != "super_admin":
        query = query.where(Claim.organization_id == current_user.organization_id)

    if status_filter is not None:
        query = query.where(Claim.status == status_filter)
    if facility_id is not None:
        query = query.where(Claim.facility_id == facility_id)
    if assigned_coder_id is not None:
        query = query.where(Claim.assigned_coder_id == assigned_coder_id)
    if assigned_biller_id is not None:
        query = query.where(Claim.assigned_biller_id == assigned_biller_id)
    if flagged is not None:
        query = query.where(Claim.flagged == flagged)

    result = await db.execute(query.order_by(Claim.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(
    body: ClaimCreate,
    current_user: User = Depends(require_permission("claims:write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a claim in the user's organization."""
    if current_user.role == "super_admin" and current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin must specify organization context",
        )

    claim = Claim(
        organization_id=current_user.organization_id,
        submitted_by_id=current_user.id,
        **body.model_dump(exclude_unset=True),
    )
    db.add(claim)
    await db.commit()
    await db.refresh(claim)
    return claim


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: uuid.UUID,
    current_user: User = Depends(require_permission("claims:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single claim by ID, scoped to org."""
    query = select(Claim).where(
        Claim.id == claim_id,
        Claim.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Claim.organization_id == current_user.organization_id)

    result = await db.execute(query)
    claim = result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.patch("/{claim_id}", response_model=ClaimResponse)
async def update_claim(
    claim_id: uuid.UUID,
    body: ClaimUpdate,
    current_user: User = Depends(require_permission("claims:write")),
    db: AsyncSession = Depends(get_db),
):
    """Update a claim, scoped to org."""
    query = select(Claim).where(
        Claim.id == claim_id,
        Claim.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Claim.organization_id == current_user.organization_id)

    result = await db.execute(query)
    claim = result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(claim, field, value)

    await db.commit()
    await db.refresh(claim)
    return claim


@router.post("/{claim_id}/transition", response_model=ClaimResponse)
async def transition_claim_status(
    claim_id: uuid.UUID,
    body: ClaimTransition,
    current_user: User = Depends(require_permission("claims:write")),
    db: AsyncSession = Depends(get_db),
):
    """Transition a claim's status with validation against allowed transitions."""
    query = select(Claim).where(
        Claim.id == claim_id,
        Claim.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Claim.organization_id == current_user.organization_id)

    result = await db.execute(query)
    claim = result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    # Validate the target status is a real status
    try:
        current = ClaimStatus(claim.status)
        target = ClaimStatus(body.target_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status value: {body.target_status}",
        )

    if not can_transition(current, target):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot transition from '{current}' to '{target}'",
        )

    claim.status = target.value
    await db.commit()
    await db.refresh(claim)
    return claim
