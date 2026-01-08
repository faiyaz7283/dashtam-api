"""Unit tests for ListHoldings handlers.

Tests ListHoldingsByAccount and ListHoldingsByUser query handlers,
including ownership verification, value aggregation, and filtering.

Reference:
    - src/application/queries/handlers/list_holdings_handler.py
    - docs/architecture/cqrs-pattern.md
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from typing import cast
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.queries.handlers.list_holdings_handler import (
    HoldingListResult,
    HoldingResult,
    ListHoldingsByAccountError,
    ListHoldingsByAccountHandler,
    ListHoldingsByUserHandler,
)
from src.application.queries.holding_queries import (
    ListHoldingsByAccount,
    ListHoldingsByUser,
)
from src.core.result import Failure, Success
from src.domain.entities.account import Account
from src.domain.entities.holding import Holding
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.account_type import AccountType
from src.domain.enums.asset_type import AssetType
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
    return cast(UUID, uuid7())


@pytest.fixture
def other_user_id() -> UUID:
    """Different user ID for ownership failure tests."""
    return cast(UUID, uuid7())


@pytest.fixture
def connection_id() -> UUID:
    """Provider connection ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def account_id() -> UUID:
    """Account ID."""
    return cast(UUID, uuid7())


@pytest.fixture
def mock_holding_repo() -> AsyncMock:
    """Mock HoldingRepository."""
    return AsyncMock()


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
def mock_account(connection_id: UUID, account_id: UUID) -> Account:
    """Mock Account entity."""
    return Account(
        id=account_id,
        connection_id=connection_id,
        provider_account_id="test-account-1",
        account_number_masked="****1234",
        name="Brokerage Account",
        account_type=AccountType.BROKERAGE,
        currency="USD",
        balance=Money(amount=Decimal("50000.00"), currency="USD"),
        available_balance=None,
        is_active=True,
        last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def mock_holdings(account_id: UUID) -> list[Holding]:
    """List of mock Holding entities."""
    return [
        Holding(
            id=uuid7(),
            account_id=account_id,
            provider_holding_id="SCHWAB-AAPL-123",
            symbol="AAPL",
            security_name="Apple Inc.",
            asset_type=AssetType.EQUITY,
            quantity=Decimal("100"),
            cost_basis=Money(amount=Decimal("15000.00"), currency="USD"),
            market_value=Money(amount=Decimal("17500.00"), currency="USD"),
            currency="USD",
            average_price=Money(amount=Decimal("150.00"), currency="USD"),
            current_price=Money(amount=Decimal("175.00"), currency="USD"),
            is_active=True,
            last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        ),
        Holding(
            id=uuid7(),
            account_id=account_id,
            provider_holding_id="SCHWAB-GOOGL-456",
            symbol="GOOGL",
            security_name="Alphabet Inc.",
            asset_type=AssetType.EQUITY,
            quantity=Decimal("50"),
            cost_basis=Money(amount=Decimal("7000.00"), currency="USD"),
            market_value=Money(amount=Decimal("7500.00"), currency="USD"),
            currency="USD",
            average_price=Money(amount=Decimal("140.00"), currency="USD"),
            current_price=Money(amount=Decimal("150.00"), currency="USD"),
            is_active=True,
            last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        ),
        Holding(
            id=uuid7(),
            account_id=account_id,
            provider_holding_id="SCHWAB-SPY-789",
            symbol="SPY",
            security_name="SPDR S&P 500 ETF",
            asset_type=AssetType.ETF,
            quantity=Decimal("20"),
            cost_basis=Money(amount=Decimal("9000.00"), currency="USD"),
            market_value=Money(amount=Decimal("10000.00"), currency="USD"),
            currency="USD",
            average_price=Money(amount=Decimal("450.00"), currency="USD"),
            current_price=Money(amount=Decimal("500.00"), currency="USD"),
            is_active=True,
            last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        ),
    ]


# ============================================================================
# ListHoldingsByAccountHandler Tests
# ============================================================================


@pytest.fixture
def list_by_account_handler(
    mock_holding_repo: AsyncMock,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
) -> ListHoldingsByAccountHandler:
    """ListHoldingsByAccountHandler instance with mocked dependencies."""
    return ListHoldingsByAccountHandler(
        holding_repo=mock_holding_repo,
        account_repo=mock_account_repo,
        connection_repo=mock_connection_repo,
    )


@pytest.mark.asyncio
async def test_list_holdings_by_account_success(
    list_by_account_handler: ListHoldingsByAccountHandler,
    mock_holding_repo: AsyncMock,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_connection: ProviderConnection,
    mock_account: Account,
    mock_holdings: list[Holding],
    user_id: UUID,
    account_id: UUID,
) -> None:
    """ListHoldingsByAccount returns Success with aggregated values."""
    # Arrange
    query = ListHoldingsByAccount(
        account_id=account_id,
        user_id=user_id,
        active_only=True,
    )
    mock_account_repo.find_by_id.return_value = mock_account
    mock_connection_repo.find_by_id.return_value = mock_connection
    mock_holding_repo.list_by_account.return_value = mock_holdings

    # Act
    result = await list_by_account_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert isinstance(dto, HoldingListResult)

    # Verify holding count
    assert dto.total_count == 3
    assert dto.active_count == 3
    assert len(dto.holdings) == 3

    # Verify market value aggregation (17500 + 7500 + 10000 = 35000)
    assert "USD" in dto.total_market_value_by_currency
    assert dto.total_market_value_by_currency["USD"] == "35000.00"

    # Verify cost basis aggregation (15000 + 7000 + 9000 = 31000)
    assert dto.total_cost_basis_by_currency["USD"] == "31000.00"

    # Verify gain/loss (35000 - 31000 = 4000)
    assert dto.total_unrealized_gain_loss_by_currency["USD"] == "4000.00"


@pytest.mark.asyncio
async def test_list_holdings_by_account_not_found(
    list_by_account_handler: ListHoldingsByAccountHandler,
    mock_account_repo: AsyncMock,
    user_id: UUID,
    account_id: UUID,
) -> None:
    """ListHoldingsByAccount returns Failure when account not found."""
    # Arrange
    query = ListHoldingsByAccount(
        account_id=account_id,
        user_id=user_id,
        active_only=True,
    )
    mock_account_repo.find_by_id.return_value = None

    # Act
    result = await list_by_account_handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == ListHoldingsByAccountError.ACCOUNT_NOT_FOUND


@pytest.mark.asyncio
async def test_list_holdings_by_account_connection_not_found(
    list_by_account_handler: ListHoldingsByAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_account: Account,
    user_id: UUID,
    account_id: UUID,
) -> None:
    """ListHoldingsByAccount returns Failure when connection not found."""
    # Arrange
    query = ListHoldingsByAccount(
        account_id=account_id,
        user_id=user_id,
        active_only=True,
    )
    mock_account_repo.find_by_id.return_value = mock_account
    mock_connection_repo.find_by_id.return_value = None

    # Act
    result = await list_by_account_handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == ListHoldingsByAccountError.CONNECTION_NOT_FOUND


@pytest.mark.asyncio
async def test_list_holdings_by_account_not_owned(
    list_by_account_handler: ListHoldingsByAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_connection: ProviderConnection,
    mock_account: Account,
    other_user_id: UUID,
    account_id: UUID,
) -> None:
    """ListHoldingsByAccount returns Failure when account not owned by user."""
    # Arrange
    query = ListHoldingsByAccount(
        account_id=account_id,
        user_id=other_user_id,  # Different user
        active_only=True,
    )
    mock_account_repo.find_by_id.return_value = mock_account
    mock_connection_repo.find_by_id.return_value = mock_connection

    # Act
    result = await list_by_account_handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == ListHoldingsByAccountError.NOT_OWNED_BY_USER


@pytest.mark.asyncio
async def test_list_holdings_by_account_filters_by_asset_type(
    list_by_account_handler: ListHoldingsByAccountHandler,
    mock_holding_repo: AsyncMock,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_connection: ProviderConnection,
    mock_account: Account,
    mock_holdings: list[Holding],
    user_id: UUID,
    account_id: UUID,
) -> None:
    """ListHoldingsByAccount filters by asset_type when provided."""
    # Arrange
    query = ListHoldingsByAccount(
        account_id=account_id,
        user_id=user_id,
        active_only=True,
        asset_type="etf",  # Filter for ETFs only
    )
    mock_account_repo.find_by_id.return_value = mock_account
    mock_connection_repo.find_by_id.return_value = mock_connection
    mock_holding_repo.list_by_account.return_value = mock_holdings

    # Act
    result = await list_by_account_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    # Only SPY should match (it's the only ETF)
    assert dto.total_count == 1
    assert dto.holdings[0].symbol == "SPY"


# ============================================================================
# ListHoldingsByUserHandler Tests
# ============================================================================


@pytest.fixture
def list_by_user_handler(
    mock_holding_repo: AsyncMock,
) -> ListHoldingsByUserHandler:
    """ListHoldingsByUserHandler instance with mocked dependencies."""
    return ListHoldingsByUserHandler(
        holding_repo=mock_holding_repo,
    )


@pytest.mark.asyncio
async def test_list_holdings_by_user_success(
    list_by_user_handler: ListHoldingsByUserHandler,
    mock_holding_repo: AsyncMock,
    mock_holdings: list[Holding],
    user_id: UUID,
) -> None:
    """ListHoldingsByUser returns Success with all user's holdings."""
    # Arrange
    query = ListHoldingsByUser(
        user_id=user_id,
        active_only=True,
    )
    mock_holding_repo.list_by_user.return_value = mock_holdings

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert isinstance(dto, HoldingListResult)
    assert dto.total_count == 3


@pytest.mark.asyncio
async def test_list_holdings_by_user_filters_by_symbol(
    list_by_user_handler: ListHoldingsByUserHandler,
    mock_holding_repo: AsyncMock,
    mock_holdings: list[Holding],
    user_id: UUID,
) -> None:
    """ListHoldingsByUser filters by symbol when provided."""
    # Arrange
    query = ListHoldingsByUser(
        user_id=user_id,
        active_only=True,
        symbol="AAPL",
    )
    mock_holding_repo.list_by_user.return_value = mock_holdings

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 1
    assert dto.holdings[0].symbol == "AAPL"


@pytest.mark.asyncio
async def test_list_holdings_by_user_empty_result(
    list_by_user_handler: ListHoldingsByUserHandler,
    mock_holding_repo: AsyncMock,
    user_id: UUID,
) -> None:
    """ListHoldingsByUser returns empty result when no holdings found."""
    # Arrange
    query = ListHoldingsByUser(
        user_id=user_id,
        active_only=True,
    )
    mock_holding_repo.list_by_user.return_value = []

    # Act
    result = await list_by_user_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.total_count == 0
    assert dto.active_count == 0
    assert len(dto.holdings) == 0


# ============================================================================
# HoldingResult DTO Tests
# ============================================================================


@pytest.mark.asyncio
async def test_holding_dto_contains_all_fields(
    list_by_account_handler: ListHoldingsByAccountHandler,
    mock_holding_repo: AsyncMock,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_connection: ProviderConnection,
    mock_account: Account,
    mock_holdings: list[Holding],
    user_id: UUID,
    account_id: UUID,
) -> None:
    """HoldingResult DTO contains all expected fields."""
    # Arrange
    query = ListHoldingsByAccount(
        account_id=account_id,
        user_id=user_id,
        active_only=True,
    )
    mock_account_repo.find_by_id.return_value = mock_account
    mock_connection_repo.find_by_id.return_value = mock_connection
    mock_holding_repo.list_by_account.return_value = mock_holdings[:1]  # Just AAPL

    # Act
    result = await list_by_account_handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value.holdings[0]
    assert isinstance(dto, HoldingResult)

    # Verify all fields are present
    assert dto.symbol == "AAPL"
    assert dto.security_name == "Apple Inc."
    assert dto.asset_type == "equity"
    assert dto.quantity == Decimal("100")
    assert dto.cost_basis == Decimal("15000.00")
    assert dto.market_value == Decimal("17500.00")
    assert dto.currency == "USD"
    assert dto.average_price == Decimal("150.00")
    assert dto.current_price == Decimal("175.00")
    assert dto.unrealized_gain_loss == Decimal("2500.00")
    assert dto.is_profitable is True
