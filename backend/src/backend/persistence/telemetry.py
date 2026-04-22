from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from threading import Lock
from time import perf_counter

from pydantic import BaseModel, Field


class TelemetrySpan(BaseModel):
    name: str
    attributes: dict[str, str] = Field(default_factory=dict)
    duration_seconds: float


class PersistenceTelemetry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = defaultdict(list)
        self._spans: list[TelemetrySpan] = []

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self._gauges[(name, _label_key(labels))] = value

    def increment(self, name: str, amount: float = 1.0, **labels: str) -> None:
        with self._lock:
            self._counters[(name, _label_key(labels))] += amount

    def observe(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self._histograms[(name, _label_key(labels))].append(value)

    @contextmanager
    def trace(self, name: str, **attributes: str | None) -> Iterator[None]:
        started = perf_counter()
        cleaned = {
            key: value
            for key, value in attributes.items()
            if value not in {None, ""}
        }
        try:
            yield
        finally:
            duration = perf_counter() - started
            subsystem = cleaned.get("subsystem", "unknown")
            operation = cleaned.get("operation", name)
            self.observe(
                "devsquad_persistence_operation_seconds",
                duration,
                subsystem=subsystem,
                operation=operation,
            )
            with self._lock:
                self._spans.append(
                    TelemetrySpan(
                        name=name,
                        attributes={key: str(value) for key, value in cleaned.items()},
                        duration_seconds=duration,
                    )
                )

    def spans(self) -> list[TelemetrySpan]:
        with self._lock:
            return [span.model_copy(deep=True) for span in self._spans]

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(_render_metric(name, value, labels))
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(_render_metric(name, value, labels))
            for (name, labels), values in sorted(self._histograms.items()):
                lines.append(_render_metric(f"{name}_count", float(len(values)), labels))
                lines.append(_render_metric(f"{name}_sum", sum(values), labels))
        return "\n".join(lines) + ("\n" if lines else "")


def bootstrap_telemetry(
    *,
    migration_version: str | None = None,
    pool_utilisation: float = 0.0,
    pool_wait_p95: float = 0.0,
) -> PersistenceTelemetry:
    telemetry = PersistenceTelemetry()
    telemetry.set_gauge("devsquad_database_pool_utilisation_ratio", pool_utilisation)
    telemetry.set_gauge("devsquad_database_pool_wait_p95_seconds", pool_wait_p95)
    telemetry.set_gauge("devsquad_redis_command_p95_seconds", 0.0)
    telemetry.set_gauge("devsquad_provider_circuit_breaker_state", 0.0, provider_id="bootstrap")
    telemetry.set_gauge("devsquad_dlq_depth", 0.0)
    telemetry.increment("devsquad_webhook_dedupe_hits_total", 0.0)
    telemetry.increment("devsquad_budget_reservation_denials_total", 0.0)
    telemetry.set_gauge("devsquad_encryption_rotation_sla_ratio", 1.0)
    telemetry.set_gauge("devsquad_encryption_rotation_due_total", 0.0)
    telemetry.set_gauge(
        "devsquad_persistence_migration_info",
        1.0,
        revision=migration_version or "unknown",
    )
    return telemetry


def _render_metric(name: str, value: float, labels: tuple[tuple[str, str], ...]) -> str:
    if labels:
        rendered_labels = ",".join(f'{key}="{value}"' for key, value in labels)
        return f"{name}{{{rendered_labels}}} {value}"
    return f"{name} {value}"


def _label_key(labels: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((key, str(value)) for key, value in labels.items()))
