"""Session database model for multi-device session management.

This module defines the Session model for storing authenticated user sessions
with rich metadata for security, audit, and multi-device tracking.

Security:
    - is_revoked: Immediate session revocation (logout, password change, theft)
    - ip_address: Track client IP for anomaly detection
    - suspicious_activity_count: Security event counter

Provider Tracking (Dashtam-specific):
    - providers_accessed: Track which providers accessed per session
    - Used for audit trail when investigating compromised sessions
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, INET
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.base import BaseMutableModel


class Session(BaseMutableModel):
    """Session model for multi-device session management.

    Stores authenticated sessions with rich metadata for security,
    audit, and multi-device tracking. Each session is tied to a user
    and optionally to a refresh token.

    Session Lifecycle:
        1. Created on successful login (with device/location enrichment)
        2. Activity tracked on each request (last_activity_at, IP changes)
        3. Revoked on logout, password change, or security event
        4. Expires naturally after 30 days (matches refresh token)

    Security Features:
        - Device fingerprinting (user_agent, device_info)
        - IP geolocation tracking (ip_address, location)
        - Suspicious activity detection (suspicious_activity_count)
        - Immediate revocation (is_revoked, revoked_at, revoked_reason)
        - Provider access tracking (providers_accessed)

    Fields:
        id: UUID primary key (from BaseMutableModel)
        created_at: Timestamp when session created (from BaseMutableModel)
        updated_at: Timestamp when session last updated (from BaseMutableModel)

        Identity:
            user_id: Foreign key to users table (cascade delete)

        Device Information:
            device_info: Parsed device info ("Chrome on macOS")
            user_agent: Full user agent string

        Network Information:
            ip_address: Client IP at session creation (PostgreSQL INET)
            location: Geographic location ("New York, US")

        Timestamps:
            last_activity_at: Last activity timestamp
            expires_at: When session expires (matches refresh token)

        Security:
            is_revoked: Whether session is revoked
            is_trusted: Whether device is trusted
            revoked_at: When session was revoked
            revoked_reason: Why session was revoked

        Token Tracking:
            refresh_token_id: Associated refresh token ID

        Security Tracking:
            last_ip_address: Most recent IP (detect changes)
            suspicious_activity_count: Security event counter

        Provider Tracking:
            last_provider_accessed: Last provider accessed
            last_provider_sync_at: Last provider sync time
            providers_accessed: List of providers accessed (PostgreSQL ARRAY)

    Indexes:
        - ix_sessions_user_id: (user_id) for user's sessions
        - ix_sessions_is_revoked: (is_revoked) for active session queries
        - ix_sessions_expires_at: (expires_at) for cleanup queries
        - idx_sessions_user_active: (user_id, is_revoked, expires_at) for active count
        - idx_sessions_cleanup: (expires_at, is_revoked) for batch cleanup

    Foreign Keys:
        - user_id: References users(id) ON DELETE CASCADE

    Example:
        # Create session (via repository)
        session = Session(
            user_id=user_id,
            device_info="Chrome on macOS",
            ip_address="192.168.1.1",
            location="New York, US",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        db_session.add(session)
        await db_session.commit()
    """

    __tablename__ = "sessions"

    # =========================================================================
    # Identity
    # =========================================================================

    # User relationship (cascade delete when user deleted)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this session",
    )

    # =========================================================================
    # Device Information
    # =========================================================================

    # Parsed device info (e.g., "Chrome 120 on macOS 14")
    device_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        comment="Parsed device info (browser, OS)",
    )

    # Full user agent string (for detailed analysis)
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
        comment="Full user agent string from HTTP header",
    )

    # =========================================================================
    # Network Information
    # =========================================================================

    # Client IP at session creation (PostgreSQL INET type)
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        default=None,
        comment="Client IP address at session creation",
    )

    # Geographic location (e.g., "New York, US")
    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        comment="Geographic location from IP geolocation",
    )

    # =========================================================================
    # Timestamps
    # =========================================================================

    # Last activity timestamp (updated on each request)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp of last user activity in this session",
    )

    # Session expiration (matches refresh token, 30 days)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When session expires (matches refresh token lifetime)",
    )

    # =========================================================================
    # Security
    # =========================================================================

    # Revocation status
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether session has been revoked",
    )

    # Trusted device flag (for future: remember device, skip MFA)
    is_trusted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this device is trusted",
    )

    # Revocation timestamp
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp when session was revoked",
    )

    # Revocation reason (for audit)
    revoked_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        comment="Reason for revocation (logout, password_change, theft, etc.)",
    )

    # =========================================================================
    # Token Tracking
    # =========================================================================

    # Associated refresh token (one-to-one relationship)
    # Note: FK constraint is on refresh_tokens.session_id, not here
    # This is optional because token may be created after session
    refresh_token_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
        default=None,
        index=True,
        comment="Associated refresh token ID (for reference)",
    )

    # =========================================================================
    # Security Tracking
    # =========================================================================

    # Most recent IP (track changes for anomaly detection)
    last_ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        default=None,
        comment="Most recent client IP (for detecting IP changes)",
    )

    # Security event counter
    suspicious_activity_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Counter for suspicious activity events",
    )

    # =========================================================================
    # Provider Tracking (Dashtam-specific)
    # =========================================================================

    # Last provider accessed
    last_provider_accessed: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        comment="Last financial provider accessed in this session",
    )

    # Last provider sync timestamp
    last_provider_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Timestamp of last provider sync in this session",
    )

    # List of providers accessed (PostgreSQL ARRAY)
    providers_accessed: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
        default=None,
        comment="List of providers accessed in this session",
    )

    # =========================================================================
    # Composite Indexes
    # =========================================================================

    __table_args__ = (
        # Index for counting active sessions per user
        Index(
            "idx_sessions_user_active",
            "user_id",
            "is_revoked",
            "expires_at",
            postgresql_where="is_revoked = false",
        ),
        # Index for cleanup queries (expired/revoked sessions)
        Index(
            "idx_sessions_cleanup",
            "expires_at",
            "is_revoked",
        ),
    )

    def __repr__(self) -> str:
        """String representation for debugging.

        Returns:
            str: Human-readable representation of session.
        """
        return (
            f"<Session("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"device_info={self.device_info!r}, "
            f"is_revoked={self.is_revoked}"
            f")>"
        )
