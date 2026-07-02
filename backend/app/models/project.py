"""Project model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Project(Base):
    """Project table."""

    __tablename__ = "projects"
    __table_args__ = (
        Index("idx_projects_builder", "builder_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    builder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("builders.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(500))
    unit_types: Mapped[dict | None] = mapped_column(JSONB, server_default="'[]'")
    tour_status: Mapped[str] = mapped_column(String(30), server_default="not_started")
    tour_script_s3_key: Mapped[str | None] = mapped_column(String(500))
    kb_id: Mapped[str | None] = mapped_column(String(128))
    hero_image_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    builder = relationship("Builder", back_populates="projects")
    partnerships = relationship("Partnership", back_populates="project", lazy="selectin")
    share_links = relationship("ShareLink", back_populates="project", lazy="selectin")
    assets = relationship("ProjectAsset", back_populates="project", lazy="selectin")
    processing_jobs = relationship("ProcessingJob", back_populates="project", lazy="selectin")
    leads = relationship("Lead", back_populates="project", lazy="selectin")
