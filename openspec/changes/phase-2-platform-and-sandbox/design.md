## Context

This phase captures the platform substrate that will host the runtime SDD flow defined in phase 1. `docs/PLAN.md` already describes a self-hosted Kubernetes architecture, public APIs, queueing model, and gVisor sandbox plane, but those concerns need to be separated into stable capability specs before implementation begins.

## Goals / Non-Goals

**Goals:**
- Define the baseline self-hosted topology for connected and air-gapped deployments.
- Define the public API contract surface and versioning rules that later backend and frontend work must follow.
- Define the worker and queue operating model, including fair dispatch, shutdown, retry capture, and scaling assumptions.
- Define the sandbox execution plane as a hardened per-tenant Kubernetes job model.

**Non-Goals:**
- Authentication, RBAC, webhook signature validation, and credential encryption details.
- LLM provider routing, budgets, metering, or billing behavior.
- Admin graph configuration, shadow mode activation, or frontend control-room behavior.
- Observability, release engineering, or disaster recovery drill definitions.

## Decisions

- The product remains self-hosted only and single-customer at the infrastructure boundary, with both connected and air-gapped profiles treated as first-class from the design stage.
- The repository structure is planned up front as `backend/`, `frontend/`, `helm/`, and `docs/` so later phases can target concrete locations without inventing parallel layouts.
- Public APIs are versioned under `/api/v1`, while webhook intake and health endpoints remain explicit surfaces with their own contracts and later security controls.
- Worker behavior is defined separately from the runtime graph contract so queue fairness, graceful draining, and DLQ handling can be validated independently.
- Sandbox execution uses hardened Kubernetes Jobs with gVisor, per-tenant namespaces, non-root execution, egress restrictions, and cleanup jobs as baseline requirements rather than optional hardening.
- The `local-minikube` profile is a functional integration environment, not proof of production HA or SLO acceptance.

## Risks / Trade-offs

- Platform scope is broad, but deferring these requirements would let implementation couple runtime behavior to ad hoc deployment assumptions.
- Queueing, sandboxing, and API design all have downstream security implications, so this phase intentionally leaves some details to later security and operations phases while still freezing the baseline contract.
- Treating air-gapped support as first-class increases upfront planning complexity, but it avoids late architectural exceptions that would violate repository guardrails.
