# Authorization Usage Guide

Quick reference guide for developers implementing authorization (RBAC) in Dashtam.

**Target Audience**: Developers building API endpoints with role-based access control

**Related Documentation**:

- Architecture: `docs/architecture/authorization.md` (why/what)
- Authentication: `docs/guides/authentication.md`

---

## Quick Reference

| Role | Inherits From | Typical Use |
|------|---------------|-------------|
| `admin` | `user` | Full system access, user management |
| `user` | `readonly` | Standard operations (CRUD on own data) |
| `readonly` | - | View-only access |

| Permission | admin | user | readonly |
|------------|-------|------|----------|
| `users:read` | ✅ | ✅ | ✅ |
| `users:write` | ✅ | ✅ | ❌ |
| `users:delete` | ✅ | ❌ | ❌ |
| `accounts:read` | ✅ | ✅ | ✅ |
| `accounts:write` | ✅ | ✅ | ❌ |
| `providers:*` | ✅ | ✅ | ❌ |
| `admin:*` | ✅ | ❌ | ❌ |

---

## 1. Requiring Authentication + Role

### Basic Role Check (JWT-based)

Use `require_role` from `auth_dependencies.py` for fast JWT-based role checks:

```python
from fastapi import APIRouter, Depends
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
    require_role,
)

router = APIRouter()

@router.get("/admin/users")
async def list_all_users(
    current_user: CurrentUser = Depends(require_role("admin")),
) -> list[UserResponse]:
    """Admin-only: List all users in system."""
    # Only admins reach here
    ...
```

### How `require_role` Works (JWT-based)

1. Gets current user from `get_current_user` dependency
2. Checks `roles` array in JWT claims
3. Returns `CurrentUser` if role matches, raises `HTTPException(403)` if not

**Note**: JWT-based checks are fast but may be stale if role was revoked after token issuance. For sensitive operations, use Casbin-based `require_casbin_role`.

---

## 2. Requiring Specific Permission (Casbin-based)

### Permission Check

Use `require_permission` from `authorization_dependencies.py` for real-time Casbin checks:

```python
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)
from src.presentation.routers.api.middleware.authorization_dependencies import (
    require_permission,
)

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission("users", "write")),
) -> None:
    """Delete user (requires users:write permission)."""
    ...
```

### Available Resources and Actions

Permissions are expressed as `resource:action` pairs.

```python
from src.domain.enums import Resource, Action

# Resources (src/domain/enums/permission.py)
class Resource(str, Enum):
    ACCOUNTS = "accounts"
    TRANSACTIONS = "transactions"
    PROVIDERS = "providers"
    SESSIONS = "sessions"
    USERS = "users"
    ADMIN = "admin"
    SECURITY = "security"

# Actions
class Action(str, Enum):
    READ = "read"
    WRITE = "write"
```

**Permission Check Format**: `require_permission(resource: str, action: str)`

Examples:

- `require_permission("accounts", "read")` - View accounts
- `require_permission("users", "write")` - Create/update/delete users
- `require_permission("admin", "write")` - Admin operations

---

## 3. Using AuthorizationProtocol Directly

### Checking Permission in Handler

```python
from src.domain.protocols.authorization_protocol import AuthorizationProtocol

class MyCommandHandler:
    def __init__(self, authorization: AuthorizationProtocol):
        self._authorization = authorization
    
    async def handle(self, command: MyCommand) -> Result[..., ...]:
        # Check if user can perform action
        allowed = await self._authorization.check_permission(
            user_id=command.user_id,
            resource="accounts",
            action="write",
        )
        
        if not allowed:
            return Failure(error="permission_denied")
        
        # Continue with business logic
        ...
```

### Checking Role Directly

```python
async def handle(self, command: MyCommand) -> Result[..., ...]:
    # Check if user has admin role
    is_admin = await self._authorization.has_role(
        user_id=command.user_id,
        role="admin",
    )
    
    if is_admin:
        # Admin-specific logic
        ...
```

**Note**: Use `get_authorization()` from container to get `CasbinAdapter` implementing `AuthorizationProtocol`.

---

## 4. Role Management (Admin Only)

### Assigning a Role

```python
from src.domain.protocols.authorization_protocol import AuthorizationProtocol
from src.presentation.routers.api.middleware.auth_dependencies import CurrentUser

async def assign_role_to_user(
    target_user_id: UUID,
    role: str,
    admin_user: CurrentUser,
    authorization: AuthorizationProtocol,
) -> bool:
    """Assign role to user (admin only)."""
    success = await authorization.assign_role(
        user_id=target_user_id,
        role=role,
        assigned_by=admin_user.user_id,
    )
    
    # Events emitted automatically:
    # - RoleAssignmentAttempted (before)
    # - RoleAssignmentSucceeded or RoleAssignmentFailed (after)
    
    return success
```

### Revoking a Role

```python
async def revoke_role_from_user(
    target_user_id: UUID,
    role: str,
    admin_user: CurrentUser,
    authorization: AuthorizationProtocol,
    reason: str | None = None,
) -> bool:
    """Revoke role from user (admin only)."""
    success = await authorization.revoke_role(
        user_id=target_user_id,
        role=role,
        revoked_by=admin_user.user_id,
        reason=reason,  # Optional reason for audit
    )
    
    return success
```

### Getting User's Roles

```python
async def get_user_roles(
    user_id: UUID,
    authorization: AuthorizationProtocol,
) -> list[str]:
    """Get all roles assigned to user."""
    roles = await authorization.get_roles_for_user(user_id)
    # Returns: ["user"] or ["admin"] (direct roles only)
    return roles
```

---

## 5. Casbin Policy Configuration

### Model Configuration

```ini
# src/infrastructure/authorization/model.conf

[request_definition]
r = sub, obj, act

[policy_definition]
p = sub, obj, act

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub) && r.obj == p.obj && r.act == p.act
```

### Policy Definition

```csv
# Role hierarchy
g, admin, user
g, user, readonly

# Admin permissions (all)
p, admin, users, read
p, admin, users, write
p, admin, users, delete
p, admin, accounts, read
p, admin, accounts, write
p, admin, accounts, delete
p, admin, providers, read
p, admin, providers, write
p, admin, providers, delete
p, admin, admin, *

# User permissions
p, user, users, read
p, user, users, write
p, user, accounts, read
p, user, accounts, write
p, user, providers, read
p, user, providers, write

# Readonly permissions
p, readonly, users, read
p, readonly, accounts, read
p, readonly, transactions, read
```

---

## 6. Cache Behavior

### Permission Caching

- **TTL**: 5 minutes
- **Key format**: `authz:{user_id}:{resource}:{action}`
- **Invalidation**: On role change (assign/revoke)

### Cache Lookup Flow

```text
1. Check Redis: authz:123:accounts:write
2. If hit: Return cached result (< 1ms)
3. If miss: Query Casbin enforcer (~5ms)
4. Cache result with 5-min TTL
```

### Manual Cache Invalidation

```python
# Happens automatically on role changes
# But can be done manually if needed:
await authorization._invalidate_user_cache(user_id)
```

---

## 7. Audit Trail

### Authorization Events Logged

All authorization checks are audited:

```python
# On allowed access
AuditAction.ACCESS_GRANTED
{
    "resource": "accounts",
    "action": "write",
    "allowed": True,
    "cached": False,
}

# On denied access
AuditAction.ACCESS_DENIED
{
    "resource": "admin",
    "action": "users",
    "allowed": False,
    "cached": False,
}
```

### Role Change Events

```python
# Role assignment
RoleAssignmentAttempted → RoleAssignmentSucceeded/Failed

# Role revocation
RoleRevocationAttempted → RoleRevocationSucceeded/Failed
```

---

## 8. Common Patterns

### Pattern 1: Admin-Only Endpoint (JWT-based)

```python
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    require_role,
)

@router.get("/admin/audit-logs")
async def get_audit_logs(
    current_user: CurrentUser = Depends(require_role("admin")),
) -> list[AuditLogResponse]:
    """Admin-only: View audit logs."""
    ...
```

### Pattern 2: Resource Owner Check

```python
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)
from src.domain.protocols.authorization_protocol import AuthorizationProtocol

@router.get("/accounts/{account_id}")
async def get_account(
    account_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    authorization: AuthorizationProtocol = Depends(get_authorization),
    account_repo: AccountRepository = Depends(get_account_repo),
) -> AccountResponse:
    """Get account (must own account or be admin)."""
    account = await account_repo.find_by_id(account_id)
    
    if not account:
        raise HTTPException(404, "Account not found")
    
    # Owner check
    if account.user_id != current_user.user_id:
        # Check if admin (can view any account)
        if not await authorization.has_role(current_user.user_id, "admin"):
            raise HTTPException(403, "Cannot access this account")
    
    return AccountResponse.from_entity(account)
```

### Pattern 3: Combined Role + Permission (Casbin-based)

```python
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)
from src.presentation.routers.api.middleware.authorization_dependencies import (
    require_casbin_role,
    require_permission,
)

@router.post("/admin/users/{user_id}/suspend")
async def suspend_user(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    _role: None = Depends(require_casbin_role("admin")),
    _perm: None = Depends(require_permission("admin", "write")),
) -> None:
    """Suspend user (requires admin role AND admin:write permission)."""
    ...
```

### Pattern 4: Feature Flag with Role (Casbin-based)

```python
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)
from src.domain.protocols.authorization_protocol import AuthorizationProtocol
from src.core.container import get_authorization

@router.get("/beta/analytics")
async def beta_analytics(
    current_user: CurrentUser = Depends(get_current_user),
    authorization: AuthorizationProtocol = Depends(get_authorization),
) -> AnalyticsResponse:
    """Beta feature: Analytics dashboard."""
    # Check if user has beta access via Casbin
    has_beta = await authorization.has_role(current_user.user_id, "beta_tester")
    
    if not has_beta:
        raise HTTPException(403, "Beta access required")
    
    ...
```

---

## 9. Testing Authorization

### Unit Testing with Mocks

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_authorization():
    authz = AsyncMock()
    authz.check_permission.return_value = True
    authz.has_role.return_value = False
    return authz

async def test_handler_checks_permission(mock_authorization):
    handler = MyHandler(authorization=mock_authorization)
    
    await handler.handle(MyCommand(user_id=user_id, ...))
    
    mock_authorization.check_permission.assert_called_once_with(
        user_id=user_id,
        resource="accounts",
        action="write",
    )
```

### API Testing

```python
def test_admin_endpoint_requires_admin_role(client: TestClient, user_token):
    """Regular user cannot access admin endpoint."""
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    
    assert response.status_code == 403

def test_admin_endpoint_allows_admin(client: TestClient, admin_token):
    """Admin can access admin endpoint."""
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    
    assert response.status_code == 200
```

### Integration Testing with Real Casbin

```python
async def test_role_hierarchy(casbin_adapter):
    """Test role inheritance works correctly."""
    user_id = uuid7()
    
    # Assign user role
    await casbin_adapter.assign_role(
        user_id=user_id,
        role="user",
        assigned_by=admin_id,
    )
    
    # User should have user permissions
    assert await casbin_adapter.check_permission(
        user_id=user_id,
        resource="accounts",
        action="write",
    )
    
    # User should NOT have admin permissions
    assert not await casbin_adapter.check_permission(
        user_id=user_id,
        resource="admin",
        action="users",
    )
```

---

## 10. Troubleshooting

### "403 Forbidden" on authorized user

1. Check user has required role: `await authz.get_roles_for_user(user_id)`
2. Check permission exists in policy: `await authz.get_permissions_for_role(role)`
3. Check cache isn't stale: Wait 5 minutes or invalidate manually
4. Check role hierarchy in model.conf

### Permission check returns wrong result

1. Check Casbin model.conf matcher syntax
2. Check policy CSV has correct format
3. Check user ID is being passed as string to Casbin
4. Enable Casbin logging for debugging

### Role assignment not taking effect

1. Check `save_policy()` was called after change
2. Check cache was invalidated
3. Check PostgreSQL transaction committed
4. Check for database constraint violations

---

**Created**: 2025-12-05 | **Last Updated**: 2026-01-10
