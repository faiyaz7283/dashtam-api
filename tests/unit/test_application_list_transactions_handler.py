"""Unit tests for ListTransactions handlers.

Tests the three transaction list query handlers covering:
- ListTransactionsByAccountHandler: Basic list, type filter, pagination
- ListTransactionsByDateRangeHandler: Date range filtering, validation
- ListSecurityTransactionsHandler: Symbol filtering, pagination

Test Coverage:
- Successful transaction list retrieval
- Account not found (ownership chain)
- Connection not found (ownership chain)
- Ownership verification failures
- Pagination (has_more flag)
- Optional filters (transaction_type, date_range, symbol)
- Date range validation
- Money value object conversion to amount+currency fields

Architecture:
    - Mock TransactionRepository, AccountRepository, ProviderConnectionRepository
    - Verify ownership chain: Account->ProviderConnection->User
    - Assert DTO list mapping and pagination

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/transaction-domain-model.md
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.queries.handlers.list_transactions_handler import (
    ListSecurityTransactionsHandler,
    ListTransactionsByAccountHandler,
    ListTransactionsByDateRangeHandler,
    ListTransactionsError,
)
from src.application.queries.transaction_queries import (
    ListSecurityTransactions,
    ListTransactionsByAccount,
    ListTransactionsByDateRange,
)
from src.core.result import Failure, Success
from src.domain.entities.account import Account
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.entities.transaction import Transaction
from src.domain.enums.account_type import AccountType
from src.domain.enums.asset_type import AssetType
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.enums.transaction_status import TransactionStatus
from src.domain.enums.transaction_subtype import TransactionSubtype
from src.domain.enums.transaction_type import TransactionType
from src.domain.value_objects.money import Money
from src.domain.value_objects.provider_credentials import ProviderCredentials


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def user_id() -> UUID:
    """User ID for ownership verification."""
    return uuid7()


@pytest.fixture
def connection_id() -> UUID:
    """Provider connection ID."""
    return uuid7()


@pytest.fixture
def account_id() -> UUID:
    """Account ID."""
    return uuid7()


@pytest.fixture
def provider_connection(user_id: UUID, connection_id: UUID) -> ProviderConnection:
    """Mock provider connection."""
    return ProviderConnection(
        id=connection_id,
        user_id=user_id,
        provider_id=uuid7(),
        provider_slug="schwab",
        status=ConnectionStatus.ACTIVE,
        credentials=ProviderCredentials(
            encrypted_data=b"encrypted-creds",
            credential_type=CredentialType.OAUTH2,
            expires_at=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        ),
        connected_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        last_sync_at=None,
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def account(account_id: UUID, connection_id: UUID) -> Account:
    """Mock account."""
    return Account(
        id=account_id,
        connection_id=connection_id,
        provider_account_id="ACC123",
        account_number_masked="****1234",
        name="My Brokerage",
        account_type=AccountType.BROKERAGE,
        currency="USD",
        balance=Money(amount=Decimal("10000.00"), currency="USD"),
        available_balance=Money(amount=Decimal("9500.00"), currency="USD"),
        is_active=True,
        last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def trade_transaction(account_id: UUID) -> Transaction:
    """Mock trade transaction."""
    return Transaction(
        id=uuid7(),
        account_id=account_id,
        provider_transaction_id="TXN123",
        transaction_type=TransactionType.TRADE,
        subtype=TransactionSubtype.BUY,
        status=TransactionStatus.SETTLED,
        amount=Money(amount=Decimal("-1500.00"), currency="USD"),
        description="Bought 10 shares of AAPL",
        asset_type=AssetType.EQUITY,
        symbol="AAPL",
        security_name="Apple Inc.",
        quantity=Decimal("10"),
        unit_price=Money(amount=Decimal("150.00"), currency="USD"),
        commission=Money(amount=Decimal("1.00"), currency="USD"),
        transaction_date=date(2025, 6, 1),
        settlement_date=date(2025, 6, 3),
        created_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def transfer_transaction(account_id: UUID) -> Transaction:
    """Mock transfer transaction."""
    return Transaction(
        id=uuid7(),
        account_id=account_id,
        provider_transaction_id="TXN456",
        transaction_type=TransactionType.TRANSFER,
        subtype=TransactionSubtype.DEPOSIT,
        status=TransactionStatus.SETTLED,
        amount=Money(amount=Decimal("1000.00"), currency="USD"),
        description="Deposit via ACH",
        transaction_date=date(2025, 6, 1),
        settlement_date=date(2025, 6, 2),
        created_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
    )


# ============================================================================
# ListTransactionsByAccount Tests
# ============================================================================


class TestListTransactionsByAccountHandler:
    """Test ListTransactionsByAccount handler."""

    @pytest.mark.asyncio
    async def test_returns_success_with_multiple_transactions(
        self,
        user_id: UUID,
        account_id: UUID,
        trade_transaction: Transaction,
        transfer_transaction: Transaction,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Success with list of transactions."""
        transactions = [trade_transaction, transfer_transaction]

        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_by_account_id_result=transactions
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = ListTransactionsByAccountHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByAccount(
            account_id=account_id, user_id=user_id, limit=50, offset=0
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Success)
        dto = result.value

        assert len(dto.transactions) == 2
        assert dto.total_count == 2
        assert dto.has_more is False

        # Verify first transaction (trade)
        assert dto.transactions[0].transaction_type == "trade"
        assert dto.transactions[0].symbol == "AAPL"

        # Verify second transaction (transfer)
        assert dto.transactions[1].transaction_type == "transfer"
        assert dto.transactions[1].symbol is None

    @pytest.mark.asyncio
    async def test_returns_success_with_type_filter(
        self,
        user_id: UUID,
        account_id: UUID,
        trade_transaction: Transaction,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Success with filtered transactions by type."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_by_account_and_type_result=[trade_transaction]
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = ListTransactionsByAccountHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByAccount(
            account_id=account_id,
            user_id=user_id,
            limit=50,
            offset=0,
            transaction_type=TransactionType.TRADE,
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Success)
        dto = result.value

        assert len(dto.transactions) == 1
        assert dto.transactions[0].transaction_type == "trade"

    @pytest.mark.asyncio
    async def test_returns_success_with_pagination_flag(
        self,
        user_id: UUID,
        account_id: UUID,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should set has_more=True when result count equals limit."""
        # Create exactly 10 transactions (limit)
        transactions = [
            Transaction(
                id=uuid7(),
                account_id=account_id,
                provider_transaction_id=f"TXN{i}",
                transaction_type=TransactionType.TRANSFER,
                subtype=TransactionSubtype.DEPOSIT,
                status=TransactionStatus.SETTLED,
                amount=Money(amount=Decimal("100.00"), currency="USD"),
                description=f"Transaction {i}",
                transaction_date=date(2025, 6, 1),
                created_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
                updated_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
            )
            for i in range(10)
        ]

        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_by_account_id_result=transactions
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = ListTransactionsByAccountHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByAccount(
            account_id=account_id, user_id=user_id, limit=10, offset=0
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Success)
        dto = result.value

        assert len(dto.transactions) == 10
        assert dto.has_more is True  # More results may exist

    @pytest.mark.asyncio
    async def test_returns_success_with_empty_list(
        self,
        user_id: UUID,
        account_id: UUID,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Success with empty list when no transactions."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(find_by_account_id_result=[])
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = ListTransactionsByAccountHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByAccount(
            account_id=account_id, user_id=user_id, limit=50, offset=0
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Success)
        dto = result.value

        assert len(dto.transactions) == 0
        assert dto.total_count == 0
        assert dto.has_more is False

    @pytest.mark.asyncio
    async def test_returns_failure_when_account_not_found(
        self, user_id: UUID, account_id: UUID
    ) -> None:
        """Should return Failure when account doesn't exist."""
        # Mock repositories
        transaction_repo = MockTransactionRepository()
        account_repo = MockAccountRepository(find_by_id_result=None)
        connection_repo = MockProviderConnectionRepository()

        # Execute
        handler = ListTransactionsByAccountHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByAccount(
            account_id=account_id, user_id=user_id, limit=50, offset=0
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ListTransactionsError.ACCOUNT_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_connection_not_found(
        self, user_id: UUID, account_id: UUID, account: Account
    ) -> None:
        """Should return Failure when connection doesn't exist."""
        # Mock repositories
        transaction_repo = MockTransactionRepository()
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(find_by_id_result=None)

        # Execute
        handler = ListTransactionsByAccountHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByAccount(
            account_id=account_id, user_id=user_id, limit=50, offset=0
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ListTransactionsError.CONNECTION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_not_owned_by_user(
        self,
        user_id: UUID,
        account_id: UUID,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Failure when account not owned by user."""
        # Different user connection
        other_user_id = uuid7()
        different_user_connection = ProviderConnection(
            id=provider_connection.id,
            user_id=other_user_id,
            provider_id=provider_connection.provider_id,
            provider_slug=provider_connection.provider_slug,
            status=provider_connection.status,
            credentials=provider_connection.credentials,
            connected_at=provider_connection.connected_at,
            last_sync_at=provider_connection.last_sync_at,
            created_at=provider_connection.created_at,
            updated_at=provider_connection.updated_at,
        )

        # Mock repositories
        transaction_repo = MockTransactionRepository()
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=different_user_connection
        )

        # Execute
        handler = ListTransactionsByAccountHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByAccount(
            account_id=account_id, user_id=user_id, limit=50, offset=0
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ListTransactionsError.NOT_OWNED_BY_USER


# ============================================================================
# ListTransactionsByDateRange Tests
# ============================================================================


class TestListTransactionsByDateRangeHandler:
    """Test ListTransactionsByDateRange handler."""

    @pytest.mark.asyncio
    async def test_returns_success_with_date_range_filter(
        self,
        user_id: UUID,
        account_id: UUID,
        trade_transaction: Transaction,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Success with transactions in date range."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_by_date_range_result=[trade_transaction]
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = ListTransactionsByDateRangeHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByDateRange(
            account_id=account_id,
            user_id=user_id,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 30),
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Success)
        dto = result.value

        assert len(dto.transactions) == 1
        assert dto.has_more is False  # No pagination for date range

    @pytest.mark.asyncio
    async def test_returns_failure_when_invalid_date_range(
        self, user_id: UUID, account_id: UUID
    ) -> None:
        """Should return Failure when start_date >= end_date."""
        # Mock repositories
        transaction_repo = MockTransactionRepository()
        account_repo = MockAccountRepository()
        connection_repo = MockProviderConnectionRepository()

        # Execute
        handler = ListTransactionsByDateRangeHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByDateRange(
            account_id=account_id,
            user_id=user_id,
            start_date=date(2025, 6, 30),
            end_date=date(2025, 6, 1),  # End before start
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ListTransactionsError.INVALID_DATE_RANGE

    @pytest.mark.asyncio
    async def test_returns_failure_when_account_not_found(
        self, user_id: UUID, account_id: UUID
    ) -> None:
        """Should return Failure when account doesn't exist."""
        # Mock repositories
        transaction_repo = MockTransactionRepository()
        account_repo = MockAccountRepository(find_by_id_result=None)
        connection_repo = MockProviderConnectionRepository()

        # Execute
        handler = ListTransactionsByDateRangeHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByDateRange(
            account_id=account_id,
            user_id=user_id,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 30),
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ListTransactionsError.ACCOUNT_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_not_owned_by_user(
        self,
        user_id: UUID,
        account_id: UUID,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Failure when account not owned by user."""
        # Different user connection
        other_user_id = uuid7()
        different_user_connection = ProviderConnection(
            id=provider_connection.id,
            user_id=other_user_id,
            provider_id=provider_connection.provider_id,
            provider_slug=provider_connection.provider_slug,
            status=provider_connection.status,
            credentials=provider_connection.credentials,
            connected_at=provider_connection.connected_at,
            last_sync_at=provider_connection.last_sync_at,
            created_at=provider_connection.created_at,
            updated_at=provider_connection.updated_at,
        )

        # Mock repositories
        transaction_repo = MockTransactionRepository()
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=different_user_connection
        )

        # Execute
        handler = ListTransactionsByDateRangeHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListTransactionsByDateRange(
            account_id=account_id,
            user_id=user_id,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 30),
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ListTransactionsError.NOT_OWNED_BY_USER


# ============================================================================
# ListSecurityTransactions Tests
# ============================================================================


class TestListSecurityTransactionsHandler:
    """Test ListSecurityTransactions handler."""

    @pytest.mark.asyncio
    async def test_returns_success_with_symbol_filter(
        self,
        user_id: UUID,
        account_id: UUID,
        trade_transaction: Transaction,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Success with transactions for security symbol."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_security_transactions_result=[trade_transaction]
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = ListSecurityTransactionsHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListSecurityTransactions(
            account_id=account_id, user_id=user_id, symbol="AAPL", limit=50
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Success)
        dto = result.value

        assert len(dto.transactions) == 1
        assert dto.transactions[0].symbol == "AAPL"
        assert dto.transactions[0].transaction_type == "trade"

    @pytest.mark.asyncio
    async def test_returns_success_with_pagination_flag(
        self,
        user_id: UUID,
        account_id: UUID,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should set has_more=True when result count equals limit."""
        # Create exactly 5 transactions (limit)
        transactions = [
            Transaction(
                id=uuid7(),
                account_id=account_id,
                provider_transaction_id=f"TXN{i}",
                transaction_type=TransactionType.TRADE,
                subtype=TransactionSubtype.BUY,
                status=TransactionStatus.SETTLED,
                amount=Money(amount=Decimal("-100.00"), currency="USD"),
                description=f"Bought AAPL {i}",
                asset_type=AssetType.EQUITY,
                symbol="AAPL",
                security_name="Apple Inc.",
                quantity=Decimal("1"),
                unit_price=Money(amount=Decimal("100.00"), currency="USD"),
                transaction_date=date(2025, 6, 1),
                created_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
                updated_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
            )
            for i in range(5)
        ]

        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_security_transactions_result=transactions
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = ListSecurityTransactionsHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListSecurityTransactions(
            account_id=account_id, user_id=user_id, symbol="AAPL", limit=5
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Success)
        dto = result.value

        assert len(dto.transactions) == 5
        assert dto.has_more is True

    @pytest.mark.asyncio
    async def test_returns_success_with_empty_list(
        self,
        user_id: UUID,
        account_id: UUID,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Success with empty list when no trades for symbol."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_security_transactions_result=[]
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = ListSecurityTransactionsHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListSecurityTransactions(
            account_id=account_id, user_id=user_id, symbol="TSLA", limit=50
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Success)
        dto = result.value

        assert len(dto.transactions) == 0
        assert dto.has_more is False

    @pytest.mark.asyncio
    async def test_returns_failure_when_account_not_found(
        self, user_id: UUID, account_id: UUID
    ) -> None:
        """Should return Failure when account doesn't exist."""
        # Mock repositories
        transaction_repo = MockTransactionRepository()
        account_repo = MockAccountRepository(find_by_id_result=None)
        connection_repo = MockProviderConnectionRepository()

        # Execute
        handler = ListSecurityTransactionsHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListSecurityTransactions(
            account_id=account_id, user_id=user_id, symbol="AAPL", limit=50
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ListTransactionsError.ACCOUNT_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_not_owned_by_user(
        self,
        user_id: UUID,
        account_id: UUID,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Failure when account not owned by user."""
        # Different user connection
        other_user_id = uuid7()
        different_user_connection = ProviderConnection(
            id=provider_connection.id,
            user_id=other_user_id,
            provider_id=provider_connection.provider_id,
            provider_slug=provider_connection.provider_slug,
            status=provider_connection.status,
            credentials=provider_connection.credentials,
            connected_at=provider_connection.connected_at,
            last_sync_at=provider_connection.last_sync_at,
            created_at=provider_connection.created_at,
            updated_at=provider_connection.updated_at,
        )

        # Mock repositories
        transaction_repo = MockTransactionRepository()
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=different_user_connection
        )

        # Execute
        handler = ListSecurityTransactionsHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = ListSecurityTransactions(
            account_id=account_id, user_id=user_id, symbol="AAPL", limit=50
        )
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == ListTransactionsError.NOT_OWNED_BY_USER


# ============================================================================
# Mock Repositories
# ============================================================================


class MockTransactionRepository:
    """Mock TransactionRepository for testing."""

    def __init__(
        self,
        find_by_account_id_result: list[Transaction] | None = None,
        find_by_account_and_type_result: list[Transaction] | None = None,
        find_by_date_range_result: list[Transaction] | None = None,
        find_security_transactions_result: list[Transaction] | None = None,
    ) -> None:
        """Initialize mock with predefined results."""
        self._find_by_account_id_result = find_by_account_id_result or []
        self._find_by_account_and_type_result = find_by_account_and_type_result or []
        self._find_by_date_range_result = find_by_date_range_result or []
        self._find_security_transactions_result = (
            find_security_transactions_result or []
        )

    async def find_by_account_id(
        self, account_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[Transaction]:
        """Mock find_by_account_id."""
        return self._find_by_account_id_result

    async def find_by_account_and_type(
        self,
        account_id: UUID,
        transaction_type: TransactionType,
        limit: int = 50,
    ) -> list[Transaction]:
        """Mock find_by_account_and_type."""
        return self._find_by_account_and_type_result

    async def find_by_date_range(
        self, account_id: UUID, start_date: date, end_date: date
    ) -> list[Transaction]:
        """Mock find_by_date_range."""
        return self._find_by_date_range_result

    async def find_security_transactions(
        self, account_id: UUID, symbol: str, limit: int = 50
    ) -> list[Transaction]:
        """Mock find_security_transactions."""
        return self._find_security_transactions_result


class MockAccountRepository:
    """Mock AccountRepository for testing."""

    def __init__(self, find_by_id_result: Account | None = None) -> None:
        """Initialize mock with predefined results."""
        self._find_by_id_result = find_by_id_result

    async def find_by_id(self, account_id: UUID) -> Account | None:
        """Mock find_by_id."""
        return self._find_by_id_result


class MockProviderConnectionRepository:
    """Mock ProviderConnectionRepository for testing."""

    def __init__(
        self, find_by_id_result: ProviderConnection | None = None
    ) -> None:
        """Initialize mock with predefined results."""
        self._find_by_id_result = find_by_id_result

    async def find_by_id(self, connection_id: UUID) -> ProviderConnection | None:
        """Mock find_by_id."""
        return self._find_by_id_result
