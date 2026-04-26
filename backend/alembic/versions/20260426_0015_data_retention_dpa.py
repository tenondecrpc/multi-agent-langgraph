"""Add data retention, tenant deletion, and DPA compliance tables.

Revision ID: 20260426_0015
Revises: 20260426_0014
Create Date: 2026-04-26 20:00:00

Expand migration - adds new tables with no destructive changes.
Reversibility: downgrade drops the new tables; no existing data is touched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260426_0015"
down_revision = "20260426_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_delete_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("approved_by_first", sa.String(255), nullable=True),
        sa.Column("approved_by_second", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("deletion_counts", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_tenant_delete_events_tenant",
        "tenant_delete_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tenant_delete_events_status",
        "tenant_delete_events",
        ["status"],
    )

    op.create_table(
        "dpa_versions",
        sa.Column("version", sa.String(32), primary_key=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("published_by", sa.String(255), nullable=False),
        sa.Column("grace_period_days", sa.Integer, nullable=False, server_default=sa.text("30")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "dpa_acknowledgements",
        sa.Column("ack_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("dpa_version", sa.String(32), nullable=False),
        sa.Column("acknowledged_by", sa.String(255), nullable=False),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "dpa_version", name="uq_dpa_ack_tenant_version"),
    )

    op.create_index(
        "ix_dpa_acknowledgements_tenant",
        "dpa_acknowledgements",
        ["tenant_id"],
    )

    op.create_table(
        "retention_policies",
        sa.Column("policy_id", sa.String(64), primary_key=True),
        sa.Column("surface", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("retention_days", sa.Integer, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("surface", "tenant_id", name="uq_retention_surface_tenant"),
    )

    op.create_index(
        "ix_retention_policies_surface_tenant",
        "retention_policies",
        ["surface", "tenant_id"],
    )

    op.create_table(
        "retention_runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("surface", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("rows_affected", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("partitions_dropped", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'success'")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("mode", sa.String(32), nullable=False, server_default=sa.text("'enforce'")),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_retention_runs_surface_tenant",
        "retention_runs",
        ["surface", "tenant_id"],
    )
    op.create_index(
        "ix_retention_runs_started_at",
        "retention_runs",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_retention_runs_started_at", table_name="retention_runs")
    op.drop_index("ix_retention_runs_surface_tenant", table_name="retention_runs")
    op.drop_table("retention_runs")

    op.drop_index("ix_retention_policies_surface_tenant", table_name="retention_policies")
    op.drop_table("retention_policies")

    op.drop_index("ix_dpa_acknowledgements_tenant", table_name="dpa_acknowledgements")
    op.drop_table("dpa_acknowledgements")

    op.drop_table("dpa_versions")

    op.drop_index("ix_tenant_delete_events_status", table_name="tenant_delete_events")
    op.drop_index("ix_tenant_delete_events_tenant", table_name="tenant_delete_events")
    op.drop_table("tenant_delete_events")
