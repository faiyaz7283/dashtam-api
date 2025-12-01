"""Account queries (CQRS read operations).

Queries represent requests for account data. They are immutable
dataclasses with question-like names. Queries NEVER change state.

Pattern:
- Queries are data containers (no logic)
- Handlers fetch and return data
- Queries never change state
- Queries do NOT emit domain events

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/account-domain-model.md
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.enums.account_type import AccountType


@dataclass(frozen=True, kw_only=True)
class GetAccount:
    """Get a single account by ID.

    Retrieves account details for display or verification.
    Includes ownership check via user_id (verified through connection).

    Attributes:
        account_id: Account to retrieve.
        user_id: User requesting (for ownership verification via connection).

    Example:
        >>> query = GetAccount(
        ...     account_id=account_id,
        ...     user_id=user_id,
        ... )
        >>> result = await handler.handle(query)
    """

    account_id: UUID
    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class ListAccountsByConnection:
    """List all accounts for a specific provider connection.

    Retrieves accounts linked to a connection (e.g., all Schwab accounts).
    Optionally filtered to active accounts only.

    Attributes:
        connection_id: Connection whose accounts to list.
        user_id: User requesting (for ownership verification).
        active_only: If True, only return active accounts.
            Default False returns all statuses.

    Example:
        >>> query = ListAccountsByConnection(
        ...     connection_id=connection_id,
        ...     user_id=user_id,
        ...     active_only=True,
        ... )
        >>> result = await handler.handle(query)
    """

    connection_id: UUID
    user_id: UUID
    active_only: bool = False


@dataclass(frozen=True, kw_only=True)
class ListAccountsByUser:
    """List all accounts across all connections for a user.

    Universal API - aggregates accounts from all provider connections.
    Optionally filtered by active status and/or account type.

    Attributes:
        user_id: User whose accounts to list.
        active_only: If True, only return active accounts.
            Default False returns all statuses.
        account_type: Optional filter by account type (e.g., BROKERAGE, IRA).
            Default None returns all types.

    Example:
        >>> query = ListAccountsByUser(
        ...     user_id=user_id,
        ...     active_only=True,
        ...     account_type=AccountType.BROKERAGE,
        ... )
        >>> result = await handler.handle(query)
    """

    user_id: UUID
    active_only: bool = False
    account_type: AccountType | None = None
