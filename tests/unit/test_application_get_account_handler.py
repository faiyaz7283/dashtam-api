"""Unit tests for GetAccountHandler.

Tests GetAccount query handler including ownership verification,
DTO mapping (Money -> amount+currency), and error cases.

Reference:
    - src/application/queries/handlers/get_account_handler.py
    - docs/architecture/cqrs-pattern.md
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from typing import cast
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.queries.account_queries import GetAccount
from src.application.queries.handlers.get_account_handler import (
    AccountResult,
    GetAccountError,
    GetAccountHandler,
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
def mock_account_repo() -> AsyncMock:
    """Mock AccountRepository."""
    return AsyncMock()


@pytest.fixture
def mock_connection_repo() -> AsyncMock:
    """Mock ProviderConnectionRepository."""
    return AsyncMock()


@pytest.fixture
def handler(
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
) -> GetAccountHandler:
    """GetAccountHandler instance with mocked dependencies."""
    return GetAccountHandler(
        account_repo=mock_account_repo,
        connection_repo=mock_connection_repo,
    )


@pytest.fixture
def mock_account(connection_id: UUID, account_id: UUID) -> Account:
    """Mock Account entity."""
    return Account(
        id=account_id,
        connection_id=connection_id,
        provider_account_id="test-account-123",
        account_number_masked="****1234",
        name="Test Brokerage",
        account_type=AccountType.BROKERAGE,
        currency="USD",
        balance=Money(amount=Decimal("15000.50"), currency="USD"),
        available_balance=Money(amount=Decimal("14000.00"), currency="USD"),
        is_active=True,
        last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


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


# ============================================================================
# Success Cases
# ============================================================================


@pytest.mark.asyncio
async def test_get_account_success_with_available_balance(
    handler: GetAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_account: Account,
    mock_connection: ProviderConnection,
    user_id: UUID,
    account_id: UUID,
) -> None:
    """GetAccount returns Success(AccountResult) when account exists and owned by user (with available balance)."""
    # Arrange
    query = GetAccount(account_id=account_id, user_id=user_id)
    mock_account_repo.find_by_id.return_value = mock_account
    mock_connection_repo.find_by_id.return_value = mock_connection

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert isinstance(dto, AccountResult)

    # Verify DTO fields
    assert dto.id == mock_account.id
    assert dto.connection_id == mock_account.connection_id
    assert dto.provider_account_id == "test-account-123"
    assert dto.account_number_masked == "****1234"
    assert dto.name == "Test Brokerage"
    assert dto.account_type == "brokerage"
    assert dto.currency == "USD"

    # Verify Money -> amount+currency conversion
    assert dto.balance_amount == Decimal("15000.50")
    assert dto.balance_currency == "USD"
    assert dto.available_balance_amount == Decimal("14000.00")
    assert dto.available_balance_currency == "USD"

    # Verify flags (is_investment, is_bank, etc.)
    assert dto.is_active is True
    assert dto.is_investment is True
    assert dto.is_bank is False
    assert dto.is_retirement is False
    assert dto.is_credit is False

    # Verify timestamps
    assert dto.last_synced_at == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert dto.created_at == datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
    assert dto.updated_at == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    # Verify repo calls
    mock_account_repo.find_by_id.assert_awaited_once_with(account_id)
    mock_connection_repo.find_by_id.assert_awaited_once_with(mock_account.connection_id)


@pytest.mark.asyncio
async def test_get_account_success_without_available_balance(
    handler: GetAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    user_id: UUID,
    account_id: UUID,
    connection_id: UUID,
    mock_connection: ProviderConnection,
) -> None:
    """GetAccount returns Success(AccountResult) when available_balance is None."""
    # Arrange
    account = Account(
        id=account_id,
        connection_id=connection_id,
        provider_account_id="test-account-456",
        account_number_masked="****5678",
        name="Test IRA",
        account_type=AccountType.IRA,
        currency="USD",
        balance=Money(amount=Decimal("50000.00"), currency="USD"),
        available_balance=None,  # No available balance
        is_active=True,
        last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )

    query = GetAccount(account_id=account_id, user_id=user_id)
    mock_account_repo.find_by_id.return_value = account
    mock_connection_repo.find_by_id.return_value = mock_connection

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.balance_amount == Decimal("50000.00")
    assert dto.balance_currency == "USD"
    assert dto.available_balance_amount is None
    assert dto.available_balance_currency is None


@pytest.mark.asyncio
async def test_get_account_success_retirement_account(
    handler: GetAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    user_id: UUID,
    account_id: UUID,
    connection_id: UUID,
    mock_connection: ProviderConnection,
) -> None:
    """GetAccount returns Success(AccountResult) for IRA account with retirement flag set."""
    # Arrange
    account = Account(
        id=account_id,
        connection_id=connection_id,
        provider_account_id="test-ira-789",
        account_number_masked="****9012",
        name="Traditional IRA",
        account_type=AccountType.IRA,
        currency="USD",
        balance=Money(amount=Decimal("100000.00"), currency="USD"),
        available_balance=None,
        is_active=True,
        last_synced_at=None,
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
    )

    query = GetAccount(account_id=account_id, user_id=user_id)
    mock_account_repo.find_by_id.return_value = account
    mock_connection_repo.find_by_id.return_value = mock_connection

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.account_type == "ira"
    assert dto.is_investment is True
    assert dto.is_bank is False
    assert dto.is_retirement is True  # IRA is retirement
    assert dto.is_credit is False


@pytest.mark.asyncio
async def test_get_account_success_bank_account(
    handler: GetAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    user_id: UUID,
    account_id: UUID,
    connection_id: UUID,
    mock_connection: ProviderConnection,
) -> None:
    """GetAccount returns Success(AccountResult) for checking account with bank flag set."""
    # Arrange
    account = Account(
        id=account_id,
        connection_id=connection_id,
        provider_account_id="test-checking-345",
        account_number_masked="****3456",
        name="Checking Account",
        account_type=AccountType.CHECKING,
        currency="USD",
        balance=Money(amount=Decimal("5000.00"), currency="USD"),
        available_balance=Money(amount=Decimal("5000.00"), currency="USD"),
        is_active=True,
        last_synced_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
    )

    query = GetAccount(account_id=account_id, user_id=user_id)
    mock_account_repo.find_by_id.return_value = account
    mock_connection_repo.find_by_id.return_value = mock_connection

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.account_type == "checking"
    assert dto.is_investment is False
    assert dto.is_bank is True  # Checking is bank
    assert dto.is_retirement is False
    assert dto.is_credit is False


# ============================================================================
# Error Cases
# ============================================================================


@pytest.mark.asyncio
async def test_get_account_account_not_found(
    handler: GetAccountHandler,
    mock_account_repo: AsyncMock,
    user_id: UUID,
    account_id: UUID,
) -> None:
    """GetAccount returns Failure(ACCOUNT_NOT_FOUND) when account does not exist."""
    # Arrange
    query = GetAccount(account_id=account_id, user_id=user_id)
    mock_account_repo.find_by_id.return_value = None

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == GetAccountError.ACCOUNT_NOT_FOUND
    mock_account_repo.find_by_id.assert_awaited_once_with(account_id)


@pytest.mark.asyncio
async def test_get_account_connection_not_found(
    handler: GetAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_account: Account,
    user_id: UUID,
    account_id: UUID,
) -> None:
    """GetAccount returns Failure(CONNECTION_NOT_FOUND) when connection does not exist."""
    # Arrange
    query = GetAccount(account_id=account_id, user_id=user_id)
    mock_account_repo.find_by_id.return_value = mock_account
    mock_connection_repo.find_by_id.return_value = None  # Connection not found

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == GetAccountError.CONNECTION_NOT_FOUND
    mock_connection_repo.find_by_id.assert_awaited_once_with(mock_account.connection_id)


@pytest.mark.asyncio
async def test_get_account_not_owned_by_user(
    handler: GetAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    mock_account: Account,
    user_id: UUID,
    other_user_id: UUID,
    account_id: UUID,
    connection_id: UUID,
) -> None:
    """GetAccount returns Failure(NOT_OWNED_BY_USER) when connection belongs to different user."""
    # Arrange
    # Connection owned by other_user_id (not user_id)
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

    query = GetAccount(account_id=account_id, user_id=user_id)
    mock_account_repo.find_by_id.return_value = mock_account
    mock_connection_repo.find_by_id.return_value = other_connection

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Failure)
    assert result.error == GetAccountError.NOT_OWNED_BY_USER


# ============================================================================
# DTO Mapping Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_get_account_inactive_account(
    handler: GetAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    user_id: UUID,
    account_id: UUID,
    connection_id: UUID,
    mock_connection: ProviderConnection,
) -> None:
    """GetAccount returns Success(AccountResult) for inactive account."""
    # Arrange
    account = Account(
        id=account_id,
        connection_id=connection_id,
        provider_account_id="test-inactive-999",
        account_number_masked="****9999",
        name="Closed Account",
        account_type=AccountType.BROKERAGE,
        currency="USD",
        balance=Money(amount=Decimal("0.00"), currency="USD"),
        available_balance=None,
        is_active=False,  # Inactive
        last_synced_at=datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC),
        created_at=datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC),
    )

    query = GetAccount(account_id=account_id, user_id=user_id)
    mock_account_repo.find_by_id.return_value = account
    mock_connection_repo.find_by_id.return_value = mock_connection

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.is_active is False
    assert dto.balance_amount == Decimal("0.00")


@pytest.mark.asyncio
async def test_get_account_never_synced(
    handler: GetAccountHandler,
    mock_account_repo: AsyncMock,
    mock_connection_repo: AsyncMock,
    user_id: UUID,
    account_id: UUID,
    connection_id: UUID,
    mock_connection: ProviderConnection,
) -> None:
    """GetAccount returns Success(AccountResult) for account that was never synced."""
    # Arrange
    account = Account(
        id=account_id,
        connection_id=connection_id,
        provider_account_id="test-new-111",
        account_number_masked="****1111",
        name="New Account",
        account_type=AccountType.BROKERAGE,
        currency="USD",
        balance=Money(amount=Decimal("0.00"), currency="USD"),
        available_balance=None,
        is_active=True,
        last_synced_at=None,  # Never synced
        created_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
    )

    query = GetAccount(account_id=account_id, user_id=user_id)
    mock_account_repo.find_by_id.return_value = account
    mock_connection_repo.find_by_id.return_value = mock_connection

    # Act
    result = await handler.handle(query)

    # Assert
    assert isinstance(result, Success)
    dto = result.value
    assert dto.last_synced_at is None
