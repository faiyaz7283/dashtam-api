# Server-Sent Events (SSE) Architecture

## 1. Overview

This document defines the **foundational architecture** for Server-Sent Events (SSE) in Dashtam API. SSE enables real-time push notifications from server to connected clients (dashtam-terminal, future web dashboard).

**Scope**: This document covers **core infrastructure only**. Individual use cases (sync progress, provider health, etc.) are tracked as separate GitHub issues and reference this foundation.

### 1.1 Technology Decision: SSE vs WebSocket

**Decision**: SSE for v1 (WebSocket deferred to v2 if bidirectional needs arise)

| Aspect | SSE | WebSocket |
|--------|-----|-----------|
| Direction | Server → Client (unidirectional) | Bidirectional |
| Protocol | HTTP/1.1 or HTTP/2 | WS/WSS (upgrade) |
| Reconnection | Built-in (automatic) | Manual implementation |
| Proxy/Firewall | Works through standard HTTP | May have issues |
| Complexity | Lower | Higher |
| Dashtam Fit | ✅ 90% of use cases | ❌ Overkill for v1 |

SSE covers all identified use cases: sync progress, provider health, balance updates, AI streaming, notifications.

### 1.2 REST Compliance

SSE is **pure HTTP** — no protocol upgrade like WebSocket. It uses standard GET requests with streaming responses. Dashtam's 100% RESTful API requirement applies.

**Endpoint Design**:

- **Resource**: `events` (noun, not verb)
- **Method**: `GET /api/v1/events` (retrieves event stream)
- **Content Type**: `Accept: text/event-stream` signals streaming format
- **Filtering**: Query params (`?categories=data_sync,provider`)

**Why not `/events/stream`?** The `/stream` suffix is a verb, violating REST. The streaming behavior is determined by the `Accept` header, not the URL.

### 1.3 Architectural Principles

1. **Registry Pattern (SSOT)**: All SSE event types defined in `SSE_EVENT_REGISTRY`
2. **Hexagonal Architecture**: Protocol in domain, adapters in infrastructure
3. **Domain Event Integration**: Bridge existing domain events to SSE streams
4. **Fail-Open Design**: SSE failures don't break core API functionality
5. **Horizontal Scaling**: Redis Pub/Sub for multi-instance deployments
6. **DRY Compliance**: Reuse existing patterns (constants, serialization, auth)
7. **Existing Auth**: Uses standard Dashtam Bearer token authentication

```text
┌─────────────────────────────────────────────────────────────────────────┐
│  Clients (dashtam-terminal, web dashboard)                              │
│  - httpx-sse (Python) / EventSource (JavaScript)                        │
│  - Reconnects automatically with Last-Event-ID                          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ SSE Connection (HTTP)
                                │ GET /api/v1/events
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Presentation Layer                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  SSE Stream Endpoint (FastAPI StreamingResponse)                │    │
│  │  - Authenticates via Bearer token                               │    │
│  │  - Subscribes to user's Redis channel                           │    │
│  │  - Streams events as text/event-stream                          │    │
│  └───────────────────────────────┬─────────────────────────────────┘    │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼──────────────────────────────────────┐
│  Infrastructure Layer            │                                      │
│  ┌───────────────────────────────┼─────────────────────────────────┐    │
│  │  SSE Publisher (Adapter)      │                                 │    │
│  │  - Implements SSEPublisherProtocol                              │    │
│  │  - Publishes to Redis channels                                  │    │
│  │  - Serializes SSE events to JSON                                │    │
│  └───────────────────────────────┬─────────────────────────────────┘    │
│                                  │                                      │
│  ┌───────────────────────────────┼─────────────────────────────────┐    │
│  │  SSE Event Handler            │                                 │    │
│  │  - Subscribes to domain events (via EVENT_BUS)                  │    │
│  │  - Maps domain events → SSE events (using SSE_EVENT_REGISTRY)   │    │
│  │  - Calls publisher to broadcast                                 │    │
│  └───────────────────────────────┬─────────────────────────────────┘    │
│                                  │                                      │
│  ┌───────────────────────────────▼─────────────────────────────────┐    │
│  │  Redis Pub/Sub                                                  │    │
│  │  - Channel per user: sse:user:{user_id}                         │    │
│  │  - Enables horizontal scaling (multiple API instances)          │    │
│  │  - Event retention: Redis Streams (optional, for Last-Event-ID) │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                   ▲
┌──────────────────────────────────┼──────────────────────────────────────┐
│  Application Layer               │                                      │
│  ┌───────────────────────────────┼─────────────────────────────────┐    │
│  │  Command Handlers (existing)  │                                 │    │
│  │  - SyncAccountsHandler        │                                 │    │
│  │  - SyncTransactionsHandler    │                                 │    │
│  │  - ImportFromFileHandler      │                                 │    │
│  │  ... publish domain events as normal ...                        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                   ▲
┌──────────────────────────────────┼──────────────────────────────────────┐
│  Domain Layer                    │                                      │
│  ┌───────────────────────────────┼─────────────────────────────────┐    │
│  │  Domain Events (existing)     │                                 │    │
│  │  - AccountSyncAttempted/Succeeded/Failed                        │    │
│  │  - TransactionSyncAttempted/Succeeded/Failed                    │    │
│  │  - ProviderTokenRefreshAttempted/Succeeded/Failed               │    │
│  │  - FileImportAttempted/Succeeded/Failed                         │    │
│  │  ... these trigger SSE broadcasts ...                           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  SSE Protocol (NEW)                                             │    │
│  │  - SSEPublisherProtocol                                         │    │
│  │  - SSEEvent dataclass                                           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. SSE Event Registry (Single Source of Truth)

Following the established registry pattern (EVENT_REGISTRY, COMMAND_REGISTRY, ROUTE_REGISTRY), SSE events are cataloged in `SSE_EVENT_REGISTRY`.

### 3.1 Registry Location

```text
src/domain/events/
├── registry.py              # Existing domain events registry
└── sse_registry.py          # NEW: SSE event registry
```

### 3.2 Registry Structure

```python
# src/domain/events/sse_registry.py
"""SSE Event Registry - Single Source of Truth.

This registry catalogs ALL SSE event types with their metadata.
Used for:
- SSE event handler auto-wiring (maps domain events → SSE events)
- Validation tests (verify no drift)
- Documentation generation (always accurate)
- Client SDK generation (event type definitions)

Adding new SSE events:
1. Add entry to SSE_EVENT_REGISTRY below
2. Implement payload schema (if not reusing domain event data)
3. Run tests - they'll tell you what's missing
"""

from dataclasses import dataclass
from enum import Enum
from typing import Type

from src.domain.events.base_event import DomainEvent


class SSECategory(Enum):
    """SSE event categories for filtering and organization."""
    
    DATA_SYNC = "data_sync"            # Account/transaction/holdings sync
    PROVIDER = "provider"              # Provider connection health
    AI = "ai"                          # AI response streaming
    IMPORT = "import"                  # File import progress
    PORTFOLIO = "portfolio"            # Balance/holdings updates
    SECURITY = "security"              # Session/security notifications


@dataclass(frozen=True)
class SSEEventMetadata:
    """Metadata for an SSE event type.
    
    Attributes:
        event_type: SSE event type string (e.g., "sync.progress").
        category: Event category for filtering.
        source_domain_events: Domain events that trigger this SSE event.
        description: Human-readable description.
        requires_auth: Whether SSE stream must be authenticated.
        payload_fields: List of fields included in payload.
    """
    
    event_type: str
    category: SSECategory
    source_domain_events: tuple[Type[DomainEvent], ...]
    description: str
    requires_auth: bool = True
    payload_fields: tuple[str, ...] = ()


# ═══════════════════════════════════════════════════════════════════════════
# SSE_EVENT_REGISTRY - Single Source of Truth
# ═══════════════════════════════════════════════════════════════════════════

SSE_EVENT_REGISTRY: list[SSEEventMetadata] = [
    # ═══════════════════════════════════════════════════════════════════════
    # Data Sync Events (6 event types)
    # Implementation: GitHub Issue #1 - SSE: Data Sync Progress
    # ═══════════════════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type="sync.accounts.started",
        category=SSECategory.DATA_SYNC,
        source_domain_events=(AccountSyncAttempted,),
        description="Account sync operation started",
        payload_fields=("connection_id", "user_id"),
    ),
    SSEEventMetadata(
        event_type="sync.accounts.completed",
        category=SSECategory.DATA_SYNC,
        source_domain_events=(AccountSyncSucceeded,),
        description="Account sync completed successfully",
        payload_fields=("connection_id", "user_id", "account_count"),
    ),
    SSEEventMetadata(
        event_type="sync.accounts.failed",
        category=SSECategory.DATA_SYNC,
        source_domain_events=(AccountSyncFailed,),
        description="Account sync failed",
        payload_fields=("connection_id", "user_id", "reason"),
    ),
    SSEEventMetadata(
        event_type="sync.transactions.started",
        category=SSECategory.DATA_SYNC,
        source_domain_events=(TransactionSyncAttempted,),
        description="Transaction sync operation started",
        payload_fields=("connection_id", "user_id", "account_id"),
    ),
    SSEEventMetadata(
        event_type="sync.transactions.completed",
        category=SSECategory.DATA_SYNC,
        source_domain_events=(TransactionSyncSucceeded,),
        description="Transaction sync completed successfully",
        payload_fields=("connection_id", "user_id", "account_id", "transaction_count"),
    ),
    SSEEventMetadata(
        event_type="sync.transactions.failed",
        category=SSECategory.DATA_SYNC,
        source_domain_events=(TransactionSyncFailed,),
        description="Transaction sync failed",
        payload_fields=("connection_id", "user_id", "account_id", "reason"),
    ),
    # ... Holdings sync events follow same pattern ...
    
    # ═══════════════════════════════════════════════════════════════════════
    # Provider Events (4 event types)
    # Implementation: GitHub Issue #2 - SSE: Provider Connection Health
    # ═══════════════════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type="provider.token.expiring",
        category=SSECategory.PROVIDER,
        source_domain_events=(),  # Generated by background job, not domain event
        description="Provider token expiring soon (proactive warning)",
        payload_fields=("connection_id", "provider_slug", "expires_in_seconds"),
    ),
    SSEEventMetadata(
        event_type="provider.token.refreshed",
        category=SSECategory.PROVIDER,
        source_domain_events=(ProviderTokenRefreshSucceeded,),
        description="Provider token refreshed successfully",
        payload_fields=("connection_id", "provider_slug"),
    ),
    SSEEventMetadata(
        event_type="provider.token.failed",
        category=SSECategory.PROVIDER,
        source_domain_events=(ProviderTokenRefreshFailed,),
        description="Provider token refresh failed (may need re-auth)",
        payload_fields=("connection_id", "provider_slug", "reason", "needs_reauth"),
    ),
    SSEEventMetadata(
        event_type="provider.disconnected",
        category=SSECategory.PROVIDER,
        source_domain_events=(ProviderDisconnectionSucceeded,),
        description="Provider connection disconnected",
        payload_fields=("connection_id", "provider_slug"),
    ),
    
    # ═══════════════════════════════════════════════════════════════════════
    # AI Events (3 event types)
    # Implementation: GitHub Issue #3 - SSE: AI Response Streaming
    # ═══════════════════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type="ai.response.chunk",
        category=SSECategory.AI,
        source_domain_events=(),  # Direct streaming, not domain event
        description="AI response text chunk (streaming)",
        payload_fields=("conversation_id", "chunk", "is_final"),
    ),
    SSEEventMetadata(
        event_type="ai.tool.executing",
        category=SSECategory.AI,
        source_domain_events=(),  # Direct streaming
        description="AI is executing a tool",
        payload_fields=("conversation_id", "tool_name"),
    ),
    SSEEventMetadata(
        event_type="ai.response.complete",
        category=SSECategory.AI,
        source_domain_events=(),  # Direct streaming
        description="AI response complete",
        payload_fields=("conversation_id", "actions_taken"),
    ),
    
    # ═══════════════════════════════════════════════════════════════════════
    # Import Events (3 event types)
    # Implementation: GitHub Issue #4 - SSE: File Import Progress
    # ═══════════════════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type="import.started",
        category=SSECategory.IMPORT,
        source_domain_events=(FileImportAttempted,),
        description="File import started",
        payload_fields=("user_id", "file_name", "file_format"),
    ),
    SSEEventMetadata(
        event_type="import.progress",
        category=SSECategory.IMPORT,
        source_domain_events=(),  # Progress events generated during import
        description="File import progress update",
        payload_fields=("user_id", "file_name", "progress_percent", "records_processed"),
    ),
    SSEEventMetadata(
        event_type="import.completed",
        category=SSECategory.IMPORT,
        source_domain_events=(FileImportSucceeded,),
        description="File import completed successfully",
        payload_fields=("user_id", "file_name", "account_count", "transaction_count"),
    ),
    
    # ═══════════════════════════════════════════════════════════════════════
    # Portfolio Events (3 event types)
    # Implementation: GitHub Issue #257 - SSE: Balance/Portfolio Updates
    # ═══════════════════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type="portfolio.balance.updated",
        category=SSECategory.PORTFOLIO,
        source_domain_events=(AccountBalanceUpdated,),
        description="Account balance updated after sync",
        payload_fields=("account_id", "previous_balance", "new_balance", "delta", "currency"),
    ),
    SSEEventMetadata(
        event_type="portfolio.holdings.updated",
        category=SSECategory.PORTFOLIO,
        source_domain_events=(AccountHoldingsUpdated,),
        description="Holdings updated after sync",
        payload_fields=("account_id", "holdings_count", "created_count", "updated_count", "deactivated_count"),
    ),
    SSEEventMetadata(
        event_type="portfolio.networth.updated",
        category=SSECategory.PORTFOLIO,
        source_domain_events=(PortfolioNetWorthRecalculated,),
        description="Portfolio net worth recalculated after sync",
        payload_fields=("previous_net_worth", "new_net_worth", "delta", "currency", "account_count"),
    ),
    
    # ═══════════════════════════════════════════════════════════════════════
    # Security Events (6 event types)
    # Implementation: GitHub Issue #258 - SSE: Security Notifications
    # ═══════════════════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type="security.session.new",
        category=SSECategory.SECURITY,
        source_domain_events=(SessionCreatedEvent,),
        description="New session created (login from new device)",
        payload_fields=("session_id", "device_info", "ip_address", "location"),
    ),
    SSEEventMetadata(
        event_type="security.session.suspicious",
        category=SSECategory.SECURITY,
        source_domain_events=(SuspiciousSessionActivityEvent,),
        description="Suspicious session activity detected",
        payload_fields=("session_id", "reason"),
    ),
    SSEEventMetadata(
        event_type="security.session.expiring",
        category=SSECategory.SECURITY,
        source_domain_events=(),  # Generated by background job (dashtam-jobs)
        description="Session expiring soon",
        payload_fields=("session_id", "expires_in_seconds"),
    ),
    SSEEventMetadata(
        event_type="security.session.revoked",
        category=SSECategory.SECURITY,
        source_domain_events=(SessionRevokedEvent,),
        description="Session revoked (logout or security action)",
        payload_fields=("session_id", "device_info", "reason"),
    ),
    SSEEventMetadata(
        event_type="security.password.changed",
        category=SSECategory.SECURITY,
        source_domain_events=(UserPasswordChangeSucceeded,),
        description="Password changed (security notification)",
        payload_fields=("initiated_by",),
    ),
    SSEEventMetadata(
        event_type="security.login.failed",
        category=SSECategory.SECURITY,
        source_domain_events=(UserLoginFailed,),  # user_id may be None
        description="Failed login attempt on account",
        payload_fields=("reason",),
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# Computed Views (for validation and introspection)
# ═══════════════════════════════════════════════════════════════════════════

def get_all_sse_event_types() -> list[str]:
    """Get all registered SSE event types."""
    return [meta.event_type for meta in SSE_EVENT_REGISTRY]


def get_sse_events_by_category(category: SSECategory) -> list[SSEEventMetadata]:
    """Get SSE events filtered by category."""
    return [meta for meta in SSE_EVENT_REGISTRY if meta.category == category]


def get_domain_event_to_sse_mapping() -> dict[Type[DomainEvent], list[str]]:
    """Get mapping from domain events to SSE event types.
    
    Used by SSEEventHandler to know which SSE events to broadcast
    when a domain event is published.
    """
    mapping: dict[Type[DomainEvent], list[str]] = {}
    for meta in SSE_EVENT_REGISTRY:
        for domain_event in meta.source_domain_events:
            if domain_event not in mapping:
                mapping[domain_event] = []
            mapping[domain_event].append(meta.event_type)
    return mapping


def get_statistics() -> dict[str, int | dict[str, int]]:
    """Get registry statistics."""
    from collections import Counter
    
    return {
        "total_events": len(SSE_EVENT_REGISTRY),
        "by_category": dict(Counter(meta.category.value for meta in SSE_EVENT_REGISTRY)),
        "domain_event_mapped": sum(
            1 for meta in SSE_EVENT_REGISTRY if meta.source_domain_events
        ),
        "direct_streaming": sum(
            1 for meta in SSE_EVENT_REGISTRY if not meta.source_domain_events
        ),
    }
```

### 3.3 Registry Benefits

| Benefit | Description |
|---------|-------------|
| Single Source of Truth | All SSE events defined in one place |
| Self-Enforcing | Tests fail if event handlers missing |
| Auto-Wiring | Container uses registry for domain→SSE mapping |
| Documentation | Always-accurate event catalog |
| Type Safety | Compile-time validation of event payloads |

## 4. Domain Layer (Protocols)

### 4.1 SSE Event Dataclass

```python
# src/domain/events/sse_event.py
"""SSE Event dataclass for structured event representation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SSEEvent:
    """Server-Sent Event representation.
    
    Follows SSE specification (https://html.spec.whatwg.org/multipage/server-sent-events.html):
    - id: Unique event ID (for Last-Event-ID reconnection)
    - event: Event type (maps to client event listeners)
    - data: JSON payload
    - retry: Reconnection time in milliseconds (optional)
    
    Attributes:
        id: Unique event identifier (UUID7 for ordering).
        event: Event type from SSE_EVENT_REGISTRY (e.g., "sync.progress").
        data: Event payload (serialized to JSON).
        occurred_at: When the event occurred.
        user_id: Target user for this event.
        retry: Optional reconnection interval hint (milliseconds).
    """
    
    id: UUID
    event: str
    data: dict[str, Any]
    occurred_at: datetime
    user_id: UUID
    retry: int | None = None
    
    def to_sse_format(self) -> str:
        """Serialize to SSE wire format.
        
        Returns:
            SSE-formatted string ready for streaming.
            
        Example:
            id: 01234567-89ab-cdef-0123-456789abcdef
            event: sync.progress
            data: {"connection_id": "...", "progress": 45}
            
        """
        import json
        
        lines = [
            f"id: {self.id}",
            f"event: {self.event}",
            f"data: {json.dumps(self.data)}",
        ]
        
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        
        # SSE events end with double newline
        return "\n".join(lines) + "\n\n"
```

### 4.2 SSE Publisher Protocol

```python
# src/domain/protocols/sse_publisher_protocol.py
"""SSE Publisher Protocol - what domain/application needs from SSE infrastructure."""

from typing import Protocol
from uuid import UUID

from src.core.result import Result
from src.domain.events.sse_event import SSEEvent


class SSEPublisherProtocol(Protocol):
    """Protocol for publishing SSE events to connected clients.
    
    Infrastructure adapters implement this without inheritance.
    Uses Result types for error handling with fail-open strategy.
    """
    
    async def publish(
        self,
        event: SSEEvent,
    ) -> Result[None, str]:
        """Publish SSE event to user's channel.
        
        Args:
            event: SSE event to publish (includes user_id).
        
        Returns:
            Result with None on success, or error message.
            
        Note:
            Fail-open: If Redis unavailable, log warning and continue.
            Event delivery is best-effort, not guaranteed.
        """
        ...
    
    async def publish_to_users(
        self,
        event: SSEEvent,
        user_ids: list[UUID],
    ) -> Result[int, str]:
        """Publish SSE event to multiple users.
        
        Args:
            event: SSE event to publish.
            user_ids: List of user IDs to receive event.
        
        Returns:
            Result with count of successful publishes, or error.
        """
        ...
    
    async def broadcast(
        self,
        event: SSEEvent,
    ) -> Result[int, str]:
        """Broadcast SSE event to all connected clients.
        
        Args:
            event: SSE event to broadcast.
        
        Returns:
            Result with count of channels published to, or error.
            
        Note:
            Use sparingly - prefer targeted publish() for user-specific events.
        """
        ...
```

### 4.3 SSE Subscriber Protocol

```python
# src/domain/protocols/sse_subscriber_protocol.py
"""SSE Subscriber Protocol - for consuming SSE events from Redis channels."""

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from src.domain.events.sse_event import SSEEvent


class SSESubscriberProtocol(Protocol):
    """Protocol for subscribing to SSE events from Redis channels.
    
    Used by SSE stream endpoint to yield events to connected clients.
    """
    
    async def subscribe(
        self,
        user_id: UUID,
        categories: list[str] | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """Subscribe to user's SSE channel.
        
        Args:
            user_id: User ID to subscribe to.
            categories: Optional filter for event categories.
                        If None, receives all events.
        
        Yields:
            SSEEvent objects as they're published.
            
        Note:
            This is a long-lived async generator. It yields events
            until the client disconnects or an error occurs.
        """
        ...
    
    async def get_missed_events(
        self,
        user_id: UUID,
        last_event_id: UUID,
        max_events: int = 100,
    ) -> list[SSEEvent]:
        """Get events missed since last_event_id.
        
        Called on reconnection when client provides Last-Event-ID header.
        
        Args:
            user_id: User ID.
            last_event_id: Last event ID received by client.
            max_events: Maximum events to return.
        
        Returns:
            List of missed events in chronological order.
            
        Note:
            Requires event retention (Redis Streams). If retention
            disabled, returns empty list.
        """
        ...
```

## 5. Infrastructure Layer (Adapters)

### 5.1 Directory Structure

```text
src/infrastructure/sse/
├── __init__.py
├── redis_publisher.py       # SSEPublisherProtocol implementation
├── redis_subscriber.py      # SSESubscriberProtocol implementation
├── sse_event_handler.py     # Subscribes to domain events, publishes SSE
└── channel_keys.py          # Redis channel naming conventions
```

### 5.2 Redis Channel Naming

```python
# src/infrastructure/sse/channel_keys.py
"""Redis channel naming conventions for SSE pub/sub."""

from uuid import UUID

from src.core.constants import SSE_CHANNEL_PREFIX


class SSEChannelKeys:
    """Centralized Redis channel key generation for SSE.
    
    Channel Pattern:
        sse:user:{user_id}              - Per-user event channel
        sse:broadcast                    - Global broadcast channel
        sse:stream:user:{user_id}       - Redis Stream for event retention
    
    Note: Prefix comes from src/core/constants.py (DRY compliance).
    """
    
    @staticmethod
    def user_channel(user_id: UUID) -> str:
        """Get Redis pub/sub channel for user."""
        return f"{SSE_CHANNEL_PREFIX}:user:{user_id}"
    
    @staticmethod
    def broadcast_channel() -> str:
        """Get Redis pub/sub channel for broadcasts."""
        return f"{SSE_CHANNEL_PREFIX}:broadcast"
    
    @staticmethod
    def user_stream(user_id: UUID) -> str:
        """Get Redis Stream key for event retention."""
        return f"{SSE_CHANNEL_PREFIX}:stream:user:{user_id}"
    
    @staticmethod
    def parse_user_id_from_channel(channel: str) -> UUID | None:
        """Extract user_id from channel name."""
        parts = channel.split(":")
        if len(parts) == 3 and parts[0] == SSE_CHANNEL_PREFIX and parts[1] == "user":
            try:
                return UUID(parts[2])
            except ValueError:
                return None
        return None
```

### 5.3 Redis Publisher Adapter

```python
# src/infrastructure/sse/redis_publisher.py
"""Redis implementation of SSEPublisherProtocol."""

import json
from uuid import UUID

from redis.asyncio import Redis

from src.core.result import Failure, Result, Success
from src.domain.events.sse_event import SSEEvent
from src.infrastructure.sse.channel_keys import SSEChannelKeys


class RedisSSEPublisher:
    """Redis Pub/Sub implementation of SSEPublisherProtocol.
    
    Publishes SSE events to Redis channels for distribution to
    connected clients. Supports event retention via Redis Streams.
    
    Note: Does NOT inherit from protocol (structural typing).
    """
    
    def __init__(
        self,
        redis_client: Redis,
        enable_retention: bool = False,
        retention_max_len: int = 1000,
        retention_ttl_seconds: int = 3600,
    ) -> None:
        """Initialize Redis SSE publisher.
        
        Args:
            redis_client: Async Redis client instance.
            enable_retention: Store events in Redis Streams for replay.
            retention_max_len: Max events per user stream.
            retention_ttl_seconds: TTL for retained events.
        """
        self._redis = redis_client
        self._enable_retention = enable_retention
        self._retention_max_len = retention_max_len
        self._retention_ttl = retention_ttl_seconds
    
    async def publish(self, event: SSEEvent) -> Result[None, str]:
        """Publish SSE event to user's channel."""
        try:
            channel = SSEChannelKeys.user_channel(event.user_id)
            payload = self._serialize_event(event)
            
            # Publish to pub/sub channel
            await self._redis.publish(channel, payload)
            
            # Optionally retain in Redis Stream
            if self._enable_retention:
                await self._retain_event(event)
            
            return Success(value=None)
            
        except Exception as e:
            # Fail-open: Log warning, don't break calling code
            return Failure(error=f"SSE publish failed: {e}")
    
    async def publish_to_users(
        self,
        event: SSEEvent,
        user_ids: list[UUID],
    ) -> Result[int, str]:
        """Publish SSE event to multiple users."""
        success_count = 0
        
        for user_id in user_ids:
            # Create event copy with different user_id
            user_event = SSEEvent(
                id=event.id,
                event=event.event,
                data=event.data,
                occurred_at=event.occurred_at,
                user_id=user_id,
                retry=event.retry,
            )
            result = await self.publish(user_event)
            if isinstance(result, Success):
                success_count += 1
        
        return Success(value=success_count)
    
    async def broadcast(self, event: SSEEvent) -> Result[int, str]:
        """Broadcast to all connected clients via broadcast channel."""
        try:
            channel = SSEChannelKeys.broadcast_channel()
            payload = self._serialize_event(event)
            
            # PUBSUB NUMSUB returns number of subscribers
            subscribers = await self._redis.pubsub_numsub(channel)
            count = subscribers.get(channel, 0) if subscribers else 0
            
            await self._redis.publish(channel, payload)
            
            return Success(value=count)
            
        except Exception as e:
            return Failure(error=f"SSE broadcast failed: {e}")
    
    def _serialize_event(self, event: SSEEvent) -> str:
        """Serialize event to JSON string."""
        return json.dumps({
            "id": str(event.id),
            "event": event.event,
            "data": event.data,
            "occurred_at": event.occurred_at.isoformat(),
            "user_id": str(event.user_id),
            "retry": event.retry,
        })
    
    async def _retain_event(self, event: SSEEvent) -> None:
        """Store event in Redis Stream for replay on reconnection."""
        stream_key = SSEChannelKeys.user_stream(event.user_id)
        payload = self._serialize_event(event)
        
        # XADD with MAXLEN for bounded retention
        await self._redis.xadd(
            stream_key,
            {"event": payload},
            maxlen=self._retention_max_len,
        )
        
        # Set TTL on stream
        await self._redis.expire(stream_key, self._retention_ttl)
```

### 5.4 SSE Event Handler (Domain Event Bridge)

```python
# src/infrastructure/sse/sse_event_handler.py
"""SSE Event Handler - bridges domain events to SSE streams."""

from datetime import UTC, datetime
from typing import Any

from uuid_extensions import uuid7

from src.domain.events.base_event import DomainEvent
from src.domain.events.sse_event import SSEEvent
from src.domain.events.sse_registry import (
    SSE_EVENT_REGISTRY,
    get_domain_event_to_sse_mapping,
)
from src.domain.protocols.logger_protocol import LoggerProtocol
from src.infrastructure.sse.redis_publisher import RedisSSEPublisher


class SSEEventHandler:
    """Handler that bridges domain events to SSE events.
    
    Subscribes to domain events via the event bus and publishes
    corresponding SSE events based on SSE_EVENT_REGISTRY mapping.
    
    Usage:
        # Container wiring (in get_event_bus)
        sse_handler = SSEEventHandler(publisher, logger)
        
        # For each domain event that maps to SSE:
        event_bus.subscribe(AccountSyncAttempted, sse_handler.handle)
    """
    
    def __init__(
        self,
        publisher: RedisSSEPublisher,
        logger: LoggerProtocol,
    ) -> None:
        """Initialize SSE event handler.
        
        Args:
            publisher: SSE publisher for broadcasting events.
            logger: Logger for observability.
        """
        self._publisher = publisher
        self._logger = logger
        self._mapping = get_domain_event_to_sse_mapping()
    
    async def handle(self, domain_event: DomainEvent) -> None:
        """Handle domain event by publishing corresponding SSE events.
        
        Args:
            domain_event: Domain event from event bus.
        """
        event_type = type(domain_event)
        sse_event_types = self._mapping.get(event_type, [])
        
        if not sse_event_types:
            return  # No SSE mapping for this domain event
        
        for sse_event_type in sse_event_types:
            # Find metadata for payload field extraction
            metadata = next(
                (m for m in SSE_EVENT_REGISTRY if m.event_type == sse_event_type),
                None,
            )
            
            if metadata is None:
                continue
            
            # Extract payload from domain event
            payload = self._extract_payload(domain_event, metadata.payload_fields)
            
            # Extract user_id from domain event
            user_id = getattr(domain_event, "user_id", None)
            if user_id is None:
                self._logger.warning(
                    "Domain event missing user_id, skipping SSE",
                    event_type=event_type.__name__,
                    sse_event_type=sse_event_type,
                )
                continue
            
            # Create and publish SSE event
            sse_event = SSEEvent(
                id=uuid7(),
                event=sse_event_type,
                data=payload,
                occurred_at=datetime.now(UTC),
                user_id=user_id,
            )
            
            result = await self._publisher.publish(sse_event)
            
            if isinstance(result, Failure):
                self._logger.warning(
                    "SSE publish failed (fail-open)",
                    error=result.error,
                    sse_event_type=sse_event_type,
                )
    
    def _extract_payload(
        self,
        event: DomainEvent,
        fields: tuple[str, ...],
    ) -> dict[str, Any]:
        """Extract payload fields from domain event."""
        payload: dict[str, Any] = {}
        
        for field in fields:
            value = getattr(event, field, None)
            if value is not None:
                # Convert UUIDs to strings for JSON serialization
                if hasattr(value, "hex"):  # UUID check
                    payload[field] = str(value)
                else:
                    payload[field] = value
        
        return payload
```

## 6. Container Wiring

### 6.1 Handler Pattern Clarification

**SSEEventHandler is NOT a CQRS handler** — it does not use `handler_factory()`.

| Aspect | CQRS Handlers | SSE Event Handler |
|--------|---------------|-------------------|
| Purpose | Handle HTTP commands/queries | Bridge domain events to SSE |
| Invocation | FastAPI `Depends()` per request | Event bus subscription at startup |
| Lifecycle | Request-scoped (new per request) | App-scoped singleton |
| Wiring | `handler_factory(HandlerClass)` | `event_bus.subscribe()` |
| Pattern | Same as `RegisterUserHandler` | Same as `LoggingEventHandler`, `AuditEventHandler` |

SSE handler follows the **existing event handler pattern** from `src/infrastructure/events/handlers/`.

### 6.2 SSE Container Module

```python
# src/core/container/sse.py
"""SSE dependency factories."""

from functools import lru_cache

from src.core.constants import (
    SSE_RETENTION_MAX_LEN_DEFAULT,
    SSE_RETENTION_TTL_DEFAULT,
)
from src.domain.protocols.sse_publisher_protocol import SSEPublisherProtocol


@lru_cache()
def get_sse_publisher() -> SSEPublisherProtocol:
    """Get SSE publisher singleton (app-scoped).
    
    Returns Redis-backed publisher for SSE event distribution.
    """
    from src.core.config import get_settings
    from src.core.container.infrastructure import get_redis_client
    from src.infrastructure.sse.redis_publisher import RedisSSEPublisher
    
    settings = get_settings()
    
    return RedisSSEPublisher(
        redis_client=get_redis_client(),
        enable_retention=settings.sse_enable_retention,
        retention_max_len=SSE_RETENTION_MAX_LEN_DEFAULT,
        retention_ttl_seconds=SSE_RETENTION_TTL_DEFAULT,
    )


def get_sse_subscriber() -> "SSESubscriberProtocol":
    """Get SSE subscriber (request-scoped).
    
    Returns Redis-backed subscriber for SSE stream consumption.
    Each SSE connection gets its own subscriber instance.
    """
    from src.core.container.infrastructure import get_redis_client
    from src.infrastructure.sse.redis_subscriber import RedisSSESubscriber
    
    return RedisSSESubscriber(redis_client=get_redis_client())
```

### 6.3 Event Bus Integration

In `src/core/container/events.py`, add SSE handler wiring **after existing handlers**:

```python
# Add to get_event_bus() after LoggingEventHandler, AuditEventHandler, etc.

# =========================================================================
# SSE EVENT HANDLER WIRING (Registry-driven)
# =========================================================================
# Same pattern as LoggingEventHandler and AuditEventHandler above.
# SSE handler subscribes to domain events and publishes to Redis channels.
from src.core.container.sse import get_sse_publisher
from src.domain.events.sse_registry import get_domain_event_to_sse_mapping
from src.infrastructure.sse.sse_event_handler import SSEEventHandler

sse_publisher = get_sse_publisher()
sse_handler = SSEEventHandler(publisher=sse_publisher, logger=logger)

# Subscribe SSE handler to all domain events that have SSE mappings
# (Registry-driven, same approach as EVENT_REGISTRY auto-wiring)
domain_to_sse = get_domain_event_to_sse_mapping()
for domain_event_class in domain_to_sse.keys():
    event_bus.subscribe(domain_event_class, sse_handler.handle)
```

## 7. Presentation Layer (SSE Endpoint)

### 7.1 SSE Stream Endpoint

```python
# src/presentation/routers/api/v1/events.py
"""SSE events stream endpoint."""

from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from src.core.container.sse import get_sse_subscriber
from src.domain.events.sse_registry import SSECategory
from src.presentation.dependencies.auth import get_current_user_id


router = APIRouter(prefix="/events", tags=["Events"])


@router.get("/")
async def get_events(
    request: Request,
    user_id: UUID = Depends(get_current_user_id),  # Existing auth dependency
    categories: list[str] | None = Query(
        default=None,
        description="Filter by event categories (e.g., data_sync, provider)",
    ),
    last_event_id: str | None = Query(
        default=None,
        alias="Last-Event-ID",
        description="Resume from last received event ID",
    ),
) -> StreamingResponse:
    """Stream real-time events via Server-Sent Events (SSE).
    
    **Authentication**: Standard Bearer token (same as all endpoints).
    
    Connect to receive push notifications for:
    - Data sync progress (accounts, transactions, holdings)
    - Provider connection health
    - Balance/portfolio updates
    - AI response streaming
    - Security notifications
    
    **Reconnection**: The client should automatically reconnect if
    disconnected. Include `Last-Event-ID` header to resume from
    where you left off (if event retention is enabled).
    
    **Categories**: Filter events by category:
    - `data_sync`: Account/transaction sync events
    - `provider`: Provider health events
    - `ai`: AI response streaming
    - `import`: File import progress
    - `portfolio`: Balance/holdings updates
    - `security`: Session/security alerts
    """
    from src.core.constants import SSE_RETRY_INTERVAL_MS
    
    subscriber = get_sse_subscriber()
    
    async def event_generator() -> AsyncGenerator[str, None]:
        # Send initial retry interval (from constants)
        yield f"retry: {SSE_RETRY_INTERVAL_MS}\n\n"
        
        # Replay missed events if last_event_id provided
        if last_event_id:
            try:
                missed = await subscriber.get_missed_events(
                    user_id=user_id,
                    last_event_id=UUID(last_event_id),
                )
                for event in missed:
                    yield event.to_sse_format()
            except ValueError:
                pass  # Invalid UUID, skip replay
        
        # Stream live events
        async for event in subscriber.subscribe(user_id, categories):
            # Check if client disconnected
            if await request.is_disconnected():
                break
            
            yield event.to_sse_format()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx/Traefik buffering
        },
    )
```

### 7.2 Route Registry Entry

Add to `ROUTE_REGISTRY`:

```python
RouteMetadata(
    method=HTTPMethod.GET,
    path="/events",  # REST compliant: resource noun, not verb
    handler=get_events,
    resource="events",
    tags=["Events"],
    summary="Get events (SSE stream)",
    description="Real-time event stream via Server-Sent Events. "
                "Use Accept: text/event-stream header.",
    operation_id="get_events",
    response_model=None,  # StreamingResponse
    status_code=200,
    errors=[
        ErrorSpec(status=401, description="Unauthorized"),
    ],
    idempotency=IdempotencyLevel.SAFE,
    auth_policy=AuthPolicy(level=AuthLevel.AUTHENTICATED),  # Uses existing auth
    rate_limit_policy=RateLimitPolicy.SSE_STREAM,  # New policy for SSE
),
```

### 7.3 Why No Response Schema?

Unlike standard REST endpoints, SSE does **not** require a Pydantic response schema in `src/schemas/`. Here's why:

| Aspect | REST Endpoints | SSE Endpoint |
|--------|----------------|---------------|
| Response type | JSON (`application/json`) | Stream (`text/event-stream`) |
| FastAPI handling | `response_model` validates & serializes | `StreamingResponse` streams raw text |
| Schema location | `src/schemas/*.py` | Not applicable |
| Serialization | Pydantic `.model_dump()` | `SSEEvent.to_sse_format()` |

**Key Points**:

- `response_model=None` in route registry is correct for SSE
- The `test_response_models_are_defined` test exempts `RateLimitPolicy.SSE_STREAM` endpoints
- Event structure is documented via `SSEEvent` dataclass and `SSE_EVENT_REGISTRY`
- Client SDKs can use the registry metadata for type generation if needed

**Future Option**: If client SDK generation requires OpenAPI-compatible schemas, add documentation-only schemas:

```python
# src/schemas/sse_schemas.py (optional - for OpenAPI docs only)

class SSEEventPayload(BaseModel):
    """Base payload structure for SSE events (documentation only)."""
    event_type: str
    data: dict[str, Any]
    occurred_at: datetime
```

This is **not required** for the foundation — add only if needed for `dashtam-terminal` SDK generation.

## 8. Authentication Strategy

**Key Point**: SSE uses **the same authentication as all Dashtam endpoints**. No separate auth mechanism.

### 8.1 Standard Bearer Token Authentication

SSE connections authenticate via the existing Dashtam Bearer token:

```http
GET /api/v1/events HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: text/event-stream
```

**Flow**:

1. Client includes JWT in `Authorization` header (same as any endpoint)
2. FastAPI dependency `get_current_user_id` validates token, extracts `user_id`
3. Endpoint uses `user_id` to subscribe to user's Redis channel
4. If token invalid/expired → standard 401 response (connection never opens)

**No new auth code** — reuses existing `src/presentation/dependencies/auth.py`.

### 8.2 Long-Lived Connection Considerations

SSE connections can persist for hours. Token handling:

| Scenario | Behavior |
|----------|----------|
| Token expires mid-stream | Connection continues (validated on connect only) |
| Session revoked | Server closes connection via heartbeat cleanup |
| Client disconnect | Standard SSE reconnection with new token |
| 401 on reconnect | Client must refresh token before retry |

**Server-side cleanup**: Background task checks session validity periodically.

### 8.3 Heartbeat

Server sends `:heartbeat\n\n` comment every 30 seconds (configurable via `SSE_HEARTBEAT_INTERVAL_SECONDS`):

- Detects stale connections (client gone but TCP not closed)
- Keeps connection alive through proxies/load balancers
- Not an event — clients ignore SSE comments

## 9. Event Retention & Replay (Optional)

### 9.1 Redis Streams for Retention

For clients that need to recover missed events on reconnection:

```python
# Configuration
SSE_ENABLE_RETENTION=true
SSE_RETENTION_MAX_LEN=1000      # Max events per user
SSE_RETENTION_TTL_SECONDS=3600  # 1 hour retention
```

### 9.2 Last-Event-ID Protocol

1. Server includes `id:` field in each SSE event
2. Client stores last received ID
3. On reconnection, client sends `Last-Event-ID` header
4. Server replays missed events from Redis Stream

### 9.3 When to Disable Retention

Retention adds Redis memory overhead. Disable if:

- Events are ephemeral (progress indicators)
- Clients don't need replay (always start fresh)
- Memory-constrained environment

## 10. Testing Strategy

### 10.1 Unit Tests

```text
tests/unit/
├── test_domain_sse_event.py           # SSEEvent dataclass
├── test_domain_sse_registry.py        # SSE_EVENT_REGISTRY validation
└── test_infrastructure_sse_handler.py # SSEEventHandler mapping
```

### 10.2 Integration Tests

```text
tests/integration/
├── test_sse_redis_publisher.py        # Redis pub/sub
└── test_sse_event_retention.py        # Redis Streams replay
```

### 10.3 API Tests

```text
tests/api/
└── test_sse_stream_endpoint.py        # SSE endpoint with mock events
```

### 10.4 Registry Compliance Tests

```python
# tests/unit/test_domain_sse_registry.py

def test_all_sse_events_have_valid_categories():
    """Verify all SSE events use valid categories."""
    for meta in SSE_EVENT_REGISTRY:
        assert isinstance(meta.category, SSECategory)


def test_domain_events_have_user_id():
    """Verify all source domain events have user_id attribute."""
    for meta in SSE_EVENT_REGISTRY:
        for domain_event in meta.source_domain_events:
            # Get type hints to verify user_id field exists
            hints = get_type_hints(domain_event)
            assert "user_id" in hints, (
                f"Domain event {domain_event.__name__} missing user_id "
                f"(required for SSE routing)"
            )


def test_event_types_are_unique():
    """Verify no duplicate event types."""
    event_types = [meta.event_type for meta in SSE_EVENT_REGISTRY]
    assert len(event_types) == len(set(event_types))
```

## 11. Configuration

Following Dashtam's established configuration pattern:

- **Environment-specific settings** → `src/core/config.py`
- **Implementation constants** → `src/core/constants.py`

### 11.1 Constants (src/core/constants.py)

```python
# =============================================================================
# SSE (Server-Sent Events)
# =============================================================================

SSE_HEARTBEAT_INTERVAL_SECONDS: int = 30
"""Interval between SSE heartbeat comments to detect stale connections."""

SSE_RETRY_INTERVAL_MS: int = 3000
"""Client reconnection interval hint (milliseconds)."""

SSE_CHANNEL_PREFIX: str = "sse"
"""Redis channel prefix for SSE pub/sub."""

SSE_RETENTION_MAX_LEN_DEFAULT: int = 1000
"""Default max events per user in Redis Stream retention."""

SSE_RETENTION_TTL_DEFAULT: int = 3600
"""Default TTL for retained events (seconds)."""
```

### 11.2 Settings (src/core/config.py)

Only **environment-specific** settings go in config:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # SSE Configuration (environment-specific)
    sse_enable_retention: bool = False  # Enable event retention for replay
```

### 11.3 Environment Variables

```bash
# .env.dev.example additions

# SSE Configuration
SSE_ENABLE_RETENTION=false
```

**Note**: Retention max_len and TTL use constants (not env vars) because they're implementation details, not deployment configuration.

## 12. Implementation Components

### Foundation Components

- SSE Protocol definitions (`domain/protocols/`)
- SSE Event dataclass (`domain/events/sse_event.py`)
- SSE Event Registry (`domain/events/sse_registry.py`)
- Redis Publisher adapter
- Redis Subscriber adapter
- SSE stream endpoint
- Container wiring

### Use Cases

SSE supports the following use cases:

| Use Case | Priority | Description |
|----------|----------|-------------|
| Data Sync Progress | High | Real-time sync status updates |
| Provider Connection Health | High | Token expiry/refresh notifications |
| AI Response Streaming | High | Streaming AI assistant responses |
| File Import Progress | Medium | Import progress updates |
| Balance/Portfolio Updates | Medium | Account balance changes |
| Security Notifications | Lower | Session/security alerts |

## 13. Related Documentation

- `docs/architecture/domain-events-architecture.md` - Domain events pattern
- `docs/architecture/registry-pattern-architecture.md` - Registry pattern
- `docs/architecture/cache-architecture.md` - Redis infrastructure

---

**Created**: 2026-01-18 | **Last Updated**: 2026-01-18
