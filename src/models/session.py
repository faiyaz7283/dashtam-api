"""Session model for session_manager package integration.

This module provides the Dashtam-specific Session implementation that
conforms to the session_manager package's SessionBase interface.

Design Decision:
    We use RefreshToken as the underlying storage model since it already
    contains all the necessary session fields (device_info, ip_address,
    location, etc.). This Session class acts as an adapter that implements
    the SessionBase interface required by the session_manager package.

    This approach avoids creating duplicate tables and maintains backwards
    compatibility with existing RefreshToken-based code while enabling
    the new session_manager package functionality.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from src.models.auth import RefreshToken
from src.session_manager.models.base import SessionBase


class Session(SessionBase):
    """Session implementation using RefreshToken as storage.

    This is an adapter that wraps RefreshToken to implement SessionBase
    interface from session_manager package. It delegates storage to the
    existing RefreshToken model to avoid table duplication.

    Attributes:
        All attributes are inherited from SessionBase and map to
        corresponding RefreshToken fields.

    Example:
        ```python
        # Create session from RefreshToken
        session = Session.from_refresh_token(refresh_token)

        # Check if active
        if session.is_active():
            print("Session is valid")

        # Use in session_manager
        await session_manager.revoke_session(session.id, "user_logout")
        ```
    """

    def __init__(self, refresh_token: RefreshToken):
        """Initialize session from RefreshToken.

        Args:
            refresh_token: RefreshToken instance to wrap
        """
        self._refresh_token = refresh_token

    @classmethod
    def from_refresh_token(cls, refresh_token: RefreshToken) -> "Session":
        """Create Session from RefreshToken instance.

        Args:
            refresh_token: RefreshToken to wrap

        Returns:
            Session instance
        """
        return cls(refresh_token)

    # Required SessionBase fields (property delegation to RefreshToken)
    @property
    def id(self) -> UUID:
        """Session ID (maps to RefreshToken.id)."""
        return self._refresh_token.id

    @property
    def user_id(self) -> str:
        """User ID (converts UUID to string)."""
        return str(self._refresh_token.user_id)

    @property
    def device_info(self) -> Optional[str]:
        """Device/browser information."""
        return self._refresh_token.device_info

    @property
    def ip_address(self) -> Optional[str]:
        """Client IP address."""
        return (
            str(self._refresh_token.ip_address)
            if self._refresh_token.ip_address
            else None
        )

    @property
    def user_agent(self) -> Optional[str]:
        """User agent string."""
        return self._refresh_token.user_agent

    @property
    def location(self) -> Optional[str]:
        """Geographic location from IP."""
        return self._refresh_token.location

    @property
    def created_at(self) -> datetime:
        """Session creation timestamp."""
        return self._refresh_token.created_at

    @property
    def last_activity(self) -> Optional[datetime]:
        """Last activity timestamp."""
        return self._refresh_token.last_used_at

    @property
    def expires_at(self) -> Optional[datetime]:
        """Session expiration timestamp."""
        return self._refresh_token.expires_at

    @property
    def is_revoked(self) -> bool:
        """Whether session is revoked."""
        return self._refresh_token.is_revoked

    @property
    def is_trusted(self) -> bool:
        """Whether device is trusted."""
        return self._refresh_token.is_trusted_device

    @property
    def revoked_at(self) -> Optional[datetime]:
        """When session was revoked."""
        return self._refresh_token.revoked_at

    @property
    def revoked_reason(self) -> Optional[str]:
        """Why session was revoked (not in RefreshToken, returns None)."""
        # RefreshToken doesn't have this field, but SessionBase requires it
        # We could store this in a separate table or just return None for now
        return None

    def is_active(self) -> bool:
        """Check if session is active (not revoked, not expired).

        Implements SessionBase.is_active() business logic.

        Returns:
            True if session is active, False otherwise
        """
        if self.is_revoked:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    @property
    def refresh_token(self) -> RefreshToken:
        """Access underlying RefreshToken (for persistence operations).

        Returns:
            Wrapped RefreshToken instance
        """
        return self._refresh_token
