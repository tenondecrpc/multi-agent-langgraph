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
| Docker | 20+ | Local dependencies and Minikube image builds |
| Docker Compose | 2.20+ | Local PostgreSQL and Redis (Option A) |
| minikube | 1.30+ | Local Kubernetes cluster (Option B) |
| kubectl | 1.28+ | Kubernetes CLI (Option B) |

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

## Local development

You have two options for running the system locally. Choose the one that fits your workflow.

| Option | Use case | PostgreSQL | Redis | Kubernetes |
|---|---|---|---|---|
| **A - Docker Compose + native processes** | Daily development, fast iteration | Yes (Docker) | Yes (Docker) | No |
| **B - Minikube** | Validate Kubernetes manifests, Helm charts, networking | No (placeholder) | No (placeholder) | Yes |

### Option A - Docker Compose + native processes (recommended)

This is the fastest way to get a fully functional local environment. PostgreSQL and Redis run in Docker containers while the backend and frontend run natively on your machine with hot reload.

#### Step 1 - Start dependencies

```bash
make local-up
```

This starts:
- **PostgreSQL 16** with `pgvector` on port `5432`
- **Redis 7** on port `6379`

Both services persist data in named Docker volumes and expose health checks.

#### Step 2 - Start the backend

```bash
make dev-backend
```

The Makefile automatically wires `BACKEND_DATABASE_URL` and `BACKEND_REDIS_URL` to the local Docker services unless you already have them set in your environment. The backend starts on http://127.0.0.1:8000 with hot reload.

To verify everything is connected, open another terminal:

```bash
curl -s http://127.0.0.1:8000/healthz | python3 -m json.tool
```

You should now see `database` and `redis` as `configured: true`.

#### Step 3 - Start the frontend

```bash
make dev-frontend
```

The dev server starts on http://127.0.0.1:5173. It proxies API requests to the local backend automatically.

#### Full pipeline test

With both backend and frontend running:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/runtime/simulate \
  -H "Content-Type: application/json" \
  -d '{"planning":{"tenant_id":"tenant-alpha","repo_id":"repo-main","ticket_key":"PROJ-1","summary":"Add login page"}}' | python3 -m json.tool
```

#### Stop dependencies

```bash
make local-down
```

This stops and removes the containers and volumes. To only stop without removing volumes, run `docker compose down`.

#### Useful targets

```bash
make local-up      # Start PostgreSQL + Redis
make local-down    # Stop and remove containers/volumes
make local-logs    # Tail Docker Compose logs
make local-status  # Show running containers
make dev-backend   # Run backend with uv (hot reload)
make dev-frontend  # Run frontend with Vite (hot reload)
```

### Option B - Minikube

Use this option when you need to validate Kubernetes manifests, Helm charts, Argo Rollouts, NetworkPolicies, or gVisor configurations. Note that the local Minikube setup does **not** deploy PostgreSQL or Redis - the backend starts in a degraded mode where persistence and queues show "not configured".

#### Quick start

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

#### Access the services

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

#### Testing the system on Minikube

There are two ways to exercise the backend: the **simulate endpoint** (synchronous, runs the full graph in one request) and the **Jira webhook** (asynchronous, requires an ARQ worker). For local validation, use the simulate endpoint.

**Step 1 - Verify the backend is healthy**

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

**Step 2 - Run the full agent pipeline**

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

**Step 3 - Test the Jira webhook (optional)**

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

#### Useful Makefile targets

```bash
make help               # List all available targets
make check-prereqs      # Verify tools and Minikube status
make minikube-status    # Show pod status
make minikube-logs      # Tail backend logs
make generate-fernet-key # Print a new Fernet encryption key
```

#### Tear down

```bash
make minikube-delete
minikube stop
```

## Integraciones necesarias para un flujo completo

PostgreSQL + Redis son la infraestructura base para que la aplicacion arranque con persistencia real, pero para un flujo **end-to-end completo** se necesitan integraciones externas adicionales.

### Que cubre Docker Compose (infraestructura base)

| Servicio | Proposito |
|---|---|
| PostgreSQL 16 + pgvector | Checkpoints, memoria, config, auditoria, metering, DLQ |
| Redis 7 | Colas ARQ, pub/sub, circuit breaker, idempotencia |

### Que falta para un pipeline real (integraciones externas)

Estas dependencias no se pueden containerizar facilmente porque son servicios SaaS o requieren configuracion externa:

#### 1. LLM Provider (imprescindible)

El grafo no puede planificar, codear, testear ni revisar sin llamadas a un LLM. El backend necesita algun provider configurado.

**Opciones:**

| Provider | Variable de entorno | Notas |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` o `BACKEND_OPENAI_API_KEY` | Requiere cuenta con saldo |
| Anthropic | `ANTHROPIC_API_KEY` o `BACKEND_ANTHROPIC_API_KEY` | Requiere cuenta con saldo |
| OpenCode-Go | `BACKEND_PROVIDER_OPENCODE_GO_ENDPOINT` | Endpoint local o remoto (por defecto apunta a `http://dev-squad-opencode-go:8080/v1`) |
| Ollama | Ollama corriendo localmente | Modelo `llama3.1` pre-configurado en el catalogo |

**Ejemplo con OpenAI:**

```bash
export OPENAI_API_KEY="sk-..."
make dev-backend
```

**Ejemplo con OpenCode-Go local:**

```bash
export BACKEND_PROVIDER_OPENCODE_GO_ENDPOINT="http://localhost:8080/v1"
make dev-backend
```

> Sin un LLM provider configurado, el `simulate` endpoint ejecutara el grafo pero fallara en los nodos que requieren LLM (planner, coder, tester, reviewer).

#### 2. ARQ Worker (para async real)

El endpoint `/api/v1/webhooks/jira` **acepta** el evento pero solo lo encola. Para procesarlo asincronicamente necesitas correr el worker ARQ.

```bash
# Ejemplo conceptual (el entrypoint exacto depende de la implementacion)
uv run --project backend arq backend.worker.WorkerSettings
```

El `simulate` endpoint corre sincronicamente y no requiere worker. El pipeline real (Jira webhook -> grafo -> PR) es asincronico y requiere workers consumiendo de Redis.

#### 3. GitHub Integration (para `pr_creator`)

El nodo `pr_creator` necesita credenciales para crear pull requests.

**Opciones:**

| Metodo | Variables / Configuracion |
|---|---|
| GitHub App | `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY_PEM` (recomendado) |
| Personal Access Token | `GITHUB_TOKEN` (fallback, mas restrictivo) |

Sin GitHub configurado, el grafo llegara al nodo `pr_creator` pero fallara al intentar crear el PR.

#### 4. Opcionales segun el caso

| Servicio | Requerido | Fallback |
|---|---|---|
| Feature Flags (Unleash/LaunchDarkly) | No | PostgreSQL mirror (funciona sin el servicio) |
| LangSmith | No | Desactivado por defecto |
| Vault | No | Encryption provider `local` en dev |
| gVisor | No | Solo para testear sandboxing en K8s |

### Verificacion rapida de integraciones

Con el backend corriendo, el health check te dice que esta configurado:

```bash
curl -s http://127.0.0.1:8000/healthz | python3 -m json.tool
```

Busca estos campos:

| Campo | `configured: true` significa |
|---|---|
| `persistence.database` | PostgreSQL conectado |
| `persistence.redis` | Redis conectado |
| `persistence.encryption` | Clave de encriptacion activa |

Para verificar el LLM provider, intenta el `simulate` endpoint y revisa si los nodos del grafo completan exitosamente.

## Troubleshooting

### Docker Compose (Option A)

#### PostgreSQL or Redis fails to start

Check the container status:

```bash
make local-status
make local-logs
```

Common causes:

| Error | Fix |
|---|---|
| Port `5432` already in use | Stop the conflicting service or change the host port in `docker-compose.yml` |
| Port `6379` already in use | Stop the conflicting service or change the host port in `docker-compose.yml` |
| `pgvector` extension missing | Ensure the image is `pgvector/pgvector:pg16` |

#### Backend cannot connect to database or Redis

If you see `configured: false` for database or Redis in the health check, verify the containers are running and healthy:

```bash
docker compose ps
```

The `dev-backend` target auto-wires connection URLs only if the environment variables are **not** already set. If you previously exported custom values, unset them first:

```bash
unset BACKEND_DATABASE_URL BACKEND_REDIS_URL
make dev-backend
```

### Minikube (Option B)

#### Curl returns empty response or "Connection refused"

The port-forward is not running or has stopped. Start it in a separate terminal:

```bash
make port-forward
# or: kubectl port-forward svc/backend 18000:8000
```

If you restarted the deployment, the port-forward dies. Kill it and start a new one.

#### Backend pod CrashLoopBackOff

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

#### Pod stuck in ImagePullBackOff

The images must be built inside Minikube's Docker daemon:

```bash
minikube image build -t langgraph-backend:latest ./backend
minikube image build -t langgraph-frontend:latest ./frontend
kubectl rollout restart deployment/backend deployment/frontend
```

#### Port-forward fails

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

#### Cannot access services via NodePort URL

Minikube with the Docker driver does not expose NodePort services on the host. The URLs like `http://192.168.49.2:30800` will not work from your browser. Use `make port-forward` or `minikube service` instead (see "Access the services" above).

#### Health check shows "not configured" for database/Redis

This is expected for local Minikube without PostgreSQL or Redis deployed. The backend starts successfully and serves API requests. Persistence-dependent features (checkpoints, queues, audit) will not function until you deploy those services.

### Common to both options

#### Webhook returns `invalid_signature`

The HMAC signature must be computed over the string `"{timestamp}.{body}"` (dot-separated), not just the body. The `X-Hub-Signature-256` header value must be prefixed with `sha256=`. The timestamp in the header must match the one used in the signature payload.

## Agent observability with LangSmith

LangSmith tracing is disabled by default. The setup differs by environment.

### Local development (Docker Compose)

Export the variables before starting the backend:

```bash
export LANGCHAIN_TRACING_V2=true
export LANGSMITH_API_KEY=<your-LANGSMITH_API_KEY>
export LANGSMITH_PROJECT=langgraph-dev-squad-local
make dev-backend
```

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

The backend graph and API are functional. The `/api/v1/runtime/simulate` endpoint runs the full 12-node pipeline synchronously and is the recommended way to validate the system locally.

For **daily development**, use Option A (Docker Compose + native processes). It provides real PostgreSQL and Redis so persistence, checkpoints, queues, and audit features work out of the box.

For **Kubernetes validation**, use Option B (Minikube). Note that the local Minikube setup does not deploy PostgreSQL or Redis - the backend starts in a degraded mode where persistence and queues show "not configured". Vault and real LLM provider connections are wired in later deployment phases via Helm chart values.

The `/api/v1/webhooks/jira` endpoint accepts and validates HMAC-signed events. Asynchronous graph execution via ARQ requires a worker deployment (available in the Helm chart, not in local Minikube).
