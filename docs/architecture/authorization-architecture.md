# Authorization Architecture

## 1. Overview

### Purpose

Provide flexible, auditable Role-Based Access Control (RBAC) for Dashtam using Casbin library, integrated with hexagonal architecture and existing JWT authentication.

### Key Requirements

**Security First**:

- All authorization decisions audited (PCI-DSS compliance)
- Fail-closed default (deny if policy missing)
- Cache authorization results (Redis, 5-minute TTL)
- Audit both allowed AND denied access attempts

**Hexagonal Architecture**:

- Domain layer: AuthorizationProtocol (port)
- Infrastructure layer: CasbinAdapter (adapter)
- Application layer: Permission checks in command/query handlers
- Presentation layer: FastAPI dependencies (`require_role`, `require_permission`)

**Integration Requirements**:

- JWT tokens contain user roles
- Audit trail records all authorization events
- Domain events for role changes

---

## 2. Authorization Strategy

### Decision: Casbin RBAC

**Why Casbin?**

- Industry-standard authorization library
- Supports multiple access control models (ACL, RBAC, ABAC)
- Policy defined in configuration (easy to modify)
- Async support (`AsyncEnforcer`) for FastAPI
- PostgreSQL adapter for persistent policy storage
- Well-tested, production-ready

**Why not custom RBAC?**

- Reinventing the wheel (Casbin has 16k+ GitHub stars)
- Complex edge cases handled (role inheritance, wildcards)
- Policy management APIs included
- Future extensibility (can add ABAC later)

### RBAC Model

```text
┌─────────────────────────────────────────────────────────────┐
│                    RBAC Hierarchy                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────┐                                               │
│   │  admin  │ ────────────────────────────────────┐         │
│   └────┬────┘                                     │         │
│        │ inherits                                 │         │
│        ↓                                          │         │
│   ┌─────────┐                                     │         │
│   │  user   │ ──────────────────────────────┐     │         │
│   └────┬────┘                               │     │         │
│        │ inherits                           │     │         │
│        ↓                                    ↓     ↓         │
│   ┌──────────┐                         Permissions:         │
│   │ readonly │                         - accounts:read      │
│   └──────────┘                         - accounts:write     │
│        │                               - transactions:read  │
│        ↓                               - transactions:write │
│   Base permissions:                    - providers:read     │
│   - accounts:read                      - providers:write    │
│   - transactions:read                  - users:read         │
│   - providers:read                     - users:write        │
│                                        - admin:*            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Role Definitions**:

| Role | Inherits | Permissions | Description |
|------|----------|-------------|-------------|
| `readonly` | - | Read-only access to own resources | View accounts, transactions |
| `user` | `readonly` | Write access to own resources | Create/modify own data |
| `admin` | `user` | Full system access | User management, system config |

---

## 3. Casbin Configuration

### Model Definition (PERM Metamodel)

```ini
# authorization/model.conf

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

**Components**:

- **Request (r)**: `sub` (user/role), `obj` (resource), `act` (action)
- **Policy (p)**: Permission rules
- **Role (g)**: User-role assignments and role inheritance
- **Effect (e)**: Allow if any policy matches
- **Matchers (m)**: How to match request against policies

### Policy Definition

```csv
# authorization/policy.csv

# Role permissions
p, readonly, accounts, read
p, readonly, transactions, read
p, readonly, providers, read
p, readonly, sessions, read

p, user, accounts, write
p, user, transactions, write
p, user, providers, write
p, user, sessions, write

p, admin, users, read
p, admin, users, write
p, admin, admin, read
p, admin, admin, write
p, admin, security, read
p, admin, security, write

# Role hierarchy
g, user, readonly
g, admin, user
```

**Policy Format**: `p, subject, object, action`
**Role Format**: `g, child_role, parent_role`

---

## 4. Hexagonal Architecture Integration

### Layer Responsibilities

```text
┌─────────────────────────────────────────────────────────────┐
│ Presentation Layer (FastAPI)                                │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  FastAPI Dependencies                                   │ │
│ │  - require_role("admin")                                │ │
│ │  - require_permission("users", "write")                 │ │
│ │  - Raises HTTPException(403) on denial                  │ │
│ └───────────────────────────┬─────────────────────────────┘ │
└─────────────────────────────┼───────────────────────────────┘
                              │ uses
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Application Layer                                           │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  Command/Query Handlers                                 │ │
│ │  - May check permissions for domain logic               │ │
│ │  - Uses AuthorizationProtocol                           │ │
│ └───────────────────────────┬─────────────────────────────┘ │
└─────────────────────────────┼───────────────────────────────┘
                              │ uses
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Domain Layer (Protocols)                                    │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  AuthorizationProtocol (PORT)                           │ │
│ │  - check_permission(user_id, resource, action)          │ │
│ │  - get_roles_for_user(user_id)                          │ │
│ │  - assign_role(user_id, role)                           │ │
│ │  - revoke_role(user_id, role)                           │ │
│ └───────────────────────────┬─────────────────────────────┘ │
└─────────────────────────────┼───────────────────────────────┘
                              ↑ implements
                              │
┌─────────────────────────────────────────────────────────────┐
│ Infrastructure Layer                                        │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  CasbinAdapter (ADAPTER)                                │ │
│ │  - AsyncEnforcer for async operations                   │ │
│ │  - PostgreSQL adapter for policy storage                │ │
│ │  - Redis cache for enforcement results                  │ │
│ │  - Audit integration for all checks                     │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Domain Protocol

```python
# src/domain/protocols/authorization_protocol.py
from typing import Protocol
from uuid import UUID

class AuthorizationProtocol(Protocol):
    """Authorization port - defines authorization operations.

    Implementations:
        - CasbinAdapter: Production (Casbin + PostgreSQL)
        - InMemoryAuthorizationAdapter: Testing

    Usage:
        # Check permission
        result = await authz.check_permission(
            user_id=user.id,
            resource="accounts",
            action="write"
        )
        if not result:
            raise AuthorizationError("Access denied")

        # Get user roles
        roles = await authz.get_roles_for_user(user.id)

    Note:
        - All operations are async for database/cache access
        - Returns Result types for error handling
        - Integrates with audit trail automatically
    """

    async def check_permission(
        self,
        user_id: UUID,
        resource: str,
        action: str,
    ) -> bool:
        """Check if user has permission for resource/action.

        Args:
            user_id: User's UUID.
            resource: Resource name (accounts, transactions, etc.).
            action: Action name (read, write, delete).

        Returns:
            True if allowed, False if denied.

        Side Effects:
            - Audits the authorization check (allowed/denied)
            - Caches result in Redis (5 min TTL)
        """
        ...

    async def get_roles_for_user(self, user_id: UUID) -> list[str]:
        """Get all roles assigned to user (including inherited).

        Args:
            user_id: User's UUID.

        Returns:
            List of role names (e.g., ["user", "readonly"]).
        """
        ...

    async def has_role(self, user_id: UUID, role: str) -> bool:
        """Check if user has specific role (including inherited).

        Args:
            user_id: User's UUID.
            role: Role name to check.

        Returns:
            True if user has role, False otherwise.
        """
        ...

    async def assign_role(self, user_id: UUID, role: str) -> bool:
        """Assign role to user.

        Args:
            user_id: User's UUID.
            role: Role name to assign.

        Returns:
            True if role assigned, False if already had role.

        Side Effects:
            - Emits RoleAssigned domain event
            - Invalidates user's permission cache
            - Audits the role assignment
        """
        ...

    async def revoke_role(self, user_id: UUID, role: str) -> bool:
        """Revoke role from user.

        Args:
            user_id: User's UUID.
            role: Role name to revoke.

        Returns:
            True if role revoked, False if didn't have role.

        Side Effects:
            - Emits RoleRevoked domain event
            - Invalidates user's permission cache
            - Audits the role revocation
        """
        ...
```

---

## 5. Casbin Adapter Implementation

### CasbinAdapter Architecture

```python
# src/infrastructure/authorization/casbin_adapter.py
from typing import TYPE_CHECKING
from uuid import UUID

import casbin

if TYPE_CHECKING:
    from src.domain.protocols.audit_protocol import AuditProtocol
    from src.domain.protocols.cache_protocol import CacheProtocol
    from src.domain.protocols.logger_protocol import LoggerProtocol

class CasbinAdapter:
    """Casbin-based authorization adapter.

    Implements AuthorizationProtocol using Casbin AsyncEnforcer
    with PostgreSQL policy storage and Redis caching.

    Architecture:
        - AsyncEnforcer: Async Casbin enforcer for FastAPI
        - PostgreSQL Adapter: Persistent policy storage
        - Redis Cache: 5-minute TTL for enforcement results
        - Audit Integration: All checks logged

    Note:
        Enforcer is initialized at FastAPI startup (async required).
        See src/main.py @app.on_event("startup") for initialization.

    Usage:
        adapter = CasbinAdapter(
            enforcer=enforcer,
            cache=cache,
            audit=audit,
            logger=logger,
        )
        allowed = await adapter.check_permission(user_id, "accounts", "write")
    """

    def __init__(
        self,
        enforcer: casbin.AsyncEnforcer,
        cache: "CacheProtocol",
        audit: "AuditProtocol",
        logger: "LoggerProtocol",
    ) -> None:
        self._enforcer = enforcer
        self._cache = cache
        self._audit = audit
        self._logger = logger

    async def check_permission(
        self,
        user_id: UUID,
        resource: str,
        action: str,
    ) -> bool:
        """Check permission with caching and audit."""
        # 1. Check cache first
        cache_key = f"authz:{user_id}:{resource}:{action}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached == "1"

        # 2. Get user's roles from JWT/database
        user_str = str(user_id)

        # 3. Check with Casbin enforcer
        allowed = await self._enforcer.enforce(user_str, resource, action)

        # 4. Cache result (5 minutes)
        await self._cache.set(
            cache_key,
            "1" if allowed else "0",
            ttl=300,
        )

        # 5. Audit the check
        await self._audit.record(
            action="ACCESS_GRANTED" if allowed else "ACCESS_DENIED",
            resource_type="authorization",
            user_id=user_id,
            context={
                "resource": resource,
                "action": action,
                "allowed": allowed,
            },
        )

        # 6. Log the check
        self._logger.info(
            "authorization_check",
            user_id=str(user_id),
            resource=resource,
            action=action,
            allowed=allowed,
        )

        return allowed
```

### Enforcer Initialization (FastAPI Startup)

Casbin's `AsyncEnforcer` requires async initialization (loading policies from database).
We initialize at FastAPI startup, then container retrieves the cached instance.

```python
# src/main.py
from contextlib import asynccontextmanager
from pathlib import Path

import casbin
from casbin_async_sqlalchemy_adapter import Adapter
from fastapi import FastAPI

from src.core.container import get_database

# Module-level storage for initialized enforcer
_enforcer: casbin.AsyncEnforcer | None = None


async def _initialize_enforcer() -> casbin.AsyncEnforcer:
    """Initialize Casbin AsyncEnforcer with PostgreSQL adapter.

    Called once at startup. Enforcer is cached for application lifetime.

    Returns:
        Configured AsyncEnforcer ready for use.
    """
    global _enforcer
    if _enforcer is not None:
        return _enforcer

    # Get database engine
    database = get_database()

    # Path to model configuration
    model_path = Path(__file__).parent / "infrastructure/authorization/model.conf"

    # Create PostgreSQL adapter for policy storage
    adapter = Adapter(database.engine)

    # Create enforcer with model and adapter
    _enforcer = casbin.AsyncEnforcer(str(model_path), adapter)

    # Load policies from database
    await _enforcer.load_policy()

    # Enable auto-save (changes persisted immediately)
    _enforcer.enable_auto_save(True)

    return _enforcer


def get_enforcer() -> casbin.AsyncEnforcer:
    """Get initialized enforcer (must call after startup)."""
    if _enforcer is None:
        raise RuntimeError("Enforcer not initialized. Call _initialize_enforcer() first.")
    return _enforcer


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager."""
    # Startup
    await _initialize_enforcer()
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(lifespan=lifespan)
```

**Why startup initialization?**

1. `AsyncEnforcer.load_policy()` is async - can't run in sync `@lru_cache()` container function
2. One-time cost at startup vs per-request initialization
3. Follows Casbin + FastAPI integration best practices
4. Container's `get_authorization()` retrieves pre-initialized enforcer

---

## 6. FastAPI Integration

### Permission Dependencies

```python
# src/presentation/api/dependencies/authorization.py
from functools import lru_cache
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.core.container import get_authorization
from src.domain.protocols.authorization_protocol import AuthorizationProtocol
from src.presentation.api.dependencies.authentication import get_current_user

class PermissionChecker:
    """FastAPI dependency for permission checking.

    Usage:
        @router.get("/users")
        async def list_users(
            _: None = Depends(require_permission("users", "read")),
            current_user: User = Depends(get_current_user),
        ):
            ...
    """

    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action

    async def __call__(
        self,
        current_user = Depends(get_current_user),
        authz: AuthorizationProtocol = Depends(get_authorization),
    ) -> None:
        """Check permission, raise 403 if denied."""
        allowed = await authz.check_permission(
            user_id=current_user.id,
            resource=self.resource,
            action=self.action,
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.resource}:{self.action}",
            )


class RoleChecker:
    """FastAPI dependency for role checking.

    Usage:
        @router.post("/admin/users")
        async def create_admin_user(
            _: None = Depends(require_role("admin")),
            current_user: User = Depends(get_current_user),
        ):
            ...
    """

    def __init__(self, role: str):
        self.role = role

    async def __call__(
        self,
        current_user = Depends(get_current_user),
        authz: AuthorizationProtocol = Depends(get_authorization),
    ) -> None:
        """Check role, raise 403 if user doesn't have role."""
        has_role = await authz.has_role(
            user_id=current_user.id,
            role=self.role,
        )
        if not has_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {self.role}",
            )


def require_permission(resource: str, action: str) -> PermissionChecker:
    """Factory for permission dependency.

    Args:
        resource: Resource name (accounts, users, etc.).
        action: Action name (read, write, delete).

    Returns:
        Callable dependency for FastAPI.

    Example:
        @router.delete("/accounts/{id}")
        async def delete_account(
            id: UUID,
            _: None = Depends(require_permission("accounts", "write")),
        ):
            ...
    """
    return PermissionChecker(resource, action)


def require_role(role: str) -> RoleChecker:
    """Factory for role dependency.

    Args:
        role: Role name (admin, user, readonly).

    Returns:
        Callable dependency for FastAPI.

    Example:
        @router.get("/admin/stats")
        async def get_admin_stats(
            _: None = Depends(require_role("admin")),
        ):
            ...
    """
    return RoleChecker(role)
```

### Endpoint Usage Examples

```python
# src/presentation/api/v1/users.py
from fastapi import APIRouter, Depends

from src.presentation.api.dependencies.authorization import (
    require_permission,
    require_role,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/")
async def list_users(
    _: None = Depends(require_permission("users", "read")),
):
    """List all users (admin only)."""
    ...


@router.post("/")
async def create_user(
    _: None = Depends(require_role("admin")),
):
    """Create new user (admin only)."""
    ...


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    _: None = Depends(require_permission("users", "write")),
):
    """Delete user (admin only)."""
    ...
```

---

## 7. Domain Events (3-State Pattern)

### Role Change Events

Following our 3-state pattern for security events (per development checklist §23b):

- `*Attempted` - Before operation (for audit trail of attempts)
- `*Succeeded` - After successful database commit
- `*Failed` - After validation/commit failure

```python
# src/domain/events/authorization_events.py
from dataclasses import dataclass
from uuid import UUID

from src.domain.events.base_event import DomainEvent


# =============================================================================
# Role Assignment Events (3-State)
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class RoleAssignmentAttempted(DomainEvent):
    """Emitted BEFORE attempting to assign a role.

    Records the attempt for audit trail, even if assignment fails.

    Handlers:
        - LoggingEventHandler: Logs attempt at INFO level
        - AuditEventHandler: Creates ROLE_ASSIGNMENT_ATTEMPTED audit record

    Example:
        await event_bus.publish(RoleAssignmentAttempted(
            user_id=target_user.id,
            role="admin",
            assigned_by=admin.id,
        ))
    """

    user_id: UUID
    role: str
    assigned_by: UUID


@dataclass(frozen=True, kw_only=True)
class RoleAssignmentSucceeded(DomainEvent):
    """Emitted AFTER role successfully assigned and committed.

    Triggers cache invalidation and notifications.

    Handlers:
        - LoggingEventHandler: Logs success at INFO level
        - AuditEventHandler: Creates ROLE_ASSIGNED audit record
        - CacheInvalidationHandler: Invalidates authz:{user_id}:* cache

    Example:
        # After session.commit() succeeds
        await event_bus.publish(RoleAssignmentSucceeded(
            user_id=target_user.id,
            role="admin",
            assigned_by=admin.id,
        ))
    """

    user_id: UUID
    role: str
    assigned_by: UUID


@dataclass(frozen=True, kw_only=True)
class RoleAssignmentFailed(DomainEvent):
    """Emitted when role assignment fails.

    Captures failure reason for audit and alerting.

    Handlers:
        - LoggingEventHandler: Logs failure at WARNING level
        - AuditEventHandler: Creates ROLE_ASSIGNMENT_FAILED audit record

    Example:
        await event_bus.publish(RoleAssignmentFailed(
            user_id=target_user.id,
            role="admin",
            assigned_by=admin.id,
            reason="User not found",
        ))
    """

    user_id: UUID
    role: str
    assigned_by: UUID
    reason: str


# =============================================================================
# Role Revocation Events (3-State)
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class RoleRevocationAttempted(DomainEvent):
    """Emitted BEFORE attempting to revoke a role.

    Records the attempt for audit trail, even if revocation fails.

    Handlers:
        - LoggingEventHandler: Logs attempt at INFO level
        - AuditEventHandler: Creates ROLE_REVOCATION_ATTEMPTED audit record

    Example:
        await event_bus.publish(RoleRevocationAttempted(
            user_id=target_user.id,
            role="admin",
            revoked_by=admin.id,
            reason="User left admin team",
        ))
    """

    user_id: UUID
    role: str
    revoked_by: UUID
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class RoleRevocationSucceeded(DomainEvent):
    """Emitted AFTER role successfully revoked and committed.

    Triggers cache invalidation and may revoke sessions.

    Handlers:
        - LoggingEventHandler: Logs success at INFO level
        - AuditEventHandler: Creates ROLE_REVOKED audit record
        - CacheInvalidationHandler: Invalidates authz:{user_id}:* cache
        - SessionRevocationHandler: May revoke sessions if admin role removed

    Example:
        # After session.commit() succeeds
        await event_bus.publish(RoleRevocationSucceeded(
            user_id=target_user.id,
            role="admin",
            revoked_by=admin.id,
            reason="User left admin team",
        ))
    """

    user_id: UUID
    role: str
    revoked_by: UUID
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class RoleRevocationFailed(DomainEvent):
    """Emitted when role revocation fails.

    Captures failure reason for audit and alerting.

    Handlers:
        - LoggingEventHandler: Logs failure at WARNING level
        - AuditEventHandler: Creates ROLE_REVOCATION_FAILED audit record

    Example:
        await event_bus.publish(RoleRevocationFailed(
            user_id=target_user.id,
            role="admin",
            revoked_by=admin.id,
            reason="User does not have this role",
        ))
    """

    user_id: UUID
    role: str
    revoked_by: UUID
    reason: str
```

### Event Flow Pattern

```text
┌────────────────────────────────────────────────────────────────┐
│              Role Assignment Flow (3-State)                    │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. Publish RoleAssignmentAttempted                            │
│     └── Audit: ROLE_ASSIGNMENT_ATTEMPTED                       │
│                          │                                     │
│                          ↓                                     │
│  2. Validate & Execute                                         │
│     ├── User exists?                                           │
│     ├── Role valid?                                            │
│     ├── Already has role?                                      │
│     └── Add to Casbin policy                                   │
│                          │                                     │
│           ┌──────────────┴──────────────┐                      │
│           │                             │                      │
│         SUCCESS                       FAILURE                  │
│           │                             │                      │
│           ↓                             ↓                      │
│  3a. session.commit()          3b. Publish RoleAssignmentFailed│
│           │                        └── Audit: ROLE_ASSIGNMENT_ │
│           ↓                            FAILED                  │
│  4. Publish RoleAssignment-                                    │
│     Succeeded                                                  │
│     ├── Audit: ROLE_ASSIGNED                                   │
│     └── Invalidate cache                                       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 8. Audit Actions

### Authorization Audit Events

```python
# Addition to src/domain/enums/audit_action.py

class AuditAction(str, Enum):
    # ... existing actions ...

    # Permission check events
    ACCESS_GRANTED = "ACCESS_GRANTED"
    ACCESS_DENIED = "ACCESS_DENIED"

    # Role assignment events (3-state)
    ROLE_ASSIGNMENT_ATTEMPTED = "ROLE_ASSIGNMENT_ATTEMPTED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"  # Success
    ROLE_ASSIGNMENT_FAILED = "ROLE_ASSIGNMENT_FAILED"

    # Role revocation events (3-state)
    ROLE_REVOCATION_ATTEMPTED = "ROLE_REVOCATION_ATTEMPTED"
    ROLE_REVOKED = "ROLE_REVOKED"  # Success
    ROLE_REVOCATION_FAILED = "ROLE_REVOCATION_FAILED"
```

### Audit Context Schema

```python
# ACCESS_GRANTED / ACCESS_DENIED context
{
    "resource": "accounts",
    "action": "write",
    "allowed": True,
    "cached": False,
    "roles": ["user", "readonly"],
}

# ROLE_ASSIGNMENT_ATTEMPTED context
{
    "role": "admin",
    "assigned_by": "550e8400-e29b-41d4-a716-446655440000",
}

# ROLE_ASSIGNED context (success)
{
    "role": "admin",
    "assigned_by": "550e8400-e29b-41d4-a716-446655440000",
}

# ROLE_ASSIGNMENT_FAILED context
{
    "role": "admin",
    "assigned_by": "550e8400-e29b-41d4-a716-446655440000",
    "reason": "User not found",
}

# ROLE_REVOKED context (success)
{
    "role": "admin",
    "revoked_by": "550e8400-e29b-41d4-a716-446655440000",
    "reason": "User left admin team",
}
```

---

## 9. Caching Strategy

### Permission Cache

```text
┌─────────────────────────────────────────────────────────────┐
│                  Permission Cache Flow                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Request: check_permission(user_id, "accounts", "write")    │
│                          │                                  │
│                          ↓                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. Check Redis Cache                                │    │
│  │    Key: authz:{user_id}:accounts:write              │    │
│  │    TTL: 5 minutes                                   │    │
│  └─────────────────────┬───────────────────────────────┘    │
│                        │                                    │
│           ┌────────────┴────────────┐                       │
│           │                         │                       │
│         Cache HIT              Cache MISS                   │
│           │                         │                       │
│           ↓                         ↓                       │
│  Return cached result    ┌─────────────────────────┐        │
│  (no DB query)           │ 2. Query Casbin Enforcer│        │
│                          │    (PostgreSQL lookup)  │        │
│                          └───────────┬─────────────┘        │
│                                      │                      │
│                                      ↓                      │
│                          ┌─────────────────────────┐        │
│                          │ 3. Cache result         │        │
│                          │    TTL: 5 minutes       │        │
│                          └───────────┬─────────────┘        │
│                                      │                      │
│                                      ↓                      │
│                          ┌─────────────────────────┐        │
│                          │ 4. Audit & Return       │        │
│                          └─────────────────────────┘        │ 
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Cache Invalidation

**When to invalidate**:

1. Role assigned to user → Invalidate `authz:{user_id}:*`
2. Role revoked from user → Invalidate `authz:{user_id}:*`
3. Policy changed → Invalidate all `authz:*` (rare operation)

```python
# Cache invalidation pattern
async def invalidate_user_permissions(
    cache: CacheProtocol,
    user_id: UUID,
) -> None:
    """Invalidate all cached permissions for user."""
    pattern = f"authz:{user_id}:*"
    await cache.delete_pattern(pattern)
```

---

## 10. Container Integration

### Authorization Factory

```python
# Addition to src/core/container.py

@lru_cache()
def get_authorization() -> "AuthorizationProtocol":
    """Get authorization singleton (app-scoped).

    Returns CasbinAdapter with:
        - AsyncEnforcer (Casbin) - initialized at FastAPI startup
        - Redis cache (5 min TTL)
        - Audit integration

    Note:
        Enforcer is initialized at startup via lifespan context manager.
        This function retrieves the pre-initialized enforcer.

    Returns:
        Authorization adapter implementing AuthorizationProtocol.

    Raises:
        RuntimeError: If called before FastAPI startup completes.

    Usage:
        # Application Layer (direct use)
        authz = get_authorization()
        allowed = await authz.check_permission(user_id, "accounts", "write")

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        authz: AuthorizationProtocol = Depends(get_authorization)
    """
    from src.infrastructure.authorization.casbin_adapter import CasbinAdapter
    from src.main import get_enforcer  # Get pre-initialized enforcer

    # Get dependencies
    cache = get_cache()
    audit = get_audit()
    logger = get_logger()

    # Get enforcer (initialized at startup)
    enforcer = get_enforcer()

    return CasbinAdapter(
        enforcer=enforcer,
        cache=cache,
        audit=audit,
        logger=logger,
    )
```

---

## 11. Testing Strategy

### Test Pyramid

```text
             ▲
            ╱ ╲
           ╱   ╲ 10% API Tests
          ╱     ╲ - Permission denied flows
         ╱───────╲ - Role-based endpoint access
        ╱         ╲
       ╱           ╲ 30% Integration Tests
      ╱             ╲ - Casbin enforcer
     ╱───────────────╲ - PostgreSQL adapter
    ╱                 ╲ - Cache integration
   ╱                   ╲
  ╱                     ╲ 60% Unit Tests
 ╱                       ╲ - PermissionChecker
╱─────────────────────────╲ - RoleChecker
                            - Cache logic
```

### Test Categories

**Unit Tests** (`tests/unit/`):

- `test_authorization_permission_checker.py` - PermissionChecker logic
- `test_authorization_role_checker.py` - RoleChecker logic
- `test_authorization_cache.py` - Cache key generation, TTL

**Integration Tests** (`tests/integration/`):

- `test_casbin_enforcer.py` - Casbin policy enforcement
- `test_casbin_postgres_adapter.py` - Policy persistence
- `test_authorization_cache_integration.py` - Redis caching

**API Tests** (`tests/api/`):

- `test_authorization_endpoints.py` - Protected endpoint access

---

## 12. File Structure

```text
src/
├── domain/
│   ├── enums/
│   │   ├── user_role.py              # UserRole enum (admin, user, readonly)
│   │   └── permission.py             # Permission enum (accounts:read, etc.)
│   ├── events/
│   │   └── authorization_events.py   # 6 events (3-state for assign/revoke)
│   └── protocols/
│       └── authorization_protocol.py # AuthorizationProtocol
│
├── infrastructure/
│   └── authorization/
│       ├── __init__.py
│       ├── casbin_adapter.py         # CasbinAdapter implementation
│       └── model.conf                # Casbin RBAC model

alembic/
├── seeds/
│   ├── __init__.py                   # run_all_seeders()
│   └── rbac_seeder.py                # Initial RBAC policy seeding
│
├── presentation/
│   └── api/
│       ├── dependencies/
│       │   └── authorization.py      # require_permission, require_role
│       └── v1/
│           └── admin/
│               └── roles.py          # Admin role management endpoints
│
├── core/
│   └── container.py                  # get_authorization() added
│
└── main.py                           # Enforcer initialization at startup

tests/
├── unit/
│   ├── test_authorization_permission_checker.py
│   ├── test_authorization_role_checker.py
│   └── test_authorization_events.py
├── integration/
│   ├── test_casbin_enforcer.py
│   └── test_casbin_postgres_adapter.py
└── api/
    └── test_authorization_endpoints.py
```

---

## 13. Dependencies

### Python Packages

```toml
# pyproject.toml additions
[project.dependencies]
casbin = "^1.43.0"
casbin-async-sqlalchemy-adapter = "^1.0.0"
```

### Infrastructure

- PostgreSQL: Policy storage (existing)
- Redis: Permission caching (existing)

---

## 14. Migration Plan

### Database Schema

Dashtam uses a custom Alembic migration for the `casbin_rule` table (YAGNI: v3-v5 added when needed):

```sql
CREATE TABLE casbin_rule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ptype VARCHAR(255) NOT NULL,
    v0 VARCHAR(255),
    v1 VARCHAR(255),
    v2 VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_casbin_rule_ptype ON casbin_rule(ptype);
CREATE INDEX ix_casbin_rule_v0 ON casbin_rule(v0);
CREATE INDEX ix_casbin_rule_v1 ON casbin_rule(v1);
```

### Initial Policy Seeding

RBAC policies are seeded via `alembic/seeds/rbac_seeder.py` (post-migration hook).

**Seeded data**:

- Role permissions: `readonly`, `user`, `admin` with appropriate resource/action access
- Role hierarchy: `admin` → `user` → `readonly`

**Pattern**: Idempotent seeding with `ON CONFLICT DO NOTHING`. Runs automatically after migrations.

**After seeding**: All role/permission changes managed via admin APIs (properly audited).

> See [Database Seeding Guide](../guides/database-seeding.md) for implementation details.

---

## 15. Security Considerations

### Fail-Closed Design

- Missing policy → Deny access (secure default)
- Cache miss → Query database, then cache result
- Database error → Deny access (log error, alert)

### Audit Trail

- All authorization checks logged (ACCESS_GRANTED/ACCESS_DENIED)
- Role changes logged (ROLE_ASSIGNED/ROLE_REVOKED)
- PCI-DSS compliant (7-year retention)

### JWT Integration

- Roles stored in JWT payload (from F1.1)
- JWT roles synchronized with Casbin on login
- Token rotation doesn't affect role assignments

---

## 16. Future Enhancements

**Phase 2+**:

- Multi-tenant RBAC (domains)
- ABAC (attribute-based conditions)
- Dynamic permission assignment UI
- Resource-level permissions (per-account access)
- Hierarchical resource permissions

---

**Created**: 2025-11-27 | **Last Updated**: 2025-11-27
