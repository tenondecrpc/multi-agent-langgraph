## 1. Assets And Metadata

- [x] 1.1 Remove the existing placeholder SVG sprite assets from `frontend/public/assets/sprites`.
- [x] 1.2 Copy the expected agent PNG sprite sheets from `/Users/tenonde/Projects/open-sources/the-dev-squad/public/sprites`.
- [x] 1.3 Update the bundled sprite manifest and frontend sample metadata to reference the PNG sprite sheets.

## 2. Simulator Implementation

- [x] 2.1 Add visual agent metadata and sprite mapping for simulator steps.
- [x] 2.2 Update the Flow Simulator to render an animated pixel agent stage with speech feedback and text state for the active step.
- [x] 2.3 Change slow-mode automatic pacing to 5000 ms per simulated agent step while preserving reduced-motion fallback.
- [x] 2.4 Update simulator styles for sprite-sheet frames, speech bubbles, active status, focus, and responsive layout.

## 3. Verification

- [x] 3.1 Update frontend tests for PNG sprite metadata, visual agent feedback, and 5000 ms slow-mode pacing.
- [x] 3.2 Run `openspec validate visual-agent-sprites-feedback --strict`.
- [x] 3.3 Run `npm run --prefix frontend test -- --run`.
- [x] 3.4 Run `npm run --prefix frontend build`.
