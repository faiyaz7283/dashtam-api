"""ListTransactions query handlers.

Handles requests to retrieve transaction lists with various filters.
Returns DTOs (not domain entities) to prevent leaking domain to presentation.

Architecture:
- Application layer handlers (orchestrate data retrieval)
- Returns Result[ListDTO, str] (explicit error handling)
- NO domain events (queries are side-effect free)
- Ownership verification: All queries scoped to account owned by user

Handlers:
    1. ListTransactionsByAccountHandler: List all transactions for an account
    2. ListTransactionsByDateRangeHandler: Filter by date range
    3. ListSecurityTransactionsHandler: Filter by security symbol (trades only)

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/transaction-domain-model.md
"""

from dataclasses import dataclass

from src.application.queries.handlers.get_transaction_handler import TransactionResult
from src.application.queries.transaction_queries import (
    ListSecurityTransactions,
    ListTransactionsByAccount,
    ListTransactionsByDateRange,
)
from src.core.result import Failure, Result, Success
from src.domain.entities.transaction import Transaction
from src.domain.protocols.account_repository import AccountRepository
from src.domain.protocols.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.domain.protocols.transaction_repository import TransactionRepository


@dataclass
class TransactionListResult:
    """Transaction list result DTO.

    Represents a paginated list of transactions for API response.

    Attributes:
        transactions: List of transaction DTOs.
        total_count: Total count of transactions (for pagination).
        has_more: True if more results available after current page.
    """

    transactions: list[TransactionResult]
    total_count: int
    has_more: bool


class ListTransactionsError:
    """ListTransactions-specific errors."""

    ACCOUNT_NOT_FOUND = "Account not found"
    CONNECTION_NOT_FOUND = "Provider connection not found"
    NOT_OWNED_BY_USER = "Account not owned by user"
    INVALID_DATE_RANGE = "Start date must be before end date"


def _map_transaction_to_dto(transaction: Transaction) -> TransactionResult:
    """Map Transaction entity to DTO (Money -> amount+currency).

    Args:
        transaction: Transaction domain entity.

    Returns:
        TransactionResult DTO.
    """
    return TransactionResult(
        id=transaction.id,
        account_id=transaction.account_id,
        provider_transaction_id=transaction.provider_transaction_id,
        transaction_type=transaction.transaction_type.value,
        subtype=transaction.subtype.value,
        status=transaction.status.value,
        amount_value=transaction.amount.amount,
        amount_currency=transaction.amount.currency,
        description=transaction.description,
        asset_type=transaction.asset_type.value if transaction.asset_type else None,
        symbol=transaction.symbol,
        security_name=transaction.security_name,
        quantity=transaction.quantity,
        unit_price_amount=(
            transaction.unit_price.amount if transaction.unit_price else None
        ),
        unit_price_currency=(
            transaction.unit_price.currency if transaction.unit_price else None
        ),
        commission_amount=(
            transaction.commission.amount if transaction.commission else None
        ),
        commission_currency=(
            transaction.commission.currency if transaction.commission else None
        ),
        transaction_date=transaction.transaction_date,
        settlement_date=transaction.settlement_date,
        is_trade=transaction.is_trade(),
        is_transfer=transaction.is_transfer(),
        is_income=transaction.is_income(),
        is_fee=transaction.is_fee(),
        is_debit=transaction.is_debit(),
        is_credit=transaction.is_credit(),
        is_settled=transaction.is_settled(),
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )


class ListTransactionsByAccountHandler:
    """Handler for ListTransactionsByAccount query.

    Retrieves transactions for an account with pagination and optional type filter.
    Ownership checked by verifying: Account->ProviderConnection->User

    Dependencies (injected via constructor):
        - TransactionRepository: For transaction retrieval
        - AccountRepository: For account lookup (ownership)
        - ProviderConnectionRepository: For ownership verification

    Returns:
        Result[TransactionListResult, str]: Success(DTO) or Failure(error)
    """

    def __init__(
        self,
        transaction_repo: TransactionRepository,
        account_repo: AccountRepository,
        connection_repo: ProviderConnectionRepository,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            transaction_repo: Transaction repository.
            account_repo: Account repository for ownership.
            connection_repo: Provider connection repository for ownership check.
        """
        self._transaction_repo = transaction_repo
        self._account_repo = account_repo
        self._connection_repo = connection_repo

    async def handle(
        self, query: ListTransactionsByAccount
    ) -> Result[TransactionListResult, str]:
        """Handle ListTransactionsByAccount query.

        Retrieves transactions for account, verifies ownership, and maps to DTO.

        Args:
            query: ListTransactionsByAccount query.

        Returns:
            Success(TransactionListResult): Transactions found and owned by user.
            Failure(error): Account not found or not owned by user.
        """
        # Fetch account to get connection_id
        account = await self._account_repo.find_by_id(query.account_id)

        if account is None:
            return Failure(error=ListTransactionsError.ACCOUNT_NOT_FOUND)

        # Fetch connection to verify ownership
        connection = await self._connection_repo.find_by_id(account.connection_id)

        if connection is None:
            return Failure(error=ListTransactionsError.CONNECTION_NOT_FOUND)

        # Verify ownership (connection belongs to user)
        if connection.user_id != query.user_id:
            return Failure(error=ListTransactionsError.NOT_OWNED_BY_USER)

        # Fetch transactions with filters
        if query.transaction_type is not None:
            transactions = await self._transaction_repo.find_by_account_and_type(
                account_id=query.account_id,
                transaction_type=query.transaction_type,
                limit=query.limit,
            )
        else:
            transactions = await self._transaction_repo.find_by_account_id(
                account_id=query.account_id, limit=query.limit, offset=query.offset
            )

        # Map to DTOs
        dtos = [_map_transaction_to_dto(t) for t in transactions]

        # Calculate pagination info
        has_more = len(transactions) == query.limit

        return Success(
            value=TransactionListResult(
                transactions=dtos,
                total_count=len(dtos),
                has_more=has_more,
            )
        )


class ListTransactionsByDateRangeHandler:
    """Handler for ListTransactionsByDateRange query.

    Retrieves transactions for an account within a date range.
    Ownership checked by verifying: Account->ProviderConnection->User

    Dependencies (injected via constructor):
        - TransactionRepository: For transaction retrieval
        - AccountRepository: For account lookup (ownership)
        - ProviderConnectionRepository: For ownership verification

    Returns:
        Result[TransactionListResult, str]: Success(DTO) or Failure(error)
    """

    def __init__(
        self,
        transaction_repo: TransactionRepository,
        account_repo: AccountRepository,
        connection_repo: ProviderConnectionRepository,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            transaction_repo: Transaction repository.
            account_repo: Account repository for ownership.
            connection_repo: Provider connection repository for ownership check.
        """
        self._transaction_repo = transaction_repo
        self._account_repo = account_repo
        self._connection_repo = connection_repo

    async def handle(
        self, query: ListTransactionsByDateRange
    ) -> Result[TransactionListResult, str]:
        """Handle ListTransactionsByDateRange query.

        Retrieves transactions within date range, verifies ownership, maps to DTO.

        Args:
            query: ListTransactionsByDateRange query.

        Returns:
            Success(TransactionListResult): Transactions found and owned by user.
            Failure(error): Invalid date range or account not owned by user.
        """
        # Validate date range
        if query.start_date >= query.end_date:
            return Failure(error=ListTransactionsError.INVALID_DATE_RANGE)

        # Fetch account to get connection_id
        account = await self._account_repo.find_by_id(query.account_id)

        if account is None:
            return Failure(error=ListTransactionsError.ACCOUNT_NOT_FOUND)

        # Fetch connection to verify ownership
        connection = await self._connection_repo.find_by_id(account.connection_id)

        if connection is None:
            return Failure(error=ListTransactionsError.CONNECTION_NOT_FOUND)

        # Verify ownership (connection belongs to user)
        if connection.user_id != query.user_id:
            return Failure(error=ListTransactionsError.NOT_OWNED_BY_USER)

        # Fetch transactions by date range
        transactions = await self._transaction_repo.find_by_date_range(
            account_id=query.account_id,
            start_date=query.start_date,
            end_date=query.end_date,
        )

        # Map to DTOs
        dtos = [_map_transaction_to_dto(t) for t in transactions]

        return Success(
            value=TransactionListResult(
                transactions=dtos,
                total_count=len(dtos),
                has_more=False,  # No pagination for date range queries
            )
        )


class ListSecurityTransactionsHandler:
    """Handler for ListSecurityTransactions query.

    Retrieves trade transactions for a specific security symbol.
    Ownership checked by verifying: Account->ProviderConnection->User

    Dependencies (injected via constructor):
        - TransactionRepository: For transaction retrieval
        - AccountRepository: For account lookup (ownership)
        - ProviderConnectionRepository: For ownership verification

    Returns:
        Result[TransactionListResult, str]: Success(DTO) or Failure(error)
    """

    def __init__(
        self,
        transaction_repo: TransactionRepository,
        account_repo: AccountRepository,
        connection_repo: ProviderConnectionRepository,
    ) -> None:
        """Initialize handler with dependencies.

        Args:
            transaction_repo: Transaction repository.
            account_repo: Account repository for ownership.
            connection_repo: Provider connection repository for ownership check.
        """
        self._transaction_repo = transaction_repo
        self._account_repo = account_repo
        self._connection_repo = connection_repo

    async def handle(
        self, query: ListSecurityTransactions
    ) -> Result[TransactionListResult, str]:
        """Handle ListSecurityTransactions query.

        Retrieves transactions for security, verifies ownership, maps to DTO.

        Args:
            query: ListSecurityTransactions query.

        Returns:
            Success(TransactionListResult): Security transactions found and owned.
            Failure(error): Account not found or not owned by user.
        """
        # Fetch account to get connection_id
        account = await self._account_repo.find_by_id(query.account_id)

        if account is None:
            return Failure(error=ListTransactionsError.ACCOUNT_NOT_FOUND)

        # Fetch connection to verify ownership
        connection = await self._connection_repo.find_by_id(account.connection_id)

        if connection is None:
            return Failure(error=ListTransactionsError.CONNECTION_NOT_FOUND)

        # Verify ownership (connection belongs to user)
        if connection.user_id != query.user_id:
            return Failure(error=ListTransactionsError.NOT_OWNED_BY_USER)

        # Fetch security transactions
        transactions = await self._transaction_repo.find_security_transactions(
            account_id=query.account_id, symbol=query.symbol, limit=query.limit
        )

        # Map to DTOs
        dtos = [_map_transaction_to_dto(t) for t in transactions]

        # Calculate pagination info
        has_more = len(transactions) == query.limit

        return Success(
            value=TransactionListResult(
                transactions=dtos,
                total_count=len(dtos),
                has_more=has_more,
            )
        )
