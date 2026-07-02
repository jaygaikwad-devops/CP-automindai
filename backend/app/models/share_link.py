"""ShareLink model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ShareLink(Base):
    """Share links table for CP-branded project URLs."""

    __tablename__ = "share_links"
    __table_args__ = (
        Index("idx_share_links_cp", "cp_id"),
        Index("idx_share_links_slug", "url_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    cp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cps.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    url_slug: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    og_title: Mapped[str | None] = mapped_column(String(255))
    og_description: Mapped[str | None] = mapped_column(Text)
    og_image_url: Mapped[str | None] = mapped_column(String(500))
    click_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    cp = relationship("CP", back_populates="share_links")
    project = relationship("Project", back_populates="share_links")
