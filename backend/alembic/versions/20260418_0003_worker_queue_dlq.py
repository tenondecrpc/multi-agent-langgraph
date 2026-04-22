"""Add durable dead-letter queue storage.

Revision ID: 20260418_0003
Revises: 20260418_0002
Create Date: 2026-04-18 14:30:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260418_0003"
down_revision = "20260418_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dead_letter_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("queue_name", sa.String(length=255), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=False),
        sa.Column("checkpoint_ref", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_dead_letter_records_tenant_team_created_at",
        "dead_letter_records",
        ["tenant_id", "team_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_dead_letter_records_tenant_team_created_at", table_name="dead_letter_records")
    op.drop_table("dead_letter_records")
