"""API tests for balance snapshots endpoints.

Tests the complete HTTP request/response cycle for balance tracking:
- GET /api/v1/balance-snapshots (latest snapshots for user)
- GET /api/v1/accounts/{id}/balance-history (history for account)
- GET /api/v1/accounts/{id}/balance-snapshots (list snapshots)

Architecture:
- Uses FastAPI TestClient with real app + dependency overrides
- Tests validation, authorization, and RFC 9457 error responses
- Mocks handlers to test HTTP layer behavior
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.application.queries.handlers.balance_snapshot_handlers import (
    GetBalanceHistoryHandler,
    GetLatestBalanceSnapshotsHandler,
    ListBalanceSnapshotsByAccountHandler,
)
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.main import app


# =============================================================================
# Test Doubles (matching actual application DTOs)
# =============================================================================


@dataclass
class MockSnapshotResult:
    """Mock DTO matching BalanceSnapshotResult from handlers."""

    id: UUID
    account_id: UUID
    balance: Decimal
    available_balance: Decimal | None
    holdings_value: Decimal | None
    cash_value: Decimal | None
    currency: str
    source: str
    captured_at: datetime
    created_at: datetime
    change_amount: Decimal | None = None
    change_percent: float | None = None


@dataclass
class MockLatestSnapshotsResult:
    """Mock result matching LatestSnapshotsResult from handlers."""

    snapshots: list[MockSnapshotResult]
    total_count: int
    total_balance_by_currency: dict[str, str]


@dataclass
class MockBalanceHistoryResult:
    """Mock result matching BalanceHistoryResult from handlers."""

    snapshots: list[MockSnapshotResult]
    total_count: int
    start_balance: Decimal | None
    end_balance: Decimal | None
    total_change_amount: Decimal | None
    total_change_percent: float | None
    currency: str | None


class MockGetLatestSnapshotsHandler:
    """Mock handler for getting latest snapshots."""

    def __init__(
        self,
        snapshots: list[MockSnapshotResult] | None = None,
        error: str | None = None,
    ) -> None:
        self._snapshots = snapshots or []
        self._error = error

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        # Build total balance by currency
        balances: dict[str, Decimal] = {}
        for s in self._snapshots:
            balances[s.currency] = balances.get(s.currency, Decimal("0")) + s.balance
        total_by_currency = {k: str(v) for k, v in balances.items()}

        result = MockLatestSnapshotsResult(
            snapshots=self._snapshots,
            total_count=len(self._snapshots),
            total_balance_by_currency=total_by_currency,
        )
        return Success(value=result)


class MockGetBalanceHistoryHandler:
    """Mock handler for getting balance history."""

    def __init__(
        self,
        snapshots: list[MockSnapshotResult] | None = None,
        error: str | None = None,
        account_id: UUID | None = None,
    ) -> None:
        self._snapshots = snapshots or []
        self._error = error
        self._account_id = account_id or uuid7()

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        values = [s.balance for s in self._snapshots] if self._snapshots else []
        start_bal = values[0] if values else None
        end_bal = values[-1] if values else None
        result = MockBalanceHistoryResult(
            snapshots=self._snapshots,
            total_count=len(self._snapshots),
            start_balance=start_bal,
            end_balance=end_bal,
            total_change_amount=Decimal("1000.00") if values else None,
            total_change_percent=5.0 if values else None,
            currency="USD" if self._snapshots else None,
        )
        return Success(value=result)


class MockListSnapshotsByAccountHandler:
    """Mock handler for listing snapshots by account."""

    def __init__(
        self,
        snapshots: list[MockSnapshotResult] | None = None,
        error: str | None = None,
        account_id: UUID | None = None,
    ) -> None:
        self._snapshots = snapshots or []
        self._error = error
        self._account_id = account_id or uuid7()

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        values = [s.balance for s in self._snapshots] if self._snapshots else []
        start_bal = values[0] if values else None
        end_bal = values[-1] if values else None
        result = MockBalanceHistoryResult(
            snapshots=self._snapshots,
            total_count=len(self._snapshots),
            start_balance=start_bal,
            end_balance=end_bal,
            total_change_amount=Decimal("1000.00") if values else None,
            total_change_percent=5.0 if values else None,
            currency="USD" if self._snapshots else None,
        )
        return Success(value=result)


# =============================================================================
# Authentication Mock
# =============================================================================


@dataclass
class MockCurrentUser:
    """Mock user for auth override."""

    user_id: UUID
    email: str = "test@example.com"
    roles: list[str] | None = None

    def __post_init__(self):
        if self.roles is None:
            self.roles = ["user"]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user_id():
    """Provide consistent user ID for tests."""
    return uuid7()


@pytest.fixture
def mock_account_id():
    """Provide consistent account ID for tests."""
    return uuid7()


@pytest.fixture
def mock_snapshot(mock_account_id):
    """Create a mock balance snapshot result."""
    now = datetime.now(UTC)
    return MockSnapshotResult(
        id=uuid7(),
        account_id=mock_account_id,
        balance=Decimal("50000.00"),
        available_balance=Decimal("48000.00"),
        holdings_value=Decimal("40000.00"),
        cash_value=Decimal("10000.00"),
        currency="USD",
        source="account_sync",
        captured_at=now - timedelta(hours=1),
        created_at=now - timedelta(hours=1),
    )


@pytest.fixture(autouse=True)
def override_auth(mock_user_id):
    """Override authentication for all tests."""
    from src.presentation.routers.api.middleware.auth_dependencies import (
        get_current_user,
    )

    mock_user = MockCurrentUser(user_id=mock_user_id)

    async def mock_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    """Provide test client."""
    return TestClient(app)


# =============================================================================
# Get Latest Snapshots Tests (GET /api/v1/balance-snapshots)
# =============================================================================


@pytest.mark.api
class TestGetLatestSnapshots:
    """Tests for GET /api/v1/balance-snapshots endpoint."""

    def test_get_latest_snapshots_empty(self, client):
        """GET /api/v1/balance-snapshots returns empty when no snapshots."""
        factory_key = handler_factory(GetLatestBalanceSnapshotsHandler)
        app.dependency_overrides[factory_key] = lambda: MockGetLatestSnapshotsHandler(
            snapshots=[]
        )

        response = client.get("/api/v1/balance-snapshots")

        assert response.status_code == 200
        data = response.json()
        assert data["snapshots"] == []
        assert data["total_count"] == 0

        app.dependency_overrides.pop(factory_key, None)

    def test_get_latest_snapshots_with_data(self, client, mock_snapshot):
        """GET /api/v1/balance-snapshots returns snapshots list."""
        factory_key = handler_factory(GetLatestBalanceSnapshotsHandler)
        app.dependency_overrides[factory_key] = lambda: MockGetLatestSnapshotsHandler(
            snapshots=[mock_snapshot]
        )

        response = client.get("/api/v1/balance-snapshots")

        assert response.status_code == 200
        data = response.json()
        assert len(data["snapshots"]) == 1
        assert data["total_count"] == 1

        app.dependency_overrides.pop(factory_key, None)


# =============================================================================
# Get Balance History Tests (GET /api/v1/accounts/{id}/balance-history)
# =============================================================================


@pytest.mark.api
class TestGetBalanceHistory:
    """Tests for GET /api/v1/accounts/{id}/balance-history endpoint."""

    def test_get_balance_history_success(self, client, mock_account_id, mock_snapshot):
        """GET /api/v1/accounts/{id}/balance-history returns history."""
        factory_key = handler_factory(GetBalanceHistoryHandler)
        app.dependency_overrides[factory_key] = lambda: MockGetBalanceHistoryHandler(
            snapshots=[mock_snapshot], account_id=mock_account_id
        )

        now = datetime.now(UTC)
        start = (now - timedelta(days=30)).isoformat()
        end = now.isoformat()

        response = client.get(
            f"/api/v1/accounts/{mock_account_id}/balance-history",
            params={"start_date": start, "end_date": end},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1

        app.dependency_overrides.pop(factory_key, None)

    def test_get_balance_history_account_not_found(self, client, mock_account_id):
        """GET /api/v1/accounts/{id}/balance-history returns 404."""
        factory_key = handler_factory(GetBalanceHistoryHandler)
        app.dependency_overrides[factory_key] = lambda: MockGetBalanceHistoryHandler(
            error="Account not found"
        )

        now = datetime.now(UTC)
        start = (now - timedelta(days=30)).isoformat()
        end = now.isoformat()

        response = client.get(
            f"/api/v1/accounts/{mock_account_id}/balance-history",
            params={"start_date": start, "end_date": end},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(factory_key, None)

    def test_get_balance_history_forbidden(self, client, mock_account_id):
        """GET /api/v1/accounts/{id}/balance-history returns 403."""
        factory_key = handler_factory(GetBalanceHistoryHandler)
        app.dependency_overrides[factory_key] = lambda: MockGetBalanceHistoryHandler(
            error="Account not owned by user"
        )

        now = datetime.now(UTC)
        start = (now - timedelta(days=30)).isoformat()
        end = now.isoformat()

        response = client.get(
            f"/api/v1/accounts/{mock_account_id}/balance-history",
            params={"start_date": start, "end_date": end},
        )

        assert response.status_code == 403

        app.dependency_overrides.pop(factory_key, None)

    def test_get_balance_history_invalid_date_range(self, client, mock_account_id):
        """GET /api/v1/accounts/{id}/balance-history returns 400 for invalid range."""
        factory_key = handler_factory(GetBalanceHistoryHandler)
        app.dependency_overrides[factory_key] = lambda: MockGetBalanceHistoryHandler(
            error="Invalid date range: end must be after start"
        )

        now = datetime.now(UTC)
        # Invalid: start > end
        start = now.isoformat()
        end = (now - timedelta(days=30)).isoformat()

        response = client.get(
            f"/api/v1/accounts/{mock_account_id}/balance-history",
            params={"start_date": start, "end_date": end},
        )

        assert response.status_code == 400

        app.dependency_overrides.pop(factory_key, None)

    def test_get_balance_history_with_source_filter(
        self, client, mock_account_id, mock_snapshot
    ):
        """GET /api/v1/accounts/{id}/balance-history with source filter."""
        factory_key = handler_factory(GetBalanceHistoryHandler)
        app.dependency_overrides[factory_key] = lambda: MockGetBalanceHistoryHandler(
            snapshots=[mock_snapshot], account_id=mock_account_id
        )

        now = datetime.now(UTC)
        start = (now - timedelta(days=30)).isoformat()
        end = now.isoformat()

        response = client.get(
            f"/api/v1/accounts/{mock_account_id}/balance-history",
            params={"start_date": start, "end_date": end, "source": "account_sync"},
        )

        assert response.status_code == 200

        app.dependency_overrides.pop(factory_key, None)


# =============================================================================
# List Balance Snapshots Tests (GET /api/v1/accounts/{id}/balance-snapshots)
# =============================================================================


@pytest.mark.api
class TestListBalanceSnapshots:
    """Tests for GET /api/v1/accounts/{id}/balance-snapshots endpoint."""

    def test_list_balance_snapshots_success(
        self, client, mock_account_id, mock_snapshot
    ):
        """GET /api/v1/accounts/{id}/balance-snapshots returns list."""
        factory_key = handler_factory(ListBalanceSnapshotsByAccountHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockListSnapshotsByAccountHandler(
                snapshots=[mock_snapshot], account_id=mock_account_id
            )
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}/balance-snapshots")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1

        app.dependency_overrides.pop(factory_key, None)

    def test_list_balance_snapshots_with_limit(
        self, client, mock_account_id, mock_snapshot
    ):
        """GET /api/v1/accounts/{id}/balance-snapshots with limit."""
        factory_key = handler_factory(ListBalanceSnapshotsByAccountHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockListSnapshotsByAccountHandler(
                snapshots=[mock_snapshot], account_id=mock_account_id
            )
        )

        response = client.get(
            f"/api/v1/accounts/{mock_account_id}/balance-snapshots",
            params={"limit": 10},
        )

        assert response.status_code == 200

        app.dependency_overrides.pop(factory_key, None)

    def test_list_balance_snapshots_account_not_found(self, client, mock_account_id):
        """GET /api/v1/accounts/{id}/balance-snapshots returns 404."""
        factory_key = handler_factory(ListBalanceSnapshotsByAccountHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockListSnapshotsByAccountHandler(error="Account not found")
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}/balance-snapshots")

        assert response.status_code == 404

        app.dependency_overrides.pop(factory_key, None)

    def test_list_balance_snapshots_forbidden(self, client, mock_account_id):
        """GET /api/v1/accounts/{id}/balance-snapshots returns 403."""
        factory_key = handler_factory(ListBalanceSnapshotsByAccountHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockListSnapshotsByAccountHandler(error="Account not owned by user")
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}/balance-snapshots")

        assert response.status_code == 403

        app.dependency_overrides.pop(factory_key, None)
