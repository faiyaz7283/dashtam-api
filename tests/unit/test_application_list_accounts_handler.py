"""Unit tests for ListAccounts handlers.

Tests ListAccountsByConnection and ListAccountsByUser query handlers,
including ownership verification, balance aggregation, and filtering.

Reference:
    - src/application/queries/handlers/list_accounts_handler.py
    - docs/architecture/cqrs-pattern.md
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.queries.account_queries import (
    ListAccountsByConnection,
    ListAccountsByUser,
)
from src.application.queries.handlers.get_account_handler import AccountResult
from src.application.queries.handlers.list_accounts_handler import (
    AccountListResult,
    ListAccountsByConnectionError,
    ListAccountsByConnectionHandler,
    ListAccountsByUserHandler,
)
from src.core.result import Failure, Success
from src.domain.entities.account import Account
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.account_type import AccountType
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.enums.credential_type import CredentialType
from src.domain.value_objects.money import Money
from src.domain.value_objects.provider_credentials import ProviderCredentials


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def user_id() -> UUID:
    """User ID for ownership verification."""
    return uuid7()


@pytest.fixture
def other_user_id() -> UUID:
    """Different user ID for ownership failure tests."""
    return uuid7()


@pytest.fixture
def connection_id() -> UUID:
    """Provider connection ID."""
    return uuid7()


@pytest.fixture
def mock_account_repo() -> AsyncMock:
    """Mock AccountRepository."""
    return AsyncMock()


@pytest.fixture
def mock_connection_repo() -> AsyncMock:
    """Mock ProviderConnectionRepository."""
    return AsyncMock()


@pytest.fixture
def mock_connection(user_id: UUID, connection_id: UUID) -> ProviderConnection:
    """Mock ProviderConnection entity owned by user_id."""
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
def mock_accounts(connection_id: UUID) -> list[Account]:
    """List of mock Account entities (3 accounts, mixed currencies)."""
    return [
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-account-1",
            account_number_masked="****1234",
            name="Brokerage Account",
            account_type=AccountType.BROKERAGE,
            currency="USD",
            balance=Money(amount=Decimal("15000.50"), currency="USD"),
            available_balance=Money(amount=Decimal("14000.00"), currency="USD"),
            is_active=True,
            last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        ),
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-account-2",
            account_number_masked="****5678",
            name="Traditional IRA",
            account_type=AccountType.IRA,
            currency="USD",
            balance=Money(amount=Decimal("50000.00"), currency="USD"),
            available_balance=None,
            is_active=True,
            last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        ),
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-account-3",
            account_number_masked="****9012",
            name="EUR Savings",
            account_type=AccountType.SAVINGS,
            currency="EUR",
            balance=Money(amount=Decimal("2000.00"), currency="EUR"),
            available_balance=Money(amount=Decimal("2000.00"), currency="EUR"),
            is_active=True,
            last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        ),
    ]


# ============================================================================
# ListAccountsByConnectionHandler Tests
# ============================================================================


@pytest.fixture
def list_by_connection_handler(
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
) -> ListAccountsByConnectionHandler:
    """ListAccountsByConnectionHandler instance with mocked dependencies."""
    return ListAccountsByConnectionHandler(
        account_repo=mock_account_repo,
        connection_repo=mock_connection_repo,
    )


@pytest.mark.asyncio
async def test_list_accounts_by_connection_success(
    list_by_connection_handler: ListAccountsByConnectionHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_connection: ProviderConnection,
    mock_accounts: list[Account],
    user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByConnection returns Success with aggregated balances by currency."""
    # Arrange
    query = ListAccountsByConnection(
        connection_id=connection_id, user_id=user_id, active_only=False
    )
    mock_connection_repo.find_by_id.return_value = mock_connection
    mock_account_repo.find_by_connection_id.return_value = mock_accounts

    # Act
    result = await list_by_connection_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert isinstance(dto, AccountListResult)

    # Verify account count
    assert dto.total_count == 3
    assert dto.active_count == 3
    assert len(dto.accounts) == 3

    # Verify balance aggregation by currency
    assert "USD" in dto.total_balance_by_currency
    assert "EUR" in dto.total_balance_by_currency
    assert dto.total_balance_by_currency["USD"] == "65000.50"  # 15000.50 + 50000.00
    assert dto.total_balance_by_currency["EUR"] == "2000.00"

    # Verify account DTOs
    assert all(isinstance(acc, AccountResult) for acc in dto.accounts)
    assert dto.accounts[0].account_type == "brokerage"
    assert dto.accounts[1].account_type == "ira"
    assert dto.accounts[2].account_type == "savings"

    # Verify repo calls
    mock_connection_repo.find_by_id.assert_awaited_once_with(connection_id)
    mock_account_repo.find_by_connection_id.assert_awaited_once_with(
        connection_id=connection_id, active_only=False
    )


@pytest.mark.asyncio
async def test_list_accounts_by_connection_active_only(
    list_by_connection_handler: ListAccountsByConnectionHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_connection: ProviderConnection,
    user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByConnection filters for active accounts only when active_only=True."""
    # Arrange
    active_accounts = [
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-active",
            account_number_masked="****1111",
            name="Active Account",
            account_type=AccountType.BROKERAGE,
            currency="USD",
            balance=Money(amount=Decimal("10000.00"), currency="USD"),
            available_balance=None,
            is_active=True,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
    ]

    query = ListAccountsByConnection(
        connection_id=connection_id, user_id=user_id, active_only=True
    )
    mock_connection_repo.find_by_id.return_value = mock_connection
    mock_account_repo.find_by_connection_id.return_value = active_accounts

    # Act
    result = await list_by_connection_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 1
    assert dto.active_count == 1

    # Verify active_only=True passed to repo
    mock_account_repo.find_by_connection_id.assert_awaited_once_with(
        connection_id=connection_id, active_only=True
    )


@pytest.mark.asyncio
async def test_list_accounts_by_connection_empty_list(
    list_by_connection_handler: ListAccountsByConnectionHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_connection: ProviderConnection,
    user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByConnection returns empty list when no accounts exist."""
    # Arrange
    query = ListAccountsByConnection(
        connection_id=connection_id, user_id=user_id, active_only=False
    )
    mock_connection_repo.find_by_id.return_value = mock_connection
    mock_account_repo.find_by_connection_id.return_value = []

    # Act
    result = await list_by_connection_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 0
    assert dto.active_count == 0
    assert dto.accounts == []
    assert dto.total_balance_by_currency == {}


@pytest.mark.asyncio
async def test_list_accounts_by_connection_mixed_active_inactive(
    list_by_connection_handler: ListAccountsByConnectionHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_connection: ProviderConnection,
    user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByConnection calculates active_count correctly with mixed active/inactive accounts."""
    # Arrange
    accounts = [
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-active",
            account_number_masked="****1111",
            name="Active",
            account_type=AccountType.BROKERAGE,
            currency="USD",
            balance=Money(amount=Decimal("5000.00"), currency="USD"),
            available_balance=None,
            is_active=True,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-inactive",
            account_number_masked="****2222",
            name="Inactive",
            account_type=AccountType.BROKERAGE,
            currency="USD",
            balance=Money(amount=Decimal("0.00"), currency="USD"),
            available_balance=None,
            is_active=False,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
    ]

    query = ListAccountsByConnection(
        connection_id=connection_id, user_id=user_id, active_only=False
    )
    mock_connection_repo.find_by_id.return_value = mock_connection
    mock_account_repo.find_by_connection_id.return_value = accounts

    # Act
    result = await list_by_connection_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 2
    assert dto.active_count == 1  # Only 1 active


@pytest.mark.asyncio
async def test_list_accounts_by_connection_not_found(
    list_by_connection_handler: ListAccountsByConnectionHandler,
    mock_connection_repo: AsyncMock,
    user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByConnection returns Failure(CONNECTION_NOT_FOUND) when connection does not exist."""
    # Arrange
    query = ListAccountsByConnection(
        connection_id=connection_id, user_id=user_id, active_only=False
    )
    mock_connection_repo.find_by_id.return_value = None

    # Act
    result = await list_by_connection_handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == ListAccountsByConnectionError.CONNECTION_NOT_FOUND


@pytest.mark.asyncio
async def test_list_accounts_by_connection_not_owned_by_user(
    list_by_connection_handler: ListAccountsByConnectionHandler,
    mock_connection_repo: AsyncMock,
    user_id: UUID,
    other_user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByConnection returns Failure(NOT_OWNED_BY_USER) when connection belongs to different user."""
    # Arrange
    other_connection = ProviderConnection(
        id=connection_id,
        user_id=other_user_id,  # Different user!
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

    query = ListAccountsByConnection(
        connection_id=connection_id, user_id=user_id, active_only=False
    )
    mock_connection_repo.find_by_id.return_value = other_connection

    # Act
    result = await list_by_connection_handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == ListAccountsByConnectionError.NOT_OWNED_BY_USER


# ============================================================================
# ListAccountsByUserHandler Tests
# ============================================================================


@pytest.fixture
def list_by_user_handler(
    mock_account_repo: AsyncMock,
) -> ListAccountsByUserHandler:
    """ListAccountsByUserHandler instance with mocked dependencies."""
    return ListAccountsByUserHandler(
        account_repo=mock_account_repo,
    )


@pytest.mark.asyncio
async def test_list_accounts_by_user_success(
    list_by_user_handler: ListAccountsByUserHandler,
    mock_account_repo: AsyncMock,
    user_id: UUID,
    mock_accounts: list[Account],
) -> None:
    """ListAccountsByUser returns Success with aggregated balances by currency."""
    # Arrange
    query = ListAccountsByUser(user_id=user_id, active_only=False, account_type=None)
    mock_account_repo.find_by_user_id.return_value = mock_accounts

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 3
    assert dto.active_count == 3
    assert len(dto.accounts) == 3

    # Verify balance aggregation
    assert "USD" in dto.total_balance_by_currency
    assert "EUR" in dto.total_balance_by_currency
    assert dto.total_balance_by_currency["USD"] == "65000.50"
    assert dto.total_balance_by_currency["EUR"] == "2000.00"

    # Verify repo call
    mock_account_repo.find_by_user_id.assert_awaited_once_with(
        user_id=user_id, active_only=False, account_type=None
    )


@pytest.mark.asyncio
async def test_list_accounts_by_user_active_only(
    list_by_user_handler: ListAccountsByUserHandler,
    mock_account_repo: AsyncMock,
    user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByUser filters for active accounts only when active_only=True."""
    # Arrange
    active_accounts = [
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-active",
            account_number_masked="****1111",
            name="Active",
            account_type=AccountType.BROKERAGE,
            currency="USD",
            balance=Money(amount=Decimal("10000.00"), currency="USD"),
            available_balance=None,
            is_active=True,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
    ]

    query = ListAccountsByUser(user_id=user_id, active_only=True, account_type=None)
    mock_account_repo.find_by_user_id.return_value = active_accounts

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 1
    assert dto.active_count == 1

    # Verify active_only=True passed to repo
    mock_account_repo.find_by_user_id.assert_awaited_once_with(
        user_id=user_id, active_only=True, account_type=None
    )


@pytest.mark.asyncio
async def test_list_accounts_by_user_filter_by_account_type(
    list_by_user_handler: ListAccountsByUserHandler,
    mock_account_repo: AsyncMock,
    user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByUser filters by account_type when provided."""
    # Arrange
    ira_accounts = [
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-ira",
            account_number_masked="****5555",
            name="Traditional IRA",
            account_type=AccountType.IRA,
            currency="USD",
            balance=Money(amount=Decimal("50000.00"), currency="USD"),
            available_balance=None,
            is_active=True,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
    ]

    query = ListAccountsByUser(user_id=user_id, active_only=False, account_type="ira")
    mock_account_repo.find_by_user_id.return_value = ira_accounts

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 1
    assert dto.accounts[0].account_type == "ira"

    # Verify account_type=IRA passed to repo
    mock_account_repo.find_by_user_id.assert_awaited_once_with(
        user_id=user_id, active_only=False, account_type=AccountType.IRA
    )


@pytest.mark.asyncio
async def test_list_accounts_by_user_invalid_account_type(
    list_by_user_handler: ListAccountsByUserHandler,
    mock_account_repo: AsyncMock,
    user_id: UUID,
) -> None:
    """ListAccountsByUser returns empty list for invalid account_type string."""
    # Arrange
    query = ListAccountsByUser(
        user_id=user_id, active_only=False, account_type="invalid-type"
    )

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 0
    assert dto.active_count == 0
    assert dto.accounts == []
    assert dto.total_balance_by_currency == {}

    # Verify repo NOT called (early return)
    mock_account_repo.find_by_user_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_accounts_by_user_empty_list(
    list_by_user_handler: ListAccountsByUserHandler,
    mock_account_repo: AsyncMock,
    user_id: UUID,
) -> None:
    """ListAccountsByUser returns empty list when no accounts exist."""
    # Arrange
    query = ListAccountsByUser(user_id=user_id, active_only=False, account_type=None)
    mock_account_repo.find_by_user_id.return_value = []

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 0
    assert dto.active_count == 0
    assert dto.accounts == []
    assert dto.total_balance_by_currency == {}


@pytest.mark.asyncio
async def test_list_accounts_by_user_mixed_active_inactive(
    list_by_user_handler: ListAccountsByUserHandler,
    mock_account_repo: AsyncMock,
    user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByUser calculates active_count correctly with mixed active/inactive accounts."""
    # Arrange
    accounts = [
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-active",
            account_number_masked="****1111",
            name="Active",
            account_type=AccountType.BROKERAGE,
            currency="USD",
            balance=Money(amount=Decimal("5000.00"), currency="USD"),
            available_balance=None,
            is_active=True,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-inactive-1",
            account_number_masked="****2222",
            name="Inactive 1",
            account_type=AccountType.BROKERAGE,
            currency="USD",
            balance=Money(amount=Decimal("0.00"), currency="USD"),
            available_balance=None,
            is_active=False,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-inactive-2",
            account_number_masked="****3333",
            name="Inactive 2",
            account_type=AccountType.IRA,
            currency="USD",
            balance=Money(amount=Decimal("0.00"), currency="USD"),
            available_balance=None,
            is_active=False,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
    ]

    query = ListAccountsByUser(user_id=user_id, active_only=False, account_type=None)
    mock_account_repo.find_by_user_id.return_value = accounts

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 3
    assert dto.active_count == 1  # Only 1 active


@pytest.mark.asyncio
async def test_list_accounts_by_user_multi_currency_aggregation(
    list_by_user_handler: ListAccountsByUserHandler,
    mock_account_repo: AsyncMock,
    user_id: UUID,
    connection_id: UUID,
) -> None:
    """ListAccountsByUser aggregates balances correctly across multiple currencies."""
    # Arrange
    accounts = [
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-usd-1",
            account_number_masked="****1111",
            name="USD Account 1",
            account_type=AccountType.BROKERAGE,
            currency="USD",
            balance=Money(amount=Decimal("10000.00"), currency="USD"),
            available_balance=None,
            is_active=True,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-usd-2",
            account_number_masked="****2222",
            name="USD Account 2",
            account_type=AccountType.IRA,
            currency="USD",
            balance=Money(amount=Decimal("5000.50"), currency="USD"),
            available_balance=None,
            is_active=True,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-eur-1",
            account_number_masked="****3333",
            name="EUR Account",
            account_type=AccountType.SAVINGS,
            currency="EUR",
            balance=Money(amount=Decimal("2000.25"), currency="EUR"),
            available_balance=None,
            is_active=True,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
        Account(
            id=uuid7(),
            connection_id=connection_id,
            provider_account_id="test-gbp-1",
            account_number_masked="****4444",
            name="GBP Account",
            account_type=AccountType.CHECKING,
            currency="GBP",
            balance=Money(amount=Decimal("3000.75"), currency="GBP"),
            available_balance=None,
            is_active=True,
            last_synced_at=None,
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        ),
    ]

    query = ListAccountsByUser(user_id=user_id, active_only=False, account_type=None)
    mock_account_repo.find_by_user_id.return_value = accounts

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 4

    # Verify aggregation by currency
    assert len(dto.total_balance_by_currency) == 3
    assert dto.total_balance_by_currency["USD"] == "15000.50"  # 10000 + 5000.50
    assert dto.total_balance_by_currency["EUR"] == "2000.25"
    assert dto.total_balance_by_currency["GBP"] == "3000.75"
