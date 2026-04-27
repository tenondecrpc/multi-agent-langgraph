## ADDED Requirements

### Requirement: PostgreSQL checkpoint integration
The `RuntimeWorkflow` SHALL use `PostgresSaver` from `langgraph-checkpoint-postgres` as the checkpointer. Each run SHALL be associated with a `thread_id`.

#### Scenario: Workflow compiles with checkpointer
- **WHEN** `RuntimeWorkflow` is initialized with a `PostgresSaver` instance
- **AND** `workflow.compile()` is called
- **THEN** the compiled graph includes the checkpointer

#### Scenario: Execute uses thread_id
- **WHEN** `workflow.execute(request)` is called
- **THEN** the graph invocation includes `config={"configurable": {"thread_id": run_id}}`

### Requirement: PostgresStore for graph memory
The `RuntimeWorkflow` SHALL use `PostgresStore` from `langgraph.store.postgres` for persistent graph memory.

#### Scenario: Workflow compiles with store
- **WHEN** `RuntimeWorkflow` is initialized with a `PostgresStore` instance
- **THEN** the compiled graph includes the store

### Requirement: Checkpoint handle in persistence factory
The `PersistenceAdapters` dataclass SHALL include `checkpoint_saver` and `graph_store` fields. The factory SHALL build them when PostgreSQL mode is selected.

#### Scenario: Factory provides checkpoint saver and store
- **WHEN** `build_persistence_adapters()` is called with PostgreSQL settings
- **THEN** the returned `PersistenceAdapters` includes non-None `checkpoint_saver` and `graph_store`
