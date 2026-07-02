"""Partnership model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Partnership(Base):
    """Partnership table linking CPs to builders and projects."""

    __tablename__ = "partnerships"
    __table_args__ = (
        UniqueConstraint("cp_id", "project_id", name="uq_partnerships_cp_project"),
        Index("idx_partnerships_cp", "cp_id"),
        Index("idx_partnerships_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    cp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cps.id"), nullable=False
    )
    builder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builders.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    cp = relationship("CP", back_populates="partnerships")
    builder = relationship("Builder", back_populates="partnerships")
    project = relationship("Project", back_populates="partnerships")
