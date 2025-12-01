"""AccountRepository protocol for account persistence.

Port (interface) for hexagonal architecture.
Infrastructure layer implements this protocol.

Reference:
    - docs/architecture/account-domain-model.md
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from src.domain.entities.account import Account

if TYPE_CHECKING:
    from src.domain.enums.account_type import AccountType


class AccountRepository(Protocol):
    """Account repository protocol (port).

    Defines the interface for account persistence operations.
    Infrastructure layer provides concrete implementation.

    This is a Protocol (not ABC) for structural typing.
    Implementations don't need to inherit from this.

    Methods:
        find_by_id: Retrieve account by ID
        find_by_connection_id: Retrieve all accounts for a connection
        find_by_user_id: Retrieve all accounts across connections for user
        find_by_provider_account_id: Retrieve account by provider's identifier
        find_active_by_user: Retrieve active accounts for user
        find_needing_sync: Retrieve accounts not synced within threshold
        save: Create or update account
        delete: Remove account

    Example Implementation:
        >>> class PostgresAccountRepository:
        ...     async def find_by_id(self, id: UUID) -> Account | None:
        ...         # Database logic here
        ...         pass
    """

    async def find_by_id(self, account_id: UUID) -> Account | None:
        """Find account by ID.

        Args:
            account_id: Account's unique identifier (internal).

        Returns:
            Account if found, None otherwise.

        Example:
            >>> account = await repo.find_by_id(account_id)
            >>> if account:
            ...     print(account.name)
        """
        ...

    async def find_by_connection_id(
        self, connection_id: UUID, active_only: bool = False
    ) -> list[Account]:
        """Find all accounts for a provider connection.

        A connection can have multiple accounts (e.g., IRA and brokerage
        at same provider).

        Args:
            connection_id: ProviderConnection's unique identifier.
            active_only: If True, return only active accounts. Default False.

        Returns:
            List of accounts (empty if none found).

        Example:
            >>> accounts = await repo.find_by_connection_id(connection_id)
            >>> for account in accounts:
            ...     print(f"{account.name}: {account.balance}")
            >>> active = await repo.find_by_connection_id(connection_id, active_only=True)
        """
        ...

    async def find_by_user_id(
        self,
        user_id: UUID,
        active_only: bool = False,
        account_type: "AccountType | None" = None,
    ) -> list[Account]:
        """Find all accounts across all connections for a user.

        Aggregates accounts from all provider connections.

        Args:
            user_id: User's unique identifier.
            active_only: If True, return only active accounts. Default False.
            account_type: Optional filter by account type (e.g., AccountType.IRA).

        Returns:
            List of accounts (empty if none found).

        Example:
            >>> all_accounts = await repo.find_by_user_id(user_id)
            >>> total = sum(a.balance.amount for a in all_accounts if a.currency == "USD")
            >>> iras = await repo.find_by_user_id(user_id, account_type=AccountType.IRA)
        """
        ...

    async def find_by_provider_account_id(
        self,
        connection_id: UUID,
        provider_account_id: str,
    ) -> Account | None:
        """Find account by provider's identifier.

        Used during sync to match provider data with existing accounts.
        Provider account ID is unique within a connection.

        Args:
            connection_id: ProviderConnection's unique identifier.
            provider_account_id: Provider's unique account identifier.

        Returns:
            Account if found, None otherwise.

        Example:
            >>> account = await repo.find_by_provider_account_id(
            ...     connection_id, "SCHWAB-12345"
            ... )
            >>> if account:
            ...     account.update_balance(new_balance)
        """
        ...

    async def find_active_by_user(self, user_id: UUID) -> list[Account]:
        """Find all active accounts for a user.

        Only returns accounts with is_active=True.

        Args:
            user_id: User's unique identifier.

        Returns:
            List of active accounts (empty if none found).

        Example:
            >>> active = await repo.find_active_by_user(user_id)
            >>> for account in active:
            ...     print(f"{account.name}: {account.balance}")
        """
        ...

    async def find_needing_sync(
        self,
        threshold: timedelta,
    ) -> list[Account]:
        """Find accounts not synced within threshold.

        Used by background job to identify stale accounts.

        Args:
            threshold: Maximum time since last sync.

        Returns:
            List of accounts needing sync (empty if none found).

        Example:
            >>> stale = await repo.find_needing_sync(timedelta(hours=1))
            >>> for account in stale:
            ...     # Trigger sync for account's connection
        """
        ...

    async def save(self, account: Account) -> None:
        """Create or update account in database.

        Uses upsert semantics - creates if not exists, updates if exists.

        Args:
            account: Account entity to persist.

        Raises:
            DatabaseError: If database operation fails.

        Example:
            >>> account = Account(...)
            >>> await repo.save(account)
        """
        ...

    async def delete(self, account_id: UUID) -> None:
        """Remove account from database.

        Hard delete - permanently removes the record.
        For soft delete, use deactivate() on the entity instead.

        Args:
            account_id: Account's unique identifier.

        Raises:
            NotFoundError: If account doesn't exist.
            DatabaseError: If database operation fails.

        Note:
            Consider using deactivate() for audit trail instead of delete.

        Example:
            >>> await repo.delete(account_id)
        """
        ...
