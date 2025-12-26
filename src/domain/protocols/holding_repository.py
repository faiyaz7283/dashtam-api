"""Holding repository protocol.

Defines the interface for holding persistence operations.
Holdings are synced from providers and represent current portfolio positions.
"""

from typing import Protocol
from uuid import UUID

from src.domain.entities.holding import Holding


class HoldingRepository(Protocol):
    """Protocol for holding persistence operations.

    Defines the contract for storing and retrieving holding data.
    Infrastructure layer provides concrete implementations (e.g., PostgreSQL).

    **Design Principles**:
    - Read methods return domain entities (Holding), not database models
    - Holdings belong to accounts (account_id FK)
    - Bulk operations for sync efficiency (save_many, delete_by_account)
    - Active/inactive filtering for closed positions

    **Implementation Notes**:
    - Holdings are synced frequently, optimize for bulk operations
    - provider_holding_id + account_id is unique
    - Support upsert for sync operations (create or update)
    """

    async def find_by_id(self, holding_id: UUID) -> Holding | None:
        """Find holding by ID.

        Args:
            holding_id: Unique holding identifier.

        Returns:
            Holding entity if found, None otherwise.

        Example:
            >>> holding = await repo.find_by_id(holding_id)
            >>> if holding:
            ...     print(f"Found: {holding.symbol}")
        """
        ...

    async def find_by_account_and_symbol(
        self, account_id: UUID, symbol: str
    ) -> Holding | None:
        """Find holding by account and symbol.

        Args:
            account_id: Account identifier.
            symbol: Security symbol (e.g., "AAPL").

        Returns:
            Holding entity if found, None otherwise.

        Example:
            >>> holding = await repo.find_by_account_and_symbol(account_id, "AAPL")
            >>> if holding:
            ...     print(f"Owns {holding.quantity} shares")
        """
        ...

    async def find_by_provider_holding_id(
        self, account_id: UUID, provider_holding_id: str
    ) -> Holding | None:
        """Find holding by provider's unique identifier.

        Used for deduplication during sync operations.

        Args:
            account_id: Account identifier.
            provider_holding_id: Provider's unique holding identifier.

        Returns:
            Holding entity if found, None otherwise.

        Example:
            >>> holding = await repo.find_by_provider_holding_id(
            ...     account_id, "SCHWAB-AAPL-123"
            ... )
        """
        ...

    async def list_by_account(
        self, account_id: UUID, *, active_only: bool = True
    ) -> list[Holding]:
        """List holdings for an account.

        Args:
            account_id: Account identifier.
            active_only: If True, only return active holdings (quantity > 0).

        Returns:
            List of holdings for the account.

        Example:
            >>> holdings = await repo.list_by_account(account_id)
            >>> print(f"Found {len(holdings)} positions")
        """
        ...

    async def list_by_user(
        self, user_id: UUID, *, active_only: bool = True
    ) -> list[Holding]:
        """List all holdings across all accounts for a user.

        Requires joining through account -> connection -> user.

        Args:
            user_id: User identifier.
            active_only: If True, only return active holdings.

        Returns:
            List of all holdings for the user.

        Example:
            >>> holdings = await repo.list_by_user(user_id)
            >>> total_value = sum(h.market_value.amount for h in holdings)
        """
        ...

    async def save(self, holding: Holding) -> None:
        """Save a holding (create or update).

        Creates new holding if ID doesn't exist, updates if it does.
        Typically used for individual holding updates.

        Args:
            holding: Holding entity to save.

        Example:
            >>> await repo.save(holding)
        """
        ...

    async def save_many(self, holdings: list[Holding]) -> None:
        """Save multiple holdings in batch.

        Optimized for sync operations. Uses upsert logic:
        - Creates new holdings if they don't exist
        - Updates existing holdings if they do

        Args:
            holdings: List of holdings to save.

        Example:
            >>> await repo.save_many(holdings_from_provider)
        """
        ...

    async def delete(self, holding_id: UUID) -> None:
        """Delete a holding.

        Typically not used - holdings are marked inactive instead.
        May be needed for data cleanup operations.

        Args:
            holding_id: Holding ID to delete.

        Example:
            >>> await repo.delete(holding_id)
        """
        ...

    async def delete_by_account(self, account_id: UUID) -> int:
        """Delete all holdings for an account.

        Used when account is disconnected or for cleanup.

        Args:
            account_id: Account identifier.

        Returns:
            Number of holdings deleted.

        Example:
            >>> deleted = await repo.delete_by_account(account_id)
            >>> print(f"Deleted {deleted} holdings")
        """
        ...
