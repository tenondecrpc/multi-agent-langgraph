"""Add admission_exceptions table for supply-chain policy exceptions.

Revision ID: 20260426_0011
Revises: 20260426_0010
Create Date: 2026-04-26 12:00:00

Expand migration - adds new table with no destructive changes.
Reversibility: downgrade drops the new table; no existing data is touched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260426_0011"
down_revision = "20260426_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admission_exceptions",
        sa.Column("exception_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("policy_name", sa.String(255), nullable=False),
        sa.Column("image_reference", sa.String(512), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("approved_by", sa.String(255), nullable=False),
        sa.Column("second_approver", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(255), nullable=True),
        sa.Column("revoke_reason", sa.Text, nullable=True),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_admission_exceptions_tenant_team",
        "admission_exceptions",
        ["tenant_id", "team_id"],
    )
    op.create_index(
        "ix_admission_exceptions_policy",
        "admission_exceptions",
        ["policy_name"],
    )
    op.create_index(
        "ix_admission_exceptions_expires_at",
        "admission_exceptions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_admission_exceptions_expires_at", table_name="admission_exceptions")
    op.drop_index("ix_admission_exceptions_policy", table_name="admission_exceptions")
    op.drop_index("ix_admission_exceptions_tenant_team", table_name="admission_exceptions")
    op.drop_table("admission_exceptions")
