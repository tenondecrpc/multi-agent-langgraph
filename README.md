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

## Agent observability with LangSmith

LangSmith tracing is disabled by default. The setup differs between local Minikube and a real cluster deployment.

### Local Minikube

Create the Kubernetes secret directly (no Vault in local):

```bash
kubectl create secret generic dev-squad-langsmith \
  --from-literal=api-key=<your-LANGSMITH_API_KEY>
```

Then set the env vars in the pod before applying the manifests:

```bash
kubectl set env deployment/backend \
  LANGCHAIN_TRACING_V2=true \
  LANGSMITH_API_KEY=<your-LANGSMITH_API_KEY> \
  LANGSMITH_PROJECT=langgraph-dev-squad-local
```

### Staging and production (Helm + Vault)

Store the API key in Vault once. External Secrets Operator syncs it into the cluster automatically (refreshes every hour).

```bash
vault kv patch kv/langgraph-dev-squad/runtime \
  langsmith_api_key=<your-LANGSMITH_API_KEY>
```

Then deploy with the environment-specific values file:

```bash
# Staging
helm upgrade --install dev-squad ./helm \
  -f helm/values.yaml \
  -f helm/values-staging.yaml

# Production
helm upgrade --install dev-squad ./helm \
  -f helm/values.yaml \
  -f helm/values-prod.yaml
```

Each file sets `langsmith.enabled: true` and a dedicated project name (`langgraph-dev-squad-staging` / `langgraph-dev-squad-prod`) so traces are separated by environment in the LangSmith UI.

For a self-hosted LangSmith instance add `langsmith.endpoint: "https://langsmith.example.internal"` to your values override.

> **Air-gapped deployments:** LangSmith is permanently disabled in `values-air-gapped.yaml`. The pods set `DO_NOT_TRACK=1` and `LANGCHAIN_TRACING_V2=false` to suppress PostHog network flush errors from the `langsmith` transitive dependency.

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
