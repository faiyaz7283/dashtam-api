"""Integration tests for AccountRepository.

Tests cover:
- Save and retrieve account
- Find by ID
- Find by connection ID
- Find by user ID (JOIN through provider_connections)
- Find by provider account ID
- Find active by user
- Find needing sync
- Delete account
- Entity ↔ Model mapping (Money, AccountType)

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
from sqlalchemy.exc import NoResultFound
from uuid_extensions import uuid7

from src.domain.entities.account import Account
from src.domain.enums.account_type import AccountType
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.value_objects.money import Money
from src.infrastructure.persistence.repositories.account_repository import (
    AccountRepository,
)


# =============================================================================
# Test Helpers
# =============================================================================


def create_test_account(
    account_id=None,
    connection_id=None,
    provider_account_id=None,
    account_number_masked="****1234",
    name="Test Account",
    account_type=AccountType.BROKERAGE,
    balance=None,
    currency="USD",
    available_balance=None,
    is_active=True,
    last_synced_at=None,
    provider_metadata=None,
) -> Account:
    """Create a test Account with default values."""
    now = datetime.now(UTC)
    if balance is None:
        balance = Money(Decimal("1000.00"), currency)
    if provider_account_id is None:
        # Generate unique provider_account_id using full UUID to avoid collisions
        # uuid7 is time-ordered, so first 8 chars may be same in rapid succession
        provider_account_id = f"TEST-{uuid7().hex.upper()}"

    return Account(
        id=account_id or uuid7(),
        connection_id=connection_id or uuid7(),
        provider_account_id=provider_account_id,
        account_number_masked=account_number_masked,
        name=name,
        account_type=account_type,
        balance=balance,
        currency=currency,
        available_balance=available_balance,
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
    """Create a provider connection in the database for FK constraint.

    Args:
        session: Database session.
        user_id: UUID of the user owning the connection.
        provider_id: UUID of the provider (must exist in providers table).
        provider_slug: Provider slug (default: "schwab").
        connection_id: Optional UUID for the connection.
        status: Connection status (default: ACTIVE).

    Returns:
        UUID of the created connection.
    """
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


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest_asyncio.fixture(autouse=True)
async def clean_accounts_table(test_database):
    """Clean up accounts table before each test.

    This fixture runs automatically before each test to ensure
    test isolation. It truncates the accounts table to remove
    any data from previous test runs.
    """
    async with test_database.get_session() as session:
        # Truncate accounts table (CASCADE not needed - accounts is leaf table)
        await session.execute(text("TRUNCATE TABLE accounts CASCADE"))
        await session.commit()
    yield


@pytest_asyncio.fixture
async def connection_with_provider(test_database, schwab_provider):
    """Create a connection with all FK dependencies satisfied.

    Creates user → provider_connection chain.
    Uses the schwab_provider fixture for valid provider_id.

    Returns:
        tuple: (connection_id, user_id) for use in tests.
    """
    provider_id, provider_slug = schwab_provider
    async with test_database.get_session() as session:
        user_id = await create_user_in_db(session)
        connection_id = await create_connection_in_db(
            session, user_id, provider_id, provider_slug
        )
    return connection_id, user_id


# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.integration
class TestAccountRepositorySave:
    """Test AccountRepository save operations."""

    @pytest.mark.asyncio
    async def test_save_account_persists_to_database(
        self, test_database, connection_with_provider
    ):
        """Test saving an account persists it to the database."""
        # Arrange
        connection_id, _ = connection_with_provider
        account = create_test_account(connection_id=connection_id)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Assert
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(account.id)

            assert found is not None
            assert found.id == account.id
            assert found.connection_id == connection_id
            assert found.name == "Test Account"
            assert found.account_type == AccountType.BROKERAGE

    @pytest.mark.asyncio
    async def test_save_account_with_available_balance(
        self, test_database, connection_with_provider
    ):
        """Test saving an account with available balance."""
        # Arrange
        connection_id, _ = connection_with_provider
        balance = Money(Decimal("1000.00"), "USD")
        available_balance = Money(Decimal("900.00"), "USD")
        account = create_test_account(
            connection_id=connection_id,
            balance=balance,
            available_balance=available_balance,
        )

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Assert
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(account.id)

            assert found is not None
            assert found.balance == balance
            assert found.available_balance == available_balance

    @pytest.mark.asyncio
    async def test_save_account_update_existing(
        self, test_database, connection_with_provider
    ):
        """Test updating an existing account."""
        # Arrange
        connection_id, _ = connection_with_provider
        account = create_test_account(
            connection_id=connection_id,
            name="Original Name",
            balance=Money(Decimal("1000.00"), "USD"),
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Act - Update the account
        account.name = "Updated Name"
        account.balance = Money(Decimal("2000.00"), "USD")
        account.updated_at = datetime.now(UTC)

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Assert
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(account.id)

            assert found is not None
            assert found.name == "Updated Name"
            assert found.balance.amount == Decimal("2000.00")

    @pytest.mark.asyncio
    async def test_save_account_with_provider_metadata(
        self, test_database, connection_with_provider
    ):
        """Test saving account with provider metadata."""
        # Arrange
        connection_id, _ = connection_with_provider
        metadata = {
            "schwab_account_type": "INDIVIDUAL",
            "tax_advantaged": False,
            "margin_enabled": True,
        }
        account = create_test_account(
            connection_id=connection_id,
            provider_metadata=metadata,
        )

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Assert
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(account.id)

            assert found is not None
            assert found.provider_metadata == metadata

    @pytest.mark.asyncio
    async def test_save_account_balance_mapping_roundtrip(
        self, test_database, connection_with_provider
    ):
        """Test Money value object survives save/load roundtrip."""
        # Arrange
        connection_id, _ = connection_with_provider

        # Use precise decimal with 4 decimal places
        balance = Money(Decimal("12345.6789"), "EUR")
        account = create_test_account(
            connection_id=connection_id,
            balance=balance,
            currency="EUR",
        )

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(account.id)

        # Assert
        assert found is not None
        assert found.balance.amount == Decimal("12345.6789")
        assert found.balance.currency == "EUR"
        assert found.currency == "EUR"


@pytest.mark.integration
class TestAccountRepositoryFindById:
    """Test AccountRepository find_by_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_id_returns_account(
        self, test_database, connection_with_provider
    ):
        """Test find_by_id returns account when found."""
        # Arrange
        connection_id, _ = connection_with_provider
        account_id = uuid7()
        account = create_test_account(
            account_id=account_id,
            connection_id=connection_id,
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(account_id)

        # Assert
        assert found is not None
        assert found.id == account_id

    @pytest.mark.asyncio
    async def test_find_by_id_returns_none_when_not_found(self, test_database):
        """Test find_by_id returns None for non-existent account."""
        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(uuid7())

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_id_maps_money_value_objects(
        self, test_database, connection_with_provider
    ):
        """Test find_by_id correctly maps Money value objects."""
        # Arrange
        connection_id, _ = connection_with_provider
        balance = Money(Decimal("5000.00"), "GBP")
        available = Money(Decimal("4500.00"), "GBP")
        account = create_test_account(
            connection_id=connection_id,
            balance=balance,
            currency="GBP",
            available_balance=available,
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(account.id)

        # Assert
        assert found is not None
        assert isinstance(found.balance, Money)
        assert found.balance.amount == Decimal("5000.00")
        assert found.balance.currency == "GBP"
        assert isinstance(found.available_balance, Money)
        assert found.available_balance.amount == Decimal("4500.00")


@pytest.mark.integration
class TestAccountRepositoryFindByConnectionId:
    """Test AccountRepository find_by_connection_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_connection_id_returns_accounts(
        self, test_database, connection_with_provider
    ):
        """Test find_by_connection_id returns accounts for connection."""
        # Arrange
        connection_id, _ = connection_with_provider
        account = create_test_account(connection_id=connection_id)

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_by_connection_id(connection_id)

        # Assert
        assert len(accounts) == 1
        assert accounts[0].id == account.id

    @pytest.mark.asyncio
    async def test_find_by_connection_id_returns_empty_list(self, test_database):
        """Test find_by_connection_id returns empty list when none found."""
        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_by_connection_id(uuid7())

        # Assert
        assert accounts == []

    @pytest.mark.asyncio
    async def test_find_by_connection_id_multiple_accounts(
        self, test_database, connection_with_provider
    ):
        """Test connection can have multiple accounts (IRA, brokerage, etc.)."""
        # Arrange
        connection_id, _ = connection_with_provider
        brokerage = create_test_account(
            connection_id=connection_id,
            name="Brokerage",
            account_type=AccountType.BROKERAGE,
        )
        ira = create_test_account(
            connection_id=connection_id,
            name="IRA",
            account_type=AccountType.IRA,
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(brokerage)
            await repo.save(ira)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_by_connection_id(connection_id)

        # Assert
        assert len(accounts) == 2
        names = {a.name for a in accounts}
        assert names == {"Brokerage", "IRA"}


@pytest.mark.integration
class TestAccountRepositoryFindByUserId:
    """Test AccountRepository find_by_user_id operations (JOIN)."""

    @pytest.mark.asyncio
    async def test_find_by_user_id_returns_all_accounts(
        self, test_database, connection_with_provider
    ):
        """Test find_by_user_id returns accounts across connections."""
        # Arrange
        connection_id, user_id = connection_with_provider
        account = create_test_account(connection_id=connection_id)

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_by_user_id(user_id)

        # Assert
        assert len(accounts) == 1
        assert accounts[0].id == account.id

    @pytest.mark.asyncio
    async def test_find_by_user_id_across_multiple_connections(
        self, test_database, provider_factory
    ):
        """Test find_by_user_id returns accounts from multiple connections."""
        # Arrange
        prov1_id, prov1_slug = await provider_factory("schwab")
        prov2_id, prov2_slug = await provider_factory("fidelity")
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            conn1_id = await create_connection_in_db(
                session, user_id, prov1_id, prov1_slug
            )
            conn2_id = await create_connection_in_db(
                session, user_id, prov2_id, prov2_slug
            )

        acc1 = create_test_account(connection_id=conn1_id, name="Schwab Account")
        acc2 = create_test_account(connection_id=conn2_id, name="Fidelity Account")

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(acc1)
            await repo.save(acc2)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_by_user_id(user_id)

        # Assert
        assert len(accounts) == 2
        names = {a.name for a in accounts}
        assert names == {"Schwab Account", "Fidelity Account"}

    @pytest.mark.asyncio
    async def test_find_by_user_id_returns_empty_list(self, test_database):
        """Test find_by_user_id returns empty list for user with no accounts."""
        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_by_user_id(uuid7())

        # Assert
        assert accounts == []

    @pytest.mark.asyncio
    async def test_find_by_user_id_excludes_other_users(
        self, test_database, provider_factory
    ):
        """Test find_by_user_id only returns accounts for specified user."""
        # Arrange - Use unique emails to avoid conflicts with previous test runs
        prov1_id, prov1_slug = await provider_factory("user1_prov")
        prov2_id, prov2_slug = await provider_factory("user2_prov")
        async with test_database.get_session() as session:
            user1_id = await create_user_in_db(session)
            user2_id = await create_user_in_db(session)
            conn1_id = await create_connection_in_db(
                session, user1_id, prov1_id, prov1_slug
            )
            conn2_id = await create_connection_in_db(
                session, user2_id, prov2_id, prov2_slug
            )

        acc1 = create_test_account(connection_id=conn1_id, name="User1 Account")
        acc2 = create_test_account(connection_id=conn2_id, name="User2 Account")

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(acc1)
            await repo.save(acc2)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_by_user_id(user1_id)

        # Assert
        assert len(accounts) == 1
        assert accounts[0].name == "User1 Account"


@pytest.mark.integration
class TestAccountRepositoryFindByProviderAccountId:
    """Test AccountRepository find_by_provider_account_id operations."""

    @pytest.mark.asyncio
    async def test_find_by_provider_account_id_returns_account(
        self, test_database, connection_with_provider
    ):
        """Test find_by_provider_account_id returns matching account."""
        # Arrange
        connection_id, _ = connection_with_provider
        provider_account_id = "SCHWAB-12345"
        account = create_test_account(
            connection_id=connection_id,
            provider_account_id=provider_account_id,
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_provider_account_id(
                connection_id, provider_account_id
            )

        # Assert
        assert found is not None
        assert found.provider_account_id == provider_account_id

    @pytest.mark.asyncio
    async def test_find_by_provider_account_id_returns_none(
        self, test_database, connection_with_provider
    ):
        """Test find_by_provider_account_id returns None when not found."""
        # Arrange
        connection_id, _ = connection_with_provider

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_provider_account_id(connection_id, "NONEXISTENT")

        # Assert
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_provider_account_id_scoped_to_connection(
        self, test_database, provider_factory
    ):
        """Test provider_account_id lookup is scoped to specific connection."""
        # Arrange - Same provider_account_id in different connections
        prov1_id, prov1_slug = await provider_factory("schwab1")
        prov2_id, prov2_slug = await provider_factory("schwab2")
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            conn1_id = await create_connection_in_db(
                session, user_id, prov1_id, prov1_slug
            )
            conn2_id = await create_connection_in_db(
                session, user_id, prov2_id, prov2_slug
            )

        provider_account_id = "SAME-ID-12345"
        acc1 = create_test_account(
            connection_id=conn1_id,
            provider_account_id=provider_account_id,
            name="Connection 1 Account",
        )
        acc2 = create_test_account(
            connection_id=conn2_id,
            provider_account_id=provider_account_id,
            name="Connection 2 Account",
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(acc1)
            await repo.save(acc2)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_provider_account_id(
                conn1_id, provider_account_id
            )

        # Assert - Should return only the account from conn1
        assert found is not None
        assert found.name == "Connection 1 Account"


@pytest.mark.integration
class TestAccountRepositoryFindActiveByUser:
    """Test AccountRepository find_active_by_user operations."""

    @pytest.mark.asyncio
    async def test_find_active_by_user_returns_only_active(
        self, test_database, connection_with_provider
    ):
        """Test find_active_by_user returns only active accounts."""
        # Arrange
        connection_id, user_id = connection_with_provider
        active_account = create_test_account(
            connection_id=connection_id,
            name="Active Account",
            is_active=True,
        )
        inactive_account = create_test_account(
            connection_id=connection_id,
            name="Inactive Account",
            is_active=False,
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(active_account)
            await repo.save(inactive_account)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_active_by_user(user_id)

        # Assert
        assert len(accounts) == 1
        assert accounts[0].name == "Active Account"
        assert accounts[0].is_active is True

    @pytest.mark.asyncio
    async def test_find_active_by_user_returns_empty_when_none_active(
        self, test_database, connection_with_provider
    ):
        """Test find_active_by_user returns empty when no active accounts."""
        # Arrange
        connection_id, user_id = connection_with_provider
        inactive = create_test_account(
            connection_id=connection_id,
            is_active=False,
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(inactive)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_active_by_user(user_id)

        # Assert
        assert accounts == []

    @pytest.mark.asyncio
    async def test_find_active_by_user_across_connections(
        self, test_database, provider_factory
    ):
        """Test find_active_by_user returns active accounts across connections."""
        # Arrange
        prov1_id, prov1_slug = await provider_factory("schwab")
        prov2_id, prov2_slug = await provider_factory("fidelity")
        async with test_database.get_session() as session:
            user_id = await create_user_in_db(session)
            conn1_id = await create_connection_in_db(
                session, user_id, prov1_id, prov1_slug
            )
            conn2_id = await create_connection_in_db(
                session, user_id, prov2_id, prov2_slug
            )

        acc1 = create_test_account(
            connection_id=conn1_id, name="Schwab Active", is_active=True
        )
        acc2 = create_test_account(
            connection_id=conn2_id, name="Fidelity Active", is_active=True
        )
        acc3 = create_test_account(
            connection_id=conn2_id, name="Fidelity Inactive", is_active=False
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(acc1)
            await repo.save(acc2)
            await repo.save(acc3)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_active_by_user(user_id)

        # Assert
        assert len(accounts) == 2
        names = {a.name for a in accounts}
        assert names == {"Schwab Active", "Fidelity Active"}


@pytest.mark.integration
class TestAccountRepositoryFindNeedingSync:
    """Test AccountRepository find_needing_sync operations."""

    @pytest.mark.asyncio
    async def test_find_needing_sync_returns_stale_accounts(
        self, test_database, connection_with_provider
    ):
        """Test find_needing_sync returns accounts not synced within threshold."""
        # Arrange
        connection_id, _ = connection_with_provider

        # Account synced 2 hours ago (stale)
        stale = create_test_account(
            connection_id=connection_id,
            name="Stale Account",
            last_synced_at=datetime.now(UTC) - timedelta(hours=2),
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(stale)

        # Act - 1 hour threshold
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_needing_sync(timedelta(hours=1))

        # Assert
        assert len(accounts) == 1
        assert accounts[0].name == "Stale Account"

    @pytest.mark.asyncio
    async def test_find_needing_sync_excludes_recently_synced(
        self, test_database, connection_with_provider
    ):
        """Test find_needing_sync excludes recently synced accounts."""
        # Arrange
        connection_id, _ = connection_with_provider

        # Account synced 5 minutes ago (recent)
        recent = create_test_account(
            connection_id=connection_id,
            name="Recent Account",
            last_synced_at=datetime.now(UTC) - timedelta(minutes=5),
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(recent)

        # Act - 1 hour threshold
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_needing_sync(timedelta(hours=1))

        # Assert
        assert accounts == []

    @pytest.mark.asyncio
    async def test_find_needing_sync_includes_never_synced(
        self, test_database, connection_with_provider
    ):
        """Test find_needing_sync includes accounts never synced (NULL)."""
        # Arrange
        connection_id, _ = connection_with_provider

        # Account never synced
        never_synced = create_test_account(
            connection_id=connection_id,
            name="Never Synced",
            last_synced_at=None,
        )

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(never_synced)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            accounts = await repo.find_needing_sync(timedelta(hours=1))

        # Assert
        assert len(accounts) == 1
        assert accounts[0].name == "Never Synced"


@pytest.mark.integration
class TestAccountRepositoryDelete:
    """Test AccountRepository delete operations."""

    @pytest.mark.asyncio
    async def test_delete_removes_account(
        self, test_database, connection_with_provider
    ):
        """Test delete removes account from database."""
        # Arrange
        connection_id, _ = connection_with_provider
        account = create_test_account(connection_id=connection_id)

        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.save(account)

        # Act
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            await repo.delete(account.id)

        # Assert
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            found = await repo.find_by_id(account.id)
            assert found is None

    @pytest.mark.asyncio
    async def test_delete_raises_when_not_found(self, test_database):
        """Test delete raises NoResultFound for non-existent account."""
        # Act & Assert
        async with test_database.get_session() as session:
            repo = AccountRepository(session=session)
            with pytest.raises(NoResultFound):
                await repo.delete(uuid7())


@pytest.mark.integration
class TestAccountRepositoryAccountTypeMapping:
    """Test AccountType enum mapping between domain and model."""

    @pytest.mark.asyncio
    async def test_all_account_types_persist_correctly(
        self, test_database, connection_with_provider
    ):
        """Test all AccountType enum values work correctly."""
        # Arrange
        connection_id, _ = connection_with_provider

        # Test a representative sample of account types
        test_types = [
            AccountType.BROKERAGE,
            AccountType.IRA,
            AccountType.CHECKING,
            AccountType.CREDIT_CARD,
            AccountType.HSA,
        ]

        for account_type in test_types:
            account = create_test_account(
                connection_id=connection_id,
                name=f"Test {account_type.value}",
                account_type=account_type,
            )

            async with test_database.get_session() as session:
                repo = AccountRepository(session=session)
                await repo.save(account)

            async with test_database.get_session() as session:
                repo = AccountRepository(session=session)
                found = await repo.find_by_id(account.id)

                assert found is not None
                assert found.account_type == account_type

    @pytest.mark.asyncio
    async def test_account_type_roundtrip_all_values(
        self, test_database, connection_with_provider
    ):
        """Test all AccountType enum values survive roundtrip."""
        # Arrange
        connection_id, _ = connection_with_provider

        # Test ALL account types
        for account_type in AccountType:
            account = create_test_account(
                connection_id=connection_id,
                name=f"Type_{account_type.value}",
                account_type=account_type,
            )

            async with test_database.get_session() as session:
                repo = AccountRepository(session=session)
                await repo.save(account)

            async with test_database.get_session() as session:
                repo = AccountRepository(session=session)
                found = await repo.find_by_id(account.id)

                assert found is not None, f"Account not found for type {account_type}"
                assert found.account_type == account_type, (
                    f"Type mismatch for {account_type}"
                )
