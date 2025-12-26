"""Unit tests for balance snapshot query handlers.

Tests GetBalanceHistoryHandler, ListBalanceSnapshotsByAccountHandler,
and GetLatestBalanceSnapshotsHandler.

Architecture:
- Tests query validation and error handling
- Tests ownership verification
- Tests DTO building and aggregation
- Uses mock repositories
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from src.application.queries.balance_snapshot_queries import (
    GetBalanceHistory,
    GetLatestBalanceSnapshots,
    ListBalanceSnapshotsByAccount,
)
from src.application.queries.handlers.balance_snapshot_handlers import (
    BalanceSnapshotQueryError,
    GetBalanceHistoryHandler,
    GetLatestBalanceSnapshotsHandler,
    ListBalanceSnapshotsByAccountHandler,
)
from src.core.result import Failure, Success
from src.domain.entities.account import Account
from src.domain.entities.balance_snapshot import BalanceSnapshot
from src.domain.entities.provider_connection import ProviderConnection
from src.domain.enums.snapshot_source import SnapshotSource
from src.domain.value_objects.money import Money


# =============================================================================
# Mock Factories
# =============================================================================


def create_mock_account(
    id: UUID | None = None,
    connection_id: UUID | None = None,
) -> MagicMock:
    """Create a mock Account entity."""
    mock = MagicMock(spec=Account)
    mock.id = id or uuid7()
    mock.connection_id = connection_id or uuid7()
    return mock


def create_mock_connection(
    id: UUID | None = None,
    user_id: UUID | None = None,
) -> MagicMock:
    """Create a mock ProviderConnection entity."""
    mock = MagicMock(spec=ProviderConnection)
    mock.id = id or uuid7()
    mock.user_id = user_id or uuid7()
    return mock


def create_mock_snapshot(
    id: UUID | None = None,
    account_id: UUID | None = None,
    balance: Decimal = Decimal("50000.00"),
    currency: str = "USD",
    captured_at: datetime | None = None,
) -> MagicMock:
    """Create a mock BalanceSnapshot entity."""
    mock = MagicMock(spec=BalanceSnapshot)
    mock.id = id or uuid7()
    mock.account_id = account_id or uuid7()
    mock.balance = Money(amount=balance, currency=currency)
    mock.available_balance = Money(amount=balance - Decimal("2000"), currency=currency)
    mock.holdings_value = Money(amount=Decimal("40000"), currency=currency)
    mock.cash_value = Money(amount=Decimal("10000"), currency=currency)
    mock.currency = currency
    mock.source = SnapshotSource.ACCOUNT_SYNC
    mock.captured_at = captured_at or datetime.now(UTC)
    mock.created_at = datetime.now(UTC)
    mock.calculate_change_from.return_value = None
    return mock


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_snapshot_repo():
    """Create mock BalanceSnapshotRepository."""
    return AsyncMock()


@pytest.fixture
def mock_account_repo():
    """Create mock AccountRepository."""
    return AsyncMock()


@pytest.fixture
def mock_connection_repo():
    """Create mock ProviderConnectionRepository."""
    return AsyncMock()


@pytest.fixture
def user_id():
    """Fixed user ID for tests."""
    return uuid7()


@pytest.fixture
def account_id():
    """Fixed account ID for tests."""
    return uuid7()


# =============================================================================
# GetBalanceHistoryHandler Tests
# =============================================================================


@pytest.mark.unit
class TestGetBalanceHistoryHandler:
    """Tests for GetBalanceHistoryHandler."""

    @pytest.fixture
    def handler(self, mock_snapshot_repo, mock_account_repo, mock_connection_repo):
        """Create handler with mocks."""
        return GetBalanceHistoryHandler(
            snapshot_repo=mock_snapshot_repo,
            account_repo=mock_account_repo,
            connection_repo=mock_connection_repo,
        )

    async def test_invalid_date_range_returns_failure(
        self, handler, user_id, account_id
    ):
        """Handle() returns failure when start_date >= end_date."""
        now = datetime.now(UTC)
        query = GetBalanceHistory(
            account_id=account_id,
            user_id=user_id,
            start_date=now,  # Same as end
            end_date=now,
        )
        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == BalanceSnapshotQueryError.INVALID_DATE_RANGE

    async def test_invalid_source_returns_failure(
        self, handler, mock_account_repo, mock_connection_repo, user_id, account_id
    ):
        """Handle() returns failure for invalid source filter."""
        connection_id = uuid7()
        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection

        now = datetime.now(UTC)
        query = GetBalanceHistory(
            account_id=account_id,
            user_id=user_id,
            start_date=now - timedelta(days=30),
            end_date=now,
            source="invalid_source",
        )
        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == BalanceSnapshotQueryError.INVALID_SOURCE

    async def test_account_not_found_returns_failure(
        self, handler, mock_account_repo, user_id, account_id
    ):
        """Handle() returns failure when account doesn't exist."""
        mock_account_repo.find_by_id.return_value = None

        now = datetime.now(UTC)
        query = GetBalanceHistory(
            account_id=account_id,
            user_id=user_id,
            start_date=now - timedelta(days=30),
            end_date=now,
        )
        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == BalanceSnapshotQueryError.ACCOUNT_NOT_FOUND

    async def test_connection_not_found_returns_failure(
        self, handler, mock_account_repo, mock_connection_repo, user_id, account_id
    ):
        """Handle() returns failure when connection doesn't exist."""
        account = create_mock_account(id=account_id)
        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = None

        now = datetime.now(UTC)
        query = GetBalanceHistory(
            account_id=account_id,
            user_id=user_id,
            start_date=now - timedelta(days=30),
            end_date=now,
        )
        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == BalanceSnapshotQueryError.CONNECTION_NOT_FOUND

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

        now = datetime.now(UTC)
        query = GetBalanceHistory(
            account_id=account_id,
            user_id=user_id,
            start_date=now - timedelta(days=30),
            end_date=now,
        )
        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == BalanceSnapshotQueryError.NOT_OWNED_BY_USER

    async def test_success_returns_history_result(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_snapshot_repo,
        user_id,
        account_id,
    ):
        """Handle() returns success with history result."""
        connection_id = uuid7()
        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)
        snapshot = create_mock_snapshot(account_id=account_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_snapshot_repo.find_by_account_id_in_range.return_value = [snapshot]

        now = datetime.now(UTC)
        query = GetBalanceHistory(
            account_id=account_id,
            user_id=user_id,
            start_date=now - timedelta(days=30),
            end_date=now,
        )
        result = await handler.handle(query)

        assert isinstance(result, Success)
        assert result.value.total_count == 1
        assert len(result.value.snapshots) == 1

    async def test_empty_result_returns_empty_history(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_snapshot_repo,
        user_id,
        account_id,
    ):
        """Handle() returns empty history when no snapshots found."""
        connection_id = uuid7()
        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_snapshot_repo.find_by_account_id_in_range.return_value = []

        now = datetime.now(UTC)
        query = GetBalanceHistory(
            account_id=account_id,
            user_id=user_id,
            start_date=now - timedelta(days=30),
            end_date=now,
        )
        result = await handler.handle(query)

        assert isinstance(result, Success)
        assert result.value.total_count == 0
        assert result.value.start_balance is None
        assert result.value.end_balance is None


# =============================================================================
# ListBalanceSnapshotsByAccountHandler Tests
# =============================================================================


@pytest.mark.unit
class TestListBalanceSnapshotsByAccountHandler:
    """Tests for ListBalanceSnapshotsByAccountHandler."""

    @pytest.fixture
    def handler(self, mock_snapshot_repo, mock_account_repo, mock_connection_repo):
        """Create handler with mocks."""
        return ListBalanceSnapshotsByAccountHandler(
            snapshot_repo=mock_snapshot_repo,
            account_repo=mock_account_repo,
            connection_repo=mock_connection_repo,
        )

    async def test_account_not_found_returns_failure(
        self, handler, mock_account_repo, user_id, account_id
    ):
        """Handle() returns failure when account doesn't exist."""
        mock_account_repo.find_by_id.return_value = None

        query = ListBalanceSnapshotsByAccount(
            account_id=account_id,
            user_id=user_id,
            limit=30,
        )
        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == BalanceSnapshotQueryError.ACCOUNT_NOT_FOUND

    async def test_connection_not_found_returns_failure(
        self, handler, mock_account_repo, mock_connection_repo, user_id, account_id
    ):
        """Handle() returns failure when connection doesn't exist."""
        account = create_mock_account(id=account_id)
        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = None

        query = ListBalanceSnapshotsByAccount(
            account_id=account_id,
            user_id=user_id,
            limit=30,
        )
        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == BalanceSnapshotQueryError.CONNECTION_NOT_FOUND

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

        query = ListBalanceSnapshotsByAccount(
            account_id=account_id,
            user_id=user_id,
            limit=30,
        )
        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == BalanceSnapshotQueryError.NOT_OWNED_BY_USER

    async def test_invalid_source_returns_failure(self, handler, user_id, account_id):
        """Handle() returns failure for invalid source filter."""
        query = ListBalanceSnapshotsByAccount(
            account_id=account_id,
            user_id=user_id,
            limit=30,
            source="invalid_source",
        )
        result = await handler.handle(query)

        assert isinstance(result, Failure)
        assert result.error == BalanceSnapshotQueryError.INVALID_SOURCE

    async def test_success_returns_snapshot_list(
        self,
        handler,
        mock_account_repo,
        mock_connection_repo,
        mock_snapshot_repo,
        user_id,
        account_id,
    ):
        """Handle() returns success with snapshot list."""
        connection_id = uuid7()
        account = create_mock_account(id=account_id, connection_id=connection_id)
        connection = create_mock_connection(id=connection_id, user_id=user_id)
        snapshot = create_mock_snapshot(account_id=account_id)

        mock_account_repo.find_by_id.return_value = account
        mock_connection_repo.find_by_id.return_value = connection
        mock_snapshot_repo.find_by_account_id.return_value = [snapshot]

        query = ListBalanceSnapshotsByAccount(
            account_id=account_id,
            user_id=user_id,
            limit=30,
        )
        result = await handler.handle(query)

        assert isinstance(result, Success)
        assert result.value.total_count == 1
        assert len(result.value.snapshots) == 1


# =============================================================================
# GetLatestBalanceSnapshotsHandler Tests
# =============================================================================


@pytest.mark.unit
class TestGetLatestBalanceSnapshotsHandler:
    """Tests for GetLatestBalanceSnapshotsHandler."""

    @pytest.fixture
    def handler(self, mock_snapshot_repo):
        """Create handler with mocks."""
        return GetLatestBalanceSnapshotsHandler(snapshot_repo=mock_snapshot_repo)

    async def test_returns_empty_when_no_snapshots(
        self, handler, mock_snapshot_repo, user_id
    ):
        """Handle() returns empty result when no snapshots exist."""
        mock_snapshot_repo.find_latest_by_user_id.return_value = []

        query = GetLatestBalanceSnapshots(user_id=user_id)
        result = await handler.handle(query)

        assert isinstance(result, Success)
        assert result.value.total_count == 0
        assert result.value.snapshots == []
        assert result.value.total_balance_by_currency == {}

    async def test_returns_latest_snapshots(self, handler, mock_snapshot_repo, user_id):
        """Handle() returns latest snapshot for each account."""
        snapshot1 = create_mock_snapshot(balance=Decimal("50000.00"), currency="USD")
        snapshot2 = create_mock_snapshot(balance=Decimal("30000.00"), currency="USD")

        mock_snapshot_repo.find_latest_by_user_id.return_value = [snapshot1, snapshot2]

        query = GetLatestBalanceSnapshots(user_id=user_id)
        result = await handler.handle(query)

        assert isinstance(result, Success)
        assert result.value.total_count == 2
        assert len(result.value.snapshots) == 2

    async def test_aggregates_balance_by_currency(
        self, handler, mock_snapshot_repo, user_id
    ):
        """Handle() aggregates balances by currency."""
        snapshot_usd1 = create_mock_snapshot(
            balance=Decimal("50000.00"), currency="USD"
        )
        snapshot_usd2 = create_mock_snapshot(
            balance=Decimal("30000.00"), currency="USD"
        )
        snapshot_eur = create_mock_snapshot(balance=Decimal("20000.00"), currency="EUR")

        mock_snapshot_repo.find_latest_by_user_id.return_value = [
            snapshot_usd1,
            snapshot_usd2,
            snapshot_eur,
        ]

        query = GetLatestBalanceSnapshots(user_id=user_id)
        result = await handler.handle(query)

        assert isinstance(result, Success)
        assert result.value.total_count == 3
        assert "USD" in result.value.total_balance_by_currency
        assert "EUR" in result.value.total_balance_by_currency
        # USD: 50000 + 30000 = 80000
        assert result.value.total_balance_by_currency["USD"] == "80000.00"
        # EUR: 20000
        assert result.value.total_balance_by_currency["EUR"] == "20000.00"

    async def test_converts_snapshots_to_dtos(
        self, handler, mock_snapshot_repo, user_id
    ):
        """Handle() converts snapshot entities to DTOs."""
        account_id = uuid7()
        snapshot = create_mock_snapshot(
            account_id=account_id,
            balance=Decimal("50000.00"),
            currency="USD",
        )

        mock_snapshot_repo.find_latest_by_user_id.return_value = [snapshot]

        query = GetLatestBalanceSnapshots(user_id=user_id)
        result = await handler.handle(query)

        assert isinstance(result, Success)
        dto = result.value.snapshots[0]
        assert dto.account_id == account_id
        assert dto.balance == Decimal("50000.00")
        assert dto.currency == "USD"
