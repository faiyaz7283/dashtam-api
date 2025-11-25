"""EmailVerificationTokenRepository protocol (port) for domain layer.

This protocol defines the interface for email verification token persistence
that the domain layer needs. Infrastructure provides concrete implementations.

Following hexagonal architecture:
- Domain defines what it needs (protocol/port)
- Infrastructure provides implementation (adapter)
- Domain has no knowledge of how tokens are stored

Reference:
    - docs/architecture/authentication-architecture.md (Lines 307-336)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass
class EmailVerificationTokenData:
    """Data transfer object for email verification token information.

    Used by protocol methods to return token data without
    exposing infrastructure model classes to domain/application layers.
    """

    id: UUID
    user_id: UUID
    token: str
    expires_at: datetime
    used_at: datetime | None


class EmailVerificationTokenRepository(Protocol):
    """Protocol for email verification token persistence operations.

    Defines the contract that all email verification token repository
    implementations must satisfy. Used for email verification flow
    during user registration.

    Token Lifecycle:
        1. Created during registration (24-hour expiration)
        2. Validated during email verification
        3. Marked as used after successful verification
        4. Expired tokens cleaned up periodically

    Implementations:
        - EmailVerificationTokenRepository (SQLAlchemy): src/infrastructure/persistence/repositories/
    """

    async def save(
        self,
        user_id: UUID,
        token: str,
        expires_at: datetime,
    ) -> EmailVerificationTokenData:
        """Create new email verification token.

        Args:
            user_id: User's unique identifier.
            token: Random hex token (64 characters, 32 bytes).
            expires_at: Token expiration timestamp (typically 24 hours from now).

        Returns:
            Created EmailVerificationTokenData.
        """
        ...

    async def find_by_token(self, token: str) -> EmailVerificationTokenData | None:
        """Find email verification token by token string.

        Only returns tokens that have NOT been used (used_at IS NULL).
        Does NOT check expiration - caller must verify expires_at.

        Args:
            token: The verification token string (64-char hex).

        Returns:
            EmailVerificationTokenData if found and not used, None otherwise.
        """
        ...

    async def mark_as_used(self, token_id: UUID) -> None:
        """Mark email verification token as used.

        Sets used_at to current timestamp. Ensures token cannot be reused.

        Args:
            token_id: Token's unique identifier.

        Raises:
            NoResultFound: If token with given ID doesn't exist.

        Example:
            >>> token = await repo.find_by_token("abc123...")
            >>> await repo.mark_as_used(token.id)
            >>> # Token now has used_at set, won't be returned by find_by_token
        """
        ...

    async def delete_expired_tokens(self) -> int:
        """Delete expired email verification tokens.

        Cleanup task to remove old tokens (typically run daily via cron).
        Deletes tokens where expires_at < current timestamp.

        Returns:
            Number of tokens deleted.

        Example:
            >>> # Run as daily cleanup task
            >>> deleted_count = await repo.delete_expired_tokens()
            >>> logger.info(f"Deleted {deleted_count} expired verification tokens")
        """
        ...

    async def find_by_user_id(self, user_id: UUID) -> list[EmailVerificationTokenData]:
        """Find all email verification tokens for a user.

        Useful for debugging or admin views. Returns all tokens
        (used and unused) ordered by creation date (newest first).

        Args:
            user_id: User's unique identifier.

        Returns:
            List of EmailVerificationTokenData (may be empty).
        """
        ...
