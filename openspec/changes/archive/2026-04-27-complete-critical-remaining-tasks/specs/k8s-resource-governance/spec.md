## ADDED Requirements

### Requirement: Resource limits on all pods
All backend, worker, and frontend pod templates SHALL define `resources.requests` and `resources.limits` for CPU and memory. Values SHALL be configurable via Helm values.

#### Scenario: Backend pod has resource limits
- **WHEN** the backend rollout is rendered with default values
- **THEN** the container spec includes `resources.requests` and `resources.limits` for CPU and memory

#### Scenario: Worker pod has resource limits
- **WHEN** the worker rollout is rendered with default values
- **THEN** the container spec includes `resources.requests` and `resources.limits` for CPU and memory

### Requirement: HPA for backend, worker, and frontend
The Helm chart SHALL include HorizontalPodAutoscaler templates for backend, worker, and frontend.

#### Scenario: Backend HPA is rendered when enabled
- **WHEN** `backend.hpa.enabled` is `true`
- **THEN** an HPA resource is rendered targeting the backend rollout

### Requirement: gVisor RuntimeClass and sandbox
The Helm chart SHALL define a `RuntimeClass` for gVisor and a sandbox Job template with `runtimeClassName: gvisor`.

#### Scenario: gVisor RuntimeClass is defined
- **WHEN** the Helm chart is rendered
- **THEN** a `RuntimeClass` resource named `gvisor` is included

### Requirement: Security contexts on all pods
All pod templates SHALL include `securityContext` with `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, and `allowPrivilegeEscalation: false`.

#### Scenario: Backend pod has security context
- **WHEN** the backend rollout is rendered
- **THEN** the container spec includes the required securityContext fields

### Requirement: Versioned image tags
Default image tags SHALL NOT use `:latest`. Default tags SHALL match the chart `appVersion`.

#### Scenario: Default tags are versioned
- **WHEN** Helm values are rendered with defaults
- **THEN** image tags are not `latest`

### Requirement: Health probe tuning
Backend health probes SHALL include `initialDelaySeconds`, `periodSeconds`, and `failureThreshold`. A `startupProbe` SHALL be added.

#### Scenario: Backend has startup probe
- **WHEN** the backend rollout is rendered
- **THEN** a startupProbe is defined

### Requirement: PodDisruptionBudget
PDB templates SHALL exist for backend, worker, and frontend with configurable `minAvailable`.

#### Scenario: Backend PDB is rendered
- **WHEN** `backend.pdb.enabled` is `true`
- **THEN** a PodDisruptionBudget resource is rendered

### Requirement: ServiceAccount resources
ServiceAccount resources SHALL be defined in the Helm chart for backend, worker, and frontend.

#### Scenario: ServiceAccounts are created
- **WHEN** the Helm chart is rendered
- **THEN** ServiceAccount resources exist for backend, worker, and frontend
