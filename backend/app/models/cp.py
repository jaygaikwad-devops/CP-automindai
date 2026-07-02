"""Channel Partner (CP) model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class CP(Base):
    """Channel Partner table."""

    __tablename__ = "cps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    phone: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(255))
    rera_id: Mapped[str | None] = mapped_column(String(50))
    cognito_sub: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    subscription_status: Mapped[str] = mapped_column(String(20), server_default="inactive")
    subscription_plan: Mapped[str | None] = mapped_column(String(20))
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credit_balance: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    partnerships = relationship("Partnership", back_populates="cp", lazy="selectin")
    share_links = relationship("ShareLink", back_populates="cp", lazy="selectin")
    subscriptions = relationship("Subscription", back_populates="cp", lazy="selectin")
    leads = relationship("Lead", back_populates="cp", lazy="selectin")
