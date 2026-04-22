"""Add durable budget ledger tables.

Revision ID: 20260418_0004
Revises: 20260418_0003
Create Date: 2026-04-18 16:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260418_0004"
down_revision = "20260418_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_cap_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_key", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("ticket_cap_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("daily_team_cap_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("monthly_team_cap_usd", sa.Numeric(precision=14, scale=6), nullable=False),
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
        sa.UniqueConstraint("run_id", name="uq_budget_cap_snapshots_run_id"),
    )
    op.create_index(
        "ix_budget_cap_snapshots_tenant_team_updated_at",
        "budget_cap_snapshots",
        ["tenant_id", "team_id", "updated_at"],
    )

    op.create_table(
        "budget_reservations",
        sa.Column("reservation_id", sa.String(length=64), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_key", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("reserved_amount_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("ticket_cap_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("daily_team_cap_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("monthly_team_cap_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("ticket_cap_remaining_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column(
            "daily_team_cap_remaining_usd",
            sa.Numeric(precision=14, scale=6),
            nullable=False,
        ),
        sa.Column(
            "monthly_team_cap_remaining_usd",
            sa.Numeric(precision=14, scale=6),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column("released_amount_usd", sa.Numeric(precision=14, scale=6), nullable=True),
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
        "ix_budget_reservations_tenant_team_created_at",
        "budget_reservations",
        ["tenant_id", "team_id", "created_at"],
    )
    op.create_index(
        "ix_budget_reservations_run_id_status",
        "budget_reservations",
        ["run_id", "status"],
    )

    op.create_table(
        "budget_charges",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("reservation_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("actual_cost_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("refunded_amount_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["reservation_id"], ["budget_reservations.reservation_id"]),
        sa.UniqueConstraint("reservation_id", name="uq_budget_charges_reservation_id"),
    )
    op.create_index(
        "ix_budget_charges_tenant_team_created_at",
        "budget_charges",
        ["tenant_id", "team_id", "created_at"],
    )

    op.create_table(
        "budget_denials",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("team_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("ticket_key", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("requested_amount_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("ticket_cap_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("daily_team_cap_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("monthly_team_cap_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("denial_reason", sa.String(length=64), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_budget_denials_tenant_team_created_at",
        "budget_denials",
        ["tenant_id", "team_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_budget_denials_tenant_team_created_at", table_name="budget_denials")
    op.drop_table("budget_denials")

    op.drop_index("ix_budget_charges_tenant_team_created_at", table_name="budget_charges")
    op.drop_table("budget_charges")

    op.drop_index("ix_budget_reservations_run_id_status", table_name="budget_reservations")
    op.drop_index("ix_budget_reservations_tenant_team_created_at", table_name="budget_reservations")
    op.drop_table("budget_reservations")

    op.drop_index(
        "ix_budget_cap_snapshots_tenant_team_updated_at",
        table_name="budget_cap_snapshots",
    )
    op.drop_table("budget_cap_snapshots")
