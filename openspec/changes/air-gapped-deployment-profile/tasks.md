## 1. Artifact Alignment

- [ ] 1.1 Compose with archived Phase 4 provider routing and Phase 7 HA/DR specs.

## 2. Helm And NetworkPolicy

- [ ] 2.1 Author `helm/values-air-gapped.yaml` and the NetworkPolicy egress-denial manifest.
- [ ] 2.2 Config validation: reject vendor LLM keys when `air_gapped: true`.

## 3. Routing

- [ ] 3.1 Wire default fallback to self-hosted OpenCode Go endpoint configurable via Helm.
- [ ] 3.2 Admin UI surfaces profile banner.

## 4. Vault

- [ ] 4.1 Offline Vault bootstrap script; document operator key custody.
- [ ] 4.2 Remove any dev-mode fallbacks and document rationale.

## 5. CI Acceptance Test

- [ ] 5.1 CI job deploys air-gapped profile and runs smoke ticket with vendor-unreachability simulation.
- [ ] 5.2 Flip from warn to enforce after soak.

## 6. Docs

- [ ] 6.1 `docs/runbooks/air-gapped-deployment.md` covering install, credential seeding, drill, recovery.
- [ ] 6.2 Operator guide updates under `docs/`.

## 7. Verification

- [ ] 7.1 Both profiles render via Helm dry-run in CI.
- [ ] 7.2 Frontend banner accessibility non-negotiable subset verified.

## 8. Archive

- [ ] 8.1 Archive after one real air-gapped install rehearsal.
