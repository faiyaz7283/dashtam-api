"""RefreshTokenRepository - SQLAlchemy implementation for refresh token persistence.

Handles CRUD operations for refresh tokens with automatic expiration checks.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.protocols.refresh_token_repository import RefreshTokenData
from src.infrastructure.persistence.models.refresh_token import RefreshToken


def _to_data(model: RefreshToken) -> RefreshTokenData:
    """Convert database model to domain DTO."""
    return RefreshTokenData(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        session_id=model.session_id,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        last_used_at=model.last_used_at,
        rotation_count=model.rotation_count,
        token_version=model.token_version,
        global_version_at_issuance=model.global_version_at_issuance,
    )


class RefreshTokenRepository:
    """SQLAlchemy implementation for refresh token persistence.

    Manages refresh tokens with support for:
    - Token creation and storage
    - Token validation (hash lookup)
    - Token rotation (delete old, create new)
    - Session-based revocation

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = RefreshTokenRepository(session)
        ...     token = await repo.find_by_token_hash(token_hash)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def save(
        self,
        user_id: UUID,
        token_hash: str,
        session_id: UUID,
        expires_at: datetime,
        *,
        token_version: int = 1,
        global_version_at_issuance: int = 1,
    ) -> RefreshTokenData:
        """Create new refresh token in database.

        Args:
            user_id: User's unique identifier.
            token_hash: Bcrypt hash of the refresh token.
            session_id: Associated session ID.
            expires_at: Token expiration timestamp.
            token_version: Token version at issuance (for breach rotation).
            global_version_at_issuance: Global min version when issued.

        Returns:
            Created RefreshTokenData.
        """
        token_model = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            session_id=session_id,
            expires_at=expires_at,
            token_version=token_version,
            global_version_at_issuance=global_version_at_issuance,
        )
        self.session.add(token_model)
        await self.session.commit()
        await self.session.refresh(token_model)
        return _to_data(token_model)

    async def find_by_token_hash(self, token_hash: str) -> RefreshTokenData | None:
        """Find refresh token by hash.

        Args:
            token_hash: Bcrypt hash of the token.

        Returns:
            RefreshTokenData if found and not revoked, None otherwise.
        """
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .where(RefreshToken.revoked_at.is_(None))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_data(model) if model else None

    async def find_by_id(self, token_id: UUID) -> RefreshTokenData | None:
        """Find refresh token by ID.

        Args:
            token_id: Token's unique identifier.

        Returns:
            RefreshTokenData if found, None otherwise.
        """
        stmt = select(RefreshToken).where(RefreshToken.id == token_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_data(model) if model else None

    async def update_last_used(self, token_id: UUID) -> None:
        """Update last_used_at timestamp.

        Args:
            token_id: Token's unique identifier.
        """
        stmt = select(RefreshToken).where(RefreshToken.id == token_id)
        result = await self.session.execute(stmt)
        token = result.scalar_one()

        token.last_used_at = datetime.now(UTC)
        await self.session.commit()

    async def delete(self, token_id: UUID) -> None:
        """Delete refresh token (for rotation).

        Args:
            token_id: Token's unique identifier.
        """
        stmt = select(RefreshToken).where(RefreshToken.id == token_id)
        result = await self.session.execute(stmt)
        token = result.scalar_one()

        await self.session.delete(token)
        await self.session.commit()

    async def revoke_by_session(self, session_id: UUID) -> None:
        """Revoke all refresh tokens for a session.

        Args:
            session_id: Session ID to revoke tokens for.
        """
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.session_id == session_id)
            .where(RefreshToken.revoked_at.is_(None))
        )
        result = await self.session.execute(stmt)
        tokens = result.scalars().all()

        for token in tokens:
            token.revoked_at = datetime.now(UTC)
            token.revoked_reason = "session_revoked"

        await self.session.commit()

    async def revoke_all_for_user(
        self,
        user_id: UUID,
        reason: str = "user_requested",
    ) -> None:
        """Revoke all refresh tokens for a user.

        Used when password changes or user logs out of all devices.

        Args:
            user_id: User's unique identifier.
            reason: Reason for revocation (for audit).
        """
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
        )
        result = await self.session.execute(stmt)
        tokens = result.scalars().all()

        for token in tokens:
            token.revoked_at = datetime.now(UTC)
            token.revoked_reason = reason

        await self.session.commit()

    async def find_by_token_verification(
        self,
        token: str,
        verify_fn: Callable[[str, str], bool],
    ) -> RefreshTokenData | None:
        """Find refresh token by verifying against stored hashes.

        Since bcrypt hashes are non-deterministic, we iterate through active
        tokens and verify each one against the provided token.

        Args:
            token: Plain refresh token from user request.
            verify_fn: Function to verify token against hash (token, hash) -> bool.

        Returns:
            RefreshTokenData if found and verified, None otherwise.
        """
        # Get all active (non-revoked) tokens
        stmt = select(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        result = await self.session.execute(stmt)
        tokens = result.scalars().all()

        # Verify each token against the provided token
        for token_model in tokens:
            if verify_fn(token, token_model.token_hash):
                return _to_data(token_model)

        return None
