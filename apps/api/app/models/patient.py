"""SQLAlchemy Patient model for Claim Cruncher."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    mrn: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ssn_last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    primary_insurance_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_insurance_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    secondary_insurance_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secondary_insurance_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Patient {self.last_name}, {self.first_name}>"
