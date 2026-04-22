"""Add durable metering facts and hourly rollups.

Revision ID: 20260418_0005
Revises: 20260418_0004
Create Date: 2026-04-18 17:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260418_0005"
down_revision = "20260418_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE metering_facts (
            usage_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            team_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            ticket_key TEXT NOT NULL,
            role TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            deployment_profile TEXT NOT NULL,
            fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            cached_tokens INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 1,
            reservation_id TEXT,
            estimated_cost_usd NUMERIC(14, 6) NOT NULL,
            actual_cost_usd NUMERIC(14, 6) NOT NULL,
            rate_card_id TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            span_id TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL,
            PRIMARY KEY (usage_id, completed_at)
        ) PARTITION BY RANGE (completed_at)
        """
    )
    op.execute(
        """
        CREATE TABLE metering_facts_default
        PARTITION OF metering_facts DEFAULT
        """
    )
    op.execute(
        """
        CREATE INDEX ix_metering_facts_default_tenant_team_completed_at
        ON metering_facts_default (tenant_id, team_id, completed_at)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_metering_facts_default_run_id_completed_at
        ON metering_facts_default (run_id, completed_at)
        """
    )

    op.create_table(
        "metering_hourly_rollups",
        sa.Column("rollup_id", sa.String(length=255), primary_key=True),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("rate_card_id", sa.String(length=255), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("total_input_tokens", sa.Integer(), nullable=False),
        sa.Column("total_output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_actual_cost_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column(
            "usage_ids",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("sealed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        "ix_metering_hourly_rollups_tenant_team_bucket_start",
        "metering_hourly_rollups",
        ["tenant_id", "team_id", "bucket_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_metering_hourly_rollups_tenant_team_bucket_start",
        table_name="metering_hourly_rollups",
    )
    op.drop_table("metering_hourly_rollups")

    op.execute("DROP INDEX IF EXISTS ix_metering_facts_default_run_id_completed_at")
    op.execute("DROP INDEX IF EXISTS ix_metering_facts_default_tenant_team_completed_at")
    op.execute("DROP TABLE IF EXISTS metering_facts_default")
    op.execute("DROP TABLE IF EXISTS metering_facts")
