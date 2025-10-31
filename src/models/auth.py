"""Authentication models for JWT token management.

This module defines models for refresh tokens, email verification tokens,
and password reset tokens used in the JWT authentication system.
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, Column
from sqlalchemy import String, DateTime, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import INET
from pydantic import field_validator

from src.models.base import DashtamBase

if TYPE_CHECKING:
    from src.models.user import User


class RefreshToken(DashtamBase, table=True):
    """Refresh token for JWT authentication with session management.

    Stores refresh tokens with rotation support. Each token is hashed
    before storage and can be revoked for logout or security events.
    Each refresh token represents a user session on a specific device.

    Session Management:
    - Users can view all active sessions (devices)
    - Users can revoke sessions individually or in bulk
    - Email alerts sent for new sessions from new devices/locations
    - Device fingerprinting for session hijacking detection

    Attributes:
        user_id: ID of user who owns this token.
        token_hash: Bcrypt hash of the refresh token.
        expires_at: Token expiration timestamp (30 days).
        revoked_at: Timestamp when token was revoked (logout).
        is_revoked: Whether token has been revoked.
        device_info: Information about device/browser.
        ip_address: IP address where token was issued.
        user_agent: User agent string of client.
        last_used_at: Timestamp of last token use (refresh).
        location: User-friendly location from IP geolocation.
        fingerprint: SHA256 hash of device fingerprint.
        is_trusted_device: User-marked trusted device flag.
        user: User who owns this token.
    """

    __tablename__ = "refresh_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
        description="ID of user who owns this token",
    )
    token_hash: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True),
        description="Bcrypt hash of the refresh token",
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        description="Token expiration timestamp",
    )
    revoked_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp when token was revoked",
    )
    is_revoked: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false", index=True),
        description="Whether token has been revoked",
    )
    device_info: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Information about device/browser",
    )
    ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(INET, nullable=True),
        description="IP address where token was issued",
    )
    user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="User agent string of client",
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp of last token use",
    )

    # Session management fields
    location: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="User-friendly location from IP geolocation (e.g., 'San Francisco, USA')",
    )
    fingerprint: Optional[str] = Field(
        default=None,
        sa_column=Column(String(64), nullable=True, index=True),
        description="SHA256 hash of device fingerprint (browser + OS + screen + timezone)",
    )
    is_trusted_device: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
        description="User-marked trusted device (future: extended session TTL)",
    )

    # Token versioning (hybrid approach)
    token_version: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False, server_default="1", index=True),
        description="User's token version at issuance time",
    )
    global_version_at_issuance: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False, server_default="1", index=True),
        description="Global token version at issuance time",
    )

    # Relationships
    user: "User" = Relationship(back_populates="refresh_tokens")

    @field_validator("expires_at", "revoked_at", "last_used_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired, not revoked)."""
        return not self.is_expired and not self.is_revoked

    def revoke(self) -> None:
        """Revoke this token."""
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)


class EmailVerificationToken(DashtamBase, table=True):
    """Email verification token.

    One-time use token sent via email to verify user's email address.
    Expires after 24 hours.

    Attributes:
        user_id: ID of user who needs to verify email.
        token_hash: Bcrypt hash of the verification token.
        expires_at: Token expiration timestamp (24 hours).
        used_at: Timestamp when token was used.
        user: User who needs to verify email.
    """

    __tablename__ = "email_verification_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
        description="ID of user who needs to verify email",
    )
    token_hash: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True),
        description="Bcrypt hash of the verification token",
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
        description="Token expiration timestamp (24 hours)",
    )
    used_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp when token was used",
    )

    # Relationships
    user: "User" = Relationship(back_populates="email_verification_tokens")

    @field_validator("expires_at", "used_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if token has already been used."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired, not used)."""
        return not self.is_expired and not self.is_used

    def mark_as_used(self) -> None:
        """Mark token as used."""
        self.used_at = datetime.now(timezone.utc)


class PasswordResetToken(DashtamBase, table=True):
    """Password reset token.

    One-time use token sent via email to reset forgotten password.
    Expires after 15 minutes for security.

    Attributes:
        user_id: ID of user requesting password reset.
        token_hash: Bcrypt hash of the reset token.
        expires_at: Token expiration timestamp (15 minutes).
        used_at: Timestamp when token was used.
        ip_address: IP address of reset request.
        user_agent: User agent string of reset request.
        user: User requesting password reset.
    """

    __tablename__ = "password_reset_tokens"

    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
        description="ID of user requesting password reset",
    )
    token_hash: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True),
        description="Bcrypt hash of the reset token",
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,
        description="Token expiration timestamp (15 minutes)",
    )
    used_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Timestamp when token was used",
    )
    ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(INET, nullable=True),
        description="IP address of reset request",
    )
    user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="User agent string of reset request",
    )

    # Relationships
    user: "User" = Relationship(back_populates="password_reset_tokens")

    @field_validator("expires_at", "used_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if token has already been used."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired, not used)."""
        return not self.is_expired and not self.is_used

    def mark_as_used(self) -> None:
        """Mark token as used."""
        self.used_at = datetime.now(timezone.utc)
