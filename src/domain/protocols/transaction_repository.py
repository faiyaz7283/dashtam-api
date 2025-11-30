"""Transaction repository protocol.

Defines the interface for transaction persistence operations.
"""

from datetime import date
from typing import Protocol
from uuid import UUID

from src.domain.entities.transaction import Transaction
from src.domain.enums.transaction_type import TransactionType


class TransactionRepository(Protocol):
    """Protocol for transaction persistence operations.

    Defines the contract for storing and retrieving transaction data.
    Infrastructure layer provides concrete implementations (e.g., PostgreSQL).

    **Design Principles**:
    - Read methods return domain entities (Transaction), not database models
    - All queries scoped to account_id (multi-tenancy boundary)
    - Pagination support for large result sets
    - Bulk operations for efficient provider sync
    - No update methods (transactions are immutable)

    **Implementation Notes**:
    - Save operations should be idempotent (handle duplicates)
    - Use provider_transaction_id for deduplication
    - created_at never changes, updated_at reflects last sync
    - Delete is soft delete (mark as CANCELLED) or hard delete (purge)
    """

    async def find_by_id(self, transaction_id: UUID) -> Transaction | None:
        """Find transaction by ID.

        Args:
            transaction_id: Unique transaction identifier.

        Returns:
            Transaction entity if found, None otherwise.

        Example:
            >>> transaction = await repo.find_by_id(transaction_id)
            >>> if transaction:
            ...     print(f"Found: {transaction.description}")
        """
        ...

    async def find_by_account_id(
        self,
        account_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        """Find all transactions for an account with pagination.

        Returns transactions ordered by transaction_date DESC (most recent first).

        Args:
            account_id: Account identifier to query.
            limit: Maximum number of transactions to return (default 50).
            offset: Number of transactions to skip (default 0).

        Returns:
            List of transactions (empty list if none found).

        Example:
            >>> # Get first page of transactions
            >>> transactions = await repo.find_by_account_id(account_id, limit=50)
            >>> # Get second page
            >>> more = await repo.find_by_account_id(account_id, limit=50, offset=50)
        """
        ...

    async def find_by_account_and_type(
        self,
        account_id: UUID,
        transaction_type: TransactionType,
        limit: int = 50,
    ) -> list[Transaction]:
        """Find transactions by account and type.

        Useful for querying specific transaction categories (e.g., all TRADE transactions).

        Args:
            account_id: Account identifier to query.
            transaction_type: Type of transactions to retrieve (TRADE, TRANSFER, etc.).
            limit: Maximum number of transactions to return (default 50).

        Returns:
            List of transactions matching the type (empty list if none found).
            Ordered by transaction_date DESC.

        Example:
            >>> # Get all trades for account
            >>> trades = await repo.find_by_account_and_type(
            ...     account_id,
            ...     TransactionType.TRADE,
            ...     limit=100
            ... )
        """
        ...

    async def find_by_date_range(
        self,
        account_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[Transaction]:
        """Find transactions within a date range.

        Queries by transaction_date (not created_at).

        Args:
            account_id: Account identifier to query.
            start_date: Start of date range (inclusive).
            end_date: End of date range (inclusive).

        Returns:
            List of transactions within date range (empty list if none found).
            Ordered by transaction_date ASC (chronological).

        Example:
            >>> # Get all transactions for Q4 2025
            >>> transactions = await repo.find_by_date_range(
            ...     account_id,
            ...     start_date=date(2025, 10, 1),
            ...     end_date=date(2025, 12, 31),
            ... )
        """
        ...

    async def find_by_provider_transaction_id(
        self,
        account_id: UUID,
        provider_transaction_id: str,
    ) -> Transaction | None:
        """Find transaction by provider's unique ID.

        Used for deduplication during sync operations.

        Args:
            account_id: Account identifier (scope to account for uniqueness).
            provider_transaction_id: Provider's unique transaction identifier.

        Returns:
            Transaction entity if found, None otherwise.

        Example:
            >>> # Check if provider transaction already exists
            >>> existing = await repo.find_by_provider_transaction_id(
            ...     account_id,
            ...     "schwab-12345678"
            ... )
            >>> if existing:
            ...     # Update instead of insert
        """
        ...

    async def find_security_transactions(
        self,
        account_id: UUID,
        symbol: str,
        limit: int = 50,
    ) -> list[Transaction]:
        """Find all transactions for a specific security.

        Queries TRADE transactions only (filters by symbol field).

        Args:
            account_id: Account identifier to query.
            symbol: Security ticker symbol (e.g., "AAPL").
            limit: Maximum number of transactions to return (default 50).

        Returns:
            List of trade transactions for the symbol (empty list if none found).
            Ordered by transaction_date DESC.

        Example:
            >>> # Get all AAPL trades
            >>> aapl_trades = await repo.find_security_transactions(
            ...     account_id,
            ...     symbol="AAPL",
            ...     limit=100
            ... )
            >>> # Calculate cost basis, P&L, etc.
        """
        ...

    async def save(self, transaction: Transaction) -> None:
        """Save a single transaction.

        Creates new transaction or updates existing (based on provider_transaction_id).

        Args:
            transaction: Transaction entity to save.

        Raises:
            DuplicateProviderTransaction: If provider_transaction_id already exists
                for this account (if not using upsert logic).

        Example:
            >>> transaction = Transaction(...)
            >>> await repo.save(transaction)
        """
        ...

    async def save_many(self, transactions: list[Transaction]) -> None:
        """Save multiple transactions in bulk.

        Efficient for provider sync operations that fetch many transactions at once.
        Uses bulk insert/upsert to minimize database round-trips.

        Args:
            transactions: List of transaction entities to save.

        Example:
            >>> # Sync transactions from provider
            >>> new_transactions = [...]  # From provider API
            >>> await repo.save_many(new_transactions)
        """
        ...

    async def delete(self, transaction_id: UUID) -> None:
        """Delete a transaction.

        **IMPORTANT**: This should be used carefully as transactions are historical records.
        Consider soft delete (mark as CANCELLED) instead of hard delete.

        Args:
            transaction_id: Unique transaction identifier to delete.

        Example:
            >>> # Hard delete (purge from database)
            >>> await repo.delete(transaction_id)
            >>>
            >>> # Soft delete alternative (preferred):
            >>> # Update transaction status to CANCELLED via re-sync
        """
        ...
