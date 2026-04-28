## ADDED Requirements

### Requirement: Office Scene Shows Agent Interactions

Pixel-art office experiences SHALL show agent collaboration as interactions between visible agents, not only as isolated role cards. Review, test, implementation, and PR creation states MUST have distinct visual arrangements that communicate which agents are collaborating.

#### Scenario: Collaboration is visually distinguishable

- **WHEN** the active phase changes from planning to implementation or review
- **THEN** the office scene changes agent positions, labels, or handoff indicators to show a different collaboration state
- **AND** the same state remains available through text labels
