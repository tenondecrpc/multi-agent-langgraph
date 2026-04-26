"""Add webhook secret rotation, rate-limit rejections, and signature_hash.

Revision ID: 20260426_0013
Revises: 20260426_0012
Create Date: 2026-04-26 18:00:00

Expand migration - adds new tables and columns with no destructive changes.
Reversibility: downgrade drops new tables, removes added columns, and restores old unique constraint.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260426_0013"
down_revision = "20260426_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "webhook_idempotency_records",
        sa.Column("signature_hash", sa.String(64), nullable=True),
    )

    op.create_index(
        "ix_webhook_idempotency_signature_hash",
        "webhook_idempotency_records",
        ["signature_hash"],
    )

    op.create_unique_constraint(
        "uq_webhook_idempotency_source_delivery_sighash",
        "webhook_idempotency_records",
        ["source", "delivery_id", "signature_hash"],
    )

    op.create_table(
        "webhook_secret_rotations",
        sa.Column("rotation_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("previous_secret_hash", sa.String(128), nullable=True),
        sa.Column("rotation_overlap_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_by", sa.String(255), nullable=False),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_webhook_secret_rotations_tenant_team",
        "webhook_secret_rotations",
        ["tenant_id", "team_id"],
    )

    op.create_table(
        "webhook_rate_limit_rejections",
        sa.Column("rejection_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("ticket_key", sa.String(128), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("delivery_id", sa.String(255), nullable=False),
        sa.Column("remote_addr", sa.String(64), nullable=False),
        sa.Column(
            "rejected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_webhook_rate_limit_rejections_tenant_ticket",
        "webhook_rate_limit_rejections",
        ["tenant_id", "ticket_key"],
    )
    op.create_index(
        "ix_webhook_rate_limit_rejections_rejected_at",
        "webhook_rate_limit_rejections",
        ["rejected_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_rate_limit_rejections_rejected_at", table_name="webhook_rate_limit_rejections")
    op.drop_index("ix_webhook_rate_limit_rejections_tenant_ticket", table_name="webhook_rate_limit_rejections")
    op.drop_table("webhook_rate_limit_rejections")

    op.drop_index("ix_webhook_secret_rotations_tenant_team", table_name="webhook_secret_rotations")
    op.drop_table("webhook_secret_rotations")

    op.drop_constraint(
        "uq_webhook_idempotency_source_delivery_sighash",
        "webhook_idempotency_records",
        type_="unique",
    )
    op.drop_index("ix_webhook_idempotency_signature_hash", table_name="webhook_idempotency_records")
    op.drop_column("webhook_idempotency_records", "signature_hash")
