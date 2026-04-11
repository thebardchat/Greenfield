"""Tickets router — CRUD with org-scoped access."""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.middleware.rbac import get_current_user, require_permission
from app.models.ticket import Ticket
from app.models.user import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TicketResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    claim_id: uuid.UUID | None
    title: str
    description: str | None
    ticket_type: str
    status: str
    priority: int
    assigned_to_id: uuid.UUID | None
    created_by_id: uuid.UUID
    due_date: date | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketCreate(BaseModel):
    claim_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    ticket_type: str
    priority: int = 2
    assigned_to_id: uuid.UUID | None = None
    due_date: date | None = None


class TicketUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    ticket_type: str | None = None
    status: str | None = None
    priority: int | None = None
    assigned_to_id: uuid.UUID | None = None
    due_date: date | None = None
    resolved_at: datetime | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[TicketResponse])
async def list_tickets(
    current_user: User = Depends(require_permission("tickets:read")),
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    ticket_type: str | None = Query(None),
    assigned_to_id: uuid.UUID | None = Query(None),
    priority: int | None = Query(None),
):
    """List tickets scoped to the user's organization with optional filters."""
    query = select(Ticket).where(Ticket.deleted_at.is_(None))

    # Non-super-admins only see their own org's tickets
    if current_user.role != "super_admin":
        query = query.where(Ticket.organization_id == current_user.organization_id)

    if status_filter is not None:
        query = query.where(Ticket.status == status_filter)
    if ticket_type is not None:
        query = query.where(Ticket.ticket_type == ticket_type)
    if assigned_to_id is not None:
        query = query.where(Ticket.assigned_to_id == assigned_to_id)
    if priority is not None:
        query = query.where(Ticket.priority == priority)

    result = await db.execute(query.order_by(Ticket.priority.desc(), Ticket.created_at.desc()))
    return result.scalars().all()


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
    current_user: User = Depends(require_permission("tickets:write")),
    db: AsyncSession = Depends(get_db),
):
    """Create a ticket in the user's organization."""
    if current_user.role == "super_admin" and current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin must specify organization context",
        )

    ticket = Ticket(
        organization_id=current_user.organization_id,
        created_by_id=current_user.id,
        **body.model_dump(exclude_unset=True),
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(require_permission("tickets:read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single ticket by ID, scoped to org."""
    query = select(Ticket).where(
        Ticket.id == ticket_id,
        Ticket.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Ticket.organization_id == current_user.organization_id)

    result = await db.execute(query)
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: uuid.UUID,
    body: TicketUpdate,
    current_user: User = Depends(require_permission("tickets:write")),
    db: AsyncSession = Depends(get_db),
):
    """Update a ticket, scoped to org."""
    query = select(Ticket).where(
        Ticket.id == ticket_id,
        Ticket.deleted_at.is_(None),
    )
    if current_user.role != "super_admin":
        query = query.where(Ticket.organization_id == current_user.organization_id)

    result = await db.execute(query)
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(ticket, field, value)

    await db.commit()
    await db.refresh(ticket)
    return ticket
