"""Lead model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Lead(Base):
    """Leads table for buyer tracking and scoring."""

    __tablename__ = "leads"
    __table_args__ = (
        Index("idx_leads_cp_score", "cp_id", "score"),
        Index("idx_leads_session", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cps.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    buyer_name: Mapped[str | None] = mapped_column(String(255))
    buyer_phone: Mapped[str | None] = mapped_column(String(10))
    score: Mapped[int] = mapped_column(Integer, server_default="0")
    classification: Mapped[str] = mapped_column(String(20), server_default="browsing")
    signals: Mapped[dict | None] = mapped_column(JSONB, server_default="'[]'")
    alert_sent: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    cp = relationship("CP", back_populates="leads")
    project = relationship("Project", back_populates="leads")
