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
