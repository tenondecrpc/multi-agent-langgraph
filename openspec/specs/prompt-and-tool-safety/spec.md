# prompt-and-tool-safety Specification

## Purpose
TBD - created by archiving change phase-3-tenant-security-and-access. Update Purpose after archive.
## Requirements
### Requirement: Untrusted Content Is Framed As Data

External ticket text, repository documents, diffs, and similar content MUST be treated as untrusted input rather than instructions.

#### Scenario: Prompt framing contains untrusted content
- **WHEN** the runtime includes ticket or repository content in model inputs
- **THEN** the content is delimited and labeled as data
- **AND** the agent instructions explicitly forbid treating that content as new authority over tools or policy

### Requirement: Tool Access Follows Role Allowlist

Runtime roles MUST operate within an explicit tool allowlist and MUST escalate policy violations instead of executing forbidden actions.

#### Scenario: Tool policy violation is blocked
- **WHEN** a role attempts to invoke a tool family outside its allowed boundary
- **THEN** the runtime blocks the call
- **AND** the run records a policy-violation escalation instead of silently broadening the role's capabilities

### Requirement: Sensitive Changes Force Higher Scrutiny

Changes touching sensitive repository paths MUST not flow through the ordinary success path without additional exception handling.

#### Scenario: Sensitive path triggers security review
- **WHEN** a planned or produced diff touches security-sensitive paths such as workflow config, infra, Dockerfiles, secrets, or equivalent protected surfaces
- **THEN** the run routes to a registered `security_review` exception path
- **AND** the change does not continue as an ordinary low-risk PR

### Requirement: LLM Output Is Screened For Unsafe Leakage

Model outputs MUST be screened for common secret-leak and prompt-leak patterns before downstream actions use them.

#### Scenario: Suspicious output is intercepted
- **WHEN** a model response contains credential-like material, high-risk prompt-leak markers, or similar unsafe payloads
- **THEN** the output is blocked or redacted according to policy
- **AND** the run escalates instead of using the output as trusted downstream input

