## Context

The UI is a product surface, not an afterthought. `docs/PLAN.md` specifies a tenant-scoped monitoring and admin UI with a distinct pixel-art control-room direction, a graph editor, sprite management, and explicit accessibility obligations. This phase translates those UI expectations into capability contracts before implementation.

## Goals / Non-Goals

**Goals:**
- Define the role-aware operator UI surfaces needed for monitoring and administration.
- Define the graph editor contract, including validation and the allowed read-only degradation path.
- Define the pixel-art control-room fidelity expectations and how it communicates runtime state.
- Define sprite asset management and frontend accessibility and localization obligations.

**Non-Goals:**
- Backend auth, provider routing, metering internals, or graph compiler implementation.
- CI rollout, SLO, or incident policy details.
- Actual frontend code, art production, or object-storage implementation.
- New visual directions that diverge from the declared control-room reference style.

## Decisions

- The monitoring and admin UI is explicitly role-aware, with backend authorization remaining authoritative even when the frontend improves UX with route guards.
- The control room follows a copy-first rule toward the declared reference implementation, rather than treating pixel art as a vague mood board.
- The graph editor remains a serious admin surface with validation and activation context, not a decorative diagramming tool.
- Bundled sprite assets live with the application, while tenant-managed replacements are stored durably outside the container filesystem.
- Accessibility is not optional polish. The WCAG subset called out in the constitution is mandatory even if some broader AA work finishes through the documented Tier 2 parity path.
- Localization is planned from the start through extraction and structured messaging, even if English-only is the initial GA degradation path.

## Risks / Trade-offs

- Faithful visual reproduction raises the implementation bar relative to a generic dashboard, but that is an intentional product decision already embedded in the plan.
- Accessibility work may constrain some pixel-art presentation choices, but the repository constitution already makes those constraints non-negotiable.
- The graph editor and asset-management surfaces create substantial admin complexity, so clear degradation paths are necessary to protect GA without silently dropping the features.

## UI Capability Coverage

This phase binds the frontend to the already-archived access and control-plane contracts.

| UI concern | Contract outcome in this phase | Upstream dependency |
|---|---|---|
| Dashboard and admin surfaces | Monitoring, interrupts, DLQ, cost views, agent config, and dry-run testing are explicit UI responsibilities. | Phase 3 role and scope enforcement, phase 5 config and activation APIs |
| Graph editor | The editor reflects the backend graph schema and invariant model, not a generic diagramming surface. | Phase 5 graph configuration runtime and validation |
| Control room | The pixel-art control room is the primary monitoring surface and must represent concurrent ticket state clearly. | Phase 1 runtime state model and phase 3 role-scoped visibility |
| Sprite management | Bundled assets and tenant-managed replacements share a manifest-driven contract. | Phase 5 activation and admin scope, phase 3 storage and permission boundaries |
| Accessibility and localization | Keyboard reachability, reduced motion, contrast, live narration, and localization extraction are mandatory design inputs. | Repository constitution non-negotiables and phase 3 access semantics |

Tier 2 degradation paths remain explicit and testable:

- Graph editing may degrade to read-only visualization plus JSON import/export.
- Sprite upload may degrade to bundled assets only with explicit `501` responses for upload.
- Full-fidelity office-scene control room may degrade to a functional reduced-motion pixel skin.
- English-only GA is allowed only when localization extraction is already wired for later Spanish parity.

## Monitoring And Admin Interface Contracts

### Future Dashboard And Admin Flows

The frontend should organize around role-aware operational surfaces.

| UI flow | Backend contract consumed | Role scope |
|---|---|---|
| Run dashboard | `/api/v1/runs`, `/api/v1/streams` | Viewer and above within tenant and team scope |
| Interrupt queue | Exception and approval surfaces derived from run pause state | Operator and above |
| DLQ management | DLQ inspection and replay controls | Operator and above, subject to tenant and team scope |
| Cost and usage views | Metering rollups and export status | Admin and above, or narrower tenant policy if configured |
| Agent config management | Graph and agent config versions, validation results, activation history | Admin and above |
| Test-agent workflow | Dry-run validation and output summary for candidate agent configs | Admin and above |

UI flow rules:

- Navigation and action affordances must be role-filtered in the UI, but final authorization remains backend-enforced.
- SSE-backed updates should hydrate the dashboard and interrupt surfaces without requiring full-page polling refreshes.
- Break-glass controls must remain visible only when the user's role and scope permit the related action.

### Graph Editor Interaction Model

The graph editor should mirror the backend config lifecycle:

1. Load the active or candidate graph snapshot from the control-plane API
2. Render nodes, edges, route labels, and protected-node metadata
3. Apply edits through a draft model backed by immediate validation feedback
4. Show compile and invariant results before activation is allowed
5. Present candidate-versus-active shadow evidence and activation status

Editor rules:

- Protected nodes and routes must be visually identified and carry inline explanations when edits are blocked.
- Invalid edits should surface actionable validation errors before the user reaches activation.
- In read-only degradation mode, the editor still exposes structure, JSON import/export, and validation results without in-place CRUD controls.

### Control-Room Scene Mapping

The control room should translate runtime state into a stable scene model.

| Runtime input | UI mapping |
|---|---|
| `planner`, `coder`, `tester`, `reviewer`, `pr_creator` active states | Scene actor position, sprite state, and status caption |
| Queue or retry state | Background activity markers, badge counts, or subtle scene overlays |
| Paused or escalated state | Distinct interrupt or alert treatment visible in the room and in text summaries |
| Parallel tickets | Multiple actor lanes, desks, or occupancy markers so concurrency remains legible |

Control-room rules:

- The scene is informative first and decorative second.
- Every meaningful visual state must have an accessible text counterpart.
- Reduced-motion mode keeps the same state semantics while minimizing animation.

## Asset, Localization, And Accessibility Contracts

### Sprite Manifest And Asset Lifecycle

The future frontend should rely on a manifest instead of scattered asset references.

```python
class SpriteManifestEntry(BaseModel):
    sprite_id: str
    source_kind: Literal["bundled", "tenant_uploaded"]
    runtime_role: str | None = None
    runtime_state: str | None = None
    reduced_motion_variant: str | None = None
    alt_text_key: str | None = None
```

Asset rules:

- Bundled assets live under a stable frontend asset root and are referenced through the manifest.
- Tenant uploads are stored durably outside the container filesystem and mapped into the same manifest shape.
- Upload deferral must be explicit: the UI uses bundled assets and the upload API returns `501` until tenant upload is implemented.

### Localization Extraction And Locale Switching

The frontend should treat localization as infrastructure, not a later string-replacement pass.

| Concern | Contract |
|---|---|
| Message definition | User-visible strings are keyed and extracted from source code |
| Locale switching | The UI can switch locale at runtime or on reload through a stable user or tenant preference |
| Fallback | Missing translations fall back to English predictably without breaking rendering |
| Degradation | English-only GA is valid only when message extraction and locale wiring already exist |

### Accessibility Acceptance Checks

The future UI acceptance model should treat accessibility as a first-class release gate.

| Accessibility area | Acceptance rule |
|---|---|
| Keyboard flow | Every interactive control is reachable in logical order with visible focus indicators |
| Contrast | Text meets AA contrast thresholds across monitoring, admin, and control-room surfaces |
| Live announcements | Meaningful status changes are announced through throttled accessible live regions |
| Reduced motion | Ambient animation and transitions honor `prefers-reduced-motion` and any product-level toggle |
| Zoom and scaling | The product remains usable at high zoom without hiding core controls or clipping status meaning |

## Verification Fixtures

| Task | Fixture definition | Expected proof |
|---|---|---|
| 4.1 UI flow validation | Exercise viewer, operator, admin, and super-admin navigation with live SSE updates and paused-run scenarios. | Navigation stays role-scoped, status updates remain tenant-safe, and break-glass controls appear only for authorized roles. |
| 4.2 Graph-editor validation | Attempt invalid route edits, protected-node removals, and read-only-mode interactions. | Invalid edits are explained before activation, protected nodes remain blocked, and read-only degradation still exposes inspection and import/export. |
| 4.3 Accessibility validation | Combine automated checks for focus, contrast, semantics, and live regions with manual checks for keyboard flow, reduced motion, and zoom. | The mandatory WCAG subset passes across all core surfaces and broader AA gaps, if any, remain explicit and tracked. |

These fixtures connect to later implementation:

- Phase 5 backend validation results must feed the graph editor and activation feedback directly.
- Phase 7 quality and release gates must include the UI and accessibility fixtures defined here.

## Implementation Slice

This phase now includes a first executable frontend slice under `frontend/` plus test coverage in `frontend/src/App.test.tsx`.

Implemented surfaces:

- A role-aware single-page monitoring shell exposes dashboard, control room, interrupts, graph editor, and admin panes based on viewer, operator, admin, and super-admin scope.
- Live run updates are simulated through a local SSE-style ticker and mirrored into a polite live region so status changes remain accessible.
- The graph editor ships on the allowed Tier 2 degradation path: read-only visualization through JSON import and export with immediate invariant feedback, but no direct node CRUD yet.
- The control room uses bundled pixel-style sprite assets and manifest data from `frontend/public/assets/sprites/`, with explicit `501`-style upload deferral messaging for tenant uploads.
- Localization ships on the allowed Tier 2 degradation path: all strings are externalized through a message catalog, but only English is exposed in the UI for now.

Implementation boundaries:

- The frontend currently uses local sample data and frontend-side validation mirrors for operator flows; later phases will wire these surfaces to the backend APIs and persisted shadow evidence.
- The visual direction intentionally prioritizes a reduced-motion pixel monitoring skin over full-fidelity scene parity, matching the constitution's allowed degradation path.
- Accessibility support is built into the slice through keyboard-reachable controls, visible focus states, live announcements, reduced-motion toggles, and no color-only status meaning.
