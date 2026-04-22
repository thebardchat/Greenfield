"""Credentials router — CRUD with org-scoped access and expiry tracking."""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.rbac import get_current_user, require_permission
from app.models.credential import Credential
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CredentialResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    facility_id: uuid.UUID | None
    provider_name: str
    credential_type: str
    credential_number: str
    issuing_state: str | None
    issued_date: date | None
    expiry_date: date | None
    status: str
    document_path: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CredentialCreate(BaseModel):
    facility_id: uuid.UUID | None = None
    provider_name: str
    credential_type: str
    credential_number: str
    issuing_state: str | None = None
    issued_date: date | None = None
    expiry_date: date | None = None
    status: str = "active"
    document_path: str | None = None
    notes: str | None = None


class CredentialUpdate(BaseModel):
    facility_id: uuid.UUID | None = None
    provider_name: str | None = None
    credential_type: str | None = None
    credential_number: str | None = None
    issuing_state: str | None = None
    issued_date: date | None = None
    expiry_date: date | None = None
    status: str | None = None
    document_path: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[CredentialResponse])
async def list_credentials(
    current_user: User = Depends(require_permission("credentials:read")),
    db: AsyncSession = Depends(get_db),
):
    """List credentials scoped to the user's organization."""
    query = select(Credential).where(Credential.deleted_at.is_(None))

    # Non-super-admins only see their own org's credentials
    if current_user.role != "super_admin":
        query = query.where(Credential.organization_id == current_user.organization_id)

    result = await db.execute(query.order_by(Credential.provider_name, Credential.credential_type))
    return result.scalars().all()


@router.get("/expiring", response_model=list[CredentialResponse])
async def list_expiring(
    current_user: User = Depends(require_permission("credentials:read")),
    db: AsyncSession = Depends(get_db),
    days: int = Query(90, ge=1, le=365),
):
    """List credentials expiring within the specified number of days."""
    cutoff = date.today() + timedelta(days=days)

    query = select(Credential).where(
        Credential.deleted_at.is_(None),
        Credential.expiry_date.is_not(None),
        Credential.expiry_date <= cutoff,
        Credential.status.in_(["active", "expiring_soon"]),
    )

    # Non-super-admins only see their own org's credentials
    if current_user.role != "super_admin":
        query = query.where(Credential.organization_id == current_user.organization_id)

    result = await db.execute(query.order_by(Credential.expiry_date))
    return result.scalars().all()


@router.post("/", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CredentialCreate,
    current_user: User = Depends(require_permission("credentials:write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a credential in the user's organization."""
    if current_user.role == "super_admin" and current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin must specify organization context",
        )

    credential = Credential(
        organization_id=current_user.organization_id,
        **body.model_dump(exclude_unset=True),
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    return credential


@router.get("/{credential_id}", response_model=CredentialResponse)
async def get_credential(
    credential_id: uuid.UUID,
    current_user: User = Depends(require_permission("credentials:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single credential by ID, scoped to org."""
    query = select(Credential).where(
        Credential.id == credential_id,
        Credential.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Credential.organization_id == current_user.organization_id)

    result = await db.execute(query)
    credential = result.scalar_one_or_none()
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return credential


@router.patch("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: uuid.UUID,
    body: CredentialUpdate,
    current_user: User = Depends(require_permission("credentials:write")),
    db: AsyncSession = Depends(get_db),
):
    """Update a credential, scoped to org."""
    query = select(Credential).where(
        Credential.id == credential_id,
        Credential.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Credential.organization_id == current_user.organization_id)

    result = await db.execute(query)
    credential = result.scalar_one_or_none()
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(credential, field, value)

    await db.commit()
    await db.refresh(credential)
    return credential
