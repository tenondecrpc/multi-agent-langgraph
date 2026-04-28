## MODIFIED Requirements

### Requirement: Visual Direction Follows The Declared Reference

The control room MUST follow the copy-first visual rule described in `docs/PLAN.md`, preserving the intended scene density, rhythm, and motion language unless a documented product reason requires divergence. Bundled agent sprites used by the control room or simulator MUST come from the declared `the-dev-squad` reference sprite sheets unless a later approved SDD change replaces the reference.

#### Scenario: Visual implementation stays faithful

- **WHEN** the control-room design is implemented later
- **THEN** it uses the declared reference as the primary baseline for layout logic, sprite treatment, and animation feel
- **AND** major stylistic divergence requires explicit product rationale

#### Scenario: Simulator and control room share reference sprite treatment

- **WHEN** the Flow Simulator renders agent feedback using bundled sprites
- **THEN** the sprite treatment matches the declared reference agent sheets
- **AND** future control-room parity can reuse the same bundled assets without remapping placeholder art
