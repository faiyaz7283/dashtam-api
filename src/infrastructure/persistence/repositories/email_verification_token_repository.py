"""EmailVerificationTokenRepository - SQLAlchemy implementation for email verification token persistence.

Handles CRUD operations for email verification tokens with expiration checks.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.protocols.email_verification_token_repository import (
    EmailVerificationTokenData,
)
from src.infrastructure.persistence.models.email_verification_token import (
    EmailVerificationToken,
)


def _to_data(model: EmailVerificationToken) -> EmailVerificationTokenData:
    """Convert database model to domain DTO."""
    return EmailVerificationTokenData(
        id=model.id,
        user_id=model.user_id,
        token=model.token,
        expires_at=model.expires_at,
        used_at=model.used_at,
    )


class EmailVerificationTokenRepository:
    """SQLAlchemy implementation for email verification token persistence.

    Manages email verification tokens with support for:
    - Token creation and storage
    - Token validation (lookup by token string)
    - One-time use enforcement (mark as used)

    Attributes:
        session: SQLAlchemy async session for database operations.

    Example:
        >>> async with get_session() as session:
        ...     repo = EmailVerificationTokenRepository(session)
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
    ) -> EmailVerificationTokenData:
        """Create new email verification token in database.

        Args:
            user_id: User's unique identifier.
            token: Random hex token (64 characters).
            expires_at: Token expiration timestamp (24 hours).

        Returns:
            Created EmailVerificationTokenData.
        """
        token_model = EmailVerificationToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )
        self.session.add(token_model)
        await self.session.commit()
        await self.session.refresh(token_model)
        return _to_data(token_model)

    async def find_by_token(self, token: str) -> EmailVerificationTokenData | None:
        """Find email verification token by token string.

        Args:
            token: The verification token string.

        Returns:
            EmailVerificationTokenData if found and not used, None otherwise.
        """
        stmt = (
            select(EmailVerificationToken)
            .where(EmailVerificationToken.token == token)
            .where(EmailVerificationToken.used_at.is_(None))
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return _to_data(model) if model else None

    async def mark_as_used(self, token_id: UUID) -> None:
        """Mark email verification token as used.

        Args:
            token_id: Token's unique identifier.
        """
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.id == token_id
        )
        result = await self.session.execute(stmt)
        token = result.scalar_one()

        token.used_at = datetime.now(UTC)
        await self.session.commit()

    async def delete_expired_tokens(self) -> int:
        """Delete expired email verification tokens.

        Cleanup task to remove old tokens (typically run daily).

        Returns:
            Number of tokens deleted.
        """
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.expires_at < datetime.now(UTC)
        )
        result = await self.session.execute(stmt)
        tokens = result.scalars().all()

        count = len(tokens)
        for token in tokens:
            await self.session.delete(token)

        await self.session.commit()
        return count

    async def find_by_user_id(self, user_id: UUID) -> list[EmailVerificationTokenData]:
        """Find all email verification tokens for a user.

        Useful for debugging or admin views.

        Args:
            user_id: User's unique identifier.

        Returns:
            List of EmailVerificationTokenData.
        """
        stmt = (
            select(EmailVerificationToken)
            .where(EmailVerificationToken.user_id == user_id)
            .order_by(EmailVerificationToken.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [_to_data(model) for model in result.scalars().all()]
