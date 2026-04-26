"""Add optional internal RAG pgvector tables.

Revision ID: 20260424_0009
Revises: 20260422_0008
Create Date: 2026-04-24 10:00:00

Expand migration - adds tenant-scoped knowledge tables for the optional
internal RAG capability. Downgrade drops only the application tables and
indexes introduced here. The vector extension is left installed because it
may be shared by other schemas in customer-owned PostgreSQL.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "20260424_0009"
down_revision = "20260422_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pgvector_available = _pgvector_available()
    if pgvector_available:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_documents",
        sa.Column("document_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("repo_id", sa.String(255), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_uri", sa.Text, nullable=False),
        sa.Column("source_version", sa.String(255), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "source_uri", "content_sha256", name="uq_knowledge_documents_source_hash"),
    )

    op.create_table(
        "knowledge_ingestion_jobs",
        sa.Column("job_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(128), nullable=False),
        sa.Column("document_id", sa.String(64), nullable=True),
        sa.Column("source_uri", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("embedding_model", sa.String(255), nullable=False),
        sa.Column("embedding_dims", sa.Integer, nullable=False, server_default=sa.text("1536")),
        sa.Column("total_chunks", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("processed_chunks", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.document_id"], ondelete="SET NULL"),
    )

    embedding_column = (
        "embedding vector(1536) NOT NULL"
        if pgvector_available
        else "embedding JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        f"""
        CREATE TABLE knowledge_chunks (
            chunk_id VARCHAR(64) PRIMARY KEY,
            tenant_id VARCHAR(128) NOT NULL,
            team_id VARCHAR(128) NOT NULL,
            document_id VARCHAR(64) NOT NULL REFERENCES knowledge_documents(document_id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            source_type VARCHAR(64) NOT NULL,
            content TEXT NOT NULL,
            content_sha256 VARCHAR(64) NOT NULL,
            embedding_model VARCHAR(255) NOT NULL,
            embedding_dims INTEGER NOT NULL DEFAULT 1536,
            {embedding_column},
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, document_id, chunk_index)
        )
        """
    )

    op.create_index("ix_knowledge_documents_tenant_team", "knowledge_documents", ["tenant_id", "team_id"])
    op.create_index("ix_knowledge_documents_repo", "knowledge_documents", ["tenant_id", "repo_id"])
    op.create_index("ix_knowledge_ingestion_jobs_tenant_status", "knowledge_ingestion_jobs", ["tenant_id", "status"])
    op.create_index("ix_knowledge_chunks_tenant_document", "knowledge_chunks", ["tenant_id", "document_id"])
    op.create_index("ix_knowledge_chunks_lookup", "knowledge_chunks", ["tenant_id", "embedding_model", "source_type"])
    if pgvector_available:
        op.execute(
            """
            CREATE INDEX ix_knowledge_chunks_embedding_hnsw
            ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)
            """
        )

    for table_name in ["knowledge_documents", "knowledge_ingestion_jobs", "knowledge_chunks"]:
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
    for table_name in ["knowledge_chunks", "knowledge_ingestion_jobs", "knowledge_documents"]:
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_scope ON {table_name}")
        op.execute(f"ALTER TABLE IF EXISTS {table_name} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_hnsw")
    op.drop_index("ix_knowledge_chunks_lookup", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_tenant_document", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_ingestion_jobs_tenant_status", table_name="knowledge_ingestion_jobs")
    op.drop_index("ix_knowledge_documents_repo", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_tenant_team", table_name="knowledge_documents")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_ingestion_jobs")
    op.drop_table("knowledge_documents")


def _pgvector_available() -> bool:
    connection = op.get_bind()
    return bool(
        connection.execute(
            sa.text("SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector')")
        ).scalar()
    )
