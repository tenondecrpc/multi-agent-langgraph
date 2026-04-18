from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class IncidentSeverity(StrEnum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class LogEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    level: str
    service: str
    component: str
    tenant_id: str | None = None
    team_id: str | None = None
    run_id: str | None = None
    trace_id: str | None = None
    event_type: str
    message: str


class HealthProbeResult(BaseModel):
    component: str
    healthy: bool
    ready: bool
    reasons: list[str] = Field(default_factory=list)


class DashboardDefinition(BaseModel):
    dashboard_id: str
    title: str
    panels: list[str]


class RunbookReference(BaseModel):
    alert_name: str
    runbook_id: str
    pager_worthy: bool = False


class StatusUpdate(BaseModel):
    component: str
    status: str
    message: str
    public: bool = True


class IncidentRecord(BaseModel):
    incident_id: str
    severity: IncidentSeverity
    component: str
    summary: str
    runbook_id: str | None = None
    public_updates: list[StatusUpdate] = Field(default_factory=list)


class ObservabilityCatalog:
    def __init__(self) -> None:
        self.logs: list[LogEvent] = []
        self.dashboards: dict[str, DashboardDefinition] = {}
        self.runbooks: dict[str, RunbookReference] = {}
        self.incidents: dict[str, IncidentRecord] = {}

    def emit_log(self, event: LogEvent) -> None:
        self.logs.append(event)

    def register_dashboard(self, dashboard: DashboardDefinition) -> None:
        self.dashboards[dashboard.dashboard_id] = dashboard

    def register_runbook(self, runbook: RunbookReference) -> None:
        self.runbooks[runbook.alert_name] = runbook

    def record_incident(self, incident: IncidentRecord) -> None:
        if incident.severity in {IncidentSeverity.SEV1, IncidentSeverity.SEV2} and incident.runbook_id is None:
            raise ValueError("Pager-worthy incidents must reference a runbook.")
        self.incidents[incident.incident_id] = incident

    def publish_status_update(self, incident_id: str, update: StatusUpdate) -> None:
        incident = self.incidents[incident_id]
        incident.public_updates.append(update)
