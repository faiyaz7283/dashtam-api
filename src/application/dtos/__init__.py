"""Data Transfer Objects (DTOs) for application layer.

DTOs are response/result dataclasses returned by command and query handlers.
They transfer data from the application layer to the presentation layer.

Categories:
    - auth_dtos: Authentication/authorization handler results
    - sync_dtos: Data synchronization handler results
    - import_dtos: File import handler results

Usage:
    from src.application.dtos import AuthenticatedUser, AuthTokens, SyncAccountsResult

Note:
    DTOs are NOT the same as:
    - Domain protocol data types (port interface contracts in domain layer)
    - Parser internal types (implementation details in infrastructure)
    - API schemas (Pydantic models in presentation layer)

Reference:
    - docs/architecture/cqrs.md (DTOs section)
"""

from src.application.dtos.auth_dtos import (
    AuthenticatedUser,
    AuthTokens,
    GlobalRotationResult,
    UserRotationResult,
)
from src.application.dtos.import_dtos import ImportResult
from src.application.dtos.sync_dtos import (
    BalanceChange,
    SyncAccountsResult,
    SyncHoldingsResult,
    SyncTransactionsResult,
)

__all__ = [
    # Auth DTOs
    "AuthenticatedUser",
    "AuthTokens",
    "GlobalRotationResult",
    "UserRotationResult",
    # Sync DTOs
    "BalanceChange",
    "SyncAccountsResult",
    "SyncTransactionsResult",
    "SyncHoldingsResult",
    # Import DTOs
    "ImportResult",
]
