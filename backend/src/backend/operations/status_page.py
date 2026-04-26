from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from backend.persistence.health import PersistenceHealthService
from backend.persistence.telemetry import PersistenceTelemetry


class PublicComponentStatus(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"


class PublicStatusComponent(BaseModel):
    component: str
    status: PublicComponentStatus
    message: str


class PublicStatusPage(BaseModel):
    schema_version: str = "public-status.v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    status: PublicComponentStatus
    components: list[PublicStatusComponent]


class PublicStatusPageService:
    COMPONENTS = (
        "api",
        "workers",
        "database",
        "redis",
        "provider_routing",
        "sandbox_runtime",
        "persistence_backbone",
    )

    def __init__(
        self,
        *,
        health: PersistenceHealthService,
        telemetry: PersistenceTelemetry,
    ) -> None:
        self._health = health
        self._telemetry = telemetry

    def snapshot(self) -> PublicStatusPage:
        metrics = _parse_prometheus_metrics(self._telemetry.render_prometheus())
        health = self._health.snapshot()
        readiness = self._health.readiness()
        liveness = self._health.liveness()
        components = [
            _component(
                "api",
                PublicComponentStatus.OPERATIONAL
                if liveness.status == "ok" and readiness.status == "ok"
                else PublicComponentStatus.DEGRADED
                if liveness.status == "ok"
                else PublicComponentStatus.MAJOR_OUTAGE,
                "API health and readiness probes are available.",
            ),
            _worker_component(metrics),
            _adapter_component("database", configured=health.database.configured, healthy=health.database.healthy),
            _adapter_component("redis", configured=health.redis.configured, healthy=health.redis.healthy),
            _provider_routing_component(metrics),
            _component(
                "sandbox_runtime",
                PublicComponentStatus.OPERATIONAL,
                "Sandbox runtime has no active public incident signal.",
            ),
            _component(
                "persistence_backbone",
                PublicComponentStatus.OPERATIONAL
                if readiness.status == "ok"
                else PublicComponentStatus.DEGRADED,
                "Persistence readiness is reported through health probes.",
            ),
        ]
        return PublicStatusPage(
            status=_aggregate_status(component.status for component in components),
            components=components,
        )


def _component(
    component: str,
    status: PublicComponentStatus,
    message: str,
) -> PublicStatusComponent:
    return PublicStatusComponent(component=component, status=status, message=message)


def _adapter_component(
    component: str,
    *,
    configured: bool,
    healthy: bool,
) -> PublicStatusComponent:
    if healthy:
        status = PublicComponentStatus.OPERATIONAL
        message = f"{component} adapter is healthy."
    elif configured:
        status = PublicComponentStatus.MAJOR_OUTAGE
        message = f"{component} adapter is configured but unhealthy."
    else:
        status = PublicComponentStatus.DEGRADED
        message = f"{component} adapter is not configured in this profile."
    return _component(component, status, message)


def _worker_component(metrics: dict[str, float]) -> PublicStatusComponent:
    dlq_depth = metrics.get("devsquad_dlq_depth", 0.0)
    if dlq_depth >= 100:
        return _component(
            "workers",
            PublicComponentStatus.PARTIAL_OUTAGE,
            "Worker dead-letter queue growth indicates failed processing.",
        )
    if dlq_depth > 0:
        return _component(
            "workers",
            PublicComponentStatus.DEGRADED,
            "Worker dead-letter queue has pending failures.",
        )
    return _component(
        "workers",
        PublicComponentStatus.OPERATIONAL,
        "Worker queue signals are within public status thresholds.",
    )


def _provider_routing_component(metrics: dict[str, float]) -> PublicStatusComponent:
    circuit_state = metrics.get("devsquad_provider_circuit_breaker_state", 0.0)
    if circuit_state >= 2:
        return _component(
            "provider_routing",
            PublicComponentStatus.PARTIAL_OUTAGE,
            "Provider routing circuit breaker is open.",
        )
    if circuit_state > 0:
        return _component(
            "provider_routing",
            PublicComponentStatus.DEGRADED,
            "Provider routing circuit breaker is probing recovery.",
        )
    return _component(
        "provider_routing",
        PublicComponentStatus.OPERATIONAL,
        "Provider routing is within public status thresholds.",
    )


def _aggregate_status(statuses: Iterable[PublicComponentStatus]) -> PublicComponentStatus:
    order = {
        PublicComponentStatus.OPERATIONAL: 0,
        PublicComponentStatus.DEGRADED: 1,
        PublicComponentStatus.PARTIAL_OUTAGE: 2,
        PublicComponentStatus.MAJOR_OUTAGE: 3,
    }
    return max(statuses, key=lambda status: order[status])


def _parse_prometheus_metrics(payload: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in payload.splitlines():
        if not line or line.startswith("#"):
            continue
        name_and_labels, _, raw_value = line.partition(" ")
        if not raw_value:
            continue
        metric_name = name_and_labels.split("{", 1)[0]
        try:
            value = float(raw_value)
        except ValueError:
            continue
        values[metric_name] = max(values.get(metric_name, value), value)
    return values
