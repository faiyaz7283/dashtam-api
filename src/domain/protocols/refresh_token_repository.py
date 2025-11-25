"""RefreshTokenRepository protocol (port) for domain layer.

This protocol defines the interface for refresh token persistence that the
domain layer needs. Infrastructure provides concrete implementations.

Following hexagonal architecture:
- Domain defines what it needs (protocol/port)
- Infrastructure provides implementation (adapter)
- Domain has no knowledge of how tokens are stored

Reference:
    - docs/architecture/authentication-architecture.md (Lines 174-233)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass
class RefreshTokenData:
    """Data transfer object for refresh token information.

    Used by protocol methods to return token data without
    exposing infrastructure model classes to domain/application layers.
    """

    id: UUID
    user_id: UUID
    token_hash: str
    session_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None
    rotation_count: int


class RefreshTokenRepository(Protocol):
    """Protocol for refresh token persistence operations.

    Defines the contract that all refresh token repository implementations
    must satisfy. Used for token rotation and session management.

    Token Lifecycle:
        1. Created during login (30-day expiration)
        2. Validated during token refresh
        3. Rotated on every refresh (old deleted, new created)
        4. Revoked when session ends or password changes

    Implementations:
        - RefreshTokenRepository (SQLAlchemy): src/infrastructure/persistence/repositories/
    """

    async def save(
        self,
        user_id: UUID,
        token_hash: str,
        session_id: UUID,
        expires_at: datetime,
    ) -> RefreshTokenData:
        """Create new refresh token.

        Args:
            user_id: User's unique identifier.
            token_hash: Bcrypt hash of the refresh token (never store plaintext).
            session_id: Associated session ID (F1.3 integration).
            expires_at: Token expiration timestamp (typically 30 days from now).

        Returns:
            Created RefreshTokenData with token info.
        """
        ...

    async def find_by_token_hash(self, token_hash: str) -> RefreshTokenData | None:
        """Find refresh token by hash.

        Only returns tokens that have NOT been revoked (revoked_at IS NULL).
        Does NOT check expiration - caller must verify expires_at.

        Args:
            token_hash: Bcrypt hash of the token to find.

        Returns:
            RefreshTokenData if found and not revoked, None otherwise.
        """
        ...

    async def find_by_id(self, token_id: UUID) -> RefreshTokenData | None:
        """Find refresh token by ID.

        Args:
            token_id: Token's unique identifier.

        Returns:
            RefreshTokenData if found, None otherwise.
        """
        ...

    async def update_last_used(self, token_id: UUID) -> None:
        """Update last_used_at timestamp.

        Tracks token usage for analytics and security monitoring.

        Args:
            token_id: Token's unique identifier.

        Raises:
            NoResultFound: If token with given ID doesn't exist.
        """
        ...

    async def delete(self, token_id: UUID) -> None:
        """Delete refresh token (for rotation).

        Used during token rotation: delete old token, create new one.

        Args:
            token_id: Token's unique identifier.

        Raises:
            NoResultFound: If token with given ID doesn't exist.
        """
        ...

    async def revoke_by_session(self, session_id: UUID) -> None:
        """Revoke all refresh tokens for a session.

        Called when session is explicitly logged out.

        Args:
            session_id: Session ID to revoke tokens for.
        """
        ...

    async def revoke_all_for_user(
        self,
        user_id: UUID,
        reason: str = "user_requested",
    ) -> None:
        """Revoke all refresh tokens for a user.

        Used when password changes (security) or user logs out of all devices.

        Args:
            user_id: User's unique identifier.
            reason: Reason for revocation (for audit trail).
                Common values: "password_changed", "user_requested", "admin_action"
        """
        ...
