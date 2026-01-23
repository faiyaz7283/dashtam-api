"""Server-Sent Events (SSE) event types and data structures.

This module defines the SSE event format for real-time client notifications.
SSE events are the wire format sent to clients - they're distinct from domain
events, which represent internal business occurrences.

Architecture:
    - SSEEvent: Immutable dataclass representing an SSE message
    - SSEEventType: Enum of all valid event types (SSOT)
    - SSEEventCategory: Categories for client-side filtering
    - to_sse_format(): Serialization to SSE wire format (text/event-stream)

Wire Format (SSE spec):
    id: <event_id>
    event: <event_type>
    retry: <reconnect_ms>
    data: <json_payload>

Reference:
    - docs/architecture/sse-architecture.md
    - https://html.spec.whatwg.org/multipage/server-sent-events.html
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from uuid_extensions import uuid7


class SSEEventCategory(StrEnum):
    """Categories for SSE event filtering.

    Clients can subscribe to specific categories via query params:
        GET /api/v1/events?categories=data_sync,provider

    Categories group related event types for efficient filtering.
    """

    DATA_SYNC = "data_sync"
    """Account, transaction, and holdings sync events."""

    PROVIDER = "provider"
    """Provider connection health and token events."""

    AI = "ai"
    """AI assistant response streaming events."""

    IMPORT = "import"
    """File import progress events."""

    PORTFOLIO = "portfolio"
    """Balance and holdings update events."""

    SECURITY = "security"
    """Session and security notification events."""


class SSEEventType(StrEnum):
    """All SSE event types (Single Source of Truth).

    Event naming convention:
        {category}.{resource}.{action}

    Examples:
        - sync.accounts.started
        - provider.token.expiring
        - ai.response.chunk

    Note:
        These are SSE event types sent to clients, NOT domain event names.
        Domain events use PascalCase (AccountSyncSucceeded).
        SSE events use dot-notation (sync.accounts.completed).
    """

    # =========================================================================
    # DATA SYNC EVENTS
    # =========================================================================
    SYNC_ACCOUNTS_STARTED = "sync.accounts.started"
    SYNC_ACCOUNTS_COMPLETED = "sync.accounts.completed"
    SYNC_ACCOUNTS_FAILED = "sync.accounts.failed"

    SYNC_TRANSACTIONS_STARTED = "sync.transactions.started"
    SYNC_TRANSACTIONS_COMPLETED = "sync.transactions.completed"
    SYNC_TRANSACTIONS_FAILED = "sync.transactions.failed"

    SYNC_HOLDINGS_STARTED = "sync.holdings.started"
    SYNC_HOLDINGS_COMPLETED = "sync.holdings.completed"
    SYNC_HOLDINGS_FAILED = "sync.holdings.failed"

    # =========================================================================
    # PROVIDER EVENTS
    # =========================================================================
    PROVIDER_TOKEN_EXPIRING = "provider.token.expiring"
    PROVIDER_TOKEN_REFRESHED = "provider.token.refreshed"
    PROVIDER_TOKEN_FAILED = "provider.token.failed"
    PROVIDER_DISCONNECTED = "provider.disconnected"

    # =========================================================================
    # AI EVENTS
    # =========================================================================
    AI_RESPONSE_CHUNK = "ai.response.chunk"
    AI_TOOL_EXECUTING = "ai.tool.executing"
    AI_RESPONSE_COMPLETE = "ai.response.complete"

    # =========================================================================
    # IMPORT EVENTS
    # =========================================================================
    IMPORT_STARTED = "import.started"
    IMPORT_PROGRESS = "import.progress"
    IMPORT_COMPLETED = "import.completed"
    IMPORT_FAILED = "import.failed"

    # =========================================================================
    # PORTFOLIO EVENTS
    # =========================================================================
    PORTFOLIO_BALANCE_UPDATED = "portfolio.balance.updated"
    PORTFOLIO_HOLDINGS_UPDATED = "portfolio.holdings.updated"

    # =========================================================================
    # SECURITY EVENTS
    # =========================================================================
    SECURITY_SESSION_NEW = "security.session.new"
    SECURITY_SESSION_SUSPICIOUS = "security.session.suspicious"
    SECURITY_SESSION_EXPIRING = "security.session.expiring"
    SECURITY_SESSION_REVOKED = "security.session.revoked"
    SECURITY_PASSWORD_CHANGED = "security.password.changed"
    SECURITY_LOGIN_FAILED = "security.login.failed"


# Mapping from event type to category for filtering
_EVENT_TYPE_TO_CATEGORY: dict[SSEEventType, SSEEventCategory] = {
    # Data Sync
    SSEEventType.SYNC_ACCOUNTS_STARTED: SSEEventCategory.DATA_SYNC,
    SSEEventType.SYNC_ACCOUNTS_COMPLETED: SSEEventCategory.DATA_SYNC,
    SSEEventType.SYNC_ACCOUNTS_FAILED: SSEEventCategory.DATA_SYNC,
    SSEEventType.SYNC_TRANSACTIONS_STARTED: SSEEventCategory.DATA_SYNC,
    SSEEventType.SYNC_TRANSACTIONS_COMPLETED: SSEEventCategory.DATA_SYNC,
    SSEEventType.SYNC_TRANSACTIONS_FAILED: SSEEventCategory.DATA_SYNC,
    SSEEventType.SYNC_HOLDINGS_STARTED: SSEEventCategory.DATA_SYNC,
    SSEEventType.SYNC_HOLDINGS_COMPLETED: SSEEventCategory.DATA_SYNC,
    SSEEventType.SYNC_HOLDINGS_FAILED: SSEEventCategory.DATA_SYNC,
    # Provider
    SSEEventType.PROVIDER_TOKEN_EXPIRING: SSEEventCategory.PROVIDER,
    SSEEventType.PROVIDER_TOKEN_REFRESHED: SSEEventCategory.PROVIDER,
    SSEEventType.PROVIDER_TOKEN_FAILED: SSEEventCategory.PROVIDER,
    SSEEventType.PROVIDER_DISCONNECTED: SSEEventCategory.PROVIDER,
    # AI
    SSEEventType.AI_RESPONSE_CHUNK: SSEEventCategory.AI,
    SSEEventType.AI_TOOL_EXECUTING: SSEEventCategory.AI,
    SSEEventType.AI_RESPONSE_COMPLETE: SSEEventCategory.AI,
    # Import
    SSEEventType.IMPORT_STARTED: SSEEventCategory.IMPORT,
    SSEEventType.IMPORT_PROGRESS: SSEEventCategory.IMPORT,
    SSEEventType.IMPORT_COMPLETED: SSEEventCategory.IMPORT,
    SSEEventType.IMPORT_FAILED: SSEEventCategory.IMPORT,
    # Portfolio
    SSEEventType.PORTFOLIO_BALANCE_UPDATED: SSEEventCategory.PORTFOLIO,
    SSEEventType.PORTFOLIO_HOLDINGS_UPDATED: SSEEventCategory.PORTFOLIO,
    # Security
    SSEEventType.SECURITY_SESSION_NEW: SSEEventCategory.SECURITY,
    SSEEventType.SECURITY_SESSION_SUSPICIOUS: SSEEventCategory.SECURITY,
    SSEEventType.SECURITY_SESSION_EXPIRING: SSEEventCategory.SECURITY,
    SSEEventType.SECURITY_SESSION_REVOKED: SSEEventCategory.SECURITY,
    SSEEventType.SECURITY_PASSWORD_CHANGED: SSEEventCategory.SECURITY,
    SSEEventType.SECURITY_LOGIN_FAILED: SSEEventCategory.SECURITY,
}


def get_category_for_event_type(event_type: SSEEventType) -> SSEEventCategory:
    """Get the category for an SSE event type.

    Args:
        event_type: The SSE event type.

    Returns:
        The category the event type belongs to.

    Raises:
        KeyError: If event type is not mapped (indicates registry bug).
    """
    return _EVENT_TYPE_TO_CATEGORY[event_type]


@dataclass(frozen=True, kw_only=True, slots=True)
class SSEEvent:
    """Server-Sent Event data structure.

    Represents a single SSE message to be sent to connected clients.
    Immutable after creation (frozen dataclass).

    Attributes:
        event_id: Unique identifier for this event (UUID v7 for ordering).
        event_type: Type of event (from SSEEventType enum).
        user_id: Target user for this event (for channel routing).
        data: Event payload (will be JSON serialized).
        occurred_at: When the event occurred (UTC).

    Example:
        >>> event = SSEEvent(
        ...     event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
        ...     user_id=user_id,
        ...     data={"connection_id": str(conn_id), "account_count": 3},
        ... )
        >>> print(event.to_sse_format())
        id: 01234567-89ab-cdef-0123-456789abcdef
        event: sync.accounts.completed
        data: {"connection_id": "...", "account_count": 3}
    """

    event_type: SSEEventType
    """Type of SSE event (determines client handling)."""

    user_id: UUID
    """Target user ID (for Redis channel routing)."""

    data: dict[str, Any]
    """Event payload (JSON serializable)."""

    event_id: UUID = field(default_factory=uuid7)
    """Unique event identifier (UUID v7 for temporal ordering)."""

    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """Timestamp when event occurred (UTC)."""

    @property
    def category(self) -> SSEEventCategory:
        """Get the category for this event type.

        Returns:
            The category this event belongs to.
        """
        return get_category_for_event_type(self.event_type)

    def to_sse_format(self) -> str:
        """Serialize to SSE wire format.

        Returns:
            SSE-formatted string ready for streaming response.

        Example output:
            id: 01234567-89ab-cdef-0123-456789abcdef
            event: sync.accounts.completed
            data: {"connection_id": "abc", "account_count": 3}

        Note:
            - Each field ends with newline
            - Message ends with double newline (SSE spec)
            - Data is JSON serialized
            - Comments (lines starting with :) are ignored by clients
        """
        import json

        lines = [
            f"id: {self.event_id}",
            f"event: {self.event_type.value}",
            f"data: {json.dumps(self.data)}",
            "",  # Empty line terminates the message
        ]
        return "\n".join(lines) + "\n"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Redis storage/transmission.

        Returns:
            Dictionary representation of the event.
        """
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "user_id": str(self.user_id),
            "data": self.data,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SSEEvent":
        """Create SSEEvent from dictionary (Redis deserialization).

        Args:
            data: Dictionary with event data.

        Returns:
            SSEEvent instance.

        Raises:
            KeyError: If required fields are missing.
            ValueError: If field values are invalid.
        """
        return cls(
            event_id=UUID(data["event_id"]),
            event_type=SSEEventType(data["event_type"]),
            user_id=UUID(data["user_id"]),
            data=data["data"],
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
        )
