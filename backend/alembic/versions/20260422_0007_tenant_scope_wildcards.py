"""Allow admin-scoped tenant GUC wildcards for tenant-partitioned tables.

Revision ID: 20260422_0007
Revises: 20260418_0006
Create Date: 2026-04-22 16:10:00
"""

from __future__ import annotations

from alembic import op

revision = "20260422_0007"
down_revision = "20260418_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.tenant_visible(row_tenant_id text, row_team_id text)
        RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $$
            SELECT
                (
                    app.current_tenant_id() = '*'
                    OR row_tenant_id = app.current_tenant_id()
                )
                AND (
                    app.current_team_id() = '*'
                    OR row_team_id = app.current_team_id()
                )
        $$;
        """
    )


def downgrade() -> None:
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
