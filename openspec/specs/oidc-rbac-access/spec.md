# oidc-rbac-access Specification

## Purpose
TBD - created by archiving change phase-3-tenant-security-and-access. Update Purpose after archive.
## Requirements
### Requirement: OIDC Authentication Is Mandatory

The platform MUST authenticate users through OIDC and derive tenant and role context from trusted identity claims.

#### Scenario: Authenticated session carries tenant context
- **WHEN** a user signs in through the configured identity provider
- **THEN** the resulting session or token contains the tenant identity and authorized team scope needed for route protection
- **AND** unauthenticated access to protected product surfaces is rejected

### Requirement: Four-Tier RBAC Is Enforced

The platform MUST support `viewer`, `operator`, `admin`, and `super-admin` roles, with backend authorization treated as authoritative.

#### Scenario: Backend remains the source of truth
- **WHEN** a user attempts an action through the API or UI
- **THEN** the backend checks the user's role and tenant scope before performing the action
- **AND** frontend route guards may improve UX but cannot authorize a forbidden action on their own

#### Scenario: Higher-privilege actions stay restricted
- **WHEN** a viewer or operator attempts to change agent config, graph config, or tenant-wide settings
- **THEN** the action is denied unless the user has the required admin or super-admin privileges

### Requirement: Session Handling Remains Predictable

Session lifecycle and privilege changes MUST be reflected consistently across the product.

#### Scenario: Session expiration removes access
- **WHEN** a session expires or becomes invalid
- **THEN** protected API requests and UI actions are rejected
- **AND** the product does not continue serving privileged data based on stale client state

#### Scenario: Role or team changes take effect
- **WHEN** a user's role or team membership changes in the identity system
- **THEN** the product applies the updated authorization scope on the next valid session evaluation
- **AND** stale elevated access is not assumed indefinitely

