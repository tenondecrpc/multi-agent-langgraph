## 1. Finalize UI Capability Boundaries

- [ ] 1.1 Confirm that dashboard, admin, graph editor, control room, sprite management, accessibility, and localization concerns are all covered by this phase.
- [ ] 1.2 Confirm that the documented Tier 2 degradation paths for graph editing, sprite upload, control-room fidelity, and Spanish localization are explicit and testable.
- [ ] 1.3 Cross-check the UI specs against the access and control-plane contracts from phases 3 and 5.

## 2. Prepare Monitoring And Admin Interfaces

- [ ] 2.1 Define the future dashboard, interrupt, DLQ, cost, agent-config, and test-agent UI flows against the planned backend contracts.
- [ ] 2.2 Define the future graph editor interaction model for viewing, validation, editing, and activation feedback.
- [ ] 2.3 Define the future control-room scene mapping from runtime states and parallel tickets into UI state.

## 3. Prepare Asset And Accessibility Interfaces

- [ ] 3.1 Define the future sprite manifest, bundled asset conventions, and tenant-uploaded asset lifecycle.
- [ ] 3.2 Define the future localization message extraction and locale-switching contract.
- [ ] 3.3 Define the future accessibility acceptance checks for keyboard flow, contrast, live announcements, reduced motion, and zoom behavior.

## 4. Verification Readiness

- [ ] 4.1 Define UI validation fixtures for role-scoped navigation, SSE-backed status updates, and break-glass control visibility.
- [ ] 4.2 Define graph-editor validation fixtures for invalid routes, protected-node behavior, and read-only degradation mode.
- [ ] 4.3 Define manual and automated accessibility validation for the required WCAG subset and the broader AA target.
