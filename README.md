# LangGraph Dev Squad

A self-hosted, enterprise-grade multi-agent system that ingests Jira tickets, iterates on code until tests pass, and opens GitHub pull requests - all running inside customer-owned Kubernetes infrastructure.

## How it works

A Jira webhook triggers the pipeline. A LangGraph graph orchestrates five agents in sequence:

```
planner -> coder -> tester -> reviewer -> pr_creator
```

Each step is guarded: code cannot reach PR creation unless tests pass, the reviewer approves, the diff is within size limits, and there are no merge conflicts. Any failure routes to a registered escalation sink instead of silently continuing.

## Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph StateGraph |
| API and webhooks | FastAPI |
| Queue and pub/sub | ARQ + Redis |
| Persistence | PostgreSQL 16 (checkpoints, config, audit) |
| Frontend | Vite + React + TypeScript |
| Sandbox | Kubernetes Jobs + gVisor |
| Secrets | HashiCorp Vault + External Secrets Operator |
| Observability | OpenTelemetry, Prometheus, Grafana, Loki |
| Delivery | Helm, Argo Rollouts |

## Repository layout

```
backend/        FastAPI app, LangGraph graph, ARQ workers
frontend/       Admin and monitoring UI
helm/           Helm charts for Kubernetes (connected and air-gapped)
k8s/            Base Kubernetes manifests for local development
docs/           Operator and integrator documentation
openspec/       Spec-Driven Development artifacts (proposals, specs, tasks)
```

## Running on Minikube

**Requirements:** [minikube](https://minikube.sigs.k8s.io/docs/start/), [kubectl](https://kubernetes.io/docs/tasks/tools/)

Minikube is the canonical local runtime workflow for this repository. Use it for local validation so the project has one consistent path as the stack evolves toward fast full-flow testing with Kubernetes-managed dependencies. This README uses one consistent access method for Minikube: `kubectl port-forward`.

### 1. Start Minikube

```bash
minikube start --driver=docker --memory=4g --cpus=2
```

### 2. Choose one deployment style

#### Option A - `make`

```bash
make minikube-up
```

This builds both images inside Minikube and deploys the manifests from `k8s/`.

#### Option B - manual commands

```bash
minikube image build -t langgraph-backend:latest ./backend
minikube image build -t langgraph-frontend:latest ./frontend
kubectl apply -f k8s/
```

### 3. Wait for pods to be ready

```bash
kubectl get pods -w
# Both pods should reach Running status with 1/1 Ready
```

### 4. Access the services

```bash
# Backend API - terminal 1
kubectl port-forward svc/backend 18000:8000
# => http://127.0.0.1:18000  (API docs at /docs)

# Frontend UI - terminal 2
kubectl port-forward svc/frontend 18080:80
# => http://127.0.0.1:18080
```

Use these forwarded localhost URLs for all manual checks and smoke tests in this mode.

### 5. Smoke test

Run the backend port-forward from step 4 before executing these commands.

```bash
# Health check
curl http://127.0.0.1:18000/healthz

# Simulate a full workflow run
curl -s -X POST http://127.0.0.1:18000/api/v1/runtime/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "planning": {
      "tenant_id": "tenant-alpha",
      "repo_id": "repo-main",
      "ticket_key": "PROJ-1",
      "summary": "Add login page"
    }
  }' | python3 -m json.tool
```

### Tear down

```bash
make minikube-delete
minikube stop
```

Manual equivalent:

```bash
kubectl delete -f k8s/
minikube stop
```

## Development commands

```bash
# Lint
uv run --project backend ruff check backend/src backend/tests

# Backend tests
uv run --project backend pytest

# Frontend tests
npm run --prefix frontend test -- --run
```

## Current state

The backend graph and API are functional, and Minikube is the only documented local runtime path. PostgreSQL, Redis, Vault, and real LLM provider connections are wired in later deployment phases via Helm chart values.
