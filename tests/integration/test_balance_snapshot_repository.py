"""Integration tests for BalanceSnapshotRepository.

Tests cover:
- Save and retrieve balance snapshot
- Find by ID
- Get latest by account
- List by account with pagination
- List by user across accounts
- Get balance history with date range
- Entity ↔ Model mapping (Money, SnapshotSource)

Architecture:
- Integration tests with REAL PostgreSQL database
- Uses test_database fixture (fresh instance per test)
- Tests actual database operations, not mocked behavior
- Async tests for database operations
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from uuid_extensions import uuid7

from src.domain.entities.balance_snapshot import BalanceSnapshot
from src.domain.enums.account_type import AccountType
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.snapshot_source import SnapshotSource
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.repositories.balance_snapshot_repository import (
    BalanceSnapshotRepository,
)


# =============================================================================
# Test Helpers
# =============================================================================


def create_test_snapshot(
    snapshot_id=None,
    account_id=None,
    captured_at=None,
    balance=None,
    available_balance=None,
    holdings_value=None,
    cash_value=None,
    currency="USD",
    source=SnapshotSource.ACCOUNT_SYNC,
    provider_metadata=None,
) -> BalanceSnapshot:
    """Create a test BalanceSnapshot with default values."""
    now = datetime.now(UTC)
    if balance is None:
        balance = Money(Decimal("10000.00"), currency)

    return BalanceSnapshot(
        id=snapshot_id or uuid7(),
        account_id=account_id or uuid7(),
        captured_at=captured_at or now,
        balance=balance,
        available_balance=available_balance,
        holdings_value=holdings_value,
        cash_value=cash_value,
        currency=currency,
        source=source,
        provider_metadata=provider_metadata,
        created_at=now,
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
async def clean_snapshots_table(test_database):
    """Clean up balance_snapshots table before each test."""
    async with test_database.get_session() as session:
        await session.execute(text("TRUNCATE TABLE balance_snapshots CASCADE"))
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
class TestBalanceSnapshotRepositorySave:
    """Test BalanceSnapshotRepository save operations."""

    @pytest.mark.asyncio
    async def test_save_snapshot_persists_to_database(
        self, test_database, account_with_connection
    ):
        """Test saving a balance snapshot persists it to the database."""
        # Arrange
        account_id, _, _ = account_with_connection
        snapshot = create_test_snapshot(account_id=account_id)

        # Act
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            await repo.save(snapshot)
            await session.commit()

        # Assert - retrieve from different session
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            retrieved = await repo.find_by_id(snapshot.id)

        assert retrieved is not None
        assert retrieved.id == snapshot.id
        assert retrieved.balance.amount == Decimal("10000.00")

    @pytest.mark.asyncio
    async def test_save_snapshot_maps_money_values(
        self, test_database, account_with_connection
    ):
        """Test Money value objects are correctly mapped."""
        # Arrange
        account_id, _, _ = account_with_connection
        snapshot = create_test_snapshot(
            account_id=account_id,
            balance=Money(Decimal("10000.00"), "USD"),
            available_balance=Money(Decimal("9000.00"), "USD"),
            holdings_value=Money(Decimal("8000.00"), "USD"),
            cash_value=Money(Decimal("2000.00"), "USD"),
        )

        # Act
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            await repo.save(snapshot)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            retrieved = await repo.find_by_id(snapshot.id)

        assert retrieved is not None
        assert retrieved.available_balance is not None
        assert retrieved.holdings_value is not None
        assert retrieved.cash_value is not None
        assert retrieved.balance.amount == Decimal("10000.00")
        assert retrieved.available_balance.amount == Decimal("9000.00")
        assert retrieved.holdings_value.amount == Decimal("8000.00")
        assert retrieved.cash_value.amount == Decimal("2000.00")

    @pytest.mark.asyncio
    async def test_save_snapshot_maps_source_enum(
        self, test_database, account_with_connection
    ):
        """Test SnapshotSource enum is correctly mapped."""
        # Arrange
        account_id, _, _ = account_with_connection
        snapshot = create_test_snapshot(
            account_id=account_id,
            source=SnapshotSource.MANUAL_SYNC,
        )

        # Act
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            await repo.save(snapshot)
            await session.commit()

        # Assert
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            retrieved = await repo.find_by_id(snapshot.id)

        assert retrieved is not None
        assert retrieved.source == SnapshotSource.MANUAL_SYNC


@pytest.mark.integration
class TestBalanceSnapshotRepositoryFind:
    """Test BalanceSnapshotRepository find operations."""

    @pytest.mark.asyncio
    async def test_find_by_id_returns_snapshot(
        self, test_database, account_with_connection
    ):
        """Test finding snapshot by ID returns the correct snapshot."""
        # Arrange
        account_id, _, _ = account_with_connection
        snapshot = create_test_snapshot(account_id=account_id)

        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            await repo.save(snapshot)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            retrieved = await repo.find_by_id(snapshot.id)

        # Assert
        assert retrieved is not None
        assert retrieved.id == snapshot.id

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_for_missing(self, test_database):
        """Test finding non-existent snapshot returns None."""
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            result = await repo.find_by_id(uuid7())

        assert result is None

    @pytest.mark.asyncio
    async def test_find_latest_by_account_id(
        self, test_database, account_with_connection
    ):
        """Test getting the latest snapshot for an account."""
        # Arrange
        account_id, _, _ = account_with_connection
        now = datetime.now(UTC)

        # Create snapshots at different times
        old_snapshot = create_test_snapshot(
            account_id=account_id,
            captured_at=now - timedelta(hours=2),
            balance=Money(Decimal("9000.00"), "USD"),
        )
        latest_snapshot = create_test_snapshot(
            account_id=account_id,
            captured_at=now,
            balance=Money(Decimal("10000.00"), "USD"),
        )

        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            await repo.save(old_snapshot)
            await repo.save(latest_snapshot)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            result = await repo.find_latest_by_account_id(account_id)

        # Assert
        assert result is not None
        assert result.id == latest_snapshot.id
        assert result.balance.amount == Decimal("10000.00")


@pytest.mark.integration
class TestBalanceSnapshotRepositoryList:
    """Test BalanceSnapshotRepository list operations."""

    @pytest.mark.asyncio
    async def test_find_by_account_id_returns_all_snapshots(
        self, test_database, account_with_connection
    ):
        """Test listing all snapshots for an account."""
        # Arrange
        account_id, _, _ = account_with_connection
        now = datetime.now(UTC)

        snapshots = [
            create_test_snapshot(
                account_id=account_id,
                captured_at=now - timedelta(hours=i),
            )
            for i in range(3)
        ]

        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            for s in snapshots:
                await repo.save(s)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            result = await repo.find_by_account_id(account_id)

        # Assert
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_find_by_account_id_with_limit(
        self, test_database, account_with_connection
    ):
        """Test listing snapshots with limit."""
        # Arrange
        account_id, _, _ = account_with_connection
        now = datetime.now(UTC)

        # Create 5 snapshots
        for i in range(5):
            snapshot = create_test_snapshot(
                account_id=account_id,
                captured_at=now - timedelta(hours=i),
            )
            async with test_database.get_session() as session:
                repo = BalanceSnapshotRepository(session)
                await repo.save(snapshot)
                await session.commit()

        # Act - get only 2
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            result = await repo.find_by_account_id(account_id, limit=2)

        # Assert
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_find_latest_by_user_id_returns_snapshots_across_accounts(
        self, test_database, schwab_provider
    ):
        """Test listing snapshots for a user across multiple accounts."""
        # Arrange - create user with two accounts
        provider_id, provider_slug = schwab_provider
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            connection_id = await create_connection_in_db(
                session, user_id, provider_id, provider_slug
            )
            account1_id = await create_account_in_db(session, connection_id)
            account2_id = await create_account_in_db(session, connection_id)

        # Create snapshots in both accounts
        snapshot1 = create_test_snapshot(account_id=account1_id)
        snapshot2 = create_test_snapshot(account_id=account2_id)

        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            await repo.save(snapshot1)
            await repo.save(snapshot2)
            await session.commit()

        # Act
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            result = await repo.find_latest_by_user_id(user_id)

        # Assert
        assert len(result) == 2


@pytest.mark.integration
class TestBalanceSnapshotRepositoryHistory:
    """Test BalanceSnapshotRepository history operations."""

    @pytest.mark.asyncio
    async def test_find_by_account_id_in_range(
        self, test_database, account_with_connection
    ):
        """Test getting balance history within a date range."""
        # Arrange
        account_id, _, _ = account_with_connection
        now = datetime.now(UTC)

        # Create snapshots over several days
        for i in range(10):
            snapshot = create_test_snapshot(
                account_id=account_id,
                captured_at=now - timedelta(days=i),
                balance=Money(Decimal(str(10000 - i * 100)), "USD"),
            )
            async with test_database.get_session() as session:
                repo = BalanceSnapshotRepository(session)
                await repo.save(snapshot)
                await session.commit()

        # Act - get last 5 days
        start_date = now - timedelta(days=5)
        end_date = now

        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            result = await repo.find_by_account_id_in_range(
                account_id=account_id,
                start_date=start_date,
                end_date=end_date,
            )

        # Assert - should get snapshots from days 0-5 (6 snapshots)
        assert len(result) == 6

    @pytest.mark.asyncio
    async def test_find_by_account_id_in_range_filters_by_source(
        self, test_database, account_with_connection
    ):
        """Test getting balance history filtered by source."""
        # Arrange
        account_id, _, _ = account_with_connection
        now = datetime.now(UTC)

        # Create snapshots with different sources
        account_sync = create_test_snapshot(
            account_id=account_id,
            captured_at=now - timedelta(hours=2),
            source=SnapshotSource.ACCOUNT_SYNC,
        )
        manual_sync = create_test_snapshot(
            account_id=account_id,
            captured_at=now - timedelta(hours=1),
            source=SnapshotSource.MANUAL_SYNC,
        )

        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            await repo.save(account_sync)
            await repo.save(manual_sync)
            await session.commit()

        # Act - filter by ACCOUNT_SYNC
        async with test_database.get_session() as session:
            repo = BalanceSnapshotRepository(session)
            result = await repo.find_by_account_id_in_range(
                account_id=account_id,
                start_date=now - timedelta(hours=3),
                end_date=now,
                source=SnapshotSource.ACCOUNT_SYNC,
            )

        # Assert
        assert len(result) == 1
        assert result[0].source == SnapshotSource.ACCOUNT_SYNC
