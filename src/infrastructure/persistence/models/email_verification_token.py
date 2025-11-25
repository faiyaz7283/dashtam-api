"""Email verification token database model for authentication.

This module defines the EmailVerificationToken model for email verification.

Security:
    - token: Random 32-byte hex string (unguessable, 2^256 possibilities)
    - expires_at: 24 hours from creation (balance security vs UX)
    - used_at: One-time use (marked as used after verification)
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseModel


class EmailVerificationToken(BaseModel):
    """Email verification token model for user registration.

    Stores one-time use tokens sent to users for email verification.
    Tokens are short-lived (24 hours) and must be marked as used after
    verification to prevent reuse.

    Token Lifecycle:
        1. Created on user registration
        2. Sent to user's email (via event handler)
        3. User clicks verification link
        4. Token validated and marked as used (used_at set)
        5. User.is_verified set to True

    Security Features:
        - Random 32-byte hex string (unguessable)
        - Short-lived (24 hours expiration)
        - One-time use (used_at timestamp)
        - Automatic cleanup of expired tokens

    Fields:
        id: UUID primary key (from BaseModel)
        created_at: Timestamp when token created (from BaseModel)
        user_id: Foreign key to users table (cascade delete)
        token: Random hex string (64 characters, unique, indexed)
        expires_at: Timestamp when token expires (24 hours from creation)
        used_at: Timestamp when token was used (nullable, one-time use)

    Indexes:
        - idx_email_verification_user_id: (user_id) for user's tokens
        - idx_email_verification_token: (token) for lookup (unique)
        - idx_email_verification_cleanup: (expires_at, used_at) for cleanup

    Foreign Keys:
        - user_id: References users(id) ON DELETE CASCADE

    Note:
        This model inherits from BaseModel (NOT BaseMutableModel) because
        verification tokens are immutable (only used_at is set once).

    Example:
        # Create verification token (via repository)
        token = EmailVerificationToken(
            user_id=user_id,
            token=secrets.token_hex(32),  # 64-char hex string
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        session.add(token)
        await session.commit()

        # Query token (verification)
        result = await session.execute(
            select(EmailVerificationToken)
            .where(EmailVerificationToken.token == token_str)
            .where(EmailVerificationToken.used_at.is_(None))
            .where(EmailVerificationToken.expires_at > datetime.now(UTC))
        )
        token = result.scalar_one_or_none()
    """

    __tablename__ = "email_verification_tokens"

    # User relationship (cascade delete when user deleted)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who needs to verify their email",
    )

    # Token (random 32-byte hex string, unique, indexed for lookup)
    token: Mapped[str] = mapped_column(
        String(64),  # 32 bytes = 64 hex characters
        nullable=False,
        unique=True,
        index=True,
        comment="Random verification token (64-char hex string)",
    )

    # Token expiration (24 hours from creation)
    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Timestamp when token expires (24 hours from creation)",
    )

    # One-time use tracking (nullable until used)
    used_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
        comment="Timestamp when token was used (one-time use)",
    )

    # Composite index for cleanup queries (expired and used tokens)
    __table_args__ = (
        Index(
            "idx_email_verification_cleanup",
            "expires_at",
            "used_at",
            postgresql_where="used_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of verification token.
        """
        return (
            f"<EmailVerificationToken("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"expires_at={self.expires_at}, "
            f"used={self.used_at is not None}"
            f")>"
        )
