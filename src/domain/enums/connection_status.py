"""Provider connection lifecycle states.

Defines the status state machine for provider connections.

State Machine:
    PENDING → ACTIVE ↔ EXPIRED/REVOKED → DISCONNECTED

    - PENDING: Auth initiated, awaiting completion
    - ACTIVE: Connected with valid credentials
    - EXPIRED: Credentials expired, needs re-auth
    - REVOKED: Access revoked by user or provider
    - FAILED: Authentication failed
    - DISCONNECTED: User explicitly disconnected (terminal)

Reference:
    - docs/architecture/provider-domain-model.md

Usage:
    from src.domain.enums import ConnectionStatus

    if connection.status == ConnectionStatus.ACTIVE:
        # Connection is usable
"""

from enum import Enum


class ConnectionStatus(str, Enum):
    """Provider connection lifecycle states.

    Defines valid states for a provider connection and the transitions
    between them. Used to track connection health and determine if
    credentials need refresh or re-authentication.

    String Enum:
        Inherits from str for easy serialization and database storage.
        Values are lowercase for consistency.

    State Transitions:
        PENDING → ACTIVE: Successful authentication
        PENDING → FAILED: Authentication failed or timed out
        ACTIVE → EXPIRED: Credentials past expiration
        ACTIVE → REVOKED: User or provider revoked access
        EXPIRED → ACTIVE: Successful re-authentication
        REVOKED → ACTIVE: Successful re-authentication
        Any → DISCONNECTED: User explicitly disconnects (terminal)
    """

    PENDING = "pending"
    """Authentication initiated, awaiting completion.

    Initial state when user starts provider connection flow.
    Transitions to ACTIVE on success, FAILED on error.
    """

    ACTIVE = "active"
    """Connected with valid credentials.

    Connection is healthy and can be used for data sync.
    Credentials are valid and not expired.
    """

    EXPIRED = "expired"
    """Credentials expired, needs re-authentication.

    Connection was previously active but credentials have expired.
    User must re-authenticate to restore connection.
    """

    REVOKED = "revoked"
    """Access revoked by user or provider.

    Provider or user explicitly revoked access.
    Differs from EXPIRED in that credentials are invalid
    regardless of expiration time.
    """

    FAILED = "failed"
    """Authentication failed.

    Initial authentication attempt failed.
    User may retry the connection flow.
    """

    DISCONNECTED = "disconnected"
    """User explicitly disconnected.

    Terminal state - user has removed this connection.
    Credentials are cleared and connection is inactive.
    """

    @classmethod
    def values(cls) -> list[str]:
        """Get all status values as strings.

        Returns:
            list[str]: List of status values.
        """
        return [status.value for status in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid status.

        Args:
            value: String to check.

        Returns:
            bool: True if value is a valid status.
        """
        return value in cls.values()

    @classmethod
    def active_states(cls) -> list["ConnectionStatus"]:
        """Get states where connection is usable.

        Returns:
            list[ConnectionStatus]: States where sync is possible.
        """
        return [cls.ACTIVE]

    @classmethod
    def needs_reauth_states(cls) -> list["ConnectionStatus"]:
        """Get states requiring re-authentication.

        Returns:
            list[ConnectionStatus]: States needing user action.
        """
        return [cls.EXPIRED, cls.REVOKED, cls.FAILED]

    @classmethod
    def terminal_states(cls) -> list["ConnectionStatus"]:
        """Get terminal states (no recovery).

        Returns:
            list[ConnectionStatus]: Terminal states.
        """
        return [cls.DISCONNECTED]
