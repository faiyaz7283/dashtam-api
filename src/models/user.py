"""User model for authentication and provider ownership.

This module defines the User model which represents application users
who can connect multiple financial providers. Supports JWT authentication
with email/password, email verification, and account security features.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import Field, Relationship, Column
from sqlalchemy import String, DateTime, Integer, Boolean
from sqlalchemy.dialects.postgresql import INET
from pydantic import field_validator

from src.models.base import DashtamBase

if TYPE_CHECKING:
    from src.models.provider import Provider
    from src.models.auth import RefreshToken, EmailVerificationToken, PasswordResetToken
    from src.models.session import Session


class User(DashtamBase, table=True):
    """Application user model with JWT authentication support.

    Represents a user who can authenticate and manage multiple financial
    provider instances. Supports JWT authentication with email/password,
    email verification, and account security features.

    Attributes:
        email: User's email address (unique, used for login).
        name: User's full name.
        password_hash: Bcrypt hash of user's password.
        email_verified: Whether email address has been verified.
        email_verified_at: Timestamp of email verification.
        failed_login_attempts: Count of consecutive failed login attempts.
        account_locked_until: Timestamp until which account is locked (after too many failures).
        last_login_at: Timestamp of last successful login.
        last_login_ip: IP address of last successful login.
        is_active: Whether account is active (for soft deletion/suspension).
        providers: List of provider instances owned by user.
        sessions: List of active sessions (devices) for this user.
        refresh_tokens: List of active refresh tokens for user sessions.
        email_verification_tokens: List of email verification tokens.
        password_reset_tokens: List of password reset tokens.
    """

    __tablename__ = "users"

    # Basic info
    email: str = Field(
        sa_column=Column(String(255), unique=True, index=True, nullable=False),
        description="User's email address (unique, used for login)",
    )
    name: str = Field(description="User's full name")

    # Authentication
    password_hash: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Bcrypt hash of user's password",
    )

    # Email verification
    email_verified: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
        description="Whether email address has been verified",
    )
    email_verified_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp of email verification",
    )

    # Account security
    failed_login_attempts: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
        description="Count of consecutive failed login attempts",
    )
    account_locked_until: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp until which account is locked",
    )

    # Login tracking
    last_login_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp of last successful login",
    )
    last_login_ip: Optional[str] = Field(
        default=None,
        sa_column=Column(INET, nullable=True),
        description="IP address of last successful login",
    )

    # Account status
    is_active: bool = Field(
        default=True,
        description="Whether account is active (for soft deletion/suspension)",
    )

    # Token rotation (per-user version)
    min_token_version: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False, server_default="1"),
        description="Minimum token version for this user (rotation)",
    )

    # Relationships
    providers: List["Provider"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    sessions: List["Session"] = Relationship(back_populates="user", cascade_delete=True)
    refresh_tokens: List["RefreshToken"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    email_verification_tokens: List["EmailVerificationToken"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    password_reset_tokens: List["PasswordResetToken"] = Relationship(
        back_populates="user", cascade_delete=True
    )

    # Validators to ensure timezone awareness
    @field_validator(
        "email_verified_at", "account_locked_until", "last_login_at", mode="before"
    )
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if not self.account_locked_until:
            return False
        return datetime.now(timezone.utc) < self.account_locked_until

    @property
    def can_login(self) -> bool:
        """Check if user can log in (active, not locked)."""
        return self.is_active and not self.is_locked

    @property
    def active_providers_count(self) -> int:
        """Count of active provider connections."""
        if not self.providers:
            return 0
        return sum(1 for p in self.providers if p.is_connected)

    @property
    def display_name(self) -> str:
        """Get display name (name or email)."""
        return self.name or self.email.split("@")[0]

    def reset_failed_login_attempts(self) -> None:
        """Reset failed login attempts counter."""
        self.failed_login_attempts = 0
        self.account_locked_until = None

    def increment_failed_login_attempts(self) -> None:
        """Increment failed login attempts and lock account if threshold exceeded."""
        self.failed_login_attempts += 1

        # Lock account after 10 failed attempts (1 hour)
        if self.failed_login_attempts >= 10:
            self.account_locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
