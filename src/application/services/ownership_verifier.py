"""Ownership verification service.

Centralizes ownership verification logic for entities. This service is used
by query handlers to verify that the requesting user owns the entity before
returning data.

Architecture:
    - Application service (not domain - uses repositories)
    - Used by query handlers to avoid duplicating ownership checks
    - Returns entities on success for convenience (avoid double fetch)

Ownership Chain:
    Transaction/Holding → Account → ProviderConnection → User

Usage:
    verifier = OwnershipVerifier(account_repo, connection_repo)

    # Verify user owns connection
    result = await verifier.verify_connection_ownership(connection_id, user_id)

    # Verify user owns account (via connection)
    result = await verifier.verify_account_ownership(account_id, user_id)

Reference:
    - WARP.md Section 8 (Dependency Injection)
"""

from dataclasses import dataclass
from uuid import UUID

from src.core.result import Failure, Result, Success
from src.domain.entities import Account, Holding, ProviderConnection, Transaction
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.holding_repository import HoldingRepository
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.protocols.transaction_repository import TransactionRepository


@dataclass(frozen=True, kw_only=True)
class OwnershipError:
    """Ownership verification error details.

    Attributes:
        code: Error code for programmatic handling.
        message: Human-readable error message.
    """

    code: str
    message: str


class OwnershipErrorCode:
    """Standard ownership error codes."""

    TRANSACTION_NOT_FOUND = "transaction_not_found"
    HOLDING_NOT_FOUND = "holding_not_found"
    ACCOUNT_NOT_FOUND = "account_not_found"
    CONNECTION_NOT_FOUND = "connection_not_found"
    NOT_OWNED_BY_USER = "not_owned_by_user"


class OwnershipVerifier:
    """Service for verifying entity ownership.

    Provides methods to verify that a user owns various entities in the
    ownership chain: ProviderConnection → Account → Holdings/Transactions.

    This centralizes the ownership verification logic that was previously
    duplicated across multiple query handlers.

    Dependencies (injected via constructor):
        - TransactionRepository: For transaction retrieval
        - HoldingRepository: For holding retrieval
        - AccountRepository: For account retrieval
        - ProviderConnectionRepository: For connection retrieval

    Example:
        >>> verifier = OwnershipVerifier(transaction_repo, holding_repo, ...)
        >>> result = await verifier.verify_account_ownership(account_id, user_id)
        >>> if isinstance(result, Success):
        ...     account = result.value
        ...     # Proceed with account data
    """

    def __init__(
        self,
        transaction_repo: TransactionRepository,
        holding_repo: HoldingRepository,
        account_repo: AccountRepository,
        connection_repo: ProviderConnectionRepository,
    ) -> None:
        """Initialize ownership verifier with dependencies.

        Args:
            transaction_repo: Repository for transaction lookup.
            holding_repo: Repository for holding lookup.
            account_repo: Repository for account lookup.
            connection_repo: Repository for connection lookup and ownership check.
        """
        self._transaction_repo = transaction_repo
        self._holding_repo = holding_repo
        self._account_repo = account_repo
        self._connection_repo = connection_repo

    async def verify_connection_ownership(
        self,
        connection_id: UUID,
        user_id: UUID,
    ) -> Result[ProviderConnection, OwnershipError]:
        """Verify user owns a provider connection.

        Args:
            connection_id: The provider connection to verify.
            user_id: The user who should own the connection.

        Returns:
            Success(ProviderConnection): Connection exists and is owned by user.
            Failure(OwnershipError): Connection not found or not owned by user.
        """
        connection = await self._connection_repo.find_by_id(connection_id)

        if connection is None:
            return Failure(
                error=OwnershipError(
                    code=OwnershipErrorCode.CONNECTION_NOT_FOUND,
                    message="Provider connection not found",
                )
            )

        if connection.user_id != user_id:
            return Failure(
                error=OwnershipError(
                    code=OwnershipErrorCode.NOT_OWNED_BY_USER,
                    message="Provider connection not owned by user",
                )
            )

        return Success(value=connection)

    async def verify_account_ownership(
        self,
        account_id: UUID,
        user_id: UUID,
    ) -> Result[Account, OwnershipError]:
        """Verify user owns an account (via provider connection).

        Fetches the account, then verifies the user owns the connection.
        Returns the account on success for convenience (avoids double fetch).

        Args:
            account_id: The account to verify.
            user_id: The user who should own the account.

        Returns:
            Success(Account): Account exists and is owned by user.
            Failure(OwnershipError): Account/connection not found or not owned.
        """
        account = await self._account_repo.find_by_id(account_id)

        if account is None:
            return Failure(
                error=OwnershipError(
                    code=OwnershipErrorCode.ACCOUNT_NOT_FOUND,
                    message="Account not found",
                )
            )

        # Verify ownership via connection
        connection = await self._connection_repo.find_by_id(account.connection_id)

        if connection is None:
            return Failure(
                error=OwnershipError(
                    code=OwnershipErrorCode.CONNECTION_NOT_FOUND,
                    message="Provider connection not found",
                )
            )

        if connection.user_id != user_id:
            return Failure(
                error=OwnershipError(
                    code=OwnershipErrorCode.NOT_OWNED_BY_USER,
                    message="Account not owned by user",
                )
            )

        return Success(value=account)

    async def verify_account_ownership_only(
        self,
        account_id: UUID,
        user_id: UUID,
    ) -> Result[None, OwnershipError]:
        """Verify user owns an account without returning the account.

        Use this when you already have the account or don't need it.
        Slightly more efficient than verify_account_ownership.

        Args:
            account_id: The account to verify.
            user_id: The user who should own the account.

        Returns:
            Success(None): Account is owned by user.
            Failure(OwnershipError): Account/connection not found or not owned.
        """
        result = await self.verify_account_ownership(account_id, user_id)

        if isinstance(result, Failure):
            return result

        return Success(value=None)

    async def verify_holding_ownership(
        self,
        holding_id: UUID,
        user_id: UUID,
    ) -> Result[Holding, OwnershipError]:
        """Verify user owns a holding (via account and provider connection).

        Fetches the holding, then verifies the user owns it via the account
        and connection chain. Returns the holding on success.

        Args:
            holding_id: The holding to verify.
            user_id: The user who should own the holding.

        Returns:
            Success(Holding): Holding exists and is owned by user.
            Failure(OwnershipError): Holding/account/connection not found or not owned.
        """
        holding = await self._holding_repo.find_by_id(holding_id)

        if holding is None:
            return Failure(
                error=OwnershipError(
                    code=OwnershipErrorCode.HOLDING_NOT_FOUND,
                    message="Holding not found",
                )
            )

        # Verify ownership via account -> connection chain
        account_result = await self.verify_account_ownership(
            holding.account_id, user_id
        )

        if isinstance(account_result, Failure):
            return account_result

        return Success(value=holding)

    async def verify_transaction_ownership(
        self,
        transaction_id: UUID,
        user_id: UUID,
    ) -> Result[Transaction, OwnershipError]:
        """Verify user owns a transaction (via account and provider connection).

        Fetches the transaction, then verifies the user owns it via the account
        and connection chain. Returns the transaction on success.

        Args:
            transaction_id: The transaction to verify.
            user_id: The user who should own the transaction.

        Returns:
            Success(Transaction): Transaction exists and is owned by user.
            Failure(OwnershipError): Transaction/account/connection not found or not owned.
        """
        transaction = await self._transaction_repo.find_by_id(transaction_id)

        if transaction is None:
            return Failure(
                error=OwnershipError(
                    code=OwnershipErrorCode.TRANSACTION_NOT_FOUND,
                    message="Transaction not found",
                )
            )

        # Verify ownership via account -> connection chain
        account_result = await self.verify_account_ownership(
            transaction.account_id, user_id
        )

        if isinstance(account_result, Failure):
            return account_result

        return Success(value=transaction)
