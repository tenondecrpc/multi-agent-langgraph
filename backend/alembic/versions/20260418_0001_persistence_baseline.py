"""Create baseline persistence tables and tenant-scoping helpers.

Revision ID: 20260418_0001
Revises:
Create Date: 2026-04-18 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260418_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.current_tenant_id()
        RETURNS text
        LANGUAGE sql
        STABLE
        AS $$
            SELECT NULLIF(current_setting('app.tenant_id', true), '')
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.current_team_id()
        RETURNS text
        LANGUAGE sql
        STABLE
        AS $$
            SELECT NULLIF(current_setting('app.team_id', true), '')
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.tenant_visible(row_tenant_id text, row_team_id text)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $$
            SELECT row_tenant_id = app.current_tenant_id()
               AND row_team_id = app.current_team_id()
        $$;
        """
    )

    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("thread_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("repo_id", sa.String(length=255), nullable=False),
        sa.Column("ticket_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_node", sa.String(length=64), nullable=False),
        sa.Column("paused_at_node", sa.String(length=64), nullable=True),
        sa.Column("escalation_reason", sa.String(length=128), nullable=True),
        sa.Column("escalation_sink", sa.Text(), nullable=True),
        sa.Column("config_snapshot_id", sa.String(length=255), nullable=False),
        sa.Column("graph_profile_id", sa.String(length=255), nullable=False),
        sa.Column("catalog_version", sa.String(length=255), nullable=False),
        sa.Column(
            "state_schema_version",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'1'"),
        ),
        sa.Column(
            "artifact_hashes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "run_payload",
            postgresql.JSONB(astext_type=sa.Text()),
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
    op.create_index("ix_runs_tenant_team_status", "runs", ["tenant_id", "team_id", "status"])

    op.create_table(
        "webhook_idempotency_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("delivery_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("hmac_digest", sa.String(length=128), nullable=False),
        sa.Column("disposition_status", sa.String(length=32), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "source",
            "delivery_id",
            name="uq_webhook_idempotency_source_delivery",
        ),
    )
    op.create_index(
        "ix_webhook_idempotency_tenant_team_received",
        "webhook_idempotency_records",
        ["tenant_id", "team_id", "received_at"],
    )

    op.execute("ALTER TABLE runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY runs_tenant_scope
        ON runs
        FOR ALL
        USING (app.tenant_visible(tenant_id, team_id))
        WITH CHECK (app.tenant_visible(tenant_id, team_id));
        """
    )

    op.execute("ALTER TABLE webhook_idempotency_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE webhook_idempotency_records FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY webhook_idempotency_records_tenant_scope
        ON webhook_idempotency_records
        FOR ALL
        USING (app.tenant_visible(tenant_id, team_id))
        WITH CHECK (app.tenant_visible(tenant_id, team_id));
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS webhook_idempotency_records_tenant_scope ON webhook_idempotency_records"
    )
    op.execute("ALTER TABLE IF EXISTS webhook_idempotency_records DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS runs_tenant_scope ON runs")
    op.execute("ALTER TABLE IF EXISTS runs DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_webhook_idempotency_tenant_team_received", table_name="webhook_idempotency_records")
    op.drop_table("webhook_idempotency_records")
    op.drop_index("ix_runs_tenant_team_status", table_name="runs")
    op.drop_table("runs")

    op.execute("DROP FUNCTION IF EXISTS app.tenant_visible(text, text)")
    op.execute("DROP FUNCTION IF EXISTS app.current_team_id()")
    op.execute("DROP FUNCTION IF EXISTS app.current_tenant_id()")
    op.execute("DROP SCHEMA IF EXISTS app")
