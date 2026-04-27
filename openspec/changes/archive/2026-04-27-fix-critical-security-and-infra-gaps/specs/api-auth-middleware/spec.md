## ADDED Requirements

### Requirement: Auth middleware on all admin routers
All admin API routers SHALL require authenticated requests via the `AuthorizationPolicy` from `security/auth.py`. The policy SHALL be wired as a FastAPI dependency on every endpoint in `compliance/admin.py`, `credentials/admin.py`, `webhook/admin.py`, and `supply_chain/admission.py`.

#### Scenario: Admin endpoint rejects unauthenticated request
- **WHEN** a request is made to any admin endpoint without a valid OIDC token
- **THEN** the response is `401 Unauthorized`

#### Scenario: Admin endpoint rejects insufficient role
- **WHEN** a request is made to an admin endpoint with a VIEWER role
- **THEN** the response is `403 Forbidden`

#### Scenario: Admin endpoint accepts valid admin request
- **WHEN** a request is made to an admin endpoint with a valid OIDC token and ADMIN or SUPER_ADMIN role
- **THEN** the request is processed normally

### Requirement: Tenant-scoped authorization
All admin endpoints SHALL enforce tenant scoping. Non-super-admin users SHALL only access resources within their assigned tenant.

#### Scenario: Cross-tenant access is blocked
- **WHEN** an OPERATOR with tenant `alpha` attempts to access resources for tenant `beta`
- **THEN** the response is `403 Forbidden`

#### Scenario: Super-admin can access all tenants
- **WHEN** a SUPER_ADMIN requests resources for any tenant
- **THEN** the request is processed normally

### Requirement: Auth dependency injection pattern
The auth dependency SHALL be injectable via FastAPI's `Depends()` mechanism. Each router builder function SHALL accept an optional `auth_policy` parameter that defaults to a production `AuthorizationPolicy` instance.

#### Scenario: Router accepts custom auth policy
- **WHEN** `build_admin_router(auth_policy=custom_policy)` is called
- **THEN** the router uses `custom_policy` for authorization checks
