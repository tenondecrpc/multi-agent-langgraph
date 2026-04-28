.PHONY: minikube-images minikube-secrets minikube-deploy minikube-up minikube-delete \
        minikube-status minikube-logs minikube-wait minikube-urls port-forward smoke-test \
        check-prereqs generate-fernet-key dev-backend dev-frontend help

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help:
	@echo "LangGraph Dev Squad - Local development targets"
	@echo ""
	@echo "  Minikube:"
	@echo "    make minikube-up          Build images, generate secrets, deploy to Minikube"
	@echo "    make minikube-delete      Remove all k8s resources"
	@echo "    make minikube-status      Show pod status"
	@echo "    make minikube-logs        Tail backend logs"
	@echo "    make minikube-wait        Wait for all pods to be ready"
	@echo "    make minikube-urls        Print direct access URLs via Minikube IP"
	@echo ""
	@echo "  Access:"
	@echo "    make port-forward         Port-forward backend (18000) and frontend (18080) to localhost"
	@echo "    make smoke-test           Run health check and simulate workflow"
	@echo ""
	@echo "  Local dev (no Minikube):"
	@echo "    make dev-backend          Run backend locally with uv (requires env vars)"
	@echo "    make dev-frontend         Run frontend locally with Vite dev server"
	@echo ""
	@echo "  Utilities:"
	@echo "    make check-prereqs        Verify all required tools are installed"
	@echo "    make generate-fernet-key  Print a new Fernet encryption key"

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
check-prereqs:
	@echo "Checking prerequisites..."
	@command -v minikube >/dev/null 2>&1 || { echo "FAIL: minikube not found. Install: https://minikube.sigs.k8s.io/docs/start/"; exit 1; }
	@command -v kubectl >/dev/null 2>&1 || { echo "FAIL: kubectl not found. Install: https://kubernetes.io/docs/tasks/tools/"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "FAIL: docker not found. Required for Minikube image builds."; exit 1; }
	@command -v uv >/dev/null 2>&1 || { echo "FAIL: uv not found. Install: https://docs.astral.sh/uv/"; exit 1; }
	@command -v node >/dev/null 2>&1 || { echo "FAIL: node not found. Required for frontend."; exit 1; }
	@minikube status >/dev/null 2>&1 || { echo "FAIL: Minikube is not running. Run: minikube start --driver=docker --memory=4g --cpus=2"; exit 1; }
	@echo "All prerequisites satisfied."

# ---------------------------------------------------------------------------
# Image builds
# ---------------------------------------------------------------------------
minikube-images:
	minikube image build -t langgraph-backend:latest ./backend
	minikube image build -t langgraph-frontend:latest ./frontend

# ---------------------------------------------------------------------------
# Secret generation (dev-only, safe defaults)
# ---------------------------------------------------------------------------
generate-fernet-key:
	@python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

minikube-secrets:
	@echo "Generating dev secrets..."
	@FERNET_KEY=$$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"); \
	WEBHOOK_SECRET=$$(python3 -c "import secrets; print(secrets.token_urlsafe(32))"); \
	kubectl create secret generic dev-squad-backend-secret \
		--from-literal=BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY=$$FERNET_KEY \
		--from-literal=BACKEND_WEBHOOK_SHARED_SECRET=$$WEBHOOK_SECRET \
		--from-literal=BACKEND_DATABASE_URL="postgresql://not-configured" \
		--from-literal=BACKEND_REDIS_URL="redis://not-configured" \
		--dry-run=client -o yaml | kubectl apply -f -
	@echo "Dev secrets applied."

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------
minikube-deploy:
	kubectl apply -f k8s/

minikube-up: check-prereqs minikube-images minikube-secrets minikube-deploy minikube-wait
	@echo ""
	@$(MAKE) --no-print-directory minikube-urls

minikube-delete:
	kubectl delete -f k8s/ --ignore-not-found=true

# ---------------------------------------------------------------------------
# Status and logs
# ---------------------------------------------------------------------------
minikube-status:
	kubectl get pods -o wide

minikube-logs:
	kubectl logs -l app=backend -f

minikube-wait:
	@echo "Waiting for pods to be ready..."
	@kubectl wait --for=condition=ready pod -l app=backend --timeout=120s || { \
		echo "Backend pod did not become ready in time. Check logs: make minikube-logs"; \
		exit 1; \
	}
	@kubectl wait --for=condition=ready pod -l app=frontend --timeout=120s || { \
		echo "Frontend pod did not become ready in time."; \
		exit 1; \
	}
	@echo "All pods ready."

# ---------------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------------
minikube-urls:
	@echo ""
	@echo "Access services (Docker driver requires port-forward or minikube service tunnel):"
	@echo ""
	@echo "  Option 1 - Port-forward (run in a terminal, then open URLs):"
	@echo "    make port-forward"
	@echo "    Backend:  http://127.0.0.1:18000/docs"
	@echo "    Frontend: http://127.0.0.1:18080"
	@echo ""
	@echo "  Option 2 - Minikube service tunnel (opens browser automatically):"
	@echo "    minikube service backend   # opens API docs in browser"
	@echo "    minikube service frontend  # opens UI in browser"

port-forward:
	@echo "Port-forwarding backend -> 127.0.0.1:18000 and frontend -> 127.0.0.1:18080"
	@echo "This blocks the terminal. Open URLs in your browser, then press Ctrl+C to stop."
	@kubectl port-forward svc/backend 18000:8000 & \
	kubectl port-forward svc/frontend 18080:80 & \
	trap 'kill %1 %2 2>/dev/null' EXIT; \
	wait

smoke-test:
	@echo "Running smoke tests against http://127.0.0.1:18000..."
	@echo ""
	@echo "--- Health check ---"
	@curl -sf http://127.0.0.1:18000/healthz | python3 -m json.tool || { echo "FAIL: backend not reachable. Run: make port-forward"; exit 1; }
	@echo ""
	@echo "--- Simulate workflow ---"
	@curl -sf -X POST http://127.0.0.1:18000/api/v1/runtime/simulate \
		-H "Content-Type: application/json" \
		-d '{"planning":{"tenant_id":"tenant-alpha","repo_id":"repo-main","ticket_key":"PROJ-1","summary":"Add login page"}}' \
		| python3 -m json.tool || echo "WARN: simulate endpoint returned non-200 (may be expected without full graph setup)"
	@echo ""
	@echo "Smoke tests complete."

# ---------------------------------------------------------------------------
# Local development (no Minikube)
# ---------------------------------------------------------------------------
dev-backend:
	@echo "Starting backend locally on http://127.0.0.1:8000"
	@echo "Required env vars: BACKEND_ENCRYPTION_ACTIVE_KEY_ID, BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY, BACKEND_WEBHOOK_SHARED_SECRET"
	@echo "Database and Redis are optional; persistence will show 'not configured' if absent."
	@echo ""
	@if [ -z "$$BACKEND_ENCRYPTION_ACTIVE_KEY_ID" ]; then \
		echo "Generating dev env vars for this session..."; \
		export BACKEND_ENCRYPTION_ACTIVE_KEY_ID="kek-dev-v1"; \
		export BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY=$$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"); \
		export BACKEND_WEBHOOK_SHARED_SECRET=$$(python3 -c "import secrets; print(secrets.token_urlsafe(32))"); \
		export BACKEND_DEPLOYMENT_PROFILE="connected"; \
		export DO_NOT_TRACK="1"; \
		export LANGCHAIN_TRACING_V2="false"; \
	fi
	uv run --project backend uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

dev-frontend:
	@echo "Starting frontend dev server on http://127.0.0.1:5173"
	npm run --prefix frontend dev
