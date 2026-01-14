"""Token rotation commands (CQRS write operations).

Commands for triggering token breach rotation - invalidating tokens
by incrementing version requirements.

Pattern:
- Commands are data containers (no logic)
- Handlers execute business logic
- Commands don't return values (handlers return Result types)
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class TriggerGlobalTokenRotation:
    """Trigger global token rotation (invalidate ALL tokens below version).

    Admin-only operation. Increments global_min_token_version, which
    causes all existing refresh tokens to fail validation on next use.

    Use cases:
    - Database breach detected
    - Security vulnerability in token generation
    - Compliance requirement (periodic rotation)

    Attributes:
        triggered_by: ID of admin user triggering rotation (for audit).
        reason: Human-readable reason for rotation (for audit).

    Example:
        >>> command = TriggerGlobalTokenRotation(
        ...     triggered_by="admin-user-123",
        ...     reason="Database breach detected",
        ... )
        >>> result = await handler.handle(command)
    """

    triggered_by: str  # Admin user ID or "system"
    reason: str


@dataclass(frozen=True, kw_only=True)
class TriggerUserTokenRotation:
    """Trigger per-user token rotation (invalidate user's tokens below version).

    Increments user.min_token_version, which causes only that user's
    existing refresh tokens to fail validation on next use.

    Use cases:
    - Password change (automatic)
    - "Log out everywhere" user action
    - Admin action (suspicious activity)

    Attributes:
        user_id: User whose tokens to rotate.
        triggered_by: Who triggered rotation (user_id, admin_id, or "system").
        reason: Human-readable reason for rotation (for audit).

    Example:
        >>> command = TriggerUserTokenRotation(
        ...     user_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        ...     triggered_by="user",
        ...     reason="password_changed",
        ... )
        >>> result = await handler.handle(command)
    """

    user_id: UUID
    triggered_by: str  # "user", admin ID, or "system"
    reason: str
