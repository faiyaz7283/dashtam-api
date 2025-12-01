"""Unit tests for GetTransactionHandler.

Tests the GetTransaction query handler covering:
- Successful transaction retrieval
- Transaction not found
- Account not found (ownership chain)
- Provider connection not found (ownership chain)
- Ownership verification failures
- Money value object conversion to amount+currency fields
- Optional security fields (trade vs non-trade)
- Boolean flags from entity query methods

Architecture:
    - Mock TransactionRepository, AccountRepository, ProviderConnectionRepository
    - Verify ownership chain: Transaction->Account->ProviderConnection->User
    - Assert DTO mapping correctness (Money, enum values, optional fields)

Reference:
    - docs/architecture/cqrs-pattern.md
    - docs/architecture/transaction-domain-model.md
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.queries.handlers.get_transaction_handler import (
    GetTransactionError,
    GetTransactionHandler,
)
from src.application.queries.transaction_queries import GetTransaction
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
def transaction_id() -> UUID:
    """Transaction ID."""
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
def trade_transaction(transaction_id: UUID, account_id: UUID) -> Transaction:
    """Mock trade transaction (has security fields)."""
    return Transaction(
        id=transaction_id,
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
def transfer_transaction(transaction_id: UUID, account_id: UUID) -> Transaction:
    """Mock transfer transaction (no security fields)."""
    return Transaction(
        id=transaction_id,
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
# Success Tests
# ============================================================================


class TestGetTransactionHandlerSuccess:
    """Test successful GetTransaction query handling."""

    @pytest.mark.asyncio
    async def test_returns_success_with_trade_transaction(
        self,
        user_id: UUID,
        transaction_id: UUID,
        trade_transaction: Transaction,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Success with DTO for trade transaction (all fields)."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_by_id_result=trade_transaction
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = GetTransactionHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = GetTransaction(transaction_id=transaction_id, user_id=user_id)
        result = await handler.handle(query)

        # Assert - Success
        assert isinstance(result, Success)
        dto = result.value

        # Assert - Basic fields
        assert dto.id == transaction_id
        assert dto.account_id == account.id
        assert dto.provider_transaction_id == "TXN123"
        assert dto.transaction_type == "trade"
        assert dto.subtype == "buy"
        assert dto.status == "settled"
        assert dto.description == "Bought 10 shares of AAPL"

        # Assert - Money conversion
        assert dto.amount_value == Decimal("-1500.00")
        assert dto.amount_currency == "USD"

        # Assert - Security fields (trade only)
        assert dto.asset_type == "equity"
        assert dto.symbol == "AAPL"
        assert dto.security_name == "Apple Inc."
        assert dto.quantity == Decimal("10")
        assert dto.unit_price_amount == Decimal("150.00")
        assert dto.unit_price_currency == "USD"
        assert dto.commission_amount == Decimal("1.00")
        assert dto.commission_currency == "USD"

        # Assert - Dates
        assert dto.transaction_date == date(2025, 6, 1)
        assert dto.settlement_date == date(2025, 6, 3)

        # Assert - Boolean flags
        assert dto.is_trade is True
        assert dto.is_transfer is False
        assert dto.is_income is False
        assert dto.is_fee is False
        assert dto.is_debit is True
        assert dto.is_credit is False
        assert dto.is_settled is True

    @pytest.mark.asyncio
    async def test_returns_success_with_transfer_transaction(
        self,
        user_id: UUID,
        transaction_id: UUID,
        transfer_transaction: Transaction,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Success with DTO for transfer (no security fields)."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_by_id_result=transfer_transaction
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=provider_connection
        )

        # Execute
        handler = GetTransactionHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = GetTransaction(transaction_id=transaction_id, user_id=user_id)
        result = await handler.handle(query)

        # Assert - Success
        assert isinstance(result, Success)
        dto = result.value

        # Assert - Basic fields
        assert dto.transaction_type == "transfer"
        assert dto.subtype == "deposit"

        # Assert - Security fields should be None
        assert dto.asset_type is None
        assert dto.symbol is None
        assert dto.security_name is None
        assert dto.quantity is None
        assert dto.unit_price_amount is None
        assert dto.unit_price_currency is None
        assert dto.commission_amount is None
        assert dto.commission_currency is None

        # Assert - Boolean flags
        assert dto.is_trade is False
        assert dto.is_transfer is True
        assert dto.is_credit is True  # Positive amount


# ============================================================================
# Failure Tests
# ============================================================================


class TestGetTransactionHandlerFailures:
    """Test GetTransaction query failure cases."""

    @pytest.mark.asyncio
    async def test_returns_failure_when_transaction_not_found(
        self, user_id: UUID, transaction_id: UUID
    ) -> None:
        """Should return Failure when transaction doesn't exist."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(find_by_id_result=None)
        account_repo = MockAccountRepository(find_by_id_result=None)
        connection_repo = MockProviderConnectionRepository(find_by_id_result=None)

        # Execute
        handler = GetTransactionHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = GetTransaction(transaction_id=transaction_id, user_id=user_id)
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == GetTransactionError.TRANSACTION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_account_not_found(
        self,
        user_id: UUID,
        transaction_id: UUID,
        trade_transaction: Transaction,
    ) -> None:
        """Should return Failure when account doesn't exist (broken chain)."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_by_id_result=trade_transaction
        )
        account_repo = MockAccountRepository(find_by_id_result=None)
        connection_repo = MockProviderConnectionRepository(find_by_id_result=None)

        # Execute
        handler = GetTransactionHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = GetTransaction(transaction_id=transaction_id, user_id=user_id)
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == GetTransactionError.ACCOUNT_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_connection_not_found(
        self,
        user_id: UUID,
        transaction_id: UUID,
        trade_transaction: Transaction,
        account: Account,
    ) -> None:
        """Should return Failure when connection doesn't exist (broken chain)."""
        # Mock repositories
        transaction_repo = MockTransactionRepository(
            find_by_id_result=trade_transaction
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(find_by_id_result=None)

        # Execute
        handler = GetTransactionHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = GetTransaction(transaction_id=transaction_id, user_id=user_id)
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == GetTransactionError.CONNECTION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_failure_when_not_owned_by_user(
        self,
        user_id: UUID,
        transaction_id: UUID,
        trade_transaction: Transaction,
        account: Account,
        provider_connection: ProviderConnection,
    ) -> None:
        """Should return Failure when connection belongs to different user."""
        # Modify connection to belong to different user
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
        transaction_repo = MockTransactionRepository(
            find_by_id_result=trade_transaction
        )
        account_repo = MockAccountRepository(find_by_id_result=account)
        connection_repo = MockProviderConnectionRepository(
            find_by_id_result=different_user_connection
        )

        # Execute
        handler = GetTransactionHandler(
            transaction_repo=transaction_repo,
            account_repo=account_repo,
            connection_repo=connection_repo,
        )
        query = GetTransaction(transaction_id=transaction_id, user_id=user_id)
        result = await handler.handle(query)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == GetTransactionError.NOT_OWNED_BY_USER


# ============================================================================
# Mock Repositories
# ============================================================================


class MockTransactionRepository:
    """Mock TransactionRepository for testing."""

    def __init__(self, find_by_id_result: Transaction | None = None) -> None:
        """Initialize mock with predefined results."""
        self._find_by_id_result = find_by_id_result

    async def find_by_id(self, transaction_id: UUID) -> Transaction | None:
        """Mock find_by_id."""
        return self._find_by_id_result


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
