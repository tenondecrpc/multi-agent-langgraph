## ADDED Requirements

### Requirement: Internal RAG Slots Into Local-First Order When Enabled

When `internal_rag_enabled` is ON for a tenant, internal knowledge retrieval SHALL slot into the local-first context resolution order immediately after checkpoints and memory and before first-party docs and APIs. When OFF, the order SHALL remain unchanged.

#### Scenario: Flag off preserves original order
- **WHEN** the flag is OFF for a tenant
- **THEN** the context resolution order does not reference internal knowledge
- **AND** no retrieval is attempted during ticket execution
