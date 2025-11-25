"""PasswordResetTokenRepository protocol (port) for domain layer.

This protocol defines the interface for password reset token persistence
that the domain layer needs. Infrastructure provides concrete implementations.

Following hexagonal architecture:
- Domain defines what it needs (protocol/port)
- Infrastructure provides implementation (adapter)
- Domain has no knowledge of how tokens are stored

Reference:
    - docs/architecture/authentication-architecture.md (Password Reset Flow)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass
class PasswordResetTokenData:
    """Data transfer object for password reset token information.

    Used by protocol methods to return token data without
    exposing infrastructure model classes to domain/application layers.
    """

    id: UUID
    user_id: UUID
    token: str
    expires_at: datetime
    used_at: datetime | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class PasswordResetTokenRepository(Protocol):
    """Protocol for password reset token persistence operations.

    Defines the contract that all password reset token repository
    implementations must satisfy. Used for password reset flow
    with rate limiting and audit trail.

    Token Lifecycle:
        1. Created during password reset request (15-minute expiration)
        2. Validated during password reset confirmation
        3. Marked as used after successful password change
        4. Rate limiting: Max 3 requests per hour per user

    Implementations:
        - PasswordResetTokenRepository (SQLAlchemy): src/infrastructure/persistence/repositories/
    """

    async def save(
        self,
        user_id: UUID,
        token: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> PasswordResetTokenData:
        """Create new password reset token.

        Args:
            user_id: User's unique identifier.
            token: Random hex token (64 characters, 32 bytes).
            expires_at: Token expiration timestamp (typically 15 minutes from now).
            ip_address: IP address of requester (for audit/abuse detection).
            user_agent: User agent of requester (for audit/abuse detection).

        Returns:
            Created PasswordResetToken model.
        """
        ...

    async def find_by_token(self, token: str) -> PasswordResetTokenData | None:
        """Find password reset token by token string.

        Only returns tokens that have NOT been used (used_at IS NULL).
        Does NOT check expiration - caller must verify expires_at.

        Args:
            token: The password reset token string (64-char hex).

        Returns:
            PasswordResetToken if found and not used, None otherwise.
        """
        ...

    async def mark_as_used(self, token_id: UUID) -> None:
        """Mark password reset token as used.

        Sets used_at to current timestamp. Ensures token cannot be reused.

        Args:
            token_id: Token's unique identifier.

        Raises:
            NoResultFound: If token with given ID doesn't exist.
        """
        ...

    async def delete_expired_tokens(self) -> int:
        """Delete expired password reset tokens.

        Cleanup task to remove old tokens (typically run hourly via cron).
        Deletes tokens where expires_at < current timestamp.

        Returns:
            Number of tokens deleted.
        """
        ...

    async def find_by_user_id(self, user_id: UUID) -> list[PasswordResetTokenData]:
        """Find all password reset tokens for a user.

        Useful for debugging, admin views, or detecting abuse patterns.
        Returns all tokens (used and unused) ordered by creation date (newest first).

        Args:
            user_id: User's unique identifier.

        Returns:
            List of PasswordResetToken models (may be empty).
        """
        ...

    async def count_recent_requests(
        self,
        user_id: UUID,
        since: datetime,
    ) -> int:
        """Count password reset requests since a given time.

        Used for rate limiting (e.g., max 3 requests per hour).

        Args:
            user_id: User's unique identifier.
            since: Start time for counting (e.g., 1 hour ago).

        Returns:
            Number of reset requests since the given time.

        Example:
            >>> from datetime import datetime, timedelta, UTC
            >>> one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
            >>> count = await repo.count_recent_requests(user_id, one_hour_ago)
            >>> if count >= 3:
            ...     raise RateLimitError("Too many password reset requests")
        """
        ...
