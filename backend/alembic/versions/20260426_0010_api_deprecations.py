"""Add API deprecations catalog.

Revision ID: 20260426_0010
Revises: 20260424_0009
Create Date: 2026-04-26 14:30:00

Expand migration - adds a public API deprecation catalog used to emit
Deprecation and Sunset headers and to drive operator visibility. Downgrade
drops only the table and indexes introduced here.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260426_0010"
down_revision = "20260424_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_deprecations",
        sa.Column("deprecation_id", sa.String(64), primary_key=True),
        sa.Column("route", sa.String(255), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sunset_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("replacement_route", sa.String(255), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("route", "method", "version", name="uq_api_deprecations_route_method_version"),
    )
    op.create_index("ix_api_deprecations_sunset_at", "api_deprecations", ["sunset_at"])


def downgrade() -> None:
    op.drop_index("ix_api_deprecations_sunset_at", table_name="api_deprecations")
    op.drop_table("api_deprecations")
