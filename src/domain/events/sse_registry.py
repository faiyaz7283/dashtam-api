"""SSE Event Registry - Single Source of Truth.

This registry catalogs all SSE event types and their mappings from domain events.
Used for:
- Container wiring (automated SSEEventHandler subscriptions)
- Validation tests (verify no drift)
- Documentation generation (always accurate)
- Gap detection (missing mappings)

Architecture:
    - Domain layer (no dependencies on infrastructure)
    - Imported by container for automated wiring
    - Verified by tests to catch drift

Adding new SSE mappings (separate issues, not foundation):
1. Add mapping to DOMAIN_TO_SSE_MAPPING
2. Run tests - they validate the mapping
3. Container auto-wires SSEEventHandler subscriptions

Reference:
    - docs/architecture/sse-architecture.md
"""

from dataclasses import dataclass, field
from typing import Any, Callable, cast, Type
from uuid import UUID

from src.domain.events.base_event import DomainEvent
from src.domain.events.data_events import (
    AccountSyncAttempted,
    AccountSyncFailed,
    AccountSyncSucceeded,
    FileImportAttempted,
    FileImportFailed,
    FileImportProgress,
    FileImportSucceeded,
    HoldingsSyncAttempted,
    HoldingsSyncFailed,
    HoldingsSyncSucceeded,
    TransactionSyncAttempted,
    TransactionSyncFailed,
    TransactionSyncSucceeded,
)
from src.domain.events.provider_events import (
    ProviderDisconnectionSucceeded,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
)
from src.domain.events.sse_event import SSEEventCategory, SSEEventType


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


@dataclass(frozen=True)
class DomainToSSEMapping:
    """Mapping from a domain event to an SSE event.

    Defines how a domain event is transformed into an SSE event
    for real-time client notification.

    Attributes:
        domain_event_class: The domain event class to listen for.
        sse_event_type: The SSE event type to emit.
        payload_extractor: Function to extract SSE payload from domain event.
            Takes (domain_event, user_id) and returns dict payload.
        user_id_extractor: Function to extract user_id from domain event.
            Takes domain_event and returns UUID.
    """

    domain_event_class: Type[DomainEvent]
    sse_event_type: SSEEventType
    payload_extractor: Callable[[DomainEvent], dict[str, Any]]
    user_id_extractor: Callable[[DomainEvent], Any]  # Returns UUID


# ═══════════════════════════════════════════════════════════════
# SSE EVENT METADATA REGISTRY - Describes all SSE event types
# ═══════════════════════════════════════════════════════════════

SSE_EVENT_REGISTRY: list[SSEEventMetadata] = [
    # ═══════════════════════════════════════════════════════════
    # Data Sync Events (Issue #253)
    # Payload fields aligned with domain event fields
    # ═══════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_ACCOUNTS_STARTED,
        category=SSEEventCategory.DATA_SYNC,
        description="Account sync operation started",
        payload_fields=["connection_id"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
        category=SSEEventCategory.DATA_SYNC,
        description="Account sync operation completed successfully",
        payload_fields=["connection_id", "account_count"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_ACCOUNTS_FAILED,
        category=SSEEventCategory.DATA_SYNC,
        description="Account sync operation failed",
        payload_fields=["connection_id", "error"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_TRANSACTIONS_STARTED,
        category=SSEEventCategory.DATA_SYNC,
        description="Transaction sync operation started",
        payload_fields=["connection_id", "account_id"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_TRANSACTIONS_COMPLETED,
        category=SSEEventCategory.DATA_SYNC,
        description="Transaction sync operation completed successfully",
        payload_fields=["connection_id", "account_id", "transaction_count"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_TRANSACTIONS_FAILED,
        category=SSEEventCategory.DATA_SYNC,
        description="Transaction sync operation failed",
        payload_fields=["connection_id", "account_id", "error"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_HOLDINGS_STARTED,
        category=SSEEventCategory.DATA_SYNC,
        description="Holdings sync operation started",
        payload_fields=["account_id"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_HOLDINGS_COMPLETED,
        category=SSEEventCategory.DATA_SYNC,
        description="Holdings sync operation completed successfully",
        payload_fields=["account_id", "holding_count"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SYNC_HOLDINGS_FAILED,
        category=SSEEventCategory.DATA_SYNC,
        description="Holdings sync operation failed",
        payload_fields=["account_id", "error"],
    ),
    # ═══════════════════════════════════════════════════════════
    # Provider Events
    # ═══════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type=SSEEventType.PROVIDER_TOKEN_EXPIRING,
        category=SSEEventCategory.PROVIDER,
        description="Provider OAuth token expiring soon",
        payload_fields=["connection_id", "provider_slug", "expires_in_seconds"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.PROVIDER_TOKEN_REFRESHED,
        category=SSEEventCategory.PROVIDER,
        description="Provider OAuth token refreshed successfully",
        payload_fields=["connection_id", "provider_slug"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.PROVIDER_TOKEN_FAILED,
        category=SSEEventCategory.PROVIDER,
        description="Provider OAuth token refresh failed",
        payload_fields=["connection_id", "provider_slug", "needs_reauth"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.PROVIDER_DISCONNECTED,
        category=SSEEventCategory.PROVIDER,
        description="Provider connection disconnected",
        payload_fields=["connection_id", "provider_slug"],
    ),
    # ═══════════════════════════════════════════════════════════
    # AI Events
    # ═══════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type=SSEEventType.AI_RESPONSE_CHUNK,
        category=SSEEventCategory.AI,
        description="AI response text chunk (streaming)",
        payload_fields=["conversation_id", "chunk", "is_final"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.AI_TOOL_EXECUTING,
        category=SSEEventCategory.AI,
        description="AI is executing a tool/function",
        payload_fields=["conversation_id", "tool_name"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.AI_RESPONSE_COMPLETE,
        category=SSEEventCategory.AI,
        description="AI response generation completed",
        payload_fields=["conversation_id"],
    ),
    # ═══════════════════════════════════════════════════════════
    # Import Events
    # ═══════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type=SSEEventType.IMPORT_STARTED,
        category=SSEEventCategory.IMPORT,
        description="File import operation started",
        payload_fields=["file_name", "file_format"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.IMPORT_PROGRESS,
        category=SSEEventCategory.IMPORT,
        description="File import progress update",
        payload_fields=["file_name", "progress_percent", "records_processed"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.IMPORT_COMPLETED,
        category=SSEEventCategory.IMPORT,
        description="File import operation completed successfully",
        payload_fields=["file_name", "records_imported"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.IMPORT_FAILED,
        category=SSEEventCategory.IMPORT,
        description="File import operation failed",
        payload_fields=["file_name", "error"],
    ),
    # ═══════════════════════════════════════════════════════════
    # Portfolio Events
    # ═══════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type=SSEEventType.PORTFOLIO_BALANCE_UPDATED,
        category=SSEEventCategory.PORTFOLIO,
        description="Account balance updated after sync",
        payload_fields=["account_id", "previous_balance", "new_balance", "currency"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.PORTFOLIO_HOLDINGS_UPDATED,
        category=SSEEventCategory.PORTFOLIO,
        description="Portfolio holdings updated after sync",
        payload_fields=["account_id", "holdings_count"],
    ),
    # ═══════════════════════════════════════════════════════════
    # Security Events
    # ═══════════════════════════════════════════════════════════
    SSEEventMetadata(
        event_type=SSEEventType.SECURITY_SESSION_NEW,
        category=SSEEventCategory.SECURITY,
        description="New session created (login from new device/location)",
        payload_fields=["session_id", "device_info", "location"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SECURITY_SESSION_SUSPICIOUS,
        category=SSEEventCategory.SECURITY,
        description="Suspicious session activity detected",
        payload_fields=["session_id", "reason"],
    ),
    SSEEventMetadata(
        event_type=SSEEventType.SECURITY_SESSION_EXPIRING,
        category=SSEEventCategory.SECURITY,
        description="Session expiring soon (warning)",
        payload_fields=["session_id", "expires_in_seconds"],
    ),
]


# ═══════════════════════════════════════════════════════════════
# DOMAIN TO SSE MAPPINGS - To be populated by use case issues
# ═══════════════════════════════════════════════════════════════
#
# Each use case issue (Issue #1-6) will add mappings here.
# The mappings define how domain events are transformed to SSE events.
#
# Example mapping (to be added in Issue #1: Data Sync Progress):
#
# DomainToSSEMapping(
#     domain_event_class=AccountSyncSucceeded,
#     sse_event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
#     payload_extractor=lambda e: {
#         "connection_id": str(e.connection_id),
#         "provider_slug": e.provider_slug,
#         "account_count": e.account_count,
#     },
#     user_id_extractor=lambda e: e.user_id,
# ),

# ═══════════════════════════════════════════════════════════════
# Payload Extractor Functions (Issue #253: Data Sync Progress)
# ═══════════════════════════════════════════════════════════════


def _uuid_to_str(value: UUID | None) -> str | None:
    """Convert UUID to string, handling None."""
    return str(value) if value is not None else None


# Account Sync extractors
def _extract_account_sync_attempted_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from AccountSyncAttempted."""
    e = cast(AccountSyncAttempted, event)
    return {"connection_id": str(e.connection_id)}


def _extract_account_sync_succeeded_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from AccountSyncSucceeded."""
    e = cast(AccountSyncSucceeded, event)
    return {
        "connection_id": str(e.connection_id),
        "account_count": e.account_count,
    }


def _extract_account_sync_failed_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from AccountSyncFailed."""
    e = cast(AccountSyncFailed, event)
    return {
        "connection_id": str(e.connection_id),
        "error": e.reason,
    }


# Transaction Sync extractors
def _extract_transaction_sync_attempted_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from TransactionSyncAttempted."""
    e = cast(TransactionSyncAttempted, event)
    return {
        "connection_id": str(e.connection_id),
        "account_id": _uuid_to_str(e.account_id),
    }


def _extract_transaction_sync_succeeded_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from TransactionSyncSucceeded."""
    e = cast(TransactionSyncSucceeded, event)
    return {
        "connection_id": str(e.connection_id),
        "account_id": _uuid_to_str(e.account_id),
        "transaction_count": e.transaction_count,
    }


def _extract_transaction_sync_failed_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from TransactionSyncFailed."""
    e = cast(TransactionSyncFailed, event)
    return {
        "connection_id": str(e.connection_id),
        "account_id": _uuid_to_str(e.account_id),
        "error": e.reason,
    }


# Holdings Sync extractors
def _extract_holdings_sync_attempted_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from HoldingsSyncAttempted."""
    e = cast(HoldingsSyncAttempted, event)
    return {"account_id": str(e.account_id)}


def _extract_holdings_sync_succeeded_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from HoldingsSyncSucceeded."""
    e = cast(HoldingsSyncSucceeded, event)
    return {
        "account_id": str(e.account_id),
        "holding_count": e.holding_count,
    }


def _extract_holdings_sync_failed_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from HoldingsSyncFailed."""
    e = cast(HoldingsSyncFailed, event)
    return {
        "account_id": str(e.account_id),
        "error": e.reason,
    }


# User ID extractor (common pattern - all data sync events have user_id)
def _extract_user_id(event: DomainEvent) -> UUID:
    """Extract user_id from any domain event with user_id field.

    All data sync events (AccountSync*, TransactionSync*, HoldingsSync*)
    and provider events have a user_id field. This extractor uses getattr
    for type safety.
    """
    return cast(UUID, getattr(event, "user_id"))


# ═══════════════════════════════════════════════════════════════
# Payload Extractor Functions (Issue #254: Provider Health)
# ═══════════════════════════════════════════════════════════════


def _extract_token_refresh_succeeded_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from ProviderTokenRefreshSucceeded."""
    e = cast(ProviderTokenRefreshSucceeded, event)
    return {
        "connection_id": str(e.connection_id),
        "provider_slug": e.provider_slug,
    }


def _extract_token_refresh_failed_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from ProviderTokenRefreshFailed."""
    e = cast(ProviderTokenRefreshFailed, event)
    return {
        "connection_id": str(e.connection_id),
        "provider_slug": e.provider_slug,
        "needs_reauth": e.needs_user_action,
    }


def _extract_disconnection_succeeded_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from ProviderDisconnectionSucceeded."""
    e = cast(ProviderDisconnectionSucceeded, event)
    return {
        "connection_id": str(e.connection_id),
        "provider_slug": e.provider_slug,
    }


# ═══════════════════════════════════════════════════════════════
# Payload Extractor Functions (Issue #256: File Import Progress)
# ═══════════════════════════════════════════════════════════════


def _extract_file_import_attempted_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from FileImportAttempted."""
    e = cast(FileImportAttempted, event)
    return {
        "file_name": e.file_name,
        "file_format": e.file_format,
    }


def _extract_file_import_progress_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from FileImportProgress."""
    e = cast(FileImportProgress, event)
    return {
        "file_name": e.file_name,
        "progress_percent": e.progress_percent,
        "records_processed": e.records_processed,
    }


def _extract_file_import_succeeded_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from FileImportSucceeded."""
    e = cast(FileImportSucceeded, event)
    return {
        "file_name": e.file_name,
        "records_imported": e.transaction_count,
    }


def _extract_file_import_failed_payload(event: DomainEvent) -> dict[str, Any]:
    """Extract payload from FileImportFailed."""
    e = cast(FileImportFailed, event)
    return {
        "file_name": e.file_name,
        "error": e.reason,
    }


# ═══════════════════════════════════════════════════════════════
# DOMAIN TO SSE MAPPINGS
# ═══════════════════════════════════════════════════════════════

DOMAIN_TO_SSE_MAPPING: list[DomainToSSEMapping] = [
    # ═══════════════════════════════════════════════════════════
    # Issue #253: Data Sync Progress (9 mappings)
    # ═══════════════════════════════════════════════════════════
    # Account Sync
    DomainToSSEMapping(
        domain_event_class=AccountSyncAttempted,
        sse_event_type=SSEEventType.SYNC_ACCOUNTS_STARTED,
        payload_extractor=_extract_account_sync_attempted_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=AccountSyncSucceeded,
        sse_event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
        payload_extractor=_extract_account_sync_succeeded_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=AccountSyncFailed,
        sse_event_type=SSEEventType.SYNC_ACCOUNTS_FAILED,
        payload_extractor=_extract_account_sync_failed_payload,
        user_id_extractor=_extract_user_id,
    ),
    # Transaction Sync
    DomainToSSEMapping(
        domain_event_class=TransactionSyncAttempted,
        sse_event_type=SSEEventType.SYNC_TRANSACTIONS_STARTED,
        payload_extractor=_extract_transaction_sync_attempted_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=TransactionSyncSucceeded,
        sse_event_type=SSEEventType.SYNC_TRANSACTIONS_COMPLETED,
        payload_extractor=_extract_transaction_sync_succeeded_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=TransactionSyncFailed,
        sse_event_type=SSEEventType.SYNC_TRANSACTIONS_FAILED,
        payload_extractor=_extract_transaction_sync_failed_payload,
        user_id_extractor=_extract_user_id,
    ),
    # Holdings Sync
    DomainToSSEMapping(
        domain_event_class=HoldingsSyncAttempted,
        sse_event_type=SSEEventType.SYNC_HOLDINGS_STARTED,
        payload_extractor=_extract_holdings_sync_attempted_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=HoldingsSyncSucceeded,
        sse_event_type=SSEEventType.SYNC_HOLDINGS_COMPLETED,
        payload_extractor=_extract_holdings_sync_succeeded_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=HoldingsSyncFailed,
        sse_event_type=SSEEventType.SYNC_HOLDINGS_FAILED,
        payload_extractor=_extract_holdings_sync_failed_payload,
        user_id_extractor=_extract_user_id,
    ),
    # ═══════════════════════════════════════════════════════════
    # Issue #254: Provider Health (3 mappings)
    # ═══════════════════════════════════════════════════════════
    DomainToSSEMapping(
        domain_event_class=ProviderTokenRefreshSucceeded,
        sse_event_type=SSEEventType.PROVIDER_TOKEN_REFRESHED,
        payload_extractor=_extract_token_refresh_succeeded_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=ProviderTokenRefreshFailed,
        sse_event_type=SSEEventType.PROVIDER_TOKEN_FAILED,
        payload_extractor=_extract_token_refresh_failed_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=ProviderDisconnectionSucceeded,
        sse_event_type=SSEEventType.PROVIDER_DISCONNECTED,
        payload_extractor=_extract_disconnection_succeeded_payload,
        user_id_extractor=_extract_user_id,
    ),
    # ═══════════════════════════════════════════════════════════
    # Issue #256: File Import Progress (4 mappings)
    # ═══════════════════════════════════════════════════════════
    DomainToSSEMapping(
        domain_event_class=FileImportAttempted,
        sse_event_type=SSEEventType.IMPORT_STARTED,
        payload_extractor=_extract_file_import_attempted_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=FileImportProgress,
        sse_event_type=SSEEventType.IMPORT_PROGRESS,
        payload_extractor=_extract_file_import_progress_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=FileImportSucceeded,
        sse_event_type=SSEEventType.IMPORT_COMPLETED,
        payload_extractor=_extract_file_import_succeeded_payload,
        user_id_extractor=_extract_user_id,
    ),
    DomainToSSEMapping(
        domain_event_class=FileImportFailed,
        sse_event_type=SSEEventType.IMPORT_FAILED,
        payload_extractor=_extract_file_import_failed_payload,
        user_id_extractor=_extract_user_id,
    ),
    # ═══════════════════════════════════════════════════════════
    # Future mappings to be added by:
    # - Issue #255: AI Response Streaming (direct publish, no domain event mapping)
    # - Issue #257: Balance/Portfolio Updates (after sync handlers)
    # - Issue #258: Security Notifications (Session events)
    # ═══════════════════════════════════════════════════════════
]


def get_domain_event_to_sse_mapping() -> dict[Type[DomainEvent], DomainToSSEMapping]:
    """Get mapping from domain event class to SSE mapping.

    Used by SSEEventHandler to determine if a domain event should
    trigger an SSE notification and how to transform it.

    Returns:
        Dict mapping domain event classes to their SSE mapping metadata.

    Example:
        >>> mapping = get_domain_event_to_sse_mapping()
        >>> if AccountSyncSucceeded in mapping:
        ...     sse_mapping = mapping[AccountSyncSucceeded]
        ...     # Transform and publish SSE event
    """
    return {m.domain_event_class: m for m in DOMAIN_TO_SSE_MAPPING}


def get_sse_event_metadata(event_type: SSEEventType) -> SSEEventMetadata | None:
    """Get metadata for an SSE event type.

    Args:
        event_type: The SSE event type to look up.

    Returns:
        SSEEventMetadata if found, None otherwise.
    """
    for metadata in SSE_EVENT_REGISTRY:
        if metadata.event_type == event_type:
            return metadata
    return None


def get_events_by_category(category: SSEEventCategory) -> list[SSEEventMetadata]:
    """Get all SSE event metadata for a category.

    Args:
        category: The category to filter by.

    Returns:
        List of SSEEventMetadata for events in that category.
    """
    return [m for m in SSE_EVENT_REGISTRY if m.category == category]


def get_all_sse_event_types() -> list[SSEEventType]:
    """Get list of all registered SSE event types.

    Returns:
        List of all SSE event types in the registry.
    """
    return [m.event_type for m in SSE_EVENT_REGISTRY]


def get_registry_statistics() -> dict[str, object]:
    """Get statistics about the SSE event registry.

    Returns:
        Dict with counts by category and totals.
        Keys: total_event_types (int), total_mappings (int), by_category (dict[str, int]).

    Example:
        >>> stats = get_registry_statistics()
        >>> print(stats)
        {
            "total_event_types": 21,
            "total_mappings": 0,  # Until use case issues implemented
            "by_category": {
                "data_sync": 9,
                "provider": 4,
                "ai": 3,
                ...
            }
        }
    """
    by_category: dict[str, int] = {}
    for metadata in SSE_EVENT_REGISTRY:
        cat_name = metadata.category.value
        by_category[cat_name] = by_category.get(cat_name, 0) + 1

    return {
        "total_event_types": len(SSE_EVENT_REGISTRY),
        "total_mappings": len(DOMAIN_TO_SSE_MAPPING),
        "by_category": by_category,
    }
