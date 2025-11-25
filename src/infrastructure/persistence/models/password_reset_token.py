"""Password reset token database model for authentication.

This module defines the PasswordResetToken model for password reset flow.

Security:
    - token: Random 32-byte hex string (unguessable)
    - expires_at: 15 minutes (very short, security vs UX tradeoff)
    - used_at: One-time use (marked as used after password reset)
    - ip_address/user_agent: Track who requested reset (security)
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseModel


class PasswordResetToken(BaseModel):
    """Password reset token model for password recovery.

    Stores very short-lived (15 minutes) one-time use tokens for password
    reset. Tracks IP address and user agent for security monitoring.

    Token Lifecycle:
        1. Created when user requests password reset
        2. Sent to user's email (via event handler)
        3. User clicks reset link with token
        4. Token validated and marked as used (used_at set)
        5. Password updated, all sessions revoked

    Security Features:
        - Random 32-byte hex string (unguessable)
        - Very short-lived (15 minutes expiration)
        - One-time use (used_at timestamp)
        - Tracks requester IP and user agent
        - Password reset revokes ALL user sessions

    Fields:
        id: UUID primary key (from BaseModel)
        created_at: Timestamp when token created (from BaseModel)
        user_id: Foreign key to users table (cascade delete)
        token: Random hex string (64 characters, unique, indexed)
        expires_at: Timestamp when token expires (15 minutes from creation)
        used_at: Timestamp when token was used (nullable, one-time use)
        ip_address: IP address of requester (security tracking)
        user_agent: User agent of requester (security tracking)

    Indexes:
        - idx_password_reset_user_id: (user_id) for user's tokens
        - idx_password_reset_token: (token) for lookup (unique)
        - idx_password_reset_cleanup: (expires_at, used_at) for cleanup

    Foreign Keys:
        - user_id: References users(id) ON DELETE CASCADE

    Note:
        This model inherits from BaseModel (NOT BaseMutableModel) because
        reset tokens are immutable (only used_at is set once).

    Security Considerations:
        - 15 minute expiration (short window for security)
        - Tracks IP/user agent (detect suspicious requests)
        - Always returns 200 OK (no user enumeration)
        - Password reset revokes all sessions (security event)

    Example:
        # Create reset token (via repository)
        token = PasswordResetToken(
            user_id=user_id,
            token=secrets.token_hex(32),  # 64-char hex string
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
        )
        session.add(token)
        await session.commit()

        # Query token (password reset)
        result = await session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.token == token_str)
            .where(PasswordResetToken.used_at.is_(None))
            .where(PasswordResetToken.expires_at > datetime.now(UTC))
        )
        token = result.scalar_one_or_none()
    """

    __tablename__ = "password_reset_tokens"

    # User relationship (cascade delete when user deleted)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who requested password reset",
    )

    # Token (random 32-byte hex string, unique, indexed for lookup)
    token: Mapped[str] = mapped_column(
        String(64),  # 32 bytes = 64 hex characters
        nullable=False,
        unique=True,
        index=True,
        comment="Random password reset token (64-char hex string)",
    )

    # Token expiration (15 minutes from creation, very short)
    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Timestamp when token expires (15 minutes from creation)",
    )

    # One-time use tracking (nullable until used)
    used_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
        comment="Timestamp when token was used (one-time use)",
    )

    # Security tracking (who requested reset)
    ip_address: Mapped[str | None] = mapped_column(
        INET,  # PostgreSQL INET type (handles IPv4 and IPv6)
        nullable=True,
        comment="IP address of requester (security tracking)",
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="User agent of requester (security tracking)",
    )

    # Composite index for cleanup queries (expired and used tokens)
    __table_args__ = (
        Index(
            "idx_password_reset_cleanup",
            "expires_at",
            "used_at",
            postgresql_where="used_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of password reset token.
        """
        return (
            f"<PasswordResetToken("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"expires_at={self.expires_at}, "
            f"used={self.used_at is not None}"
            f")>"
        )
