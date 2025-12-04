"""Sync commands for account and transaction synchronization.

Commands that trigger data synchronization from external providers.
These are blocking operations (sync execution, not background job).

Architecture:
    - Commands are immutable value objects representing user intent
    - Handlers execute the sync operation and return results
    - Domain events published for audit/observability

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/api-design-patterns.md
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SyncAccounts:
    """Command to sync accounts from a provider connection.

    Triggers account data synchronization for all accounts associated
    with the specified provider connection.

    Attributes:
        connection_id: Provider connection to sync.
        user_id: Requesting user (for authorization).
        force: Force sync even if recently synced.
    """

    connection_id: UUID
    user_id: UUID
    force: bool = False


@dataclass(frozen=True, kw_only=True)
class SyncTransactions:
    """Command to sync transactions from a provider connection.

    Triggers transaction data synchronization for all accounts
    associated with the specified provider connection.

    Attributes:
        connection_id: Provider connection to sync.
        user_id: Requesting user (for authorization).
        start_date: Sync transactions from this date (default: 30 days ago).
        end_date: Sync transactions until this date (default: today).
        account_id: Optionally sync only for specific account.
        force: Force sync even if recently synced.
    """

    connection_id: UUID
    user_id: UUID
    start_date: date | None = None
    end_date: date | None = None
    account_id: UUID | None = None
    force: bool = False
