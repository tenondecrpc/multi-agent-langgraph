"""Add billing rate-card and reconciliation tables.

Revision ID: 20260426_0012
Revises: 20260426_0011
Create Date: 2026-04-26 17:00:00

Expand migration - adds new tables and columns with no destructive changes.
Reversibility: downgrade drops new tables and removes added columns; no existing data is touched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260426_0012"
down_revision = "20260426_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_rate_cards",
        sa.Column("rate_card_id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False, server_default="per_1k_tokens"),
        sa.Column("rate_usd", sa.Numeric(14, 6), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("activated_by", sa.String(255), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
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
        "ix_price_rate_cards_provider_model",
        "price_rate_cards",
        ["provider", "model"],
    )
    op.create_index(
        "ix_price_rate_cards_effective_from",
        "price_rate_cards",
        ["effective_from"],
    )
    op.create_index(
        "ix_price_rate_cards_status",
        "price_rate_cards",
        ["status"],
    )

    op.create_table(
        "reconciliation_reports",
        sa.Column("report_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("metered_total_usd", sa.Numeric(14, 6), nullable=False),
        sa.Column("provider_reported_total_usd", sa.Numeric(14, 6), nullable=False),
        sa.Column("drift_amount_usd", sa.Numeric(14, 6), nullable=False),
        sa.Column("drift_percentage", sa.Numeric(8, 4), nullable=False),
        sa.Column("missing_provider_request_ids", sa.Integer, nullable=False, server_default="0"),
        sa.Column("matched_usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unmatched_usage_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mode", sa.String(32), nullable=False, server_default="dry_run"),
        sa.Column(
            "usage_ids",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "rollup_ids",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_reconciliation_reports_tenant_period",
        "reconciliation_reports",
        ["tenant_id", "period_start", "period_end"],
    )
    op.create_index(
        "ix_reconciliation_reports_provider",
        "reconciliation_reports",
        ["provider"],
    )

    op.add_column(
        "metering_facts",
        sa.Column("provider_request_id", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_metering_facts_provider_request_id",
        "metering_facts",
        ["provider_request_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_metering_facts_provider_request_id", table_name="metering_facts")
    op.drop_column("metering_facts", "provider_request_id")

    op.drop_index("ix_reconciliation_reports_provider", table_name="reconciliation_reports")
    op.drop_index("ix_reconciliation_reports_tenant_period", table_name="reconciliation_reports")
    op.drop_table("reconciliation_reports")

    op.drop_index("ix_price_rate_cards_status", table_name="price_rate_cards")
    op.drop_index("ix_price_rate_cards_effective_from", table_name="price_rate_cards")
    op.drop_index("ix_price_rate_cards_provider_model", table_name="price_rate_cards")
    op.drop_table("price_rate_cards")
