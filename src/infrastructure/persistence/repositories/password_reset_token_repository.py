"""PasswordResetTokenRepository - SQLAlchemy implementation for password reset token persistence.

Handles CRUD operations for password reset tokens with expiration checks.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.protocols.password_reset_token_repository import (
    PasswordResetTokenData,
)
from src.infrastructure.persistence.models.password_reset_token import (
    PasswordResetToken,
)


def _to_data(model: PasswordResetToken) -> PasswordResetTokenData:
    """Convert database model to domain DTO."""
    return PasswordResetTokenData(
        id=model.id,
        user_id=model.user_id,
        token=model.token,
        expires_at=model.expires_at,
        used_at=model.used_at,
        ip_address=model.ip_address,
        user_agent=model.user_agent,
        created_at=model.created_at,
    )


class PasswordResetTokenRepository:
    """SQLAlchemy implementation for password reset token persistence.

    Manages password reset tokens with support for:
    - Token creation and storage
    - Token validation (lookup by token string)
    - One-time use enforcement (mark as used)
    - IP address and user agent tracking

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = PasswordResetTokenRepository(session)
        ...     token = await repo.find_by_token("abc123...")
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
        token: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> PasswordResetTokenData:
        """Create new password reset token in database.

        Args:
            user_id: User's unique identifier.
            token: Random hex token (64 characters).
            expires_at: Token expiration timestamp (15 minutes).
            ip_address: IP address of requester (for audit).
            user_agent: User agent of requester (for audit).

        Returns:
            Created PasswordResetTokenData.
        """
        token_model = PasswordResetToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(token_model)
        await self.session.commit()
        await self.session.refresh(token_model)
        return _to_data(token_model)

    async def find_by_token(self, token: str) -> PasswordResetTokenData | None:
        """Find password reset token by token string.

        Args:
            token: The reset token string.

        Returns:
            PasswordResetTokenData if found and not used, None otherwise.
        """
        stmt = (
            select(PasswordResetToken)
            .where(PasswordResetToken.token == token)
            .where(PasswordResetToken.used_at.is_(None))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_data(model) if model else None

    async def mark_as_used(self, token_id: UUID) -> None:
        """Mark password reset token as used.

        Args:
            token_id: Token's unique identifier.
        """
        stmt = select(PasswordResetToken).where(PasswordResetToken.id == token_id)
        result = await self.session.execute(stmt)
        token = result.scalar_one()

        token.used_at = datetime.now(UTC)
        await self.session.commit()

    async def delete_expired_tokens(self) -> int:
        """Delete expired password reset tokens.

        Cleanup task to remove old tokens (typically run hourly).

        Returns:
            Number of tokens deleted.
        """
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.expires_at < datetime.now(UTC)
        )
        result = await self.session.execute(stmt)
        tokens = result.scalars().all()

        count = len(tokens)
        for token in tokens:
            await self.session.delete(token)

        await self.session.commit()
        return count

    async def find_by_user_id(self, user_id: UUID) -> list[PasswordResetTokenData]:
        """Find all password reset tokens for a user.

        Useful for debugging, admin views, or detecting abuse.

        Args:
            user_id: User's unique identifier.

        Returns:
            List of PasswordResetTokenData.
        """
        stmt = (
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id)
            .order_by(PasswordResetToken.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [_to_data(model) for model in result.scalars().all()]

    async def count_recent_requests(
        self,
        user_id: UUID,
        since: datetime,
    ) -> int:
        """Count password reset requests since a given time.

        Used for rate limiting (e.g., max 3 requests per hour).

        Args:
            user_id: User's unique identifier.
            since: Start time for counting.

        Returns:
            Number of reset requests since the given time.
        """
        stmt = (
            select(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id)
            .where(PasswordResetToken.created_at >= since)
        )
        result = await self.session.execute(stmt)
        tokens = result.scalars().all()
        return len(tokens)
