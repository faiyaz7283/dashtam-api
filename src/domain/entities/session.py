"""Session domain entity for multi-device session management.

Pure business logic, no framework dependencies.

This entity represents an authenticated user session with rich metadata
tracking for security, audit, and multi-device management.

Reference:
    - docs/architecture/session-management-architecture.md
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID


@dataclass(slots=True, kw_only=True)
class Session:
    """Session domain entity with multi-device tracking.

    Pure business logic with no infrastructure dependencies.
    Represents an authenticated session with rich metadata.

    Business Rules:
        - Session is active if not revoked and not expired
        - Session tied to refresh token (same lifecycle)
        - Revocation is immediate (no grace period)
        - Provider access tracked per session for audit trail

    Attributes:
        id: Unique session identifier.
        user_id: User who owns this session.

        Device Information:
            device_info: Parsed device info ("Chrome on macOS").
            user_agent: Full user agent string.

        Network Information:
            ip_address: Client IP at session creation.
            location: Geographic location ("New York, US").

        Timestamps:
            created_at: When session was created.
            last_activity_at: Last activity timestamp.
            expires_at: When session expires (matches refresh token).

        Security:
            is_revoked: Whether session is revoked.
            is_trusted: Whether device is trusted (future: remember device).
            revoked_at: When session was revoked.
            revoked_reason: Why session was revoked.

        Token Tracking:
            refresh_token_id: Associated refresh token ID.

        Security Tracking:
            last_ip_address: Most recent IP (detect changes).
            suspicious_activity_count: Security event counter.

        Provider Tracking (Dashtam-specific):
            last_provider_accessed: Last provider accessed.
            last_provider_sync_at: Last provider sync time.
            providers_accessed: List of providers accessed in this session.

    Example:
        >>> from uuid_extensions import uuid7
        >>> from datetime import datetime, UTC, timedelta
        >>>
        >>> session = Session(
        ...     id=uuid7(),
        ...     user_id=uuid7(),
        ...     device_info="Chrome on macOS",
        ...     ip_address="192.168.1.1",
        ...     expires_at=datetime.now(UTC) + timedelta(days=30),
        ... )
        >>> session.is_active()
        True
        >>> session.revoke("user_logout")
        >>> session.is_active()
        False
    """

    # Identity
    id: UUID
    user_id: UUID

    # Device Information
    device_info: str | None = None
    user_agent: str | None = None

    # Network Information
    ip_address: str | None = None
    location: str | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime | None = None
    expires_at: datetime | None = None

    # Security
    is_revoked: bool = False
    is_trusted: bool = False
    revoked_at: datetime | None = None
    revoked_reason: str | None = None

    # Token Tracking
    refresh_token_id: UUID | None = None

    # Security Tracking
    last_ip_address: str | None = None
    suspicious_activity_count: int = 0

    # Provider Tracking
    last_provider_accessed: str | None = None
    last_provider_sync_at: datetime | None = None
    providers_accessed: list[str] = field(default_factory=list)

    def is_active(self) -> bool:
        """Check if session is active (not revoked, not expired).

        A session is active if:
        - It has not been revoked (is_revoked=False)
        - It has not expired (expires_at is None or in the future)

        Returns:
            True if session is active, False otherwise.

        Example:
            >>> session = Session(id=uuid7(), user_id=uuid7())
            >>> session.is_active()
            True
            >>> session.revoke("test")
            >>> session.is_active()
            False
        """
        if self.is_revoked:
            return False
        if self.expires_at and datetime.now(UTC) > self.expires_at:
            return False
        return True

    def revoke(self, reason: str) -> None:
        """Revoke this session.

        Marks the session as revoked with timestamp and reason.
        Revocation is immediate and permanent.

        Args:
            reason: Why session is being revoked. Common reasons:
                - "user_logout": User initiated logout
                - "password_changed": Password was changed
                - "max_sessions_exceeded": Session limit reached
                - "admin_action": Admin revoked session
                - "security_concern": Suspicious activity detected

        Example:
            >>> session = Session(id=uuid7(), user_id=uuid7())
            >>> session.revoke("user_logout")
            >>> session.is_revoked
            True
            >>> session.revoked_reason
            'user_logout'
        """
        self.is_revoked = True
        self.revoked_at = datetime.now(UTC)
        self.revoked_reason = reason

    def update_activity(self, ip_address: str | None = None) -> None:
        """Update last activity timestamp and optionally track IP changes.

        Called when user performs an action in this session.
        If IP address changed, stores previous IP in last_ip_address
        for security tracking.

        Args:
            ip_address: Current client IP (optional). If provided and
                different from stored IP, triggers IP change tracking.

        Example:
            >>> session = Session(id=uuid7(), user_id=uuid7(), ip_address="1.1.1.1")
            >>> session.update_activity(ip_address="2.2.2.2")
            >>> session.last_ip_address
            '2.2.2.2'
        """
        self.last_activity_at = datetime.now(UTC)
        if ip_address:
            if self.ip_address and ip_address != self.ip_address:
                # IP changed - track for security monitoring
                self.last_ip_address = ip_address
            elif not self.ip_address:
                self.ip_address = ip_address

    def record_provider_access(self, provider_name: str) -> None:
        """Record provider access for audit trail.

        Tracks which financial providers were accessed in this session.
        Used for security audit when investigating compromised sessions.

        Args:
            provider_name: Provider that was accessed (e.g., "schwab", "fidelity").

        Example:
            >>> session = Session(id=uuid7(), user_id=uuid7())
            >>> session.record_provider_access("schwab")
            >>> session.last_provider_accessed
            'schwab'
            >>> session.providers_accessed
            ['schwab']
            >>> session.record_provider_access("fidelity")
            >>> session.providers_accessed
            ['schwab', 'fidelity']
        """
        self.last_provider_accessed = provider_name
        self.last_provider_sync_at = datetime.now(UTC)
        if provider_name not in self.providers_accessed:
            self.providers_accessed.append(provider_name)

    def increment_suspicious_activity(self) -> None:
        """Increment suspicious activity counter.

        Called when suspicious activity is detected:
        - Multiple failed API calls
        - Unusual access patterns
        - IP changes from different geolocations

        Example:
            >>> session = Session(id=uuid7(), user_id=uuid7())
            >>> session.suspicious_activity_count
            0
            >>> session.increment_suspicious_activity()
            >>> session.suspicious_activity_count
            1
        """
        self.suspicious_activity_count += 1

    def mark_as_trusted(self) -> None:
        """Mark this device/session as trusted.

        Trusted devices may have different security policies:
        - Skip MFA on future logins (future feature)
        - Higher session limits
        - Extended session duration

        Example:
            >>> session = Session(id=uuid7(), user_id=uuid7())
            >>> session.is_trusted
            False
            >>> session.mark_as_trusted()
            >>> session.is_trusted
            True
        """
        self.is_trusted = True
