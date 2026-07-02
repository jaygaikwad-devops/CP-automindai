"""Add credit billing: credit_balance column and credit_transactions table.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2024-01-02 00:02:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add credit_balance column to cps table
    op.add_column(
        "cps",
        sa.Column("credit_balance", sa.Integer(), server_default="0", nullable=False),
    )

    # Create credit_transactions table
    op.create_table(
        "credit_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pack_type", sa.String(20), nullable=True),
        sa.Column("razorpay_order_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cp_id"], ["cps.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )

    # Create index on cp_id for fast lookups
    op.create_index("idx_credit_transactions_cp", "credit_transactions", ["cp_id"])


def downgrade() -> None:
    op.drop_index("idx_credit_transactions_cp", table_name="credit_transactions")
    op.drop_table("credit_transactions")
    op.drop_column("cps", "credit_balance")
