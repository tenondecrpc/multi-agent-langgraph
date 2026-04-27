# Persistence Migrations

This repository now uses Alembic for persistence-backbone schema changes.

## Operator commands

- Upgrade to the latest revision:
  `uv --cache-dir /tmp/uv-cache run --project backend alembic -c backend/alembic.ini upgrade head`
- Show the current applied revision:
  `uv --cache-dir /tmp/uv-cache run --project backend alembic -c backend/alembic.ini current`
- Roll back one revision:
  `uv --cache-dir /tmp/uv-cache run --project backend alembic -c backend/alembic.ini downgrade -1`

## Startup behavior

- The FastAPI app runs the migration runner on startup when `BACKEND_DATABASE_URL` or `DATABASE_URL` is configured.
- For air-gapped deployments with a pre-seeded database, set `BACKEND_AIR_GAPPED_SKIP_MIGRATIONS=1` or `BACKEND_SKIP_STARTUP_MIGRATIONS=1` to skip startup migration execution.
- The skip switch is only for pre-seeded databases. If the schema is not already at the expected revision, startup should fail during validation before rollout.

## High-risk note

- Database migrations are a high-risk change category in this repository.
- Follow expand/contract discipline: additive migration first, destructive cleanup only in a later contract migration.
- Every migration must keep a downgrade path and a reversibility test.
