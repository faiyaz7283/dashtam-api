"""Data Sync DTOs (Data Transfer Objects).

Response/result dataclasses for sync command handlers.
These carry sync operation results from handlers back to the presentation layer.

DTOs:
    - SyncAccountsResult: Result from SyncAccounts command
    - SyncTransactionsResult: Result from SyncTransactions command
    - SyncHoldingsResult: Result from SyncHoldings command

Reference:
    - docs/architecture/cqrs.md (DTOs section)
"""

from dataclasses import dataclass


@dataclass
class SyncAccountsResult:
    """Result of account sync operation.

    Attributes:
        created: Number of new accounts created.
        updated: Number of existing accounts updated.
        unchanged: Number of accounts unchanged.
        errors: Number of accounts that failed to sync.
        message: Human-readable summary.
    """

    created: int
    updated: int
    unchanged: int
    errors: int
    message: str


@dataclass
class SyncTransactionsResult:
    """Result of transaction sync operation.

    Attributes:
        created: Number of new transactions created.
        updated: Number of existing transactions updated.
        unchanged: Number of transactions unchanged.
        errors: Number of transactions that failed to sync.
        accounts_synced: Number of accounts processed.
        message: Human-readable summary.
    """

    created: int
    updated: int
    unchanged: int
    errors: int
    accounts_synced: int
    message: str


@dataclass
class SyncHoldingsResult:
    """Result of holdings sync operation.

    Attributes:
        created: Number of new holdings created.
        updated: Number of existing holdings updated.
        unchanged: Number of holdings unchanged.
        deactivated: Number of holdings deactivated (no longer in provider).
        errors: Number of holdings that failed to sync.
        message: Human-readable summary.
    """

    created: int
    updated: int
    unchanged: int
    deactivated: int
    errors: int
    message: str
