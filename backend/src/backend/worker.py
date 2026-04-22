from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.persistence.contracts import WorkerController
from backend.persistence.factory import PersistenceAdapters, build_persistence_adapters


@dataclass(slots=True)
class WorkerBootstrap:
    worker_controller: WorkerController
    queue_name: str = "ticket-runs"


def build_worker_bootstrap(
    persistence: PersistenceAdapters | None = None,
) -> WorkerBootstrap:
    adapters = persistence or build_persistence_adapters()
    return WorkerBootstrap(
        worker_controller=adapters.worker_controller,
        queue_name=getattr(adapters.worker_controller, "queue_name", "ticket-runs"),
    )


def process_metering_rollups(
    tenant_id: str,
    period_start_iso: str,
    period_end_iso: str,
    persistence: PersistenceAdapters | None = None,
) -> int:
    adapters = persistence or build_persistence_adapters()
    period_start = datetime.fromisoformat(period_start_iso)
    period_end = datetime.fromisoformat(period_end_iso)
    rollups = adapters.metering_ledger.build_hourly_rollups(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
    )
    return len(rollups)


def process_encryption_key_rotation(
    envelopes: list[dict[str, str]],
    persistence: PersistenceAdapters | None = None,
) -> list[dict[str, str]]:
    adapters = persistence or build_persistence_adapters()
    report = adapters.encryption.rotate_stale_envelopes(envelopes)
    total = max(report.total_envelopes, 1)
    compliant = report.total_envelopes - report.due_before_rotation
    adapters.telemetry.set_gauge(
        "devsquad_encryption_rotation_sla_ratio",
        compliant / total,
    )
    adapters.telemetry.set_gauge(
        "devsquad_encryption_rotation_due_total",
        float(report.due_before_rotation),
    )
    return report.rotated_envelopes
