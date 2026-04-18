## 1. Artifact Alignment

- [ ] 1.1 Confirm alignment with Phase 7 observability and release-engineering archived specs.

## 2. Argo Rollouts

- [ ] 2.1 Add Argo Rollouts Helm dependency and RBAC.
- [ ] 2.2 Convert API and worker Deployments to Rollouts with 5/25/50/100 steps.
- [ ] 2.3 Author AnalysisTemplates against error rate, latency p95, circuit-breaker, DLQ growth, pool saturation.

## 3. Frontend Blue/Green

- [ ] 3.1 Frontend Rollout with blue/green strategy and post-deploy smoke.

## 4. Feature Flags

- [ ] 4.1 Integrate OpenFeature with Unleash (self-hosted) or LaunchDarkly (customer-owned).
- [ ] 4.2 Implement PostgreSQL mirror `feature_flag_state` with TTL fail-safe.
- [ ] 4.3 Wire six mandatory kill switches and their fail-closed paths.
- [ ] 4.4 Audit on toggle; flag registry with owner, age, retirement intent.

## 5. Drills

- [ ] 5.1 Quarterly kill-switch drill in staging (toggle each mandatory flag off, verify behavior).
- [ ] 5.2 Rollback drill: introduce synthetic SLO breach and verify automated rollback.

## 6. Observability

- [ ] 6.1 Metrics: rollout-state, analysis-failure, flag-toggle, stale-flag-age.
- [ ] 6.2 Runbooks: canary rollback, kill-switch activation, flag-service outage.

## 7. Verification

- [ ] 7.1 Integration test on ephemeral cluster validates rollback path.
- [ ] 7.2 Accessibility subset verified on admin UI flag toggles and rollout status.

## 8. Archive

- [ ] 8.1 Archive after a quarterly drill evidence bundle is attached.
