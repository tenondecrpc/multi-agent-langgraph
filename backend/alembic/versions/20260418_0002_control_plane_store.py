"""Add durable control-plane persistence tables.

Revision ID: 20260418_0002
Revises: 20260418_0001
Create Date: 2026-04-18 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260418_0002"
down_revision = "20260418_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "graph_versions",
        sa.Column("record_id", sa.String(length=64), primary_key=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("version_number", name="uq_graph_versions_version_number"),
    )

    op.create_table(
        "agent_versions",
        sa.Column("record_id", sa.String(length=64), primary_key=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("version_number", name="uq_agent_versions_version_number"),
    )

    op.create_table(
        "shadow_reports",
        sa.Column("report_id", sa.String(length=64), primary_key=True),
        sa.Column("candidate_version_id", sa.String(length=64), nullable=False),
        sa.Column("active_version_id", sa.String(length=64), nullable=True),
        sa.Column("success_rate_delta", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("cost_delta_usd", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column(
            "safety_regressions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("blocked", sa.Boolean(), nullable=False),
        sa.Column(
            "blocking_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "report_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "snapshots",
        sa.Column("snapshot_id", sa.String(length=64), primary_key=True),
        sa.Column("graph_version_id", sa.String(length=64), nullable=False),
        sa.Column(
            "agent_version_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("shadow_report_id", sa.String(length=64), nullable=True),
        sa.Column("supersedes_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["graph_version_id"], ["graph_versions.record_id"]),
        sa.ForeignKeyConstraint(["shadow_report_id"], ["shadow_reports.report_id"]),
        sa.ForeignKeyConstraint(["supersedes_snapshot_id"], ["snapshots.snapshot_id"]),
    )
    op.create_index("ix_snapshots_graph_version_created", "snapshots", ["graph_version_id", "created_at"])

    op.create_table(
        "control_plane_state",
        sa.Column("state_key", sa.String(length=32), primary_key=True),
        sa.Column("active_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["active_snapshot_id"], ["snapshots.snapshot_id"]),
    )
    op.execute(
        """
        INSERT INTO control_plane_state (state_key, active_snapshot_id, revision)
        VALUES ('global', NULL, 0)
        """
    )

    op.create_table(
        "run_snapshot_bindings",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(["run_id"], ["runs.run_id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["snapshots.snapshot_id"]),
    )
    op.create_index(
        "ix_run_snapshot_bindings_snapshot_status",
        "run_snapshot_bindings",
        ["snapshot_id", "status"],
    )

    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_audit_events_target_created_at",
        "audit_events",
        ["target_id", "created_at"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.reject_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION app.reject_audit_event_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS app.reject_audit_event_mutation()")

    op.drop_index("ix_audit_events_target_created_at", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_run_snapshot_bindings_snapshot_status", table_name="run_snapshot_bindings")
    op.drop_table("run_snapshot_bindings")

    op.drop_table("control_plane_state")

    op.drop_index("ix_snapshots_graph_version_created", table_name="snapshots")
    op.drop_table("snapshots")

    op.drop_table("shadow_reports")
    op.drop_table("agent_versions")
    op.drop_table("graph_versions")
