"""Integration tests for TransactionRepository.

Tests cover:
- Save and retrieve transaction
- Save many (bulk operations)
- Find by ID
- Find by account ID (with pagination)
- Find by account and type
- Find by date range
- Find by provider transaction ID
- Find security transactions (by symbol)
- Delete transaction
- Entity ↔ Model mapping (Money, enums)

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations
"""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from uuid_extensions import uuid7

from src.domain.entities.transaction import Transaction
from src.domain.enums.asset_type import AssetType
from src.domain.enums.transaction_status import TransactionStatus
from src.domain.enums.transaction_subtype import TransactionSubtype
from src.domain.enums.transaction_type import TransactionType
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.repositories.transaction_repository import (
    TransactionRepository,
)


# =============================================================================
# Test Helpers
# =============================================================================


# Sentinel value for distinguishing "not provided" from "explicitly None"
_NOT_PROVIDED = object()


def create_test_transaction(
    transaction_id=None,
    account_id=None,
    provider_transaction_id=None,
    transaction_type=TransactionType.TRADE,
    subtype=TransactionSubtype.BUY,
    status=TransactionStatus.SETTLED,
    amount=_NOT_PROVIDED,
    currency="USD",
    description="Test transaction",
    asset_type=_NOT_PROVIDED,
    symbol=_NOT_PROVIDED,
    security_name=_NOT_PROVIDED,
    quantity=_NOT_PROVIDED,
    unit_price=_NOT_PROVIDED,
    commission=_NOT_PROVIDED,
    transaction_date=None,
    settlement_date=None,
    provider_metadata=None,
) -> Transaction:
    """Create a test Transaction with default values.

    Uses sentinel value _NOT_PROVIDED to distinguish between:
    - Parameter not provided → use default (e.g., quantity=10 for TRADE)
    - Parameter explicitly None → keep None (e.g., quantity=None for TRANSFER)
    """
    now = datetime.now(UTC)

    # Defaults for TRADE transactions
    if amount is _NOT_PROVIDED:
        amount = Money(Decimal("-1050.00"), currency)
    if asset_type is _NOT_PROVIDED:
        asset_type = AssetType.EQUITY
    if symbol is _NOT_PROVIDED:
        symbol = "AAPL"
    if security_name is _NOT_PROVIDED:
        security_name = "Apple Inc."
    if quantity is _NOT_PROVIDED:
        quantity = Decimal("10")
    if unit_price is _NOT_PROVIDED:
        unit_price = Money(Decimal("105.00"), currency)
    if commission is _NOT_PROVIDED:
        commission = None  # Optional field

    if transaction_date is None:
        transaction_date = date.today()
    if provider_transaction_id is None:
        # Generate unique provider_transaction_id
        provider_transaction_id = f"TEST-{uuid7().hex.upper()}"

    return Transaction(
        id=transaction_id or uuid7(),
        account_id=account_id or uuid7(),
        provider_transaction_id=provider_transaction_id,
        transaction_type=transaction_type,
        subtype=subtype,
        status=status,
        amount=amount,
        description=description,
        asset_type=asset_type,
        symbol=symbol,
        security_name=security_name,
        quantity=quantity,
        unit_price=unit_price,
        commission=commission,
        transaction_date=transaction_date,
        settlement_date=settlement_date,
        provider_metadata=provider_metadata,
        created_at=now,
        updated_at=now,
    )


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


async def create_connection_in_db(session, user_id, connection_id=None):
    """Create a provider connection in the database for FK constraint."""
    from src.domain.enums.connection_status import ConnectionStatus
    from src.infrastructure.persistence.models.provider_connection import (
        ProviderConnection as ProviderConnectionModel,
    )

    connection_id = connection_id or uuid7()

    connection = ProviderConnectionModel(
        id=connection_id,
        user_id=user_id,
        provider_id=uuid7(),
        provider_slug="schwab",
        status=ConnectionStatus.ACTIVE.value,
    )
    session.add(connection)
    await session.commit()
    return connection_id


async def create_account_in_db(session, connection_id, account_id=None):
    """Create an account in the database for FK constraint."""
    from src.infrastructure.persistence.models.account import Account as AccountModel

    account_id = account_id or uuid7()

    account = AccountModel(
        id=account_id,
        connection_id=connection_id,
        provider_account_id=f"ACCT-{uuid7().hex[:8].upper()}",
        account_number_masked="****1234",
        name="Test Account",
        account_type="brokerage",
        balance=Decimal("10000.00"),
        currency="USD",
        is_active=True,
    )
    session.add(account)
    await session.commit()
    return account_id


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest_asyncio.fixture(autouse=True)
async def clean_transactions_table(test_database):
    """Clean up transactions table before each test.

    This fixture runs automatically before each test to ensure
    test isolation. It truncates the transactions table to remove
    any data from previous test runs.
    """
    async with test_database.get_session() as session:
        # Truncate transactions table (CASCADE to handle FK dependencies)
        await session.execute(text("TRUNCATE TABLE transactions CASCADE"))
        await session.commit()
    yield


# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.integration
class TestTransactionRepositorySave:
    """Test TransactionRepository save operations."""

    @pytest.mark.asyncio
    async def test_save_transaction_persists_to_database(self, test_database):
        """Test saving a transaction persists it to the database."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        transaction = create_test_transaction(account_id=account_id)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Assert
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_id(transaction.id)

            assert found is not None
            assert found.id == transaction.id
            assert found.account_id == account_id
            assert found.transaction_type == TransactionType.TRADE
            assert found.symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_save_transaction_with_all_money_fields(self, test_database):
        """Test saving transaction with amount, unit_price, and commission."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        amount = Money(Decimal("-1050.00"), "USD")
        unit_price = Money(Decimal("105.00"), "USD")
        commission = Money(Decimal("5.00"), "USD")

        transaction = create_test_transaction(
            account_id=account_id,
            amount=amount,
            unit_price=unit_price,
            commission=commission,
        )

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Assert
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_id(transaction.id)

            assert found is not None
            assert found.amount == amount
            assert found.unit_price == unit_price
            assert found.commission == commission

    @pytest.mark.asyncio
    async def test_save_transaction_update_existing(self, test_database):
        """Test updating an existing transaction."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        transaction = create_test_transaction(
            account_id=account_id,
            status=TransactionStatus.PENDING,
        )

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Act - Update status
        transaction = Transaction(
            id=transaction.id,
            account_id=transaction.account_id,
            provider_transaction_id=transaction.provider_transaction_id,
            transaction_type=transaction.transaction_type,
            subtype=transaction.subtype,
            status=TransactionStatus.SETTLED,  # Changed
            amount=transaction.amount,
            description=transaction.description,
            asset_type=transaction.asset_type,
            symbol=transaction.symbol,
            security_name=transaction.security_name,
            quantity=transaction.quantity,
            unit_price=transaction.unit_price,
            commission=transaction.commission,
            transaction_date=transaction.transaction_date,
            settlement_date=date.today(),  # Added
            provider_metadata=transaction.provider_metadata,
            created_at=transaction.created_at,
            updated_at=datetime.now(UTC),
        )

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Assert
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_id(transaction.id)

            assert found is not None
            assert found.status == TransactionStatus.SETTLED
            assert found.settlement_date == date.today()

    @pytest.mark.asyncio
    async def test_save_non_trade_transaction(self, test_database):
        """Test saving non-TRADE transaction (no security fields)."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        transaction = create_test_transaction(
            account_id=account_id,
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.DEPOSIT,
            amount=Money(Decimal("1000.00"), "USD"),
            description="Bank deposit",
            asset_type=None,
            symbol=None,
            security_name=None,
            quantity=None,
            unit_price=None,
            commission=None,
        )

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Assert
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_id(transaction.id)

            assert found is not None
            assert found.transaction_type == TransactionType.TRANSFER
            assert found.asset_type is None
            assert found.symbol is None
            assert found.quantity is None


@pytest.mark.integration
class TestTransactionRepositorySaveMany:
    """Test TransactionRepository save_many bulk operations."""

    @pytest.mark.asyncio
    async def test_save_many_creates_multiple_transactions(self, test_database):
        """Test save_many creates multiple transactions efficiently."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        transactions = [
            create_test_transaction(account_id=account_id, symbol="AAPL"),
            create_test_transaction(account_id=account_id, symbol="GOOGL"),
            create_test_transaction(account_id=account_id, symbol="MSFT"),
        ]

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save_many(transactions)

        # Assert
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_account_id(account_id, limit=10)

            assert len(found) == 3
            symbols = {t.symbol for t in found}
            assert symbols == {"AAPL", "GOOGL", "MSFT"}

    @pytest.mark.asyncio
    async def test_save_many_updates_existing_transactions(self, test_database):
        """Test save_many can update existing transactions."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        tx1 = create_test_transaction(
            account_id=account_id, status=TransactionStatus.PENDING
        )
        tx2 = create_test_transaction(
            account_id=account_id, status=TransactionStatus.PENDING
        )

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save_many([tx1, tx2])

        # Act - Update both to SETTLED
        tx1_updated = Transaction(
            id=tx1.id,
            account_id=tx1.account_id,
            provider_transaction_id=tx1.provider_transaction_id,
            transaction_type=tx1.transaction_type,
            subtype=tx1.subtype,
            status=TransactionStatus.SETTLED,
            amount=tx1.amount,
            description=tx1.description,
            asset_type=tx1.asset_type,
            symbol=tx1.symbol,
            security_name=tx1.security_name,
            quantity=tx1.quantity,
            unit_price=tx1.unit_price,
            commission=tx1.commission,
            transaction_date=tx1.transaction_date,
            settlement_date=date.today(),
            provider_metadata=tx1.provider_metadata,
            created_at=tx1.created_at,
            updated_at=datetime.now(UTC),
        )
        tx2_updated = Transaction(
            id=tx2.id,
            account_id=tx2.account_id,
            provider_transaction_id=tx2.provider_transaction_id,
            transaction_type=tx2.transaction_type,
            subtype=tx2.subtype,
            status=TransactionStatus.SETTLED,
            amount=tx2.amount,
            description=tx2.description,
            asset_type=tx2.asset_type,
            symbol=tx2.symbol,
            security_name=tx2.security_name,
            quantity=tx2.quantity,
            unit_price=tx2.unit_price,
            commission=tx2.commission,
            transaction_date=tx2.transaction_date,
            settlement_date=date.today(),
            provider_metadata=tx2.provider_metadata,
            created_at=tx2.created_at,
            updated_at=datetime.now(UTC),
        )

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save_many([tx1_updated, tx2_updated])

        # Assert
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_account_id(account_id, limit=10)

            assert len(found) == 2
            for tx in found:
                assert tx.status == TransactionStatus.SETTLED

    @pytest.mark.asyncio
    async def test_save_many_empty_list(self, test_database):
        """Test save_many with empty list does nothing."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save_many([])

        # Assert - No crash, no records
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_account_id(account_id)
            assert found == []


@pytest.mark.integration
class TestTransactionRepositoryFindById:
    """Test TransactionRepository find_by_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_id_returns_transaction(self, test_database):
        """Test find_by_id returns transaction."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        transaction = create_test_transaction(account_id=account_id)

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_id(transaction.id)

        # Assert
        assert found is not None
        assert found.id == transaction.id

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_when_not_found(self, test_database):
        """Test find_by_id returns None for non-existent transaction."""
        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_id(uuid7())

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_id_maps_money_value_objects(self, test_database):
        """Test find_by_id correctly maps Money value objects."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        amount = Money(Decimal("-500.00"), "GBP")
        unit_price = Money(Decimal("50.00"), "GBP")
        commission = Money(Decimal("2.50"), "GBP")

        transaction = create_test_transaction(
            account_id=account_id,
            currency="GBP",
            amount=amount,
            unit_price=unit_price,
            commission=commission,
        )

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_id(transaction.id)

        # Assert
        assert found is not None
        assert isinstance(found.amount, Money)
        assert found.amount.amount == Decimal("-500.00")
        assert found.amount.currency == "GBP"
        assert isinstance(found.unit_price, Money)
        assert found.unit_price.amount == Decimal("50.00")
        assert isinstance(found.commission, Money)
        assert found.commission.amount == Decimal("2.50")


@pytest.mark.integration
class TestTransactionRepositoryFindByAccountId:
    """Test TransactionRepository find_by_account_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_account_id_returns_transactions(self, test_database):
        """Test find_by_account_id returns transactions."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        transaction = create_test_transaction(account_id=account_id)

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            transactions = await repo.find_by_account_id(account_id)

        # Assert
        assert len(transactions) == 1
        assert transactions[0].id == transaction.id

    @pytest.mark.asyncio
    async def test_find_by_account_id_pagination(self, test_database):
        """Test find_by_account_id supports pagination."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        # Create 10 transactions
        transactions = [
            create_test_transaction(account_id=account_id) for _ in range(10)
        ]

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save_many(transactions)

        # Act - First page
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            page1 = await repo.find_by_account_id(account_id, limit=5, offset=0)

        # Act - Second page
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            page2 = await repo.find_by_account_id(account_id, limit=5, offset=5)

        # Assert
        assert len(page1) == 5
        assert len(page2) == 5
        # No overlap
        page1_ids = {t.id for t in page1}
        page2_ids = {t.id for t in page2}
        assert len(page1_ids & page2_ids) == 0

    @pytest.mark.asyncio
    async def test_find_by_account_id_returns_empty_list(self, test_database):
        """Test find_by_account_id returns empty list when none found."""
        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            transactions = await repo.find_by_account_id(uuid7())

        # Assert
        assert transactions == []


@pytest.mark.integration
class TestTransactionRepositoryFindByAccountAndType:
    """Test TransactionRepository find_by_account_and_type operations."""

    @pytest.mark.asyncio
    async def test_find_by_account_and_type_filters_correctly(self, test_database):
        """Test find_by_account_and_type filters by type."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        trade = create_test_transaction(
            account_id=account_id,
            transaction_type=TransactionType.TRADE,
        )
        transfer = create_test_transaction(
            account_id=account_id,
            transaction_type=TransactionType.TRANSFER,
            subtype=TransactionSubtype.DEPOSIT,
            asset_type=None,
            symbol=None,
            quantity=None,
            unit_price=None,
        )

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save_many([trade, transfer])

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            trades = await repo.find_by_account_and_type(
                account_id, TransactionType.TRADE
            )

        # Assert
        assert len(trades) == 1
        assert trades[0].transaction_type == TransactionType.TRADE

    @pytest.mark.asyncio
    async def test_find_by_account_and_type_returns_empty_list(self, test_database):
        """Test find_by_account_and_type returns empty when no match."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            trades = await repo.find_by_account_and_type(
                account_id, TransactionType.TRADE
            )

        # Assert
        assert trades == []


@pytest.mark.integration
class TestTransactionRepositoryFindByDateRange:
    """Test TransactionRepository find_by_date_range operations."""

    @pytest.mark.asyncio
    async def test_find_by_date_range_filters_correctly(self, test_database):
        """Test find_by_date_range returns transactions in range."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        tx_old = create_test_transaction(
            account_id=account_id,
            transaction_date=date(2025, 1, 1),
        )
        tx_in_range = create_test_transaction(
            account_id=account_id,
            transaction_date=date(2025, 6, 15),
        )
        tx_future = create_test_transaction(
            account_id=account_id,
            transaction_date=date(2025, 12, 31),
        )

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save_many([tx_old, tx_in_range, tx_future])

        # Act - Query for Q2-Q3
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            transactions = await repo.find_by_date_range(
                account_id,
                start_date=date(2025, 4, 1),
                end_date=date(2025, 9, 30),
            )

        # Assert
        assert len(transactions) == 1
        assert transactions[0].id == tx_in_range.id

    @pytest.mark.asyncio
    async def test_find_by_date_range_ordered_chronologically(self, test_database):
        """Test find_by_date_range returns results in chronological order."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        tx1 = create_test_transaction(
            account_id=account_id, transaction_date=date(2025, 6, 1)
        )
        tx2 = create_test_transaction(
            account_id=account_id, transaction_date=date(2025, 6, 15)
        )
        tx3 = create_test_transaction(
            account_id=account_id, transaction_date=date(2025, 6, 30)
        )

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            # Save in random order
            await repo.save_many([tx2, tx3, tx1])

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            transactions = await repo.find_by_date_range(
                account_id,
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 30),
            )

        # Assert - Should be chronological
        assert len(transactions) == 3
        assert transactions[0].transaction_date == date(2025, 6, 1)
        assert transactions[1].transaction_date == date(2025, 6, 15)
        assert transactions[2].transaction_date == date(2025, 6, 30)


@pytest.mark.integration
class TestTransactionRepositoryFindByProviderTransactionId:
    """Test TransactionRepository find_by_provider_transaction_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_provider_transaction_id_returns_transaction(
        self, test_database
    ):
        """Test find_by_provider_transaction_id returns matching transaction."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        provider_tx_id = "SCHWAB-12345"
        transaction = create_test_transaction(
            account_id=account_id,
            provider_transaction_id=provider_tx_id,
        )

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_provider_transaction_id(
                account_id, provider_tx_id
            )

        # Assert
        assert found is not None
        assert found.provider_transaction_id == provider_tx_id

    @pytest.mark.asyncio
    async def test_find_by_provider_transaction_id_returns_none(self, test_database):
        """Test find_by_provider_transaction_id returns None when not found."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_provider_transaction_id(
                account_id, "NONEXISTENT"
            )

        # Assert
        assert found is None


@pytest.mark.integration
class TestTransactionRepositoryFindSecurityTransactions:
    """Test TransactionRepository find_security_transactions operations."""

    @pytest.mark.asyncio
    async def test_find_security_transactions_filters_by_symbol(self, test_database):
        """Test find_security_transactions returns transactions for symbol."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        aapl_tx = create_test_transaction(account_id=account_id, symbol="AAPL")
        googl_tx = create_test_transaction(account_id=account_id, symbol="GOOGL")

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save_many([aapl_tx, googl_tx])

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            aapl_transactions = await repo.find_security_transactions(
                account_id, "AAPL"
            )

        # Assert
        assert len(aapl_transactions) == 1
        assert aapl_transactions[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_find_security_transactions_returns_empty_list(self, test_database):
        """Test find_security_transactions returns empty when no match."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            transactions = await repo.find_security_transactions(account_id, "TSLA")

        # Assert
        assert transactions == []


@pytest.mark.integration
class TestTransactionRepositoryDelete:
    """Test TransactionRepository delete operations."""

    @pytest.mark.asyncio
    async def test_delete_removes_transaction(self, test_database):
        """Test delete removes transaction from database."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        transaction = create_test_transaction(account_id=account_id)

        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.save(transaction)

        # Act
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            await repo.delete(transaction.id)

        # Assert
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            found = await repo.find_by_id(transaction.id)
            assert found is None

    @pytest.mark.asyncio
    async def test_delete_raises_when_not_found(self, test_database):
        """Test delete raises NoResultFound for non-existent transaction."""
        # Act & Assert
        async with test_database.get_session() as session:
            repo = TransactionRepository(session=session)
            with pytest.raises(NoResultFound):
                await repo.delete(uuid7())


@pytest.mark.integration
class TestTransactionRepositoryEnumMapping:
    """Test enum mapping between domain and model."""

    @pytest.mark.asyncio
    async def test_all_transaction_types_persist_correctly(self, test_database):
        """Test all TransactionType enum values work correctly."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        test_types = [
            TransactionType.TRADE,
            TransactionType.TRANSFER,
            TransactionType.INCOME,
            TransactionType.FEE,
            TransactionType.OTHER,
        ]

        for tx_type in test_types:
            # Set appropriate subtype for each type
            if tx_type == TransactionType.TRADE:
                subtype = TransactionSubtype.BUY
            elif tx_type == TransactionType.TRANSFER:
                subtype = TransactionSubtype.DEPOSIT
            elif tx_type == TransactionType.INCOME:
                subtype = TransactionSubtype.DIVIDEND
            elif tx_type == TransactionType.FEE:
                subtype = TransactionSubtype.COMMISSION
            else:
                subtype = TransactionSubtype.UNKNOWN

            transaction = create_test_transaction(
                account_id=account_id,
                transaction_type=tx_type,
                subtype=subtype,
                asset_type=None
                if tx_type != TransactionType.TRADE
                else AssetType.EQUITY,
                symbol=None if tx_type != TransactionType.TRADE else "TEST",
                quantity=None if tx_type != TransactionType.TRADE else Decimal("1"),
                unit_price=None
                if tx_type != TransactionType.TRADE
                else Money(Decimal("10"), "USD"),
            )

            async with test_database.get_session() as session:
                repo = TransactionRepository(session=session)
                await repo.save(transaction)

            # Verify round-trip
            async with test_database.get_session() as session:
                repo = TransactionRepository(session=session)
                found = await repo.find_by_id(transaction.id)
                assert found is not None
                assert found.transaction_type == tx_type

    @pytest.mark.asyncio
    async def test_all_asset_types_persist_correctly(self, test_database):
        """Test all AssetType enum values work correctly."""
        # Arrange
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(session, user_id)
            account_id = await create_account_in_db(session, connection_id)

        test_types = [
            AssetType.EQUITY,
            AssetType.ETF,
            AssetType.OPTION,
            AssetType.MUTUAL_FUND,
            AssetType.CRYPTOCURRENCY,
        ]

        for asset_type in test_types:
            transaction = create_test_transaction(
                account_id=account_id,
                asset_type=asset_type,
            )

            async with test_database.get_session() as session:
                repo = TransactionRepository(session=session)
                await repo.save(transaction)

            # Verify round-trip
            async with test_database.get_session() as session:
                repo = TransactionRepository(session=session)
                found = await repo.find_by_id(transaction.id)
                assert found is not None
                assert found.asset_type == asset_type
