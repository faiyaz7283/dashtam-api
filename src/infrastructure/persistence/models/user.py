"""User database model for authentication.

This module defines the User model for storing user account information.

Security:
    - password_hash: NEVER stores plaintext passwords (bcrypt hashed)
    - is_verified: Email verification required before login
    - failed_login_attempts: Track for account lockout
    - locked_until: Temporary account lockout after failed attempts

Session Management:
    - session_tier: Role-based tier determining default session limit
    - max_sessions: Admin override for session limit (None = use tier default)

Token Breach Rotation:
    - min_token_version: Per-user minimum acceptable token version
      Increment to invalidate all user's tokens (password change, security event)
"""

from datetime import datetime

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class User(BaseMutableModel):
    """User model for authentication and account management.

    This model stores user credentials and account state. Users must verify
    their email before login (is_verified). Failed login attempts trigger
    temporary account lockout.

    Security Features:
        - Email verification required (is_verified must be True)
        - Password hashing (bcrypt, cost factor 12)
        - Account lockout (5 failed attempts = 15 minute lockout)
        - Active/inactive states (is_active)

    Fields:
        id: UUID primary key (from BaseMutableModel)
        created_at: Timestamp when user registered (from BaseMutableModel)
        updated_at: Timestamp when user last updated (from BaseMutableModel)
        email: Unique email address (lowercase, indexed)
        password_hash: Bcrypt hashed password (NEVER plaintext)
        is_verified: Email verification status (blocks login if False)
        is_active: Account active status (deactivated users cannot login)
        failed_login_attempts: Counter for failed logins (resets on success)
        locked_until: Timestamp until which account is locked (nullable)
        session_tier: Role-based tier for session limits (basic, essential, plus, premium, pro)
        max_sessions: Admin override for session limit (nullable, None = use tier default)
        min_token_version: Per-user minimum token version (increment to invalidate user's tokens)

    Indexes:
        - idx_users_email: (email) for login queries
        - idx_users_is_verified: (is_verified) for filtering unverified users

    Relationships:
        - refresh_tokens: One-to-many (cascade delete)
        - email_verification_tokens: One-to-many (cascade delete)
        - password_reset_tokens: One-to-many (cascade delete)

    Example:
        # Create user (via repository)
        user = User(
            email="user@example.com",
            password_hash="$2b$12$...",  # Bcrypt hash
            is_verified=False,
            is_active=True,
            failed_login_attempts=0,
        )
        session.add(user)
        await session.commit()

        # Query user by email (login)
        result = await session.execute(
            select(User)
            .where(User.email == "user@example.com")
        )
        user = result.scalar_one_or_none()
    """

    __tablename__ = "users"

    # Email address (unique, indexed for login queries)
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="User email address (unique, lowercase)",
    )

    # Password hash (NEVER plaintext, bcrypt with cost factor 12)
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password (cost factor 12)",
    )

    # Email verification (blocks login if False)
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Email verification status (must be True to login)",
    )

    # Account active status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Account active status (deactivated users cannot login)",
    )

    # Failed login tracking (for account lockout)
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Counter for failed login attempts (resets on success)",
    )

    # Account lockout timestamp (nullable, set after 5 failed attempts)
    locked_until: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
        comment="Timestamp until which account is locked (15 min after 5 failures)",
    )

    # Session management (F1.3)
    # Role-based tier determining default session limit
    session_tier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="basic",
        index=True,
        comment="Session tier (basic, essential, plus, premium, pro)",
    )

    # Admin override for session limit (None = use tier default)
    max_sessions: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
        comment="Admin override for max sessions (null = use tier default)",
    )

    # Token breach rotation
    # Per-user minimum token version (increment to invalidate all user's tokens)
    min_token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        index=True,
        comment="Per-user minimum token version (increment on password change, security event)",
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of user.
        """
        return (
            f"<User("
            f"id={self.id}, "
            f"email={self.email!r}, "
            f"is_verified={self.is_verified}, "
            f"is_active={self.is_active}"
            f")>"
        )
