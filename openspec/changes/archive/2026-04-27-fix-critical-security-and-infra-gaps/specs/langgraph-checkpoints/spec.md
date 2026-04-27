## ADDED Requirements

### Requirement: PostgreSQL checkpoint integration
The `RuntimeWorkflow` SHALL use `PostgresSaver` from `langgraph-checkpoint-postgres` as the checkpointer for graph execution. Each run SHALL be associated with a `thread_id` for state persistence.

#### Scenario: Workflow compiles with checkpointer
- **WHEN** `RuntimeWorkflow` is initialized with a `PostgresSaver` instance
- **AND** `workflow.compile()` is called
- **THEN** the compiled graph includes the checkpointer

#### Scenario: Execute uses thread_id
- **WHEN** `workflow.execute(request)` is called
- **THEN** the graph invocation includes `config={"configurable": {"thread_id": request.run_id}}`

#### Scenario: State persists across nodes
- **WHEN** a graph node updates state
- **AND** the process crashes before completion
- **THEN** the state is recoverable via the checkpoint using the same `thread_id`

### Requirement: PostgresStore for graph memory
The `RuntimeWorkflow` SHALL use `PostgresStore` from `langgraph.store.postgres` for persistent graph memory.

#### Scenario: Workflow compiles with store
- **WHEN** `RuntimeWorkflow` is initialized with a `PostgresStore` instance
- **AND** `workflow.compile()` is called
- **THEN** the compiled graph includes the store

### Requirement: Checkpoint handle in persistence factory
The `PersistenceAdapters` dataclass SHALL include a `checkpoint_saver` field of type `PostgresCheckpointSaverHandle`. The factory SHALL build the handle when PostgreSQL mode is selected.

#### Scenario: Factory provides checkpoint saver
- **WHEN** `build_persistence_adapters()` is called with PostgreSQL settings
- **THEN** the returned `PersistenceAdapters` includes a non-None `checkpoint_saver`

### Requirement: Resume from checkpoint
The ARQ worker SHALL support resuming a paused run from its last checkpoint. When a run is resumed, the worker SHALL load the checkpoint state and continue from the last completed node.

#### Scenario: Worker resumes from checkpoint
- **WHEN** a run with `thread_id` has a checkpoint saved
- **AND** the worker receives a resume command for that `thread_id`
- **THEN** the graph execution continues from the last checkpointed node
