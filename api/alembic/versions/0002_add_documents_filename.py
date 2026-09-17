"""add filename to documents

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("filename", sa.Text(), nullable=False))


def downgrade() -> None:
    op.drop_column("documents", "filename")
