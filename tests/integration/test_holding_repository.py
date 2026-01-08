"""Integration tests for HoldingRepository.

Tests cover:
- Save and retrieve holding
- Find by ID
- Find by account and symbol
- Find by provider holding ID
- List by account
- List by user (JOIN through account → connection)
- Save many (batch)
- Delete holding
- Entity ↔ Model mapping (Money, AssetType)

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from uuid_extensions import uuid7

from src.domain.entities.holding import Holding
from src.domain.enums.account_type import AccountType
from src.domain.enums.asset_type import AssetType
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.repositories.holding_repository import (
    HoldingRepository,
)


# =============================================================================
# Test Helpers
# =============================================================================


def create_test_holding(
    holding_id=None,
    account_id=None,
    provider_holding_id=None,
    symbol="AAPL",
    security_name="Apple Inc.",
    asset_type=AssetType.EQUITY,
    quantity=None,
    cost_basis=None,
    market_value=None,
    currency="USD",
    average_price=None,
    current_price=None,
    is_active=True,
    last_synced_at=None,
    provider_metadata=None,
) -> Holding:
    """Create a test Holding with default values."""
    now = datetime.now(UTC)
    if quantity is None:
        quantity = Decimal("100")
    if cost_basis is None:
        cost_basis = Money(Decimal("15000.00"), currency)
    if market_value is None:
        market_value = Money(Decimal("17500.00"), currency)
    if provider_holding_id is None:
        provider_holding_id = f"TEST-{uuid7().hex.upper()}"

    return Holding(
        id=holding_id or uuid7(),
        account_id=account_id or uuid7(),
        provider_holding_id=provider_holding_id,
        symbol=symbol,
        security_name=security_name,
        asset_type=asset_type,
        quantity=quantity,
        cost_basis=cost_basis,
        market_value=market_value,
        currency=currency,
        average_price=average_price,
        current_price=current_price,
        is_active=is_active,
        last_synced_at=last_synced_at,
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


async def create_connection_in_db(
    session,
    user_id,
    provider_id,
    provider_slug="schwab",
    connection_id=None,
    status=ConnectionStatus.ACTIVE,
):
    """Create a provider connection in the database for FK constraint."""
    from src.infrastructure.persistence.models.provider_connection import (
        ProviderConnection as ProviderConnectionModel,
    )

    connection_id = connection_id or uuid7()

    connection = ProviderConnectionModel(
        id=connection_id,
        user_id=user_id,
        provider_id=provider_id,
        provider_slug=provider_slug,
        status=status.value,
    )
    session.add(connection)
    await session.commit()
    return connection_id


async def create_account_in_db(
    session,
    connection_id,
    account_id=None,
    provider_account_id=None,
    account_type=AccountType.BROKERAGE,
):
    """Create an account in the database for FK constraint."""
    from src.infrastructure.persistence.models.account import Account as AccountModel

    account_id = account_id or uuid7()
    provider_account_id = provider_account_id or f"TEST-{uuid7().hex.upper()}"
    now = datetime.now(UTC)

    account = AccountModel(
        id=account_id,
        connection_id=connection_id,
        provider_account_id=provider_account_id,
        account_number_masked="****1234",
        name="Test Account",
        account_type=account_type.value,
        balance=Decimal("10000.00"),
        currency="USD",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(account)
    await session.commit()
    return account_id


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest_asyncio.fixture(autouse=True)
async def clean_holdings_table(test_database):
    """Clean up holdings table before each test."""
    async with test_database.get_session() as session:
        await session.execute(text("TRUNCATE TABLE holdings CASCADE"))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def account_with_connection(test_database, schwab_provider):
    """Create an account with all FK dependencies satisfied.

    Creates user → connection → account chain.

    Returns:
        tuple: (account_id, connection_id, user_id) for use in tests.
    """
    provider_id, provider_slug = schwab_provider
    async with test_database.get_session() as session:
        user_id = await create_user_in_db(session)
        connection_id = await create_connection_in_db(
            session, user_id, provider_id, provider_slug
        )
        account_id = await create_account_in_db(session, connection_id)
    return account_id, connection_id, user_id


# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.integration
class TestHoldingRepositorySave:
    """Test HoldingRepository save operations."""

    @pytest.mark.asyncio
    async def test_save_holding_persists_to_database(
        self, test_database, account_with_connection
    ):
        """Test saving a holding persists it to the database."""
        # Arrange
        account_id, _, _ = account_with_connection
        holding = create_test_holding(account_id=account_id)

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save(holding)
            await session.commit()

        # Assert - retrieve from different session
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            retrieved = await repo.find_by_id(holding.id)

        assert retrieved is not None
        assert retrieved.id == holding.id
        assert retrieved.symbol == "AAPL"
        assert retrieved.security_name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_save_holding_maps_money_values(
        self, test_database, account_with_connection
    ):
        """Test Money value objects are correctly mapped."""
        # Arrange
        account_id, _, _ = account_with_connection
        holding = create_test_holding(
            account_id=account_id,
            cost_basis=Money(Decimal("15000.00"), "USD"),
            market_value=Money(Decimal("17500.00"), "USD"),
            average_price=Money(Decimal("150.00"), "USD"),
            current_price=Money(Decimal("175.00"), "USD"),
        )

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save(holding)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            retrieved = await repo.find_by_id(holding.id)

        assert retrieved is not None
        assert retrieved.cost_basis is not None
        assert retrieved.market_value is not None
        assert retrieved.cost_basis.amount == Decimal("15000.00")
        assert retrieved.market_value.amount == Decimal("17500.00")
        assert retrieved.average_price is not None
        assert retrieved.current_price is not None
        assert retrieved.average_price.amount == Decimal("150.00")
        assert retrieved.current_price.amount == Decimal("175.00")

    @pytest.mark.asyncio
    async def test_save_holding_maps_asset_type(
        self, test_database, account_with_connection
    ):
        """Test AssetType enum is correctly mapped."""
        # Arrange
        account_id, _, _ = account_with_connection
        holding = create_test_holding(
            account_id=account_id,
            asset_type=AssetType.ETF,
        )

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save(holding)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            retrieved = await repo.find_by_id(holding.id)

        assert retrieved is not None
        assert retrieved.asset_type == AssetType.ETF


@pytest.mark.integration
class TestHoldingRepositoryFind:
    """Test HoldingRepository find operations."""

    @pytest.mark.asyncio
    async def test_find_by_id_returns_holding(
        self, test_database, account_with_connection
    ):
        """Test finding holding by ID returns the correct holding."""
        # Arrange
        account_id, _, _ = account_with_connection
        holding = create_test_holding(account_id=account_id)

        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save(holding)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            retrieved = await repo.find_by_id(holding.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == holding.id

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_for_missing(self, test_database):
        """Test finding non-existent holding returns None."""
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            result = await repo.find_by_id(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_account_and_symbol(
        self, test_database, account_with_connection
    ):
        """Test finding holding by account and symbol."""
        # Arrange
        account_id, _, _ = account_with_connection
        holding = create_test_holding(account_id=account_id, symbol="TSLA")

        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save(holding)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            retrieved = await repo.find_by_account_and_symbol(account_id, "TSLA")

        # Assert
        assert retrieved is not None
        assert retrieved.symbol == "TSLA"

    @pytest.mark.asyncio
    async def test_find_by_provider_holding_id(
        self, test_database, account_with_connection
    ):
        """Test finding holding by provider holding ID."""
        # Arrange
        account_id, _, _ = account_with_connection
        provider_id = "SCHWAB-AAPL-123"
        holding = create_test_holding(
            account_id=account_id, provider_holding_id=provider_id
        )

        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save(holding)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            retrieved = await repo.find_by_provider_holding_id(account_id, provider_id)

        # Assert
        assert retrieved is not None
        assert retrieved.provider_holding_id == provider_id


@pytest.mark.integration
class TestHoldingRepositoryList:
    """Test HoldingRepository list operations."""

    @pytest.mark.asyncio
    async def test_list_by_account_returns_all_holdings(
        self, test_database, account_with_connection
    ):
        """Test listing all holdings for an account."""
        # Arrange
        account_id, _, _ = account_with_connection
        holdings = [
            create_test_holding(account_id=account_id, symbol="AAPL"),
            create_test_holding(account_id=account_id, symbol="GOOGL"),
            create_test_holding(account_id=account_id, symbol="MSFT"),
        ]

        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            for h in holdings:
                await repo.save(h)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            result = await repo.list_by_account(account_id)

        # Assert
        assert len(result) == 3
        symbols = {h.symbol for h in result}
        assert symbols == {"AAPL", "GOOGL", "MSFT"}

    @pytest.mark.asyncio
    async def test_list_by_account_active_only(
        self, test_database, account_with_connection
    ):
        """Test listing only active holdings."""
        # Arrange
        account_id, _, _ = account_with_connection
        active_holding = create_test_holding(
            account_id=account_id, symbol="AAPL", is_active=True
        )
        inactive_holding = create_test_holding(
            account_id=account_id, symbol="GOOGL", is_active=False
        )

        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save(active_holding)
            await repo.save(inactive_holding)
            await session.commit()

        # Act - active_only=True (default)
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            active_result = await repo.list_by_account(account_id, active_only=True)
            all_result = await repo.list_by_account(account_id, active_only=False)

        # Assert
        assert len(active_result) == 1
        assert active_result[0].symbol == "AAPL"
        assert len(all_result) == 2

    @pytest.mark.asyncio
    async def test_list_by_user_returns_holdings_across_accounts(
        self, test_database, schwab_provider
    ):
        """Test listing holdings for a user across multiple accounts."""
        # Arrange - create user with two accounts
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(
                session, user_id, provider_id, provider_slug
            )
            account1_id = await create_account_in_db(session, connection_id)
            account2_id = await create_account_in_db(session, connection_id)

        # Create holdings in both accounts
        holding1 = create_test_holding(account_id=account1_id, symbol="AAPL")
        holding2 = create_test_holding(account_id=account2_id, symbol="GOOGL")

        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save(holding1)
            await repo.save(holding2)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            result = await repo.list_by_user(user_id)

        # Assert
        assert len(result) == 2
        symbols = {h.symbol for h in result}
        assert symbols == {"AAPL", "GOOGL"}


@pytest.mark.integration
class TestHoldingRepositoryBatch:
    """Test HoldingRepository batch operations."""

    @pytest.mark.asyncio
    async def test_save_many_persists_all_holdings(
        self, test_database, account_with_connection
    ):
        """Test saving multiple holdings in batch."""
        # Arrange
        account_id, _, _ = account_with_connection
        holdings = [
            create_test_holding(account_id=account_id, symbol=f"SYM{i}")
            for i in range(5)
        ]

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save_many(holdings)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            result = await repo.list_by_account(account_id)

        assert len(result) == 5


@pytest.mark.integration
class TestHoldingRepositoryDelete:
    """Test HoldingRepository delete operations."""

    @pytest.mark.asyncio
    async def test_delete_removes_holding(self, test_database, account_with_connection):
        """Test deleting a holding removes it from database."""
        # Arrange
        account_id, _, _ = account_with_connection
        holding = create_test_holding(account_id=account_id)

        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.save(holding)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            await repo.delete(holding.id)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            result = await repo.find_by_id(holding.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_by_account_removes_all_holdings(
        self, test_database, account_with_connection
    ):
        """Test deleting all holdings for an account."""
        # Arrange
        account_id, _, _ = account_with_connection
        holdings = [
            create_test_holding(account_id=account_id, symbol=f"SYM{i}")
            for i in range(3)
        ]

        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            for h in holdings:
                await repo.save(h)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            deleted_count = await repo.delete_by_account(account_id)
            await session.commit()

        # Assert
        assert deleted_count == 3
        async with test_database.get_session() as session:
            repo = HoldingRepository(session)
            result = await repo.list_by_account(account_id, active_only=False)
        assert len(result) == 0
