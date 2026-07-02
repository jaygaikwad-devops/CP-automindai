"""Initial schema - all tables and indexes.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2024-01-01 00:01:00.000000+00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- cps ---
    op.create_table(
        "cps",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("phone", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("rera_id", sa.String(50), nullable=True),
        sa.Column("cognito_sub", sa.String(128), nullable=False),
        sa.Column("subscription_status", sa.String(20), server_default="inactive", nullable=False),
        sa.Column("subscription_plan", sa.String(20), nullable=True),
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("cognito_sub"),
    )

    # --- builders ---
    op.create_table(
        "builders",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- projects ---
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("builder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("unit_types", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("tour_status", sa.String(30), server_default="not_started", nullable=False),
        sa.Column("tour_script_s3_key", sa.String(500), nullable=True),
        sa.Column("kb_id", sa.String(128), nullable=True),
        sa.Column("hero_image_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["builder_id"], ["builders.id"]),
    )

    # --- partnerships ---
    op.create_table(
        "partnerships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("builder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cp_id"], ["cps.id"]),
        sa.ForeignKeyConstraint(["builder_id"], ["builders.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.UniqueConstraint("cp_id", "project_id", name="uq_partnerships_cp_project"),
    )

    # --- share_links ---
    op.create_table(
        "share_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url_slug", sa.String(32), nullable=False),
        sa.Column("og_title", sa.String(255), nullable=True),
        sa.Column("og_description", sa.Text(), nullable=True),
        sa.Column("og_image_url", sa.String(500), nullable=True),
        sa.Column("click_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cp_id"], ["cps.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.UniqueConstraint("url_slug"),
    )

    # --- project_assets ---
    op.create_table(
        "project_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_type", sa.String(20), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )

    # --- processing_jobs ---
    op.create_table(
        "processing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), server_default="queued", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )

    # --- subscriptions ---
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("cp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", sa.String(20), nullable=False),
        sa.Column("razorpay_subscription_id", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), server_default="created", nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cp_id"], ["cps.id"]),
    )

    # --- leads ---
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("cp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_name", sa.String(255), nullable=True),
        sa.Column("buyer_phone", sa.String(10), nullable=True),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("classification", sa.String(20), server_default="browsing", nullable=False),
        sa.Column("signals", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column("alert_sent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cp_id"], ["cps.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )

    # --- admins ---
    op.create_table(
        "admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("cognito_sub", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("cognito_sub"),
    )

    # --- Indexes ---
    op.create_index("idx_partnerships_cp", "partnerships", ["cp_id"])
    op.create_index("idx_partnerships_project", "partnerships", ["project_id"])
    op.create_index("idx_share_links_cp", "share_links", ["cp_id"])
    op.create_index("idx_share_links_slug", "share_links", ["url_slug"])
    op.create_index("idx_leads_cp_score", "leads", ["cp_id", sa.text("score DESC")])
    op.create_index("idx_leads_session", "leads", ["session_id"])
    op.create_index("idx_project_assets_project", "project_assets", ["project_id", "asset_type"])
    op.create_index("idx_projects_builder", "projects", ["builder_id"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_projects_builder", table_name="projects")
    op.drop_index("idx_project_assets_project", table_name="project_assets")
    op.drop_index("idx_leads_session", table_name="leads")
    op.drop_index("idx_leads_cp_score", table_name="leads")
    op.drop_index("idx_share_links_slug", table_name="share_links")
    op.drop_index("idx_share_links_cp", table_name="share_links")
    op.drop_index("idx_partnerships_project", table_name="partnerships")
    op.drop_index("idx_partnerships_cp", table_name="partnerships")

    # Drop tables in reverse dependency order
    op.drop_table("admins")
    op.drop_table("leads")
    op.drop_table("subscriptions")
    op.drop_table("processing_jobs")
    op.drop_table("project_assets")
    op.drop_table("share_links")
    op.drop_table("partnerships")
    op.drop_table("projects")
    op.drop_table("builders")
    op.drop_table("cps")
