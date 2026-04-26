"""Add GitHub App and PAT integration tables.

Revision ID: 20260422_0008
Revises: 20260422_0007
Create Date: 2026-04-22 16:30:00

Expand migration - adds new tables with no destructive changes.
Reversibility: downgrade drops the four new tables; no existing data is touched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260422_0008"
down_revision = "20260422_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_app_installations",
        sa.Column("installation_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("account_login", sa.String(255), nullable=False),
        sa.Column("github_installation_id", sa.BigInteger, nullable=False),
        sa.Column("permissions_hash", sa.String(128), nullable=False),
        sa.Column(
            "github_base_url",
            sa.String(512),
            nullable=False,
            server_default="https://api.github.com",
        ),
        sa.Column("drift_acknowledged", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "team_id", name="uq_github_app_installations_tenant_team"),
    )

    op.create_table(
        "github_integration_credentials",
        sa.Column("credential_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("credential_type", sa.String(32), nullable=False),
        sa.Column("encrypted_payload", sa.Text, nullable=False),
        sa.Column("kek_id", sa.String(255), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("rotation_window_days", sa.Integer, nullable=False, server_default=sa.text("90")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tenant_id", "team_id", "credential_type",
            name="uq_github_integration_credentials_tenant_team_type",
        ),
    )

    op.create_table(
        "pat_opt_ins",
        sa.Column("opt_in_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("approver_actor", sa.String(255), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("allowed_scopes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "branch_protection_verifications",
        sa.Column("verification_id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("repo_full_name", sa.String(512), nullable=False),
        sa.Column("branch", sa.String(255), nullable=False),
        sa.Column("shadow_mode", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("missing_protections", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("evidence_summary", sa.Text, nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_github_app_installations_tenant_team", "github_app_installations", ["tenant_id", "team_id"])
    op.create_index("ix_github_integration_credentials_tenant_team", "github_integration_credentials", ["tenant_id", "team_id"])
    op.create_index("ix_pat_opt_ins_tenant_team", "pat_opt_ins", ["tenant_id", "team_id"])
    op.create_index("ix_branch_protection_verifications_run_id", "branch_protection_verifications", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_branch_protection_verifications_run_id", table_name="branch_protection_verifications")
    op.drop_index("ix_pat_opt_ins_tenant_team", table_name="pat_opt_ins")
    op.drop_index("ix_github_integration_credentials_tenant_team", table_name="github_integration_credentials")
    op.drop_index("ix_github_app_installations_tenant_team", table_name="github_app_installations")
    op.drop_table("branch_protection_verifications")
    op.drop_table("pat_opt_ins")
    op.drop_table("github_integration_credentials")
    op.drop_table("github_app_installations")
