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
contracts/      Machine-readable API contracts and approval registries
operations/     Deployable operational artifacts such as alerts and dashboards
docs/           Human-readable operator, integrator, and developer documentation
openspec/       Spec-Driven Development artifacts (proposals, specs, tasks)
```

## Prerequisites

| Tool | Minimum version | Purpose |
|---|---|---|
| Python | 3.12+ | Backend runtime |
| uv | latest | Python dependency management |
| Node.js | 18+ | Frontend build and dev server |
| Docker | 20+ | Minikube image builds |
| minikube | 1.30+ | Local Kubernetes cluster |
| kubectl | 1.28+ | Kubernetes CLI |

Install [uv](https://docs.astral.sh/uv/) if you do not have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Required environment variables

The backend requires these variables at startup. Without them the process exits immediately with a `RuntimeError`.

| Variable | Required | Source | Notes |
|---|---|---|---|
| `BACKEND_ENCRYPTION_ACTIVE_KEY_ID` | Yes | Secret | Key identifier (e.g. `kek-dev-v1`) |
| `BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY` | Yes | Secret | Fernet symmetric key (32-byte URL-safe base64) |
| `BACKEND_WEBHOOK_SHARED_SECRET` | Yes | Secret | HMAC shared secret for webhook verification |
| `BACKEND_DEPLOYMENT_PROFILE` | No | ConfigMap | `connected` or `air_gapped` (default: `connected`) |
| `BACKEND_DATABASE_URL` | No | Secret | PostgreSQL URL. Without it, persistence shows "not configured" |
| `BACKEND_REDIS_URL` | No | Secret | Redis URL. Without it, queue shows "not configured" |

The `make minikube-secrets` target generates safe dev defaults for all required values. For local development without Kubernetes, `make dev-backend` auto-generates them if not already set in your environment.

## Running on Minikube

### Quick start

```bash
# Start Minikube
minikube start --driver=docker --memory=4g --cpus=2

# Build, configure, and deploy (one command)
make minikube-up
```

`make minikube-up` performs these steps in order:

1. **check-prereqs** - verifies all required tools are installed and Minikube is running
2. **minikube-images** - builds backend and frontend images inside Minikube
3. **minikube-secrets** - generates dev encryption keys and webhook secrets, applies them as a Kubernetes Secret
4. **minikube-deploy** - applies all manifests from `k8s/`
5. **minikube-wait** - waits for both pods to reach Ready status

### Manual commands

If you prefer to run steps individually:

```bash
# 1. Build images
minikube image build -t langgraph-backend:latest ./backend
minikube image build -t langgraph-frontend:latest ./frontend

# 2. Generate and apply dev secrets
make minikube-secrets

# 3. Deploy
kubectl apply -f k8s/

# 4. Wait for pods
kubectl wait --for=condition=ready pod -l app=backend --timeout=120s
kubectl wait --for=condition=ready pod -l app=frontend --timeout=120s
```

### Access the services

Minikube with the Docker driver does not expose NodePort services directly on the host IP. Use one of these methods:

**Option A - Port-forward (recommended):**

```bash
# Run in a terminal - this blocks until you press Ctrl+C
make port-forward

# Then open in your browser:
#   Backend API docs: http://127.0.0.1:18000/docs
#   Frontend UI:      http://127.0.0.1:18080
```

Or manually in separate terminals:

```bash
kubectl port-forward svc/backend 18000:8000    # terminal 1
kubectl port-forward svc/frontend 18080:80     # terminal 2
```

**Option B - Minikube service tunnel (opens browser automatically):**

```bash
minikube service backend   # opens API docs in browser
minikube service frontend  # opens UI in browser
```

| Service | URL |
|---|---|
| Backend API | http://127.0.0.1:18000 |
| API docs (Swagger) | http://127.0.0.1:18000/docs |
| Frontend UI | http://127.0.0.1:18080 |

> The port-forward must be running in a separate terminal for these localhost URLs to work.
> If your curl returns an empty response or "Connection refused", the port-forward is not active.

### Testing the system

There are two ways to exercise the backend: the **simulate endpoint** (synchronous, runs the full graph in one request) and the **Jira webhook** (asynchronous, requires an ARQ worker). For local validation, use the simulate endpoint.

#### Step 1 - Verify the backend is healthy

With port-forward running in another terminal:

```bash
curl -s http://127.0.0.1:18000/healthz | python3 -m json.tool
```

Expected response:

```json
{
    "status": "ok",
    "reasons": [],
    "persistence": {
        "database": {"name": "database", "configured": false, "healthy": false},
        "redis": {"name": "redis", "configured": false, "healthy": false},
        "encryption": {"name": "encryption", "configured": true, "healthy": true}
    }
}
```

`"status": "ok"` and `"encryption": {"configured": true}` are the two things that matter. Database and Redis show `"configured": false` in local Minikube - this is expected.

#### Step 2 - Run the full agent pipeline

```bash
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

This endpoint runs the entire LangGraph graph synchronously. It takes a few seconds. Look for these fields in the response:

| Field | Expected value | What it means |
|---|---|---|
| `status` | `"completed"` | The full pipeline finished successfully |
| `current_node` | `"pr_creator"` | Execution reached the final node |
| `tests_passed` | `true` | The tester node passed |
| `review_approved` | `true` | The reviewer node approved |
| `pr_created` | `true` | The PR creator node executed |
| `node_history` | 12 entries | Full path from intake to pr_creator |

The `node_history` array shows every node that ran in order:

```
intake -> load_constitution -> create_feature_spec -> clarify ->
create_plan -> create_task_list -> readiness_gate -> coder ->
tester -> reviewer -> pre_pr_sync -> pr_creator
```

If any guard fails, the response will show `escalation_reason` set and `status` will not be `"completed"`.

#### Step 3 - Test the Jira webhook (optional)

The webhook endpoint validates HMAC-SHA256 signatures. It accepts the event but does **not** run the graph synchronously - that requires an ARQ worker (not deployed in local Minikube).

```bash
# Generate a signed request (Python required)
python3 -c "
import hmac, hashlib, json, time, secrets

secret = '$(kubectl get secret dev-squad-backend-secret -o jsonpath={.data.BACKEND_WEBHOOK_SHARED_SECRET} | base64 -d)'
event = {'event_id': secrets.token_hex(8), 'ticket_key': 'PROJ-42', 'tenant_id': 'tenant-alpha', 'team_id': 'team-core', 'summary': 'Fix something'}
body = json.dumps(event)
timestamp = int(time.time())
payload = f'{timestamp}.{body}'
sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
print(f'curl -s -X POST http://127.0.0.1:18000/api/v1/webhooks/jira \\')
print(f'  -H \"Content-Type: application/json\" \\')
print(f'  -H \"X-Hub-Signature-256: sha256={sig}\" \\')
print(f'  -H \"X-Atlassian-Webhook-Timestamp: {timestamp}\" \\')
print(f'  -d \"{body}\"')
"
```

Expected response: `{"event_id": "...", "ticket_key": "PROJ-42", "accepted": true, "deduplicated": false}`

If you get `{"detail": "invalid_signature"}`, the signature was computed incorrectly. The signing payload must be `"{timestamp}.{body}"` (dot-separated), not just the body.

#### Quick test with Makefile

```bash
# Requires port-forward running in another terminal
make smoke-test
```

This runs the health check and simulate workflow automatically.

### Useful Makefile targets

```bash
make help               # List all available targets
make check-prereqs      # Verify tools and Minikube status
make minikube-status    # Show pod status
make minikube-logs      # Tail backend logs
make generate-fernet-key # Print a new Fernet encryption key
```

### Tear down

```bash
make minikube-delete
minikube stop
```

## Local development (no Minikube)

You can run the backend and frontend directly on your machine for faster iteration.

### Backend

```bash
# Auto-generates dev env vars and starts with hot reload
make dev-backend
```

The backend starts on http://127.0.0.1:8000. Database and Redis are optional - the health endpoint will show them as "not configured" but the API remains functional.

To test it, open another terminal:

```bash
# Health check
curl http://127.0.0.1:8000/healthz

# Full pipeline simulation
curl -s -X POST http://127.0.0.1:8000/api/v1/runtime/simulate \
  -H "Content-Type: application/json" \
  -d '{"planning":{"tenant_id":"tenant-alpha","repo_id":"repo-main","ticket_key":"PROJ-1","summary":"Add login page"}}' | python3 -m json.tool
```

### Frontend

```bash
make dev-frontend
# or: npm run --prefix frontend dev
```

The frontend dev server starts on http://127.0.0.1:5173 with hot reload. Configure it to point to the local backend by setting `VITE_API_URL=http://127.0.0.1:8000` if needed.

## Troubleshooting

### Curl returns empty response or "Connection refused"

The port-forward is not running or has stopped. Start it in a separate terminal:

```bash
make port-forward
# or: kubectl port-forward svc/backend 18000:8000
```

If you restarted the deployment, the port-forward dies. Kill it and start a new one.

### Backend pod CrashLoopBackOff

Check the logs:

```bash
kubectl logs -l app=backend --tail=50
```

Common causes:

| Error | Fix |
|---|---|
| `Encryption is not configured` | Run `make minikube-secrets` and redeploy |
| `Webhook shared secret is not configured` | Run `make minikube-secrets` and redeploy |
| `Connection refused` to database | Database URL is missing or PostgreSQL is not running (non-fatal for local dev) |

If you changed the secret after deploying, restart the pods:

```bash
kubectl rollout restart deployment/backend
```

### Webhook returns `invalid_signature`

The HMAC signature must be computed over the string `"{timestamp}.{body}"` (dot-separated), not just the body. The `X-Hub-Signature-256` header value must be prefixed with `sha256=`. The timestamp in the header must match the one used in the signature payload.

### Pod stuck in ImagePullBackOff

The images must be built inside Minikube's Docker daemon:

```bash
minikube image build -t langgraph-backend:latest ./backend
minikube image build -t langgraph-frontend:latest ./frontend
kubectl rollout restart deployment/backend deployment/frontend
```

### Port-forward fails

Make sure the pods are running first:

```bash
kubectl get pods
# Both should show 1/1 Running
```

If a port-forward is already running on that port, kill it:

```bash
lsof -ti:18000 | xargs kill 2>/dev/null
lsof -ti:18080 | xargs kill 2>/dev/null
```

### Cannot access services via NodePort URL

Minikube with the Docker driver does not expose NodePort services on the host. The URLs like `http://192.168.49.2:30800` will not work from your browser. Use `make port-forward` or `minikube service` instead (see "Access the services" above).

### Health check shows "not configured" for database/Redis

This is expected for local Minikube without PostgreSQL or Redis deployed. The backend starts successfully and serves API requests. Persistence-dependent features (checkpoints, queues, audit) will not function until you deploy those services.

## Agent observability with LangSmith

LangSmith tracing is disabled by default. The setup differs between local Minikube and a real cluster deployment.

### Local Minikube

Enable LangSmith by setting the environment variables on the running deployment:

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
# Backend lint
uv run --project backend ruff check backend/src backend/tests

# Backend tests
uv run --project backend pytest

# Frontend test
npm run --prefix frontend test -- --run

# Frontend build
npm run --prefix frontend build
```

## Current state

The backend graph and API are functional. The `/api/v1/runtime/simulate` endpoint runs the full 12-node pipeline synchronously and is the recommended way to validate the system locally. The `/api/v1/webhooks/jira` endpoint accepts and validates HMAC-signed events but does not execute the graph asynchronously because the ARQ worker is not deployed in local Minikube. PostgreSQL, Redis, Vault, and real LLM provider connections are wired in later deployment phases via Helm chart values.
