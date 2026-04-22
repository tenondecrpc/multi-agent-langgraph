"""Add model catalog, provider health audit, and broaden tenant RLS coverage.

Revision ID: 20260418_0006
Revises: 20260418_0005
Create Date: 2026-04-22 13:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260418_0006"
down_revision = "20260418_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_catalog_entries",
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("deployment_profile", sa.String(length=64), nullable=False),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("default_price_card_id", sa.String(length=255), nullable=False),
        sa.Column("supports_tools", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_json_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "allowed_fallback_targets",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("model_id", "deployment_profile"),
    )
    op.create_table(
        "role_token_policies",
        sa.Column("role", sa.String(length=64), primary_key=True),
        sa.Column("max_input_tokens", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_table(
        "provider_health_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("remaining_probe_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    for table_name in [
        "dead_letter_records",
        "budget_cap_snapshots",
        "budget_reservations",
        "budget_charges",
        "budget_denials",
        "metering_facts",
        "metering_facts_default",
        "metering_hourly_rollups",
    ]:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_scope
            ON {table_name}
            FOR ALL
            USING (app.tenant_visible(tenant_id, team_id))
            WITH CHECK (app.tenant_visible(tenant_id, team_id));
            """
        )


def downgrade() -> None:
    for table_name in [
        "metering_hourly_rollups",
        "metering_facts_default",
        "metering_facts",
        "budget_denials",
        "budget_charges",
        "budget_reservations",
        "budget_cap_snapshots",
        "dead_letter_records",
    ]:
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_scope ON {table_name}")
        op.execute(f"ALTER TABLE IF EXISTS {table_name} DISABLE ROW LEVEL SECURITY")

    op.drop_table("provider_health_events")
    op.drop_table("role_token_policies")
    op.drop_table("model_catalog_entries")
