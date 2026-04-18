# LangGraph Dev Squad Frontend

This directory contains the first executable frontend slice for the operator UI.

## Commands

- Install dependencies: `npm install --prefix frontend`
- Start development server: `npm run --prefix frontend dev`
- Run tests: `npm run --prefix frontend test -- --run`
- Build production bundle: `npm run --prefix frontend build`

## Current scope

The current implementation covers these frontend slices:

- role-aware navigation for viewer, operator, admin, and super-admin monitoring surfaces
- live dashboard updates with accessible announcements and break-glass visibility rules
- a read-only graph editor with JSON import or export and immediate invariant feedback
- a reduced-motion pixel control room driven by runtime state cards and bundled sprite manifests
- English-only localization infrastructure with externalized messages and accessibility-first interaction patterns
