"""Data synchronization domain events (F7.7 Phase 2).

Pattern: 3 events per workflow (ATTEMPTED → SUCCEEDED/FAILED)
- *Attempted: User initiated sync (before business logic)
- *Succeeded: Operation completed successfully (after business commit)
- *Failed: Operation failed (after business rollback)

Handlers:
- LoggingEventHandler: ALL 3 events
- AuditEventHandler: ALL 3 events

Workflows:
1. Account Sync: Sync account data from provider
2. Transaction Sync: Sync transaction data from provider
3. Holdings Sync: Sync holdings (positions) from provider
4. File Import: Import data from uploaded file
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.events.base_event import DomainEvent


# ═══════════════════════════════════════════════════════════════
# Account Sync (Workflow 1)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class AccountSyncAttempted(DomainEvent):
    """Account sync attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record ACCOUNT_SYNC_ATTEMPTED

    Attributes:
        connection_id: Provider connection being synced.
        user_id: User initiating sync.
    """

    connection_id: UUID
    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class AccountSyncSucceeded(DomainEvent):
    """Account sync completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record ACCOUNT_SYNC_SUCCEEDED

    Attributes:
        connection_id: Provider connection synced.
        user_id: User who initiated sync.
        account_count: Number of accounts synced.
    """

    connection_id: UUID
    user_id: UUID
    account_count: int


@dataclass(frozen=True, kw_only=True)
class AccountSyncFailed(DomainEvent):
    """Account sync failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record ACCOUNT_SYNC_FAILED

    Attributes:
        connection_id: Provider connection attempted.
        user_id: User who initiated sync.
        reason: Failure reason (e.g., "connection_not_found", "provider_error",
            "authentication_failed").
    """

    connection_id: UUID
    user_id: UUID
    reason: str


# ═══════════════════════════════════════════════════════════════
# Transaction Sync (Workflow 2)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class TransactionSyncAttempted(DomainEvent):
    """Transaction sync attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record TRANSACTION_SYNC_ATTEMPTED

    Attributes:
        connection_id: Provider connection being synced.
        user_id: User initiating sync.
        account_id: Specific account if targeted sync (optional).
    """

    connection_id: UUID
    user_id: UUID
    account_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class TransactionSyncSucceeded(DomainEvent):
    """Transaction sync completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record TRANSACTION_SYNC_SUCCEEDED

    Attributes:
        connection_id: Provider connection synced.
        user_id: User who initiated sync.
        account_id: Specific account if targeted sync (optional).
        transaction_count: Number of transactions synced.
    """

    connection_id: UUID
    user_id: UUID
    account_id: UUID | None
    transaction_count: int


@dataclass(frozen=True, kw_only=True)
class TransactionSyncFailed(DomainEvent):
    """Transaction sync failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record TRANSACTION_SYNC_FAILED

    Attributes:
        connection_id: Provider connection attempted.
        user_id: User who initiated sync.
        account_id: Specific account if targeted sync (optional).
        reason: Failure reason (e.g., "connection_not_found", "provider_error",
            "date_range_invalid").
    """

    connection_id: UUID
    user_id: UUID
    account_id: UUID | None
    reason: str


# ═══════════════════════════════════════════════════════════════
# Holdings Sync (Workflow 3)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class HoldingsSyncAttempted(DomainEvent):
    """Holdings sync attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record HOLDINGS_SYNC_ATTEMPTED

    Attributes:
        account_id: Account being synced.
        user_id: User initiating sync.
    """

    account_id: UUID
    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class HoldingsSyncSucceeded(DomainEvent):
    """Holdings sync completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record HOLDINGS_SYNC_SUCCEEDED

    Attributes:
        account_id: Account synced.
        user_id: User who initiated sync.
        holding_count: Number of holdings synced.
    """

    account_id: UUID
    user_id: UUID
    holding_count: int


@dataclass(frozen=True, kw_only=True)
class HoldingsSyncFailed(DomainEvent):
    """Holdings sync failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record HOLDINGS_SYNC_FAILED

    Attributes:
        account_id: Account attempted.
        user_id: User who initiated sync.
        reason: Failure reason (e.g., "account_not_found", "provider_error",
            "holdings_not_supported").
    """

    account_id: UUID
    user_id: UUID
    reason: str


# ═══════════════════════════════════════════════════════════════
# File Import (Workflow 4)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class FileImportAttempted(DomainEvent):
    """File import attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record FILE_IMPORT_ATTEMPTED

    Attributes:
        user_id: User importing file.
        provider_slug: Provider identifier (e.g., "chase_file").
        file_name: Original filename.
        file_format: File format (e.g., "qfx", "ofx", "csv").
    """

    user_id: UUID
    provider_slug: str
    file_name: str
    file_format: str


@dataclass(frozen=True, kw_only=True)
class FileImportSucceeded(DomainEvent):
    """File import completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record FILE_IMPORT_SUCCEEDED

    Attributes:
        user_id: User who imported file.
        provider_slug: Provider identifier.
        file_name: Original filename.
        file_format: File format.
        account_count: Number of accounts created/updated.
        transaction_count: Number of transactions imported.
    """

    user_id: UUID
    provider_slug: str
    file_name: str
    file_format: str
    account_count: int
    transaction_count: int


@dataclass(frozen=True, kw_only=True)
class FileImportFailed(DomainEvent):
    """File import failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record FILE_IMPORT_FAILED

    Attributes:
        user_id: User who attempted import.
        provider_slug: Provider identifier.
        file_name: Original filename.
        file_format: File format.
        reason: Failure reason (e.g., "parse_error", "unsupported_format",
            "invalid_file_structure").
    """

    user_id: UUID
    provider_slug: str
    file_name: str
    file_format: str
    reason: str
