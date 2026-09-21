"""create jobs queue and stub extractions table

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-18
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("step", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "document_id", "step", "payload_hash", name="uq_jobs_dedupe_key"
        ),
    )
    op.create_index(
        "ix_jobs_claimable",
        "jobs",
        ["status", "available_at"],
    )

    op.create_table(
        "extractions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("raw_output", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("extractions")
    op.drop_index("ix_jobs_claimable", table_name="jobs")
    op.drop_table("jobs")
