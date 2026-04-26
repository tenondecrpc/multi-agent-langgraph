from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Metric names emitted as structured log events consumed by the Prometheus
# log-exporter or the OpenTelemetry collector.
METRIC_MINT_LATENCY_MS = "github_mint_latency_ms"
METRIC_MINT_FAILURE_TOTAL = "github_mint_failure_total"
METRIC_PERMISSION_DRIFT_TOTAL = "github_permission_drift_total"
METRIC_BRANCH_PROTECTION_FAILURE_TOTAL = "github_branch_protection_failure_total"
METRIC_PAT_MODE_ACTIVE = "github_pat_mode_active"


@dataclass
class GitHubMetricLabels:
    tenant_id: str = ""
    team_id: str = ""
    installation_id: str = ""


@contextmanager
def mint_latency_span(labels: GitHubMetricLabels) -> Iterator[None]:
    start = time.monotonic()
    try:
        yield
    finally:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            METRIC_MINT_LATENCY_MS,
            extra={
                "metric": METRIC_MINT_LATENCY_MS,
                "value_ms": elapsed_ms,
                "tenant_id": labels.tenant_id,
                "team_id": labels.team_id,
                "installation_id": labels.installation_id,
            },
        )


def record_mint_failure(labels: GitHubMetricLabels, *, reason: str) -> None:
    logger.error(
        METRIC_MINT_FAILURE_TOTAL,
        extra={
            "metric": METRIC_MINT_FAILURE_TOTAL,
            "reason": reason,
            "tenant_id": labels.tenant_id,
            "team_id": labels.team_id,
            "installation_id": labels.installation_id,
        },
    )


def record_permission_drift(labels: GitHubMetricLabels) -> None:
    logger.error(
        METRIC_PERMISSION_DRIFT_TOTAL,
        extra={
            "metric": METRIC_PERMISSION_DRIFT_TOTAL,
            "tenant_id": labels.tenant_id,
            "team_id": labels.team_id,
            "installation_id": labels.installation_id,
        },
    )


def record_branch_protection_failure(
    labels: GitHubMetricLabels,
    *,
    repo: str,
    branch: str,
    missing: list[str],
    shadow_mode: bool,
) -> None:
    logger.warning(
        METRIC_BRANCH_PROTECTION_FAILURE_TOTAL,
        extra={
            "metric": METRIC_BRANCH_PROTECTION_FAILURE_TOTAL,
            "tenant_id": labels.tenant_id,
            "team_id": labels.team_id,
            "repo": repo,
            "branch": branch,
            "missing": missing,
            "shadow_mode": shadow_mode,
            "blocked": not shadow_mode,
        },
    )
