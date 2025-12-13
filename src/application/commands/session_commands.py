"""Session management commands (CQRS write operations).

Commands represent user intent to change session state.
All commands are immutable (frozen=True) and use keyword-only arguments (kw_only=True).

Pattern:
- Commands are data containers (no logic)
- Handlers execute business logic
- Commands don't return values (handlers return Result types)
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class CreateSession:
    """Create a new session for a user.

    Called during login to create session with device/location metadata.
    Enforces session limits per user tier.

    Attributes:
        user_id: User identifier.
        ip_address: Client IP address (for geolocation, audit).
        user_agent: Client user agent (for device parsing).
        expires_at: When session expires (matches refresh token).
        refresh_token_id: Associated refresh token ID (optional, set after token created).

    Example:
        >>> command = CreateSession(
        ...     user_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        ...     ip_address="192.168.1.1",
        ...     user_agent="Mozilla/5.0...",
        ...     expires_at=datetime.now(UTC) + timedelta(days=30),
        ... )
        >>> result = await handler.handle(command)
    """

    user_id: UUID
    ip_address: str | None = None
    user_agent: str | None = None
    expires_at: datetime | None = None
    refresh_token_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class RevokeSession:
    """Revoke a specific session.

    Called on logout or when user manually revokes a session.
    Soft-deletes session (marks as revoked, keeps for audit).

    Attributes:
        session_id: Session identifier to revoke.
        user_id: User identifier (for authorization check).
        reason: Revocation reason for audit (logout, manual, suspicious, etc.).

    Example:
        >>> command = RevokeSession(
        ...     session_id=UUID("abc123..."),
        ...     user_id=UUID("123e4567..."),
        ...     reason="logout",
        ... )
        >>> result = await handler.handle(command)
    """

    session_id: UUID
    user_id: UUID
    reason: str = "logout"


@dataclass(frozen=True, kw_only=True)
class RevokeAllUserSessions:
    """Revoke all sessions for a user.

    Called on password change, security event, or user-initiated "logout everywhere".
    Can optionally exclude current session.

    Attributes:
        user_id: User identifier.
        reason: Revocation reason for audit.
        except_session_id: Session ID to exclude (current session).

    Example:
        >>> command = RevokeAllUserSessions(
        ...     user_id=UUID("123e4567..."),
        ...     reason="password_change",
        ...     except_session_id=current_session_id,
        ... )
        >>> result = await handler.handle(command)
    """

    user_id: UUID
    reason: str
    except_session_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class UpdateSessionActivity:
    """Update session's last activity timestamp.

    Called on each authenticated request to track activity.
    Lightweight operation - updates cache and database.

    Attributes:
        session_id: Session identifier.
        ip_address: Current client IP (for detecting IP changes).

    Example:
        >>> command = UpdateSessionActivity(
        ...     session_id=UUID("abc123..."),
        ...     ip_address="192.168.1.100",
        ... )
        >>> await handler.handle(command)
    """

    session_id: UUID
    ip_address: str | None = None


@dataclass(frozen=True, kw_only=True)
class RecordProviderAccess:
    """Record provider access in session.

    Called when user accesses a financial provider (Schwab, etc.).
    Tracks which providers accessed per session for audit.

    Attributes:
        session_id: Session identifier.
        provider_name: Name of provider accessed.

    Example:
        >>> command = RecordProviderAccess(
        ...     session_id=UUID("abc123..."),
        ...     provider_name="schwab",
        ... )
        >>> await handler.handle(command)
    """

    session_id: UUID
    provider_name: str


@dataclass(frozen=True, kw_only=True)
class LinkRefreshTokenToSession:
    """Link a refresh token to a session.

    Called after refresh token is created to establish the relationship.

    Attributes:
        session_id: Session identifier.
        refresh_token_id: Refresh token identifier.

    Example:
        >>> command = LinkRefreshTokenToSession(
        ...     session_id=UUID("abc123..."),
        ...     refresh_token_id=UUID("def456..."),
        ... )
        >>> await handler.handle(command)
    """

    session_id: UUID
    refresh_token_id: UUID
