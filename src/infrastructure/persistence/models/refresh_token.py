"""Refresh token database model for authentication.

This module defines the RefreshToken model for storing long-lived refresh tokens.

Security:
    - token_hash: Bcrypt hashed token (NOT plaintext, revocable)
    - expires_at: 30 days from creation
    - revoked_at: Immediate revocation (logout, password change, theft detection)
    - rotation_count: Track token rotations for security monitoring
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class RefreshToken(BaseMutableModel):
    """Refresh token model for JWT refresh flow.

    Stores opaque refresh tokens (hashed) that can be revoked. Used with
    short-lived JWT access tokens for secure authentication.

    Token Lifecycle:
        1. Created on login (30 day expiration)
        2. Used to get new access token (rotated on each use)
        3. Revoked on logout, password change, or theft detection
        4. Expires naturally after 30 days

    Security Features:
        - Opaque tokens (long random strings, not JWT)
        - Hashed with bcrypt before storage (like passwords)
        - One-time use (rotated on every refresh)
        - Immediate revocation (logout, security events)
        - Theft detection (attempt to use rotated token)

    Fields:
        id: UUID primary key (from BaseMutableModel)
        created_at: Timestamp when token created (from BaseMutableModel)
        updated_at: Timestamp when token last used (from BaseMutableModel)
        user_id: Foreign key to users table (cascade delete)
        token_hash: Bcrypt hashed token (NEVER plaintext)
        session_id: Foreign key to sessions table (F1.3, cascade delete)
        expires_at: Timestamp when token expires (30 days from creation)
        revoked_at: Timestamp when revoked (nullable, set on revocation)
        revoked_reason: Why token was revoked (logout, password_change, theft)
        last_used_at: Timestamp when token last used (for monitoring)
        rotation_count: Number of times token has been rotated

    Indexes:
        - idx_refresh_tokens_user_id: (user_id) for user's active tokens
        - idx_refresh_tokens_token_hash: (token_hash) for lookup (unique)
        - idx_refresh_tokens_expires_at: (expires_at) for cleanup queries
        - idx_refresh_tokens_session_id: (session_id) for session revocation

    Foreign Keys:
        - user_id: References users(id) ON DELETE CASCADE
        - session_id: References sessions(id) ON DELETE CASCADE (F1.3)

    Example:
        # Create refresh token (via repository)
        token = RefreshToken(
            user_id=user_id,
            token_hash="$2b$12$...",  # Bcrypt hash of token
            session_id=session_id,
            expires_at=datetime.now(UTC) + timedelta(days=30),
            rotation_count=0,
        )
        session.add(token)
        await session.commit()

        # Query token by hash (refresh)
        result = await session.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .where(RefreshToken.revoked_at.is_(None))
            .where(RefreshToken.expires_at > datetime.now(UTC))
        )
        token = result.scalar_one_or_none()
    """

    __tablename__ = "refresh_tokens"

    # User relationship (cascade delete when user deleted)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this refresh token",
    )

    # Token hash (bcrypt, unique, indexed for lookup)
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Bcrypt hashed refresh token (NEVER plaintext)",
    )

    # Session relationship (F1.3 dependency - sessions table not yet created)
    # TODO: Add FK constraint when sessions table is created in F1.3
    session_id: Mapped[UUID] = mapped_column(
        # ForeignKey("sessions.id", ondelete="CASCADE"),  # Uncomment in F1.3
        nullable=False,
        index=True,
        comment="Session this token belongs to (FK constraint added in F1.3)",
    )

    # Token expiration (30 days from creation)
    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
        comment="Timestamp when token expires (30 days from creation)",
    )

    # Revocation tracking (nullable until revoked)
    revoked_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
        comment="Timestamp when token was revoked (nullable)",
    )

    revoked_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="Reason for revocation (logout, password_change, theft_detected)",
    )

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
        comment="Timestamp when token was last used (for monitoring)",
    )

    rotation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times token has been rotated (security monitoring)",
    )

    # Composite index for cleanup queries (expired and revoked tokens)
    __table_args__ = (
        Index(
            "idx_refresh_tokens_cleanup",
            "expires_at",
            "revoked_at",
            postgresql_where="revoked_at IS NULL",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of refresh token.
        """
        return (
            f"<RefreshToken("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"expires_at={self.expires_at}, "
            f"revoked={self.revoked_at is not None}"
            f")>"
        )
