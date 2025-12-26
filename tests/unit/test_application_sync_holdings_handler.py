"""Unit tests for SyncHoldingsHandler.

Tests the command handler for syncing holdings from provider to repository.

Architecture:
- Tests command validation and error handling
- Tests provider API integration flow
- Tests holdings upsert logic (create/update/deactivate)
- Uses mock repositories and provider adapter
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.commands.handlers.sync_holdings_handler import (
    SyncHoldingsError,
    SyncHoldingsHandler,
)
from src.application.commands.sync_commands import SyncHoldings
from src.core.result import Failure, Success
from src.domain.entities.account import Account
from src.domain.entities.holding import Holding
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.connection_status import ConnectionStatus
from src.domain.protocols.provider_protocol import ProviderHoldingData
from src.domain.value_objects.provider_credentials import ProviderCredentials


# =============================================================================
# Mock Factories
# =============================================================================


def create_mock_account(
    id: UUID | None = None,
    connection_id: UUID | None = None,
    provider_account_id: str = "ACCT-123",
    last_synced_at: datetime | None = None,
) -> MagicMock:
    """Create a mock Account entity."""
    mock = MagicMock(spec=Account)
    mock.id = id or uuid7()
    mock.connection_id = connection_id or uuid7()
    mock.provider_account_id = provider_account_id
    mock.last_synced_at = last_synced_at
    return mock


def create_mock_connection(
    id: UUID | None = None,
    user_id: UUID | None = None,
    status: ConnectionStatus = ConnectionStatus.ACTIVE,
    credentials: Any | None = "has_creds",
) -> MagicMock:
    """Create a mock ProviderConnection entity."""
    mock = MagicMock(spec=ProviderConnection)
    mock.id = id or uuid7()
    mock.user_id = user_id or uuid7()
    mock.status = status
    mock.is_connected.return_value = status == ConnectionStatus.ACTIVE

    if credentials == "has_creds":
        creds = MagicMock(spec=ProviderCredentials)
        creds.encrypted_data = b"encrypted_data"
        mock.credentials = creds
    else:
        mock.credentials = None
    return mock


def create_mock_holding(
    id: UUID | None = None,
    account_id: UUID | None = None,
    provider_holding_id: str = "HOLDING-123",
    symbol: str = "AAPL",
    is_active: bool = True,
) -> MagicMock:
    """Create a mock Holding entity."""
    mock = MagicMock(spec=Holding)
    mock.id = id or uuid7()
    mock.account_id = account_id or uuid7()
    mock.provider_holding_id = provider_holding_id
    mock.symbol = symbol
    mock.is_active = is_active
    mock.currency = "USD"
    return mock


def create_provider_holding_data(
    provider_holding_id: str = "HOLDING-123",
    symbol: str = "AAPL",
    security_name: str = "Apple Inc.",
    asset_type: str = "equity",
    quantity: Decimal = Decimal("100"),
    cost_basis: Decimal = Decimal("15000.00"),
    market_value: Decimal = Decimal("17500.00"),
    currency: str = "USD",
    average_price: Decimal | None = Decimal("150.00"),
    current_price: Decimal | None = Decimal("175.00"),
) -> ProviderHoldingData:
    """Create ProviderHoldingData for testing."""
    return ProviderHoldingData(
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
        raw_data={},
    )


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_account_repo():
    """Create mock AccountRepository."""
    return AsyncMock()


@pytest.fixture
def mock_connection_repo():
    """Create mock ProviderConnectionRepository."""
    return AsyncMock()


@pytest.fixture
def mock_holding_repo():
    """Create mock HoldingRepository."""
    return AsyncMock()


@pytest.fixture
def mock_encryption_service():
    """Create mock EncryptionService."""
    return MagicMock()


@pytest.fixture
def mock_provider():
    """Create mock ProviderProtocol."""
    return AsyncMock()


@pytest.fixture
def mock_event_bus():
    """Create mock EventBusProtocol."""
    return AsyncMock()


@pytest.fixture
def handler(
    mock_account_repo,
    mock_connection_repo,
    mock_holding_repo,
    mock_encryption_service,
    mock_provider,
    mock_event_bus,
):
    """Create SyncHoldingsHandler with mocks."""
    return SyncHoldingsHandler(
        account_repo=mock_account_repo,
        connection_repo=mock_connection_repo,
        holding_repo=mock_holding_repo,
        encryption_service=mock_encryption_service,
        provider=mock_provider,
        event_bus=mock_event_bus,
    )


@pytest.fixture
def user_id():
    """Fixed user ID for tests."""
    return uuid7()


@pytest.fixture
def account_id():
    """Fixed account ID for tests."""
    return uuid7()


# =============================================================================
# Account Validation Tests
# =============================================================================


@pytest.mark.unit
class TestAccountValidation:
    """Tests for account validation in SyncHoldingsHandler."""

    async def test_account_not_found_returns_failure(
        self, handler, mock_account_repo, user_id, account_id
    ):
        """Handle() returns failure when account doesn't exist."""
        mock_account_repo.find_by_id.return_value = None

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == SyncHoldingsError.ACCOUNT_NOT_FOUND

    async def test_connection_not_found_returns_failure(
        self, handler, mock_account_repo, mock_connection_repo, user_id, account_id
    ):
        """Handle() returns failure when connection doesn't exist."""
        account = create_mock_account(id=account_id)
        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = None

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == SyncHoldingsError.CONNECTION_NOT_FOUND

    async def test_not_owned_by_user_returns_failure(
        self, handler, mock_account_repo, mock_connection_repo, user_id, account_id
    ):
        """Handle() returns failure when user doesn't own the account."""
        other_user_id = uuid7()
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=other_user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == SyncHoldingsError.NOT_OWNED_BY_USER


# =============================================================================
# Connection Validation Tests
# =============================================================================


@pytest.mark.unit
class TestConnectionValidation:
    """Tests for connection validation in SyncHoldingsHandler."""

    async def test_connection_not_active_returns_failure(
        self, handler, mock_account_repo, mock_connection_repo, user_id, account_id
    ):
        """Handle() returns failure when connection is not active."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(
            id=connection_id,
            user_id=user_id,
            status=ConnectionStatus.DISCONNECTED,
        )

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == SyncHoldingsError.CONNECTION_NOT_ACTIVE

    async def test_no_credentials_returns_failure(
        self, handler, mock_account_repo, mock_connection_repo, user_id, account_id
    ):
        """Handle() returns failure when credentials are missing."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(
            id=connection_id,
            user_id=user_id,
            credentials=None,
        )

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == SyncHoldingsError.CREDENTIALS_INVALID


# =============================================================================
# Rate Limiting Tests
# =============================================================================


@pytest.mark.unit
class TestRateLimiting:
    """Tests for sync rate limiting in SyncHoldingsHandler."""

    async def test_recently_synced_without_force_returns_failure(
        self, handler, mock_account_repo, mock_connection_repo, user_id, account_id
    ):
        """Handle() returns failure when synced recently and force=False."""
        connection_id = uuid7()
        recent_sync = datetime.now(UTC) - timedelta(minutes=2)  # 2 minutes ago

        account = create_mock_account(
            id=account_id, connection_id=connection_id, last_synced_at=recent_sync
        )
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == SyncHoldingsError.RECENTLY_SYNCED

    async def test_recently_synced_with_force_proceeds(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        mock_provider,
        mock_holding_repo,
        user_id,
        account_id,
    ):
        """Handle() proceeds when synced recently but force=True."""
        connection_id = uuid7()
        recent_sync = datetime.now(UTC) - timedelta(minutes=2)

        account = create_mock_account(
            id=account_id, connection_id=connection_id, last_synced_at=recent_sync
        )
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Success(
            value={"access_token": "test_token"}
        )
        mock_provider.fetch_holdings.return_value = Success(value=[])
        mock_holding_repo.list_by_account.return_value = []

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=True)
        result = await handler.handle(command)

        assert isinstance(result, Success)

    async def test_old_sync_proceeds(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        mock_provider,
        mock_holding_repo,
        user_id,
        account_id,
    ):
        """Handle() proceeds when last sync was long ago."""
        connection_id = uuid7()
        old_sync = datetime.now(UTC) - timedelta(hours=1)  # 1 hour ago

        account = create_mock_account(
            id=account_id, connection_id=connection_id, last_synced_at=old_sync
        )
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Success(
            value={"access_token": "test_token"}
        )
        mock_provider.fetch_holdings.return_value = Success(value=[])
        mock_holding_repo.list_by_account.return_value = []

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Success)


# =============================================================================
# Credential Handling Tests
# =============================================================================


@pytest.mark.unit
class TestCredentialHandling:
    """Tests for credential decryption in SyncHoldingsHandler."""

    async def test_decryption_failure_returns_error(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        user_id,
        account_id,
    ):
        """Handle() returns failure when credential decryption fails."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Failure(
            error="Decryption failed"
        )

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == SyncHoldingsError.CREDENTIALS_DECRYPTION_FAILED

    async def test_missing_access_token_returns_error(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        user_id,
        account_id,
    ):
        """Handle() returns failure when decrypted data has no access_token."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Success(value={})  # No token

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert result.error == SyncHoldingsError.CREDENTIALS_INVALID


# =============================================================================
# Provider API Tests
# =============================================================================


@pytest.mark.unit
class TestProviderAPI:
    """Tests for provider API interaction in SyncHoldingsHandler."""

    async def test_provider_error_returns_failure(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        mock_provider,
        user_id,
        account_id,
    ):
        """Handle() returns failure when provider API fails."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Success(
            value={"access_token": "test_token"}
        )

        error_mock = MagicMock()
        error_mock.message = "API timeout"
        mock_provider.fetch_holdings.return_value = Failure(error=error_mock)

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Failure)
        assert SyncHoldingsError.PROVIDER_ERROR in result.error


# =============================================================================
# Sync Logic Tests
# =============================================================================


@pytest.mark.unit
class TestSyncLogic:
    """Tests for holdings sync logic in SyncHoldingsHandler."""

    async def test_creates_new_holdings(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        mock_provider,
        mock_holding_repo,
        user_id,
        account_id,
    ):
        """Handle() creates new holdings when they don't exist."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Success(
            value={"access_token": "test_token"}
        )

        provider_holding = create_provider_holding_data(
            provider_holding_id="NEW-HOLDING",
            symbol="AAPL",
        )
        mock_provider.fetch_holdings.return_value = Success(value=[provider_holding])
        mock_holding_repo.find_by_provider_holding_id.return_value = None
        mock_holding_repo.list_by_account.return_value = []

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Success)
        assert result.value.created == 1
        assert result.value.updated == 0
        mock_holding_repo.save.assert_called()

    async def test_updates_existing_holdings(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        mock_provider,
        mock_holding_repo,
        user_id,
        account_id,
    ):
        """Handle() updates existing holdings."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)
        existing_holding = create_mock_holding(
            account_id=account_id,
            provider_holding_id="EXISTING-HOLDING",
        )

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Success(
            value={"access_token": "test_token"}
        )

        provider_holding = create_provider_holding_data(
            provider_holding_id="EXISTING-HOLDING",
            symbol="AAPL",
        )
        mock_provider.fetch_holdings.return_value = Success(value=[provider_holding])
        mock_holding_repo.find_by_provider_holding_id.return_value = existing_holding
        mock_holding_repo.list_by_account.return_value = [existing_holding]

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Success)
        assert result.value.updated == 1
        assert result.value.created == 0

    async def test_deactivates_removed_holdings(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        mock_provider,
        mock_holding_repo,
        user_id,
        account_id,
    ):
        """Handle() deactivates holdings no longer in provider response."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)
        old_holding = create_mock_holding(
            account_id=account_id,
            provider_holding_id="OLD-HOLDING",
        )

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Success(
            value={"access_token": "test_token"}
        )

        # Provider returns empty list - old holding should be deactivated
        mock_provider.fetch_holdings.return_value = Success(value=[])
        mock_holding_repo.find_by_provider_holding_id.return_value = None
        mock_holding_repo.list_by_account.return_value = [old_holding]

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Success)
        assert result.value.deactivated == 1
        old_holding.deactivate.assert_called_once()

    async def test_updates_account_sync_timestamp(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        mock_provider,
        mock_holding_repo,
        user_id,
        account_id,
    ):
        """Handle() updates account's last_synced_at timestamp."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Success(
            value={"access_token": "test_token"}
        )
        mock_provider.fetch_holdings.return_value = Success(value=[])
        mock_holding_repo.list_by_account.return_value = []

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Success)
        account.mark_synced.assert_called_once()
        mock_account_repo.save.assert_called_with(account)


# =============================================================================
# Result Message Tests
# =============================================================================


@pytest.mark.unit
class TestResultMessages:
    """Tests for result message formatting in SyncHoldingsHandler."""

    async def test_message_includes_all_counts(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_encryption_service,
        mock_provider,
        mock_holding_repo,
        user_id,
        account_id,
    ):
        """Handle() result message includes all operation counts."""
        connection_id = uuid7()

        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_encryption_service.decrypt.return_value = Success(
            value={"access_token": "test_token"}
        )
        mock_provider.fetch_holdings.return_value = Success(value=[])
        mock_holding_repo.list_by_account.return_value = []

        command = SyncHoldings(account_id=account_id, user_id=user_id, force=False)
        result = await handler.handle(command)

        assert isinstance(result, Success)
        assert "Synced" in result.value.message
        assert "created" in result.value.message
        assert "updated" in result.value.message
        assert "unchanged" in result.value.message
