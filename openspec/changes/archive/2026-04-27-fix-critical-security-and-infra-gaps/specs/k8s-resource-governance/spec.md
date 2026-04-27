## ADDED Requirements

### Requirement: Resource limits on all pods
All backend, worker, and frontend pod templates SHALL define `resources.requests` and `resources.limits` for CPU and memory. The values SHALL be configurable via Helm values.

#### Scenario: Backend pod has resource limits
- **WHEN** the backend rollout or deployment is rendered with default values
- **THEN** the container spec includes `resources.requests` and `resources.limits` for CPU and memory

#### Scenario: Worker pod has resource limits
- **WHEN** the worker rollout is rendered with default values
- **THEN** the container spec includes `resources.requests` and `resources.limits` for CPU and memory

#### Scenario: Resource values are configurable
- **WHEN** Helm values override `backend.resources.requests.cpu`
- **THEN** the rendered manifest reflects the overridden value

### Requirement: HPA for backend, worker, and frontend
The Helm chart SHALL include HorizontalPodAutoscaler templates for backend, worker, and frontend. HPA SHALL scale based on CPU and memory utilization targets configurable via Helm values.

#### Scenario: Backend HPA is rendered when enabled
- **WHEN** `backend.hpa.enabled` is `true` in Helm values
- **THEN** an HPA resource is rendered targeting the backend deployment/rollout

#### Scenario: HPA targets are configurable
- **WHEN** `backend.hpa.targetCPUUtilization` is set to `70`
- **THEN** the HPA spec includes `targetCPUUtilizationPercentage: 70`

### Requirement: gVisor RuntimeClass and sandbox
The Helm chart SHALL define a `RuntimeClass` for gVisor and include a sandbox Job template with `runtimeClassName: gvisor`, `runAsNonRoot: true`, and resource quotas.

#### Scenario: gVisor RuntimeClass is defined
- **WHEN** the Helm chart is rendered
- **THEN** a `RuntimeClass` resource named `gvisor` is included

#### Scenario: Sandbox Job uses gVisor
- **WHEN** a sandbox Job is rendered
- **THEN** the pod spec includes `runtimeClassName: gvisor` and `securityContext.runAsNonRoot: true`

### Requirement: Security contexts on all pods
All pod templates SHALL include `securityContext` with `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, and `allowPrivilegeEscalation: false`.

#### Scenario: Backend pod has security context
- **WHEN** the backend rollout is rendered
- **THEN** the container spec includes `securityContext` with `runAsNonRoot`, `readOnlyRootFilesystem`, and `allowPrivilegeEscalation`

### Requirement: Versioned image tags
Default image tags SHALL NOT use `:latest`. Default tags SHALL match the chart `appVersion`.

#### Scenario: Default tags are versioned
- **WHEN** Helm values are rendered with defaults
- **THEN** `backend.image.tag`, `worker.image.tag`, and `frontend.image.tag` are not `latest`

#### Scenario: Tags match appVersion
- **WHEN** `appVersion` is `0.1.0`
- **THEN** default image tags are `0.1.0`
