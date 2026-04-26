from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: object) -> str:
        return f"vector({self.dimensions})"

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)

runs = Table(
    "runs",
    metadata,
    # High-level run state lives here; LangGraph checkpoints land in
    # PostgresSaver-managed tables in a later task.
    Column("run_id", String(64), primary_key=True),
    Column("thread_id", String(255), nullable=False, unique=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("repo_id", String(255), nullable=False),
    Column("ticket_key", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("current_node", String(64), nullable=False),
    Column("paused_at_node", String(64), nullable=True),
    Column("escalation_reason", String(128), nullable=True),
    Column("escalation_sink", Text(), nullable=True),
    Column("config_snapshot_id", String(255), nullable=False),
    Column("graph_profile_id", String(255), nullable=False),
    Column("catalog_version", String(255), nullable=False),
    Column("state_schema_version", String(32), nullable=False, server_default=text("'1'")),
    Column(
        "artifact_hashes",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    ),
    Column(
        "run_payload",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

webhook_idempotency_records = Table(
    "webhook_idempotency_records",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("source", String(64), nullable=False),
    Column("delivery_id", String(255), nullable=False),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("endpoint", String(255), nullable=False),
    Column("hmac_digest", String(128), nullable=False),
    Column("disposition_status", String(32), nullable=False),
    Column(
        "received_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    UniqueConstraint("source", "delivery_id", name="uq_webhook_idempotency_source_delivery"),
)

dead_letter_records = Table(
    "dead_letter_records",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("job_id", String(64), nullable=False),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("run_id", String(64), nullable=False),
    Column("queue_name", String(255), nullable=False),
    Column("worker_id", String(255), nullable=True),
    Column("failure_reason", Text, nullable=False),
    Column("checkpoint_ref", Text, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

budget_cap_snapshots = Table(
    "budget_cap_snapshots",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("run_id", String(64), nullable=False, unique=True),
    Column("ticket_key", String(128), nullable=False),
    Column("role", String(64), nullable=False),
    Column("ticket_cap_usd", Numeric(14, 6), nullable=False),
    Column("daily_team_cap_usd", Numeric(14, 6), nullable=False),
    Column("monthly_team_cap_usd", Numeric(14, 6), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

budget_reservations = Table(
    "budget_reservations",
    metadata,
    Column("reservation_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("run_id", String(64), nullable=False),
    Column("ticket_key", String(128), nullable=False),
    Column("role", String(64), nullable=False),
    Column("reserved_amount_usd", Numeric(14, 6), nullable=False),
    Column("ticket_cap_usd", Numeric(14, 6), nullable=False),
    Column("daily_team_cap_usd", Numeric(14, 6), nullable=False),
    Column("monthly_team_cap_usd", Numeric(14, 6), nullable=False),
    Column("ticket_cap_remaining_usd", Numeric(14, 6), nullable=False),
    Column("daily_team_cap_remaining_usd", Numeric(14, 6), nullable=False),
    Column("monthly_team_cap_remaining_usd", Numeric(14, 6), nullable=False),
    Column("status", String(32), nullable=False),
    Column("release_reason", Text, nullable=True),
    Column("released_amount_usd", Numeric(14, 6), nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

budget_charges = Table(
    "budget_charges",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("reservation_id", String(64), nullable=False, unique=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("run_id", String(64), nullable=False),
    Column("estimated_cost_usd", Numeric(14, 6), nullable=False),
    Column("actual_cost_usd", Numeric(14, 6), nullable=False),
    Column("refunded_amount_usd", Numeric(14, 6), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

budget_denials = Table(
    "budget_denials",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("run_id", String(64), nullable=False),
    Column("ticket_key", String(128), nullable=False),
    Column("role", String(64), nullable=False),
    Column("requested_amount_usd", Numeric(14, 6), nullable=False),
    Column("ticket_cap_usd", Numeric(14, 6), nullable=False),
    Column("daily_team_cap_usd", Numeric(14, 6), nullable=False),
    Column("monthly_team_cap_usd", Numeric(14, 6), nullable=False),
    Column("denial_reason", String(64), nullable=False),
    Column("evidence_summary", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

metering_facts = Table(
    "metering_facts",
    metadata,
    Column("usage_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("run_id", String(64), nullable=False),
    Column("ticket_key", String(128), nullable=False),
    Column("role", String(64), nullable=False),
    Column("provider_id", String(128), nullable=False),
    Column("model_id", String(255), nullable=False),
    Column("deployment_profile", String(64), nullable=False),
    Column("fallback_used", Boolean, nullable=False, server_default=text("false")),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cached_tokens", Integer, nullable=False, server_default=text("0")),
    Column("latency_ms", Integer, nullable=False),
    Column("request_count", Integer, nullable=False, server_default=text("1")),
    Column("reservation_id", String(64), nullable=True),
    Column("estimated_cost_usd", Numeric(14, 6), nullable=False),
    Column("actual_cost_usd", Numeric(14, 6), nullable=False),
    Column("rate_card_id", String(255), nullable=False),
    Column("trace_id", String(255), nullable=False),
    Column("span_id", String(255), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True), nullable=False),
    Column("status", String(64), nullable=False),
)

metering_hourly_rollups = Table(
    "metering_hourly_rollups",
    metadata,
    Column("rollup_id", String(255), primary_key=True),
    Column("bucket_start", DateTime(timezone=True), nullable=False),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("role", String(64), nullable=False),
    Column("provider_id", String(128), nullable=False),
    Column("model_id", String(255), nullable=False),
    Column("rate_card_id", String(255), nullable=False),
    Column("request_count", Integer, nullable=False),
    Column("total_input_tokens", Integer, nullable=False),
    Column("total_output_tokens", Integer, nullable=False),
    Column("total_actual_cost_usd", Numeric(14, 6), nullable=False),
    Column("usage_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("sealed", Boolean, nullable=False, server_default=text("false")),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

model_catalog_entries = Table(
    "model_catalog_entries",
    metadata,
    Column("model_id", String(255), primary_key=True),
    Column("provider_id", String(128), nullable=False),
    Column("deployment_profile", String(64), primary_key=True),
    Column("max_input_tokens", Integer, nullable=False),
    Column("max_output_tokens", Integer, nullable=False),
    Column("default_price_card_id", String(255), nullable=False),
    Column("supports_tools", Boolean, nullable=False, server_default=text("false")),
    Column("supports_json_mode", Boolean, nullable=False, server_default=text("false")),
    Column("supports_streaming", Boolean, nullable=False, server_default=text("false")),
    Column(
        "allowed_fallback_targets",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    ),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

role_token_policies = Table(
    "role_token_policies",
    metadata,
    Column("role", String(64), primary_key=True),
    Column("max_input_tokens", Integer, nullable=False),
    Column("max_output_tokens", Integer, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

provider_health_events = Table(
    "provider_health_events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("provider_id", String(128), nullable=False),
    Column("event_kind", String(64), nullable=False),
    Column("state", String(32), nullable=False),
    Column("consecutive_failures", Integer, nullable=False, server_default=text("0")),
    Column("remaining_probe_attempts", Integer, nullable=False, server_default=text("0")),
    Column("evidence_summary", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

graph_versions = Table(
    "graph_versions",
    metadata,
    Column("record_id", String(64), primary_key=True),
    Column("version_number", Integer, nullable=False, unique=True),
    Column("created_by", String(255), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

agent_versions = Table(
    "agent_versions",
    metadata,
    Column("record_id", String(64), primary_key=True),
    Column("version_number", Integer, nullable=False, unique=True),
    Column("created_by", String(255), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

shadow_reports = Table(
    "shadow_reports",
    metadata,
    Column("report_id", String(64), primary_key=True),
    Column("candidate_version_id", String(64), nullable=False),
    Column("active_version_id", String(64), nullable=True),
    Column("success_rate_delta", Numeric(8, 4), nullable=False),
    Column("cost_delta_usd", Numeric(12, 4), nullable=False),
    Column("safety_regressions", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("blocked", Boolean, nullable=False),
    Column("blocking_reasons", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("report_payload", JSONB, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

snapshots = Table(
    "snapshots",
    metadata,
    Column("snapshot_id", String(64), primary_key=True),
    Column("graph_version_id", String(64), nullable=False),
    Column("agent_version_ids", JSONB, nullable=False),
    Column("shadow_report_id", String(64), nullable=True),
    Column("supersedes_snapshot_id", String(64), nullable=True),
    Column("created_by", String(255), nullable=False),
    Column("evidence_summary", Text, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

control_plane_state = Table(
    "control_plane_state",
    metadata,
    Column("state_key", String(32), primary_key=True),
    Column("active_snapshot_id", String(64), nullable=True),
    Column("revision", Integer, nullable=False, server_default=text("0")),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

run_snapshot_bindings = Table(
    "run_snapshot_bindings",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("snapshot_id", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("event_id", String(64), primary_key=True),
    Column("action", String(32), nullable=False),
    Column("actor", String(255), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("target_id", String(64), nullable=False),
    Column("evidence_summary", Text, nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

api_deprecations = Table(
    "api_deprecations",
    metadata,
    Column("deprecation_id", String(64), primary_key=True),
    Column("route", String(255), nullable=False),
    Column("method", String(16), nullable=False),
    Column("version", String(32), nullable=False),
    Column("deprecated_at", DateTime(timezone=True), nullable=False),
    Column("sunset_at", DateTime(timezone=True), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("replacement_route", String(255), nullable=True),
    Column("active", Boolean, nullable=False, server_default=text("true")),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    UniqueConstraint("route", "method", "version", name="uq_api_deprecations_route_method_version"),
)

github_app_installations = Table(
    "github_app_installations",
    metadata,
    Column("installation_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("account_login", String(255), nullable=False),
    Column("github_installation_id", BigInteger, nullable=False),
    Column("permissions_hash", String(128), nullable=False),
    Column("github_base_url", String(512), nullable=False, server_default=text("'https://api.github.com'")),
    Column("drift_acknowledged", Boolean, nullable=False, server_default=text("true")),
    Column(
        "granted_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    UniqueConstraint("tenant_id", "team_id", name="uq_github_app_installations_tenant_team"),
)

github_integration_credentials = Table(
    "github_integration_credentials",
    metadata,
    Column("credential_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("credential_type", String(32), nullable=False),
    Column("encrypted_payload", Text, nullable=False),
    Column("kek_id", String(255), nullable=False),
    Column(
        "rotated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("rotation_window_days", Integer, nullable=False, server_default=text("90")),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    UniqueConstraint(
        "tenant_id", "team_id", "credential_type",
        name="uq_github_integration_credentials_tenant_team_type",
    ),
)

pat_opt_ins = Table(
    "pat_opt_ins",
    metadata,
    Column("opt_in_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("approver_actor", String(255), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("allowed_scopes", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column(
        "expires_at",
        DateTime(timezone=True),
        nullable=False,
    ),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

branch_protection_verifications = Table(
    "branch_protection_verifications",
    metadata,
    Column("verification_id", String(64), primary_key=True),
    Column("run_id", String(64), nullable=False),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("repo_full_name", String(512), nullable=False),
    Column("branch", String(255), nullable=False),
    Column("shadow_mode", Boolean, nullable=False, server_default=text("true")),
    Column("passed", Boolean, nullable=False),
    Column("missing_protections", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("evidence_summary", Text, nullable=False),
    Column(
        "verified_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

knowledge_documents = Table(
    "knowledge_documents",
    metadata,
    Column("document_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column("repo_id", String(255), nullable=True),
    Column("title", String(512), nullable=False),
    Column("source_type", String(64), nullable=False),
    Column("source_uri", Text, nullable=False),
    Column("source_version", String(255), nullable=True),
    Column("content_sha256", String(64), nullable=False),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("active", Boolean, nullable=False, server_default=text("true")),
    Column("created_by", String(255), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    UniqueConstraint("tenant_id", "source_uri", "content_sha256", name="uq_knowledge_documents_source_hash"),
)

knowledge_ingestion_jobs = Table(
    "knowledge_ingestion_jobs",
    metadata,
    Column("job_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column(
        "document_id",
        String(64),
        ForeignKey("knowledge_documents.document_id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("source_uri", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("embedding_model", String(255), nullable=False),
    Column("embedding_dims", Integer, nullable=False, server_default=text("1536")),
    Column("total_chunks", Integer, nullable=False, server_default=text("0")),
    Column("processed_chunks", Integer, nullable=False, server_default=text("0")),
    Column("error_message", Text, nullable=True),
    Column("created_by", String(255), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("completed_at", DateTime(timezone=True), nullable=True),
)

knowledge_chunks = Table(
    "knowledge_chunks",
    metadata,
    Column("chunk_id", String(64), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("team_id", String(128), nullable=False),
    Column(
        "document_id",
        String(64),
        ForeignKey("knowledge_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("chunk_index", Integer, nullable=False),
    Column("source_type", String(64), nullable=False),
    Column("content", Text, nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("embedding_model", String(255), nullable=False),
    Column("embedding_dims", Integer, nullable=False, server_default=text("1536")),
    Column("embedding", Vector(1536), nullable=False),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    UniqueConstraint("tenant_id", "document_id", "chunk_index", name="uq_knowledge_chunks_tenant_document_index"),
)
