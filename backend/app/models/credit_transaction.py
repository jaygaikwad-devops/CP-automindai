"""Credit Transaction model for tracking credit purchases and deductions."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CreditTransaction(Base):
    """Credit transaction log table.

    Records all credit purchases (+) and deductions (-) for channel partners.
    """

    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    cp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cps.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'purchase' or 'deduction'
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # positive for purchase, negative for deduction
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True
    )  # set on deduction
    pack_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'starter', 'growth', 'agency'
    razorpay_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # set on purchase
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
