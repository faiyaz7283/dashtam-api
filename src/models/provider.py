"""Database models for provider connections and token management.

This module implements a simplified provider connection system where users can
create multiple named instances of the same provider type. Each provider instance
represents a unique connection to a financial institution with its own authentication.

The key design principles:
- Users can have multiple instances of the same provider (multi-account support)
- Each instance has a user-defined alias for easy identification
- Simple one-to-one relationships: Provider → Connection → Token
- Provider keys must match registered providers in the registry
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID
from enum import Enum

from sqlmodel import Field, Relationship, Column, JSON
from sqlalchemy import Text, UniqueConstraint, DateTime
from pydantic import field_validator

from src.models.base import DashtamBase
from src.models.user import User


class ProviderStatus(str, Enum):
    """Status of a provider connection."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"
    PENDING = "pending"


class Provider(DashtamBase, table=True):
    """User's provider instances.

    Each row represents a user's connection to a financial provider.
    Users can have multiple instances of the same provider with different
    aliases (e.g., "Schwab Personal" and "Schwab 401k").

    Attributes:
        user_id: The user who owns this provider instance.
        provider_key: The provider identifier (must match registry).
        alias: User's custom name for this instance.
        is_active: Whether this instance is currently active.
        metadata: Additional user-specific metadata.
    """

    __tablename__ = "providers"

    # Core fields
    user_id: UUID = Field(
        foreign_key="users.id",
        index=True,
        description="User who owns this provider instance",
    )

    provider_key: str = Field(
        index=True, description="Provider identifier (e.g., 'schwab', 'chase')"
    )

    alias: str = Field(
        description="User's custom name for this connection (e.g., 'Schwab Personal')"
    )

    # Additional fields
    provider_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="User-specific metadata for this instance",
    )

    # Ensure unique aliases per user
    __table_args__ = (
        UniqueConstraint("user_id", "alias", name="unique_user_provider_alias"),
    )

    # Relationships
    user: Optional["User"] = Relationship(back_populates="providers")
    connection: Optional["ProviderConnection"] = Relationship(
        back_populates="provider",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )

    @field_validator("provider_key")
    @classmethod
    def validate_provider_key(cls, v: str) -> str:
        """Validate that provider_key exists in the registry.

        This validation happens at the application level.
        The actual check against the registry should be done in the service layer.
        """
        # Note: We can't import ProviderRegistry here due to circular imports
        # Validation should be done in the service/API layer
        return v.lower().strip()

    @property
    def is_connected(self) -> bool:
        """Check if this provider has an active connection."""
        return (
            self.connection is not None
            and self.connection.status == ProviderStatus.ACTIVE
        )

    @property
    def needs_reconnection(self) -> bool:
        """Check if this provider needs to be reconnected."""
        if not self.connection:
            return True
        return self.connection.status in [
            ProviderStatus.EXPIRED,
            ProviderStatus.REVOKED,
            ProviderStatus.ERROR,
        ]

    @property
    def display_status(self) -> str:
        """Get a user-friendly status string."""
        if not self.connection:
            return "Not Connected"
        return self.connection.status.value.title()


class ProviderConnection(DashtamBase, table=True):
    """Connection details for a provider instance.

    Each provider instance has exactly one connection that manages the
    authentication state and sync schedule.

    Attributes:
        provider_id: The provider instance this connection belongs to.
        status: Current status of the connection.
        connected_at: When the connection was established.
        last_sync_at: When data was last synced.
        next_sync_at: When the next sync should occur.
        sync_frequency_minutes: How often to sync data.
        error_message: Last error message if any.
        error_count: Number of consecutive errors.
        accounts_count: Number of accounts accessible.
        accounts_list: List of account IDs accessible.
    """

    __tablename__ = "provider_connections"

    # One-to-one with Provider
    provider_id: UUID = Field(
        foreign_key="providers.id",
        unique=True,
        index=True,
        description="The provider instance this connection belongs to",
    )

    # Connection status
    status: ProviderStatus = Field(
        default=ProviderStatus.PENDING,
        index=True,
        description="Current connection status",
    )

    connected_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="When connection was first established",
    )

    # Sync tracking
    last_sync_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Last successful data sync",
    )

    next_sync_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        index=True,
        description="Next scheduled sync",
    )

    sync_frequency_minutes: int = Field(default=60, description="Minutes between syncs")

    # Error tracking
    error_message: Optional[str] = Field(
        default=None, sa_column=Column(Text), description="Last error message if any"
    )

    error_count: int = Field(default=0, description="Consecutive error count")

    # Account information
    accounts_count: int = Field(default=0, description="Number of accounts accessible")

    accounts_list: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="List of account IDs accessible",
    )

    # Relationships
    provider: Provider = Relationship(back_populates="connection")
    token: Optional["ProviderToken"] = Relationship(
        back_populates="connection",
        sa_relationship_kwargs={"uselist": False, "cascade": "all, delete-orphan"},
    )
    audit_logs: List["ProviderAuditLog"] = Relationship(
        back_populates="connection", cascade_delete=True
    )

    # Validators to ensure timezone awareness
    @field_validator("connected_at", "last_sync_at", "next_sync_at", mode="before")
    @classmethod
    def ensure_timezone_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware (UTC)."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    def mark_connected(self) -> None:
        """Mark the connection as successfully connected."""
        self.status = ProviderStatus.ACTIVE
        self.connected_at = datetime.now(timezone.utc)
        self.error_count = 0
        self.error_message = None
        self.schedule_next_sync()

    def schedule_next_sync(self) -> None:
        """Schedule the next sync based on frequency."""
        self.next_sync_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.sync_frequency_minutes
        )

    def mark_sync_successful(self, accounts: Optional[List[str]] = None) -> None:
        """Mark a sync as successful and schedule next one.

        Args:
            accounts: Optional list of account IDs that were synced.
        """
        self.last_sync_at = datetime.now(timezone.utc)
        self.error_count = 0
        self.error_message = None
        self.status = ProviderStatus.ACTIVE

        if accounts is not None:
            self.accounts_list = accounts
            self.accounts_count = len(accounts)

        self.schedule_next_sync()

    def mark_sync_failed(self, error_message: str) -> None:
        """Mark a sync as failed and increment error count.

        Args:
            error_message: Description of the error that occurred.
        """
        self.error_count += 1
        self.error_message = error_message

        # Set status to error after 3 consecutive failures
        if self.error_count >= 3:
            self.status = ProviderStatus.ERROR

        # Schedule next sync with exponential backoff
        backoff_minutes = min(
            self.sync_frequency_minutes * (2**self.error_count),
            1440,  # Max 24 hours
        )
        self.next_sync_at = datetime.now(timezone.utc) + timedelta(
            minutes=backoff_minutes
        )


class ProviderToken(DashtamBase, table=True):
    """OAuth tokens for a provider connection.

    Each connection has exactly one token record that stores encrypted
    OAuth credentials. Tokens are automatically refreshed when expired.

    The tokens are encrypted before storage for security. The encryption
    is handled by the TokenService layer.

    Attributes:
        connection_id: The connection this token belongs to.
        access_token_encrypted: Encrypted OAuth access token.
        refresh_token_encrypted: Encrypted OAuth refresh token.
        id_token: JWT ID token if provided (for identifying unique connections).
        token_type: Type of token (usually 'Bearer').
        expires_at: When the access token expires.
        scope: OAuth scopes granted.
        last_refreshed_at: When token was last refreshed.
        refresh_count: Number of times refreshed.
    """

    __tablename__ = "provider_tokens"

    # One-to-one with ProviderConnection
    connection_id: UUID = Field(
        foreign_key="provider_connections.id",
        unique=True,
        index=True,
        description="The connection this token belongs to",
    )

    # Encrypted token data
    access_token_encrypted: str = Field(
        sa_column=Column(Text), description="Encrypted OAuth access token"
    )

    refresh_token_encrypted: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="Encrypted OAuth refresh token",
    )

    # ID token for provider identification (not encrypted as it's already a JWT)
    id_token: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
        description="JWT ID token from provider (used for deduplication)",
    )

    # Token metadata
    token_type: str = Field(default="Bearer", description="Type of token")

    expires_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        index=True,
        description="Access token expiration",
    )

    scope: Optional[str] = Field(default=None, description="OAuth scopes granted")

    # Refresh tracking
    last_refreshed_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        description="Last refresh timestamp",
    )

    refresh_count: int = Field(default=0, description="Number of refreshes")

    # Relationships
    connection: ProviderConnection = Relationship(back_populates="token")

    # Validators to ensure timezone awareness
    @field_validator("expires_at", "last_refreshed_at", mode="before")
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
        """Check if the access token is expired.

        Returns:
            True if the token has expired, False otherwise.
        """
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def is_expiring_soon(self) -> bool:
        """Check if token expires within 5 minutes.

        Returns:
            True if the token expires within 5 minutes, False otherwise.
        """
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) >= (self.expires_at - timedelta(minutes=5))

    @property
    def needs_refresh(self) -> bool:
        """Check if token should be refreshed."""
        return self.is_expired or self.is_expiring_soon

    def update_tokens(
        self,
        access_token_encrypted: str,
        refresh_token_encrypted: Optional[str] = None,
        expires_in: Optional[int] = None,
        id_token: Optional[str] = None,
    ) -> None:
        """Update tokens from a refresh response.

        Handles token rotation if the provider sends a new refresh token.

        Args:
            access_token_encrypted: New encrypted access token.
            refresh_token_encrypted: New encrypted refresh token (if rotated).
            expires_in: Token lifetime in seconds.
            id_token: New ID token if provided.
        """
        self.access_token_encrypted = access_token_encrypted

        # Handle token rotation - update refresh token if provider sends new one
        if refresh_token_encrypted:
            self.refresh_token_encrypted = refresh_token_encrypted

        if expires_in:
            self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        if id_token:
            self.id_token = id_token

        self.last_refreshed_at = datetime.now(timezone.utc)
        self.refresh_count += 1


class ProviderAuditLog(DashtamBase, table=True):
    """Audit log for provider operations.

    Tracks all significant operations on provider connections for debugging,
    security, and compliance purposes. This provides a complete audit trail
    of all provider-related activities.

    Attributes:
        connection_id: The connection this log entry relates to.
        user_id: User who performed the action.
        action: Type of action performed.
        details: Additional details about the action.
        ip_address: IP address of the request.
        user_agent: User agent string.
    """

    __tablename__ = "provider_audit_logs"

    # References
    connection_id: UUID = Field(
        foreign_key="provider_connections.id",
        index=True,
        description="Connection this log relates to",
    )

    user_id: UUID = Field(
        foreign_key="users.id", index=True, description="User who performed the action"
    )

    # Log details
    action: str = Field(index=True, description="Action performed")

    # Common action types
    # - provider_created: New provider instance created
    # - connection_initiated: OAuth flow started
    # - token_created: Initial tokens stored
    # - token_refreshed: Access token refreshed
    # - token_refresh_failed: Refresh attempt failed
    # - sync_started: Data sync initiated
    # - sync_completed: Data sync successful
    # - sync_failed: Data sync failed
    # - connection_revoked: User revoked connection
    # - connection_error: Connection entered error state

    details: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Additional action details",
    )

    # Request information
    ip_address: Optional[str] = Field(
        default=None, description="IP address of the request"
    )

    user_agent: Optional[str] = Field(
        default=None, sa_column=Column(Text), description="User agent of the request"
    )

    # Relationships
    connection: ProviderConnection = Relationship(back_populates="audit_logs")

    @classmethod
    def log_action(
        cls,
        connection_id: UUID,
        user_id: UUID,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> "ProviderAuditLog":
        """Factory method to create an audit log entry.

        Args:
            connection_id: The connection this action relates to.
            user_id: User who performed the action.
            action: Description of the action.
            details: Additional context about the action.
            ip_address: Client IP address if available.
            user_agent: Client user agent if available.

        Returns:
            New audit log entry (not yet persisted).
        """
        return cls(
            connection_id=connection_id,
            user_id=user_id,
            action=action,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
