#!/usr/bin/env sh
set -eu

if [ "${VAULT_ADDR:-}" = "" ]; then
  echo "VAULT_ADDR is required" >&2
  exit 2
fi

if [ "${VAULT_TOKEN:-}" = "" ]; then
  echo "VAULT_TOKEN must be supplied from operator custody for this shell only" >&2
  exit 2
fi

vault status >/dev/null
vault secrets enable -path=kv kv-v2 2>/dev/null || true
vault auth enable kubernetes 2>/dev/null || true

vault policy write dev-squad-backend - <<'POLICY'
path "kv/data/langgraph-dev-squad/runtime" {
  capabilities = ["read"]
}

path "kv/metadata/langgraph-dev-squad/runtime" {
  capabilities = ["read"]
}
POLICY

vault kv put kv/langgraph-dev-squad/runtime \
  database_url="${BACKEND_DATABASE_URL:?BACKEND_DATABASE_URL is required}" \
  redis_url="${BACKEND_REDIS_URL:?BACKEND_REDIS_URL is required}" \
  wrapping_key="${BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY:?BACKEND_ENCRYPTION_ACTIVE_WRAPPING_KEY is required}"

echo "Vault air-gapped bootstrap complete. Revoke the operator token before leaving the maintenance window."
