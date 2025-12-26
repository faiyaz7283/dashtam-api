"""Holding queries (CQRS read operations).

Queries represent requests for holding data. They are immutable
dataclasses with question-like names. Queries NEVER change state.

Pattern:
- Queries are data containers (no logic)
- Handlers fetch and return data
- Queries never change state
- Queries do NOT emit domain events

Reference:
    - docs/architecture/cqrs-pattern.md
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class GetHolding:
    """Get a single holding by ID.

    Retrieves holding details for display.
    Includes ownership check via user_id (verified through account → connection).

    Attributes:
        holding_id: Holding to retrieve.
        user_id: User requesting (for ownership verification).

    Example:
        >>> query = GetHolding(
        ...     holding_id=holding_id,
        ...     user_id=user_id,
        ... )
        >>> result = await handler.handle(query)
    """

    holding_id: UUID
    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class ListHoldingsByAccount:
    """List all holdings for a specific account.

    Retrieves all positions/holdings for an account.
    Optionally filtered to active holdings only.

    Attributes:
        account_id: Account whose holdings to list.
        user_id: User requesting (for ownership verification).
        active_only: If True, only return active holdings.
            Default True (exclude sold/deactivated positions).
        asset_type: Optional filter by asset type (e.g., "equity", "option").
            Default None returns all types.

    Example:
        >>> query = ListHoldingsByAccount(
        ...     account_id=account_id,
        ...     user_id=user_id,
        ...     active_only=True,
        ... )
        >>> result = await handler.handle(query)
    """

    account_id: UUID
    user_id: UUID
    active_only: bool = True
    asset_type: str | None = None


@dataclass(frozen=True, kw_only=True)
class ListHoldingsByUser:
    """List all holdings across all accounts for a user.

    Universal API - aggregates holdings from all accounts.
    Optionally filtered by active status and/or asset type.

    Attributes:
        user_id: User whose holdings to list.
        active_only: If True, only return active holdings.
            Default True (exclude sold/deactivated positions).
        asset_type: Optional filter by asset type (e.g., "equity", "option").
            Default None returns all types.
        symbol: Optional filter by security symbol.
            Default None returns all symbols.

    Example:
        >>> query = ListHoldingsByUser(
        ...     user_id=user_id,
        ...     active_only=True,
        ...     asset_type="equity",
        ... )
        >>> result = await handler.handle(query)
    """

    user_id: UUID
    active_only: bool = True
    asset_type: str | None = None
    symbol: str | None = None
