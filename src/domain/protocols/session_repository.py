"""Session repository protocol for persistence abstraction.

This module defines the port (interface) for session persistence.
Infrastructure layer implements the adapter.

Reference:
    - docs/architecture/session-management-architecture.md
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(slots=True, kw_only=True)
class SessionData:
    """Data transfer object for session persistence.

    Used to transfer session data between domain and infrastructure layers.
    Decouples the Session entity from database models.

    All fields are optional except identity fields (id, user_id)
    to support partial updates.

    Attributes:
        id: Session identifier.
        user_id: User who owns this session.
        device_info: Parsed device info.
        user_agent: Full user agent string.
        ip_address: Client IP at creation.
        location: Geographic location.
        created_at: When session was created.
        last_activity_at: Last activity timestamp.
        expires_at: When session expires.
        is_revoked: Whether session is revoked.
        is_trusted: Whether device is trusted.
        revoked_at: When session was revoked.
        revoked_reason: Why session was revoked.
        refresh_token_id: Associated refresh token.
        last_ip_address: Most recent IP.
        suspicious_activity_count: Security event counter.
        last_provider_accessed: Last provider accessed.
        last_provider_sync_at: Last provider sync time.
        providers_accessed: List of providers accessed.
    """

    id: UUID
    user_id: UUID
    device_info: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    location: str | None = None
    created_at: datetime | None = None
    last_activity_at: datetime | None = None
    expires_at: datetime | None = None
    is_revoked: bool = False
    is_trusted: bool = False
    revoked_at: datetime | None = None
    revoked_reason: str | None = None
    refresh_token_id: UUID | None = None
    last_ip_address: str | None = None
    suspicious_activity_count: int = 0
    last_provider_accessed: str | None = None
    last_provider_sync_at: datetime | None = None
    providers_accessed: list[str] | None = None


class SessionRepository(Protocol):
    """Session repository protocol (port) for persistence.

    Defines the interface for session storage operations.
    Infrastructure layer provides the adapter implementation.

    This follows hexagonal architecture: domain defines ports,
    infrastructure implements adapters.

    Example:
        >>> class PostgresSessionRepository:
        ...     async def save(self, session_data: SessionData) -> None:
        ...         # Store in PostgreSQL
        ...         ...
        ...
        >>> # PostgresSessionRepository implements SessionRepository
        >>> # via structural typing (no inheritance needed)
    """

    async def save(self, session_data: SessionData) -> None:
        """Save or update a session.

        Creates new session if it doesn't exist, updates if it does.

        Args:
            session_data: Session data to persist.
        """
        ...

    async def find_by_id(self, session_id: UUID) -> SessionData | None:
        """Find session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            SessionData if found, None otherwise.
        """
        ...

    async def find_by_user_id(
        self,
        user_id: UUID,
        *,
        active_only: bool = False,
    ) -> list[SessionData]:
        """Find all sessions for a user.

        Args:
            user_id: User identifier.
            active_only: If True, only return active (non-revoked, non-expired) sessions.

        Returns:
            List of session data, empty if none found.
        """
        ...

    async def find_by_refresh_token_id(
        self,
        refresh_token_id: UUID,
    ) -> SessionData | None:
        """Find session by refresh token ID.

        Used during token refresh to locate associated session.

        Args:
            refresh_token_id: Refresh token identifier.

        Returns:
            SessionData if found, None otherwise.
        """
        ...

    async def count_active_sessions(self, user_id: UUID) -> int:
        """Count active sessions for a user.

        Used to enforce session limits.

        Args:
            user_id: User identifier.

        Returns:
            Number of active sessions.
        """
        ...

    async def delete(self, session_id: UUID) -> bool:
        """Delete a session (hard delete).

        Args:
            session_id: Session identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def delete_all_for_user(self, user_id: UUID) -> int:
        """Delete all sessions for a user (hard delete).

        Used during account deletion or security reset.

        Args:
            user_id: User identifier.

        Returns:
            Number of sessions deleted.
        """
        ...

    async def revoke_all_for_user(
        self,
        user_id: UUID,
        reason: str,
        *,
        except_session_id: UUID | None = None,
    ) -> int:
        """Revoke all sessions for a user (soft delete).

        Used during password change or security event.
        Optionally excludes the current session.

        Args:
            user_id: User identifier.
            reason: Revocation reason for audit.
            except_session_id: Session ID to exclude (e.g., current session).

        Returns:
            Number of sessions revoked.
        """
        ...

    async def get_oldest_active_session(
        self,
        user_id: UUID,
    ) -> SessionData | None:
        """Get the oldest active session for a user.

        Used when enforcing session limits (FIFO eviction).

        Args:
            user_id: User identifier.

        Returns:
            Oldest active session data, None if no active sessions.
        """
        ...

    async def cleanup_expired_sessions(
        self,
        *,
        before: datetime | None = None,
    ) -> int:
        """Clean up expired sessions (batch operation).

        Called by scheduled job to remove old sessions.

        Args:
            before: Delete sessions expired before this time.
                   Defaults to now.

        Returns:
            Number of sessions cleaned up.
        """
        ...
