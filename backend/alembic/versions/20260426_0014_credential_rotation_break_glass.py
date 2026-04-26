"""Add credential rotation, break-glass, and KEK version tables.

Revision ID: 20260426_0014
Revises: 20260426_0013
Create Date: 2026-04-26 19:00:00

Expand migration - adds new tables with no destructive changes.
Reversibility: downgrade drops the new tables; no existing data is touched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260426_0014"
down_revision = "20260426_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credential_rotation_schedule",
        sa.Column("schedule_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("credential_kind", sa.String(64), nullable=False),
        sa.Column("credential_id", sa.String(255), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_rotation_due", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotation_sla_days", sa.Integer, nullable=False, server_default=sa.text("90")),
        sa.Column("overdue", sa.Boolean, nullable=False, server_default=sa.text("false")),
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
            "tenant_id", "team_id", "credential_kind", "credential_id",
            name="uq_credential_rotation_scope",
        ),
    )

    op.create_index(
        "ix_credential_rotation_schedule_tenant_team",
        "credential_rotation_schedule",
        ["tenant_id", "team_id"],
    )
    op.create_index(
        "ix_credential_rotation_schedule_next_rotation_due",
        "credential_rotation_schedule",
        ["next_rotation_due"],
    )
    op.create_index(
        "ix_credential_rotation_schedule_overdue",
        "credential_rotation_schedule",
        ["overdue"],
    )

    op.create_table(
        "break_glass_grants",
        sa.Column("grant_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("scope", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("approved_by_first", sa.String(255), nullable=True),
        sa.Column("approved_by_second", sa.String(255), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(255), nullable=True),
        sa.Column("revoke_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_break_glass_grants_tenant_team",
        "break_glass_grants",
        ["tenant_id", "team_id"],
    )
    op.create_index(
        "ix_break_glass_grants_expires_at",
        "break_glass_grants",
        ["expires_at"],
    )
    op.create_index(
        "ix_break_glass_grants_granted_at",
        "break_glass_grants",
        ["granted_at"],
    )

    op.create_table(
        "kek_versions",
        sa.Column("kek_id", sa.String(64), primary_key=True),
        sa.Column("kms_ref", sa.String(512), nullable=False),
        sa.Column("introduced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("introduced_by", sa.String(255), nullable=False),
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
        "ix_kek_versions_is_default",
        "kek_versions",
        ["is_default"],
    )
    op.create_index(
        "ix_kek_versions_introduced_at",
        "kek_versions",
        ["introduced_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_kek_versions_introduced_at", table_name="kek_versions")
    op.drop_index("ix_kek_versions_is_default", table_name="kek_versions")
    op.drop_table("kek_versions")

    op.drop_index("ix_break_glass_grants_granted_at", table_name="break_glass_grants")
    op.drop_index("ix_break_glass_grants_expires_at", table_name="break_glass_grants")
    op.drop_index("ix_break_glass_grants_tenant_team", table_name="break_glass_grants")
    op.drop_table("break_glass_grants")

    op.drop_index("ix_credential_rotation_schedule_overdue", table_name="credential_rotation_schedule")
    op.drop_index("ix_credential_rotation_schedule_next_rotation_due", table_name="credential_rotation_schedule")
    op.drop_index("ix_credential_rotation_schedule_tenant_team", table_name="credential_rotation_schedule")
    op.drop_table("credential_rotation_schedule")
