## 1. Finalize UI Capability Boundaries

- [x] 1.1 Confirm that dashboard, admin, graph editor, control room, sprite management, accessibility, and localization concerns are all covered by this phase.
- [x] 1.2 Confirm that the documented Tier 2 degradation paths for graph editing, sprite upload, control-room fidelity, and Spanish localization are explicit and testable.
- [x] 1.3 Cross-check the UI specs against the access and control-plane contracts from phases 3 and 5.

## 2. Prepare Monitoring And Admin Interfaces

- [x] 2.1 Define the future dashboard, interrupt, DLQ, cost, agent-config, and test-agent UI flows against the planned backend contracts.
- [x] 2.2 Define the future graph editor interaction model for viewing, validation, editing, and activation feedback.
- [x] 2.3 Define the future control-room scene mapping from runtime states and parallel tickets into UI state.

## 3. Prepare Asset And Accessibility Interfaces

- [x] 3.1 Define the future sprite manifest, bundled asset conventions, and tenant-uploaded asset lifecycle.
- [x] 3.2 Define the future localization message extraction and locale-switching contract.
- [x] 3.3 Define the future accessibility acceptance checks for keyboard flow, contrast, live announcements, reduced motion, and zoom behavior.

## 4. Verification Readiness

- [x] 4.1 Define UI validation fixtures for role-scoped navigation, SSE-backed status updates, and break-glass control visibility.
- [x] 4.2 Define graph-editor validation fixtures for invalid routes, protected-node behavior, and read-only degradation mode.
- [x] 4.3 Define manual and automated accessibility validation for the required WCAG subset and the broader AA target.

## 5. Implement First Frontend Slice

- [x] 5.1 Scaffold the React and Vite frontend with role-aware monitoring panes, live run cards, interrupt visibility, and admin summaries.
- [x] 5.2 Implement the graph editor on the allowed read-only degradation path with JSON import and export plus immediate protected-path validation feedback.
- [x] 5.3 Implement the reduced-motion control room, bundled sprite manifest, and explicit upload deferral messaging for the allowed sprite-upload degradation path.
- [x] 5.4 Externalize UI strings through a localization catalog, keep English-only GA explicit, and add accessibility support for keyboard flow, visible focus, live announcements, and reduced motion.
- [x] 5.5 Verify the frontend slice with `npm run --prefix frontend test -- --run` and `npm run --prefix frontend build`, and record the remaining parity gaps for direct graph CRUD, tenant sprite upload, and Spanish locale support.
