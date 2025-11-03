"""Session model - user session on a specific device.

This module defines the Session model representing an authenticated user
session on a specific device/browser. Each session can have multiple
refresh tokens over time (due to token rotation).

This is a proper database table (not a wrapper) that separates session
concerns from token concerns, following proper relational design.
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, Column
from sqlalchemy import String, Text, DateTime, Boolean
from sqlalchemy.dialects.postgresql import INET
from pydantic import field_validator

from src.models.base import DashtamBase
from src.session_manager.models.base import SessionBase

if TYPE_CHECKING:
    from src.models.user import User
    from src.models.auth import RefreshToken


class Session(DashtamBase, SessionBase, table=True):
    """User session (device/browser connection).

    Represents a user's authenticated session on a specific device.
    Each session can have multiple refresh tokens over time (due to rotation).

    Separation of Concerns:
        - Session: Device/browser connection with metadata
        - RefreshToken: Credential for token refresh
        - Relationship: Session (1) → RefreshTokens (many)

    This is the proper session model that session_manager package expects,
    implementing the SessionBase interface.

    Attributes:
        user_id: User who owns this session
        device_info: Device/browser information
        ip_address: IP address where session originated
        user_agent: Full user agent string
        location: Geographic location from IP
        fingerprint: SHA256 hash of device fingerprint
        is_trusted_device: User-marked trusted device
        last_activity: Last activity timestamp
        expires_at: Session expiration timestamp
        is_revoked: Whether session is revoked
        revoked_at: When session was revoked
        revoked_reason: Why session was revoked

    Relationships:
        user: User who owns this session
        refresh_tokens: All refresh tokens for this session
    """

    __tablename__ = "sessions"

    # User relationship
    user_id: UUID = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
        description="User who owns this session",
    )

    # Device/Browser information
    device_info: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Device/browser information (e.g., 'Chrome on macOS')",
    )

    ip_address: Optional[str] = Field(
        default=None,
        sa_column=Column(INET, nullable=True),
        description="IP address where session originated",
    )

    user_agent: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Full user agent string",
    )

    location: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Geographic location from IP (e.g., 'San Francisco, USA')",
    )

    fingerprint: Optional[str] = Field(
        default=None,
        sa_column=Column(String(64), nullable=True, index=True),
        description="SHA256 hash of device fingerprint",
    )

    is_trusted_device: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
        description="User-marked trusted device",
    )

    # Session lifecycle
    last_activity: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Last activity timestamp",
    )

    expires_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Session expiration timestamp",
    )

    is_revoked: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false", index=True),
        description="Whether session is revoked",
    )

    revoked_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="When session was revoked",
    )

    revoked_reason: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Why session was revoked",
    )

    # Relationships
    user: "User" = Relationship(back_populates="sessions")
    refresh_tokens: List["RefreshToken"] = Relationship(
        back_populates="session",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # Field validators
    @field_validator("last_activity", "expires_at", "revoked_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    # SessionBase interface implementation
    @property
    def is_trusted(self) -> bool:
        """Alias for SessionBase compatibility.

        SessionBase expects is_trusted, but our model uses is_trusted_device.
        This property provides compatibility.
        """
        return self.is_trusted_device

    def is_active(self) -> bool:
        """Check if session is active (SessionBase interface).

        A session is active if:
        - Not revoked
        - Not expired

        Returns:
            True if session is active, False otherwise
        """
        if self.is_revoked:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<Session("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"device={self.device_info}, "
            f"active={self.is_active()}"
            f")>"
        )
