"""Add openclaw_agent_id to employees

Revision ID: 1c2d3e4f5a6b
Revises: 0a1b2c3d4e5f
Create Date: 2026-02-02

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "1c2d3e4f5a6b"
down_revision = "0a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Be tolerant if the column was added manually during development.
    op.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS openclaw_agent_id VARCHAR")


def downgrade() -> None:
    op.drop_column("employees", "openclaw_agent_id")
