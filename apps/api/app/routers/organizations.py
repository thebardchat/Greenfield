"""Organizations router — CRUD for billing organizations.

An organization is the top-level tenant. All claims, patients, facilities,
and users belong to one organization. Only super_admin can create new orgs.
Org admins can read and update their own organization.

Endpoints:
  GET    /api/organizations/         — List all (super_admin only)
  POST   /api/organizations/         — Create org (super_admin only)
  GET    /api/organizations/{id}     — Get one (org-scoped)
  PATCH  /api/organizations/{id}     — Update (org_admin+)
  DELETE /api/organizations/{id}     — Soft delete (super_admin only)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.rbac import get_current_user, require_permission
from app.models.organization import Organization
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class OrgCreate(BaseModel):
    name: str
    slug: str
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    npi: str | None = None


class OrgUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    npi: str | None = None
    is_active: bool | None = None


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    address: str | None
    phone: str | None
    email: str | None
    npi: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgListResponse(BaseModel):
    organizations: list[OrgResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=OrgListResponse)
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    active_only: bool = Query(True),
    current_user: User = Depends(require_permission("users:read")),
    db: AsyncSession = Depends(get_db),
):
    """List organizations. Super admins see all; org admins see only theirs."""
    query = select(Organization).where(Organization.deleted_at.is_(None))

    # Non-super-admins are scoped to their own org
    if current_user.role != "super_admin":
        query = query.where(Organization.id == current_user.organization_id)

    if active_only:
        query = query.where(Organization.is_active.is_(True))

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    orgs_result = await db.execute(
        query.offset((page - 1) * page_size).limit(page_size).order_by(Organization.name)
    )
    orgs = orgs_result.scalars().all()

    return OrgListResponse(
        organizations=[OrgResponse.model_validate(o) for o in orgs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrgCreate,
    current_user: User = Depends(require_permission("users:write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new billing organization. Requires super_admin."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can create organizations",
        )

    # Check slug uniqueness
    existing = await db.execute(
        select(Organization).where(
            Organization.slug == body.slug,
            Organization.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with slug '{body.slug}' already exists",
        )

    org = Organization(
        name=body.name,
        slug=body.slug,
        address=body.address,
        phone=body.phone,
        email=body.email,
        npi=body.npi,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return OrgResponse.model_validate(org)


@router.get("/{org_id}", response_model=OrgResponse)
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single organization by ID."""
    # Scope check
    if current_user.role != "super_admin":
        if str(current_user.organization_id) != org_id:
            raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(Organization).where(
            Organization.id == uuid.UUID(org_id),
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrgResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_organization(
    org_id: str,
    body: OrgUpdate,
    current_user: User = Depends(require_permission("users:write")),
    db: AsyncSession = Depends(get_db),
):
    """Update organization details. Org admins can only update their own org."""
    if current_user.role != "super_admin":
        if str(current_user.organization_id) != org_id:
            raise HTTPException(status_code=403, detail="Cannot modify another organization")

    result = await db.execute(
        select(Organization).where(
            Organization.id == uuid.UUID(org_id),
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    updates = body.model_dump(exclude_none=True)
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        await db.execute(
            update(Organization)
            .where(Organization.id == uuid.UUID(org_id))
            .values(**updates)
        )
        await db.commit()
        await db.refresh(org)

    return OrgResponse.model_validate(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: str,
    current_user: User = Depends(require_permission("users:write")),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete an organization. Super admin only."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can delete organizations",
        )

    result = await db.execute(
        select(Organization).where(
            Organization.id == uuid.UUID(org_id),
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    await db.execute(
        update(Organization)
        .where(Organization.id == uuid.UUID(org_id))
        .values(
            deleted_at=datetime.now(timezone.utc),
            is_active=False,
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
