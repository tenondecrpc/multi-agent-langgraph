"""Add LangGraph checkpoint tables.

Revision ID: 20260427_0017
Revises: 20260426_0016
Create Date: 2026-04-27 12:00:00

Expand migration - adds checkpoint tables required by langgraph-checkpoint-postgres.
These tables are used by LangGraph's PostgresSaver for graph state persistence.
Reversibility: downgrade drops the new tables; no existing app data is touched.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260427_0017"
down_revision = "20260426_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migration version tracking for langgraph-checkpoint-postgres
    op.create_table(
        "checkpoint_migrations",
        sa.Column("v", sa.Integer, primary_key=True),
    )

    # Core checkpoint storage
    op.create_table(
        "checkpoints",
        sa.Column("thread_id", sa.Text, nullable=False),
        sa.Column("checkpoint_ns", sa.Text, nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.Text, nullable=False),
        sa.Column("parent_checkpoint_id", sa.Text, nullable=True),
        sa.Column("type", sa.Text, nullable=True),
        sa.Column("checkpoint", JSONB, nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id"),
    )

    # Large blob offloading for checkpoint channels
    op.create_table(
        "checkpoint_blobs",
        sa.Column("thread_id", sa.Text, nullable=False),
        sa.Column("checkpoint_ns", sa.Text, nullable=False, server_default=""),
        sa.Column("channel", sa.Text, nullable=False),
        sa.Column("version", sa.Text, nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("blob", sa.LargeBinary, nullable=True),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "channel", "version"),
    )

    # Pending writes (for async/interrupt paths)
    op.create_table(
        "checkpoint_writes",
        sa.Column("thread_id", sa.Text, nullable=False),
        sa.Column("checkpoint_ns", sa.Text, nullable=False, server_default=""),
        sa.Column("checkpoint_id", sa.Text, nullable=False),
        sa.Column("task_id", sa.Text, nullable=False),
        sa.Column("idx", sa.Integer, nullable=False),
        sa.Column("channel", sa.Text, nullable=False),
        sa.Column("type", sa.Text, nullable=True),
        sa.Column("blob", sa.LargeBinary, nullable=False),
        sa.Column("task_path", sa.Text, nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"),
    )

    # LangGraph checkpoint migrations seed (mimics PostgresSaver.setup() state)
    op.execute("INSERT INTO checkpoint_migrations (v) VALUES (0), (1), (2), (3), (4), (5), (6), (7), (8)")

    # Indexes for checkpoint lookups
    op.create_index(
        "ix_checkpoints_thread_id",
        "checkpoints",
        ["thread_id"],
    )
    op.create_index(
        "ix_checkpoint_blobs_thread_id",
        "checkpoint_blobs",
        ["thread_id"],
    )
    op.create_index(
        "ix_checkpoint_writes_thread_id",
        "checkpoint_writes",
        ["thread_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_checkpoint_writes_thread_id", table_name="checkpoint_writes")
    op.drop_index("ix_checkpoint_blobs_thread_id", table_name="checkpoint_blobs")
    op.drop_index("ix_checkpoints_thread_id", table_name="checkpoints")
    op.drop_table("checkpoint_writes")
    op.drop_table("checkpoint_blobs")
    op.drop_table("checkpoints")
    op.drop_table("checkpoint_migrations")
