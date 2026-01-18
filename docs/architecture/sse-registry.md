# SSE Event Registry Architecture

## Overview

### Purpose

The **SSE Event Registry** is a metadata-driven catalog that serves as the single source of truth for all Server-Sent Events (SSE) event types and their mappings from domain events. It follows the **Registry Pattern** established by the Domain Events Registry, Route Registry, and Validation Registry.

**Key Benefits**:

- **Single source of truth** - All SSE event types cataloged in one place
- **Self-documenting** - Metadata includes descriptions, payload fields, categories
- **Self-enforcing** - Compliance tests fail if registry incomplete
- **Zero drift** - Can't add SSE event type without registry entry
- **Easy discovery** - Helper functions for accessing metadata
- **Auto-wiring ready** - Mappings enable automatic domain→SSE event bridging

### Problem Statement

**Before Registry Pattern**:

- **Scattered definitions** (Gap ⚠️): SSE event types defined ad-hoc across codebase
- **No catalog** (Gap ⚠️): No central place to see all SSE events
- **No metadata** (Gap ⚠️): Event types lack descriptions, expected payloads
- **Manual wiring** (Gap ⚠️): Must manually wire each domain event to SSE
- **Inconsistent naming** (Gap ⚠️): Event type names vary without standard

**The Gap**: Without a registry, developers must manually search for SSE events, lack payload documentation, and have no automated way to ensure complete coverage.

### Solution

**With Registry Pattern**:

```python
# src/domain/events/sse_registry.py - Single source of truth
SSE_EVENT_REGISTRY: list[SSEEventMetadata] = [
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
        category=SSEEventCategory.DATA_SYNC,
        description="Account sync operation completed successfully",
        payload_fields=["connection_id", "provider_slug", "account_count"],
    ),
    # ... 24 more event types
]
```

**Benefits**:

- ✅ All 25 SSE event types cataloged with complete metadata
- ✅ 6 categories for client-side filtering
- ✅ Self-enforcing compliance tests
- ✅ Helper functions for easy access
- ✅ Domain→SSE mapping support for automated bridging
- ✅ Zero drift - tests fail if metadata incomplete

---

## Architecture Components

### 1. SSEEventType (Enum)

**Purpose**: Enumerate all valid SSE event types sent to clients.

**Location**: `src/domain/events/sse_event.py`

**Structure**:

```python
class SSEEventType(StrEnum):
    """All SSE event types (Single Source of Truth).
    
    Naming convention: {category}.{resource}.{action}
    Examples: sync.accounts.completed, provider.token.expiring
    """
    # Data Sync (9 types)
    SYNC_ACCOUNTS_STARTED = "sync.accounts.started"
    SYNC_ACCOUNTS_COMPLETED = "sync.accounts.completed"
    SYNC_ACCOUNTS_FAILED = "sync.accounts.failed"
    SYNC_TRANSACTIONS_STARTED = "sync.transactions.started"
    # ... more

    # Provider (4 types)
    PROVIDER_TOKEN_EXPIRING = "provider.token.expiring"
    PROVIDER_TOKEN_REFRESHED = "provider.token.refreshed"
    # ... more

    # AI (3 types), Import (4 types), Portfolio (2 types), Security (3 types)
```

**Naming Convention**:

- Use **dot notation**: `{category}.{resource}.{action}`
- **Lowercase** with dots separating segments
- **Descriptive actions**: `started`, `completed`, `failed`, `expiring`

### 2. SSEEventCategory (Enum)

**Purpose**: Categorize SSE events for client-side filtering.

**Location**: `src/domain/events/sse_event.py`

**Structure**:

```python
class SSEEventCategory(StrEnum):
    """Categories for SSE event filtering."""
    DATA_SYNC = "data_sync"     # Account/transaction/holdings sync
    PROVIDER = "provider"       # Provider connection health
    AI = "ai"                   # AI assistant streaming
    IMPORT = "import"           # File import progress
    PORTFOLIO = "portfolio"     # Balance/holdings updates
    SECURITY = "security"       # Session/security alerts
```

**Client Usage**:

```text
GET /api/v1/events?categories=data_sync&categories=provider
```

### 3. SSEEventMetadata (Dataclass)

**Purpose**: Immutable metadata container for a single SSE event type.

**Location**: `src/domain/events/sse_registry.py`

**Structure**:

```python
@dataclass(frozen=True)
class SSEEventMetadata:
    """Metadata for an SSE event type.
    
    Attributes:
        event_type: The SSE event type enum value.
        category: Event category for filtering.
        description: Human-readable description.
        payload_fields: Expected fields in the event data payload.
    """
    event_type: SSEEventType
    category: SSEEventCategory
    description: str
    payload_fields: list[str] = field(default_factory=list)
```

**Key Properties**:

- **Immutable** (`frozen=True`) - Prevents accidental modification
- **Type-safe** - All fields have type hints
- **Self-documenting** - Description and payload_fields included
- **Category-aware** - Links to filtering category

### 4. SSE_EVENT_REGISTRY (Constant)

**Purpose**: The registry itself - single source of truth for all SSE event metadata.

**Location**: `src/domain/events/sse_registry.py`

**Structure**:

```python
SSE_EVENT_REGISTRY: list[SSEEventMetadata] = [
    # Data Sync Events (9)
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_ACCOUNTS_STARTED,
        category=SSEEventCategory.DATA_SYNC,
        description="Account sync operation started",
        payload_fields=["connection_id", "provider_slug"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
        category=SSEEventCategory.DATA_SYNC,
        description="Account sync operation completed successfully",
        payload_fields=["connection_id", "provider_slug", "account_count"],
    ),
    # ... 23 more entries
]
```

**Event Type Distribution**:

| Category | Count | Event Types |
|----------|-------|-------------|
| DATA_SYNC | 9 | Accounts, Transactions, Holdings (started/completed/failed) |
| PROVIDER | 4 | Token expiring/refreshed/failed, Disconnected |
| AI | 3 | Response chunk, Tool executing, Response complete |
| IMPORT | 4 | Started, Progress, Completed, Failed |
| PORTFOLIO | 2 | Balance updated, Holdings updated |
| SECURITY | 3 | Session new/suspicious/expiring |

### 5. DomainToSSEMapping (Dataclass)

**Purpose**: Define how domain events are transformed to SSE events.

**Location**: `src/domain/events/sse_registry.py`

**Structure**:

```python
@dataclass(frozen=True)
class DomainToSSEMapping:
    """Mapping from a domain event to an SSE event.
    
    Attributes:
        domain_event_class: The domain event class to listen for.
        sse_event_type: The SSE event type to emit.
        payload_extractor: Function to extract SSE payload from domain event.
        user_id_extractor: Function to extract user_id from domain event.
    """
    domain_event_class: Type[DomainEvent]
    sse_event_type: SSEEventType
    payload_extractor: Callable[[DomainEvent], dict[str, Any]]
    user_id_extractor: Callable[[DomainEvent], UUID]
```

**Usage** (added by use case issues):

```python
DOMAIN_TO_SSE_MAPPING: list[DomainToSSEMapping] = [
    DomainToSSEMapping(
        domain_event_class=AccountSyncSucceeded,
        sse_event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
        payload_extractor=lambda e: {
            "connection_id": str(e.connection_id),
            "provider_slug": e.provider_slug,
            "account_count": e.account_count,
        },
        user_id_extractor=lambda e: e.user_id,
    ),
    # ... more mappings
]
```

### 6. Helper Functions

**Purpose**: Convenient access to registry data.

**Location**: `src/domain/events/sse_registry.py`

#### get_sse_event_metadata()

```python
def get_sse_event_metadata(event_type: SSEEventType) -> SSEEventMetadata | None:
    """Get metadata for an SSE event type.
    
    Args:
        event_type: The SSE event type to look up.
    
    Returns:
        SSEEventMetadata if found, None otherwise.
    
    Example:
        >>> meta = get_sse_event_metadata(SSEEventType.SYNC_ACCOUNTS_COMPLETED)
        >>> print(meta.description)
        "Account sync operation completed successfully"
    """
```

#### get_events_by_category()

```python
def get_events_by_category(category: SSEEventCategory) -> list[SSEEventMetadata]:
    """Get all SSE event metadata for a category.
    
    Args:
        category: The category to filter by.
    
    Returns:
        List of SSEEventMetadata for events in that category.
    
    Example:
        >>> data_sync = get_events_by_category(SSEEventCategory.DATA_SYNC)
        >>> print(f"Data sync events: {len(data_sync)}")  # 9
    """
```

#### get_all_sse_event_types()

```python
def get_all_sse_event_types() -> list[SSEEventType]:
    """Get list of all registered SSE event types.
    
    Returns:
        List of all SSE event types in the registry.
    """
```

#### get_registry_statistics()

```python
def get_registry_statistics() -> dict[str, int]:
    """Get statistics about the SSE event registry.
    
    Returns:
        Dict with counts by category and totals.
    
    Example:
        >>> stats = get_registry_statistics()
        >>> print(stats)
        {
            "total_event_types": 25,
            "total_mappings": 0,
            "by_category": {
                "data_sync": 9,
                "provider": 4,
                ...
            }
        }
    """
```

#### get_domain_event_to_sse_mapping()

```python
def get_domain_event_to_sse_mapping() -> dict[Type[DomainEvent], DomainToSSEMapping]:
    """Get mapping from domain event class to SSE mapping.
    
    Used by SSEEventHandler to determine if a domain event should
    trigger an SSE notification.
    
    Returns:
        Dict mapping domain event classes to their SSE mapping metadata.
    """
```

---

## Category-to-Event Type Mapping

The registry maintains a separate mapping from `SSEEventType` to `SSEEventCategory`:

**Location**: `src/domain/events/sse_event.py`

```python
_EVENT_TYPE_TO_CATEGORY: dict[SSEEventType, SSEEventCategory] = {
    # Data Sync
    SSEEventType.SYNC_ACCOUNTS_STARTED: SSEEventCategory.DATA_SYNC,
    SSEEventType.SYNC_ACCOUNTS_COMPLETED: SSEEventCategory.DATA_SYNC,
    # ... all 25 mappings
}

def get_category_for_event_type(event_type: SSEEventType) -> SSEEventCategory:
    """Get the category for an SSE event type."""
    return _EVENT_TYPE_TO_CATEGORY[event_type]
```

**Compliance**: Tests verify that:

1. Every `SSEEventType` has a category mapping
2. Registry metadata category matches `_EVENT_TYPE_TO_CATEGORY`

---

## Compliance Tests

**Location**: `tests/unit/test_domain_sse_registry_compliance.py`

### Registry Completeness

```python
def test_all_sse_event_types_have_registry_metadata():
    """CRITICAL: Every SSEEventType must have metadata in SSE_EVENT_REGISTRY."""
    registered_types = {m.event_type for m in SSE_EVENT_REGISTRY}
    for event_type in SSEEventType:
        assert event_type in registered_types
```

### Category Consistency

```python
def test_registry_category_matches_event_type_mapping():
    """CRITICAL: Registry category must match _EVENT_TYPE_TO_CATEGORY."""
    for meta in SSE_EVENT_REGISTRY:
        expected = get_category_for_event_type(meta.event_type)
        assert meta.category == expected
```

### Statistics Accuracy

```python
def test_statistics_expected_counts():
    """Test expected counts for each category."""
    stats = get_registry_statistics()
    expected = {
        "data_sync": 9,
        "provider": 4,
        "ai": 3,
        "import": 4,
        "portfolio": 2,
        "security": 3,
    }
    for cat_name, count in expected.items():
        assert stats["by_category"][cat_name] == count
```

### No Duplicates

```python
def test_no_duplicate_event_types_in_registry():
    """Each event type should appear exactly once."""
    event_types = [m.event_type for m in SSE_EVENT_REGISTRY]
    assert len(event_types) == len(set(event_types))
```

---

## Adding New SSE Event Types

### Process

1. **Add enum value** in `SSEEventType` (sse_event.py)
2. **Add category mapping** in `_EVENT_TYPE_TO_CATEGORY` (sse_event.py)
3. **Add registry entry** in `SSE_EVENT_REGISTRY` (sse_registry.py)
4. **Run tests** - compliance tests validate completeness
5. **Add domain mapping** (optional) in `DOMAIN_TO_SSE_MAPPING`

### Example: Adding New Event Type

```python
# Step 1: Add to SSEEventType enum (sse_event.py)
class SSEEventType(StrEnum):
    # ... existing types
    EXPORT_COMPLETED = "export.completed"

# Step 2: Add category mapping (sse_event.py)
_EVENT_TYPE_TO_CATEGORY = {
    # ... existing mappings
    SSEEventType.EXPORT_COMPLETED: SSEEventCategory.IMPORT,  # or new category
}

# Step 3: Add registry entry (sse_registry.py)
SSE_EVENT_REGISTRY.append(
    SSEEventMetadata(
        event_type=SSEEventType.EXPORT_COMPLETED,
        category=SSEEventCategory.IMPORT,
        description="File export operation completed successfully",
        payload_fields=["file_name", "file_url", "record_count"],
    )
)

# Step 4: Run tests
pytest tests/unit/test_domain_sse_registry_compliance.py -v
```

---

## SSEEvent Wire Format

The registry defines event types that are serialized to SSE wire format:

**Location**: `src/domain/events/sse_event.py`

```python
@dataclass(frozen=True, kw_only=True, slots=True)
class SSEEvent:
    """Server-Sent Event data structure."""
    event_type: SSEEventType
    user_id: UUID
    data: dict[str, Any]
    event_id: UUID = field(default_factory=uuid7)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_sse_format(self) -> str:
        """Serialize to SSE wire format."""
        return (
            f"id: {self.event_id}\n"
            f"event: {self.event_type.value}\n"
            f"data: {json.dumps(self.data)}\n\n"
        )
```

**Example Output**:

```text
id: 019447f2-3a5b-7c8d-9e0f-1a2b3c4d5e6f
event: sync.accounts.completed
data: {"connection_id": "abc123", "account_count": 3}

```

---

## Related Documentation

- [SSE Architecture](sse-architecture.md) - Complete SSE system design
- [Domain Events Registry](registry.md) - Domain events registry pattern
- [Route Registry](route-registry.md) - API route registration pattern
- [Validation Registry](validation-registry.md) - Validation rules registry

---

**Created**: 2026-01-18 | **Last Updated**: 2026-01-18
