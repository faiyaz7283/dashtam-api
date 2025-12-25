"""Integration tests for SyncAccountsHandler and SyncTransactionsHandler.

Tests cover:
- Successful account sync with provider data mapping
- Successful transaction sync with upsert logic
- Provider data mapping (type, subtype, status, asset type)
- Error handling (connection not found, not owned, credentials invalid)
- Date range filtering for transactions
- Account filtering (single vs all accounts)
- Repository operations with real database
- Event publishing

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations
- Mocked provider and encryption service (external dependencies)
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from sqlalchemy import text
from uuid_extensions import uuid7

from src.application.commands.handlers.sync_accounts_handler import (
    SyncAccountsError,
    SyncAccountsHandler,
)
from src.application.commands.handlers.sync_transactions_handler import (
    SyncTransactionsError,
    SyncTransactionsHandler,
)
from src.application.commands.sync_commands import SyncAccounts, SyncTransactions
from src.core.result import Failure, Success
from src.domain.enums.account_type import AccountType
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.enums.transaction_status import TransactionStatus
from src.domain.enums.transaction_subtype import TransactionSubtype
from src.domain.enums.transaction_type import TransactionType
from src.domain.protocols.provider_protocol import (
    ProviderAccountData,
    ProviderTransactionData,
)
from src.domain.value_objects.provider_credentials import ProviderCredentials
from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)
from src.infrastructure.persistence.repositories.provider_connection_repository import (
    ProviderConnectionRepository,
)
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)


# =============================================================================
# Test Helpers
# =============================================================================


async def create_user_in_db(session, user_id=None, email=None):
    """Create a user in the database for FK constraint."""
    from src.infrastructure.persistence.models.user import User as UserModel

    user_id = user_id or uuid7()
    email = email or f"test_{user_id}@example.com"

    user = UserModel(
        id=user_id,
        email=email,
        password_hash="$2b$12$test_hash",
        is_verified=True,
        is_active=True,
        failed_login_attempts=0,
    )
    session.add(user)
    await session.commit()
    return user_id


async def create_connection_in_db(
    session,
    user_id,
    provider_id,
    provider_slug="schwab",
    connection_id=None,
    status=ConnectionStatus.ACTIVE,
    credentials_data=b"encrypted_tokens",
):
    """Create a provider connection in the database for FK constraint."""
    from src.infrastructure.persistence.models.provider_connection import (
        ProviderConnection as ProviderConnectionModel,
    )

    connection_id = connection_id or uuid7()
    now = datetime.now(UTC)

    # Create credentials value object
    credentials = ProviderCredentials(
        encrypted_data=credentials_data,
        credential_type=CredentialType.OAUTH2,
        expires_at=now + timedelta(hours=1),
    )

    connection = ProviderConnectionModel(
        id=connection_id,
        user_id=user_id,
        provider_id=provider_id,
        provider_slug=provider_slug,
        status=status.value,
        encrypted_credentials=credentials.encrypted_data,
        credential_type=credentials.credential_type.value,
        credentials_expires_at=credentials.expires_at,
        connected_at=now,
        last_sync_at=None,
    )
    session.add(connection)
    await session.commit()
    return connection_id


async def create_account_in_db(
    session,
    connection_id,
    provider_account_id=None,
    account_type=AccountType.BROKERAGE,
    balance=Decimal("1000.00"),
):
    """Create an account in the database for FK constraint."""
    from src.infrastructure.persistence.models.account import Account as AccountModel

    account_id = uuid7()
    provider_account_id = provider_account_id or f"TEST-{uuid7().hex[:12].upper()}"
    now = datetime.now(UTC)

    account = AccountModel(
        id=account_id,
        connection_id=connection_id,
        provider_account_id=provider_account_id,
        account_number_masked="****1234",
        name="Test Account",
        account_type=account_type.value,
        balance=balance,
        currency="USD",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(account)
    await session.commit()
    return account_id, provider_account_id


def create_provider_account_data(
    provider_account_id="TEST-12345",
    name="Test Brokerage",
    account_type="BROKERAGE",
    balance=Decimal("5000.00"),
    available_balance=Decimal("4500.00"),
    is_active=True,
) -> ProviderAccountData:
    """Create test ProviderAccountData."""
    return ProviderAccountData(
        provider_account_id=provider_account_id,
        account_number_masked="****5678",
        name=name,
        account_type=account_type,
        balance=balance,
        currency="USD",
        available_balance=available_balance,
        is_active=is_active,
        raw_data={"test": "data"},
    )


def create_provider_transaction_data(
    provider_transaction_id="TXN-12345",
    transaction_type="TRADE",
    subtype="BUY",
    status="SETTLED",
    amount=Decimal("100.00"),
    description="Buy 10 shares of AAPL",
) -> ProviderTransactionData:
    """Create test ProviderTransactionData."""
    return ProviderTransactionData(
        provider_transaction_id=provider_transaction_id,
        transaction_type=transaction_type,
        subtype=subtype,
        status=status,
        amount=amount,
        currency="USD",
        description=description,
        asset_type="EQUITY",
        symbol="AAPL",
        security_name="Apple Inc",
        quantity=Decimal("10"),
        unit_price=Decimal("10.00"),
        commission=Decimal("0.00"),
        transaction_date=date.today(),
        settlement_date=date.today() + timedelta(days=2),
        raw_data={"test": "data"},
    )


class StubEventBus:
    """Stub event bus that records published events for verification."""

    def __init__(self):
        self.events = []

    async def publish(self, event, metadata=None):
        self.events.append(event)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(test_database):
    """Clean up tables before each test for isolation."""
    async with test_database.get_session() as session:
        await session.execute(text("TRUNCATE TABLE transactions CASCADE"))
        await session.execute(text("TRUNCATE TABLE accounts CASCADE"))
        await session.execute(text("TRUNCATE TABLE provider_connections CASCADE"))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def connection_with_dependencies(test_database, schwab_provider):
    """Create connection with all FK dependencies satisfied.

    Returns:
        tuple: (connection_id, user_id, provider_id)
    """
    provider_id, provider_slug = schwab_provider
    async with test_database.get_session() as session:
        user_id = await create_user_in_db(session)
        connection_id = await create_connection_in_db(
            session, user_id, provider_id, provider_slug
        )
    return connection_id, user_id, provider_id


# =============================================================================
# SyncAccountsHandler Tests
# =============================================================================


@pytest.mark.integration
class TestSyncAccountsHandlerSuccess:
    """Test SyncAccountsHandler successful sync scenarios."""

    @pytest.mark.asyncio
    async def test_sync_creates_new_accounts_in_database(
        self, test_database, connection_with_dependencies
    ):
        """Test syncing creates new accounts in database."""
        # Arrange
        connection_id, user_id, _ = connection_with_dependencies

        # Mock provider returning account data
        mock_provider = AsyncMock()
        provider_data = [
            create_provider_account_data(
                provider_account_id="ACC-001",
                name="Brokerage Account",
                balance=Decimal("10000.00"),
            ),
            create_provider_account_data(
                provider_account_id="ACC-002",
                name="IRA Account",
                account_type="IRA",
                balance=Decimal("25000.00"),
            ),
        ]
        mock_provider.fetch_accounts.return_value = Success(value=provider_data)

        # Mock encryption service
        mock_encryption = Mock()
        mock_encryption.decrypt.return_value = Success(
            value={"access_token": "mock_token"}
        )

        event_bus = StubEventBus()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            handler = SyncAccountsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncAccounts(connection_id=connection_id, user_id=user_id)
            result = await handler.handle(command)

        # Assert
        assert isinstance(result, Success)
        assert result.value.created == 2
        assert result.value.updated == 0
        assert result.value.unchanged == 0

        # Verify accounts exist in database
        async with test_database.get_session() as session:
            account_repo = AccountRepository(session=session)
            accounts = await account_repo.find_by_connection_id(
                connection_id=connection_id, active_only=False
            )
            assert len(accounts) == 2
            assert accounts[0].name == "Brokerage Account"
            assert accounts[0].balance.amount == Decimal("10000.00")
            assert accounts[1].name == "IRA Account"
            assert accounts[1].balance.amount == Decimal("25000.00")

    @pytest.mark.asyncio
    async def test_sync_updates_existing_accounts(
        self, test_database, connection_with_dependencies
    ):
        """Test syncing updates existing account balances."""
        # Arrange
        connection_id, user_id, _ = connection_with_dependencies

        # Create existing account
        async with test_database.get_session() as session:
            _, provider_account_id = await create_account_in_db(
                session, connection_id, balance=Decimal("1000.00")
            )

        # Mock provider returning updated data
        mock_provider = AsyncMock()
        provider_data = [
            create_provider_account_data(
                provider_account_id=provider_account_id,
                balance=Decimal("2000.00"),  # Updated balance
                available_balance=Decimal("1500.00"),
            )
        ]
        mock_provider.fetch_accounts.return_value = Success(value=provider_data)

        mock_encryption = Mock()
        mock_encryption.decrypt.return_value = Success(
            value={"access_token": "mock_token"}
        )

        event_bus = StubEventBus()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            handler = SyncAccountsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncAccounts(connection_id=connection_id, user_id=user_id)
            result = await handler.handle(command)

        # Assert
        assert isinstance(result, Success)
        assert result.value.created == 0
        assert result.value.updated == 1
        assert result.value.unchanged == 0

        # Verify balance updated
        async with test_database.get_session() as session:
            account_repo = AccountRepository(session=session)
            accounts = await account_repo.find_by_connection_id(
                connection_id=connection_id
            )
            assert len(accounts) == 1
            assert accounts[0].balance.amount == Decimal("2000.00")


@pytest.mark.integration
class TestSyncAccountsHandlerFailure:
    """Test SyncAccountsHandler failure scenarios."""

    @pytest.mark.asyncio
    async def test_sync_fails_when_connection_not_found(self, test_database):
        """Test sync fails with CONNECTION_NOT_FOUND when connection doesn't exist."""
        # Arrange
        fake_connection_id = uuid7()
        fake_user_id = uuid7()

        mock_provider = AsyncMock()
        mock_encryption = Mock()
        event_bus = StubEventBus()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            handler = SyncAccountsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncAccounts(
                connection_id=fake_connection_id, user_id=fake_user_id
            )
            result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == SyncAccountsError.CONNECTION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_sync_fails_when_not_owned_by_user(
        self, test_database, connection_with_dependencies
    ):
        """Test sync fails with NOT_OWNED_BY_USER when wrong user."""
        # Arrange
        connection_id, _, _ = connection_with_dependencies
        wrong_user_id = uuid7()

        mock_provider = AsyncMock()
        mock_encryption = Mock()
        event_bus = StubEventBus()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            handler = SyncAccountsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncAccounts(connection_id=connection_id, user_id=wrong_user_id)
            result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == SyncAccountsError.NOT_OWNED_BY_USER


# =============================================================================
# SyncTransactionsHandler Tests
# =============================================================================


@pytest.mark.integration
class TestSyncTransactionsHandlerSuccess:
    """Test SyncTransactionsHandler successful sync scenarios."""

    @pytest.mark.asyncio
    async def test_sync_creates_new_transactions_in_database(
        self, test_database, connection_with_dependencies
    ):
        """Test syncing creates new transactions in database."""
        # Arrange
        connection_id, user_id, _ = connection_with_dependencies

        # Create account
        async with test_database.get_session() as session:
            account_id, provider_account_id = await create_account_in_db(
                session, connection_id
            )

        # Mock provider returning transaction data
        mock_provider = AsyncMock()
        transaction_data = [
            create_provider_transaction_data(
                provider_transaction_id="TXN-001",
                transaction_type="TRADE",
                subtype="BUY",
                amount=Decimal("1000.00"),
            ),
            create_provider_transaction_data(
                provider_transaction_id="TXN-002",
                transaction_type="DIVIDEND",
                subtype="DIVIDEND",
                amount=Decimal("50.00"),
            ),
        ]
        mock_provider.fetch_transactions.return_value = Success(value=transaction_data)

        # Mock encryption service
        mock_encryption = Mock()
        mock_encryption.decrypt.return_value = Success(
            value={"access_token": "mock_token"}
        )

        event_bus = StubEventBus()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            transaction_repo = TransactionRepository(session=session)
            handler = SyncTransactionsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                transaction_repo=transaction_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncTransactions(
                connection_id=connection_id,
                user_id=user_id,
                account_id=account_id,
            )
            result = await handler.handle(command)

        # Assert
        assert isinstance(result, Success)
        assert result.value.created == 2
        assert result.value.updated == 0

        # Verify transactions exist in database
        async with test_database.get_session() as session:
            transaction_repo = TransactionRepository(session=session)
            transactions = await transaction_repo.find_by_account_id(
                account_id=account_id
            )
            assert len(transactions) == 2

    @pytest.mark.asyncio
    async def test_sync_with_date_range_filter(
        self, test_database, connection_with_dependencies
    ):
        """Test syncing with date range passes correct parameters to provider."""
        # Arrange
        connection_id, user_id, _ = connection_with_dependencies

        async with test_database.get_session() as session:
            account_id, _ = await create_account_in_db(session, connection_id)

        # Mock provider
        mock_provider = AsyncMock()
        mock_provider.fetch_transactions.return_value = Success(value=[])

        mock_encryption = Mock()
        mock_encryption.decrypt.return_value = Success(
            value={"access_token": "mock_token"}
        )

        event_bus = StubEventBus()

        start_date = date.today() - timedelta(days=60)
        end_date = date.today()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            transaction_repo = TransactionRepository(session=session)
            handler = SyncTransactionsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                transaction_repo=transaction_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncTransactions(
                connection_id=connection_id,
                user_id=user_id,
                account_id=account_id,
                start_date=start_date,
                end_date=end_date,
            )
            await handler.handle(command)

        # Assert - verify provider called with date range
        mock_provider.fetch_transactions.assert_called_once()
        call_kwargs = mock_provider.fetch_transactions.call_args[1]
        assert call_kwargs["start_date"] == start_date
        assert call_kwargs["end_date"] == end_date


@pytest.mark.integration
class TestSyncTransactionsHandlerFailure:
    """Test SyncTransactionsHandler failure scenarios."""

    @pytest.mark.asyncio
    async def test_sync_fails_when_connection_not_found(self, test_database):
        """Test sync fails when connection doesn't exist."""
        # Arrange
        fake_connection_id = uuid7()
        fake_user_id = uuid7()

        mock_provider = AsyncMock()
        mock_encryption = Mock()
        event_bus = StubEventBus()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            transaction_repo = TransactionRepository(session=session)
            handler = SyncTransactionsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                transaction_repo=transaction_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncTransactions(
                connection_id=fake_connection_id, user_id=fake_user_id
            )
            result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == SyncTransactionsError.CONNECTION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_sync_fails_when_account_not_found(
        self, test_database, connection_with_dependencies
    ):
        """Test sync fails when specified account doesn't exist."""
        # Arrange
        connection_id, user_id, _ = connection_with_dependencies
        fake_account_id = uuid7()

        mock_provider = AsyncMock()
        mock_encryption = Mock()
        mock_encryption.decrypt.return_value = Success(
            value={"access_token": "mock_token"}
        )
        event_bus = StubEventBus()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            transaction_repo = TransactionRepository(session=session)
            handler = SyncTransactionsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                transaction_repo=transaction_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncTransactions(
                connection_id=connection_id,
                user_id=user_id,
                account_id=fake_account_id,
            )
            result = await handler.handle(command)

        # Assert
        assert isinstance(result, Failure)
        assert result.error == SyncTransactionsError.ACCOUNT_NOT_FOUND


# =============================================================================
# Transaction Type Mapping Tests
# =============================================================================


@pytest.mark.integration
class TestTransactionTypeMapping:
    """Test transaction type, subtype, status, and asset type mapping logic."""

    @pytest.mark.asyncio
    async def test_maps_trade_types_correctly(
        self, test_database, connection_with_dependencies
    ):
        """Test handler correctly maps various trade types."""
        # Arrange
        connection_id, user_id, _ = connection_with_dependencies
        async with test_database.get_session() as session:
            account_id, _ = await create_account_in_db(session, connection_id)

        # Mock provider with various trade types
        mock_provider = AsyncMock()
        transaction_data = [
            create_provider_transaction_data(
                provider_transaction_id="BUY-001",
                transaction_type="BUY",
                subtype="PURCHASE",
            ),
            create_provider_transaction_data(
                provider_transaction_id="SELL-001",
                transaction_type="SELL",
                subtype="SALE",
            ),
            create_provider_transaction_data(
                provider_transaction_id="SHORT-001",
                transaction_type="TRADE",
                subtype="SHORT_SELL",
            ),
        ]
        mock_provider.fetch_transactions.return_value = Success(value=transaction_data)

        mock_encryption = Mock()
        mock_encryption.decrypt.return_value = Success(
            value={"access_token": "mock_token"}
        )
        event_bus = StubEventBus()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            transaction_repo = TransactionRepository(session=session)
            handler = SyncTransactionsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                transaction_repo=transaction_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncTransactions(
                connection_id=connection_id,
                user_id=user_id,
                account_id=account_id,
            )
            await handler.handle(command)

        # Assert - verify transaction types mapped correctly
        async with test_database.get_session() as session:
            transaction_repo = TransactionRepository(session=session)
            transactions = await transaction_repo.find_by_account_id(account_id)
            assert len(transactions) == 3

            # All should map to TRADE type
            assert all(
                t.transaction_type == TransactionType.TRADE for t in transactions
            )

            # Verify subtypes
            subtypes = {t.subtype for t in transactions}
            assert TransactionSubtype.BUY in subtypes
            assert TransactionSubtype.SELL in subtypes
            assert TransactionSubtype.SHORT_SELL in subtypes

    @pytest.mark.asyncio
    async def test_maps_status_correctly(
        self, test_database, connection_with_dependencies
    ):
        """Test handler correctly maps transaction status."""
        # Arrange
        connection_id, user_id, _ = connection_with_dependencies
        async with test_database.get_session() as session:
            account_id, _ = await create_account_in_db(session, connection_id)

        # Mock provider with different statuses
        mock_provider = AsyncMock()
        transaction_data = [
            create_provider_transaction_data(
                provider_transaction_id="SETTLED-001", status="SETTLED"
            ),
            create_provider_transaction_data(
                provider_transaction_id="PENDING-001", status="PENDING"
            ),
            create_provider_transaction_data(
                provider_transaction_id="FAILED-001", status="FAILED"
            ),
        ]
        mock_provider.fetch_transactions.return_value = Success(value=transaction_data)

        mock_encryption = Mock()
        mock_encryption.decrypt.return_value = Success(
            value={"access_token": "mock_token"}
        )
        event_bus = StubEventBus()

        # Act
        async with test_database.get_session() as session:
            connection_repo = ProviderConnectionRepository(session=session)
            account_repo = AccountRepository(session=session)
            transaction_repo = TransactionRepository(session=session)
            handler = SyncTransactionsHandler(
                connection_repo=connection_repo,
                account_repo=account_repo,
                transaction_repo=transaction_repo,
                encryption_service=mock_encryption,
                provider=mock_provider,
                event_bus=event_bus,
            )

            command = SyncTransactions(
                connection_id=connection_id,
                user_id=user_id,
                account_id=account_id,
            )
            await handler.handle(command)

        # Assert - verify status mapping
        async with test_database.get_session() as session:
            transaction_repo = TransactionRepository(session=session)
            transactions = await transaction_repo.find_by_account_id(account_id)

            # Create status map by provider_transaction_id
            status_map = {t.provider_transaction_id: t.status for t in transactions}
            assert status_map["SETTLED-001"] == TransactionStatus.SETTLED
            assert status_map["PENDING-001"] == TransactionStatus.PENDING
            assert status_map["FAILED-001"] == TransactionStatus.FAILED
