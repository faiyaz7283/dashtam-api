"""Authorization domain events.

Pattern: 3 events per workflow (ATTEMPTED → SUCCEEDED/FAILED)
- *Attempted: Operation initiated (before business logic)
- *Succeeded: Operation completed successfully (after commit)
- *Failed: Operation failed (validation/commit failure)

Handlers:
- LoggingEventHandler: ALL 3 events
- AuditEventHandler: ALL 3 events
- CacheInvalidationHandler: SUCCEEDED only (invalidate authz:* cache)

Reference:
    - docs/architecture/authorization-architecture.md
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.events.base_event import DomainEvent


# ═══════════════════════════════════════════════════════════════
# Role Assignment (Workflow 1)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class RoleAssignmentAttempted(DomainEvent):
    """Role assignment attempt initiated.

    Emitted BEFORE attempting to assign a role.
    Records the attempt for audit trail, even if assignment fails.

    Triggers:
    - LoggingEventHandler: Log attempt at INFO level
    - AuditEventHandler: Record ROLE_ASSIGNMENT_ATTEMPTED

    Attributes:
        user_id: ID of user to receive role.
        role: Role being assigned (admin, user, readonly).
        assigned_by: ID of user performing the assignment.
    """

    user_id: UUID
    role: str
    assigned_by: UUID


@dataclass(frozen=True, kw_only=True)
class RoleAssignmentSucceeded(DomainEvent):
    """Role assignment completed successfully.

    Emitted AFTER role successfully assigned and committed.
    Triggers cache invalidation and notifications.

    Triggers:
    - LoggingEventHandler: Log success at INFO level
    - AuditEventHandler: Record ROLE_ASSIGNED
    - CacheInvalidationHandler: Invalidate authz:{user_id}:* cache

    Attributes:
        user_id: ID of user who received role.
        role: Role that was assigned.
        assigned_by: ID of user who performed the assignment.
    """

    user_id: UUID
    role: str
    assigned_by: UUID


@dataclass(frozen=True, kw_only=True)
class RoleAssignmentFailed(DomainEvent):
    """Role assignment failed.

    Emitted when role assignment fails (validation, already has role, etc.).
    Captures failure reason for audit and alerting.

    Triggers:
    - LoggingEventHandler: Log failure at WARNING level
    - AuditEventHandler: Record ROLE_ASSIGNMENT_FAILED

    Attributes:
        user_id: ID of user targeted for role.
        role: Role that was attempted.
        assigned_by: ID of user who attempted assignment.
        reason: Why assignment failed (e.g., "user_not_found", "already_has_role").
    """

    user_id: UUID
    role: str
    assigned_by: UUID
    reason: str


# ═══════════════════════════════════════════════════════════════
# Role Revocation (Workflow 2)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class RoleRevocationAttempted(DomainEvent):
    """Role revocation attempt initiated.

    Emitted BEFORE attempting to revoke a role.
    Records the attempt for audit trail, even if revocation fails.

    Triggers:
    - LoggingEventHandler: Log attempt at INFO level
    - AuditEventHandler: Record ROLE_REVOCATION_ATTEMPTED

    Attributes:
        user_id: ID of user to lose role.
        role: Role being revoked (admin, user, readonly).
        revoked_by: ID of user performing the revocation.
        reason: Optional reason for revocation (for audit).
    """

    user_id: UUID
    role: str
    revoked_by: UUID
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class RoleRevocationSucceeded(DomainEvent):
    """Role revocation completed successfully.

    Emitted AFTER role successfully revoked and committed.
    Triggers cache invalidation and may revoke sessions.

    Triggers:
    - LoggingEventHandler: Log success at INFO level
    - AuditEventHandler: Record ROLE_REVOKED
    - CacheInvalidationHandler: Invalidate authz:{user_id}:* cache
    - SessionRevocationHandler: May revoke sessions if admin role removed

    Attributes:
        user_id: ID of user who lost role.
        role: Role that was revoked.
        revoked_by: ID of user who performed the revocation.
        reason: Optional reason for revocation.
    """

    user_id: UUID
    role: str
    revoked_by: UUID
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class RoleRevocationFailed(DomainEvent):
    """Role revocation failed.

    Emitted when role revocation fails (user doesn't have role, etc.).
    Captures failure reason for audit and alerting.

    Triggers:
    - LoggingEventHandler: Log failure at WARNING level
    - AuditEventHandler: Record ROLE_REVOCATION_FAILED

    Attributes:
        user_id: ID of user targeted for revocation.
        role: Role that was attempted to revoke.
        revoked_by: ID of user who attempted revocation.
        reason: Why revocation failed (e.g., "user_not_found", "does_not_have_role").
    """

    user_id: UUID
    role: str
    revoked_by: UUID
    reason: str
