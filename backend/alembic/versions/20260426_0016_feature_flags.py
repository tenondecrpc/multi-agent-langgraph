"""Add feature flag state mirror and audit tables.

Revision ID: 20260426_0016
Revises: 20260426_0015
Create Date: 2026-04-26 21:00:00

Expand migration - adds new tables with no destructive changes.
Reversibility: downgrade drops the new tables; no existing data is touched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "20260426_0016"
down_revision = "20260426_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_flag_state",
        sa.Column("flag_key", sa.String(128), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("variant", sa.String(64), nullable=True),
        sa.Column("targeting_rules", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("is_kill_switch", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("stale_flag_days", sa.Integer, nullable=False, server_default=sa.text("90")),
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "mirror_synced_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_feature_flag_state_owner",
        "feature_flag_state",
        ["owner"],
    )

    op.create_index(
        "ix_feature_flag_state_is_kill_switch",
        "feature_flag_state",
        ["is_kill_switch"],
    )

    op.create_index(
        "ix_feature_flag_state_mirror_synced_at",
        "feature_flag_state",
        ["mirror_synced_at"],
    )

    op.create_table(
        "feature_flag_audit",
        sa.Column("audit_id", sa.String(64), primary_key=True),
        sa.Column("flag_key", sa.String(128), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("previous_value", JSONB, nullable=True),
        sa.Column("new_value", JSONB, nullable=True),
        sa.Column("changed_by", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "changed_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_feature_flag_audit_flag_key",
        "feature_flag_audit",
        ["flag_key"],
    )

    op.create_index(
        "ix_feature_flag_audit_changed_at",
        "feature_flag_audit",
        ["changed_at"],
    )

    op.create_table(
        "feature_flag_registry",
        sa.Column("flag_key", sa.String(128), primary_key=True),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("flag_type", sa.String(32), nullable=False, server_default=sa.text("'release'")),
        sa.Column("retirement_intent", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_modified_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_feature_flag_registry_owner",
        "feature_flag_registry",
        ["owner"],
    )


def downgrade() -> None:
    op.drop_table("feature_flag_registry")
    op.drop_table("feature_flag_audit")
    op.drop_table("feature_flag_state")
