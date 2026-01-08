"""API tests for holdings endpoints.

Tests the complete HTTP request/response cycle for holdings management:
- GET /api/v1/holdings (list all user holdings)
- GET /api/v1/accounts/{id}/holdings (list holdings for account)
- POST /api/v1/accounts/{id}/holdings/syncs (sync holdings from provider)

Architecture:
- Uses FastAPI TestClient with real app + dependency overrides
- Tests validation, authorization, and RFC 7807 error responses
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

from src.core.result import Failure, Success
from src.main import app


# =============================================================================
# Test Doubles (matching actual application DTOs)
# =============================================================================


@dataclass(frozen=True, kw_only=True)
class MockHoldingResult:
    """Mock DTO matching HoldingResult from list_holdings_handler.py."""

    id: UUID
    account_id: UUID
    provider_holding_id: str
    symbol: str
    security_name: str
    asset_type: str
    quantity: Decimal
    cost_basis: Decimal
    market_value: Decimal
    currency: str
    average_price: Decimal | None
    current_price: Decimal | None
    unrealized_gain_loss: Decimal | None
    unrealized_gain_loss_percent: Decimal | None
    is_active: bool
    is_profitable: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class MockHoldingListResult:
    """Mock result matching HoldingListResult from list_holdings_handler.py."""

    holdings: list[MockHoldingResult]
    total_count: int
    active_count: int
    total_market_value_by_currency: dict[str, str]
    total_cost_basis_by_currency: dict[str, str]
    total_unrealized_gain_loss_by_currency: dict[str, str]


@dataclass
class MockSyncHoldingsResult:
    """Mock result matching SyncHoldingsResult from sync_holdings_handler.py."""

    created: int
    updated: int
    unchanged: int
    deactivated: int
    errors: int
    message: str


class MockListHoldingsHandler:
    """Mock handler for listing holdings."""

    def __init__(
        self,
        holdings: list[MockHoldingResult] | None = None,
        error: str | None = None,
    ) -> None:
        self._holdings = holdings or []
        self._error = error

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        result = MockHoldingListResult(
            holdings=self._holdings,
            total_count=len(self._holdings),
            active_count=sum(1 for h in self._holdings if h.is_active),
            total_market_value_by_currency={"USD": "35000.00"}
            if self._holdings
            else {},
            total_cost_basis_by_currency={"USD": "31000.00"} if self._holdings else {},
            total_unrealized_gain_loss_by_currency=(
                {"USD": "4000.00"} if self._holdings else {}
            ),
        )
        return Success(value=result)


class MockSyncHoldingsHandler:
    """Mock handler for syncing holdings."""

    def __init__(
        self,
        result: MockSyncHoldingsResult | None = None,
        error: str | None = None,
    ) -> None:
        self._result = result or MockSyncHoldingsResult(
            created=3,
            updated=2,
            unchanged=1,
            deactivated=0,
            errors=0,
            message="Synced 6 holdings: 3 created, 2 updated, 1 unchanged",
        )
        self._error = error

    async def handle(self, command: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        return Success(value=self._result)


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
def mock_holding(mock_account_id):
    """Create a mock holding result."""
    now = datetime.now(UTC)
    return MockHoldingResult(
        id=uuid7(),
        account_id=mock_account_id,
        provider_holding_id="SCHWAB-AAPL-123",
        symbol="AAPL",
        security_name="Apple Inc.",
        asset_type="equity",
        quantity=Decimal("100"),
        cost_basis=Decimal("15000.00"),
        market_value=Decimal("17500.00"),
        currency="USD",
        average_price=Decimal("150.00"),
        current_price=Decimal("175.00"),
        unrealized_gain_loss=Decimal("2500.00"),
        unrealized_gain_loss_percent=Decimal("16.67"),
        is_active=True,
        is_profitable=True,
        last_synced_at=now - timedelta(hours=1),
        created_at=now - timedelta(days=30),
        updated_at=now,
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
# List Holdings Tests (GET /api/v1/holdings)
# =============================================================================


@pytest.mark.api
class TestListHoldings:
    """Tests for GET /api/v1/holdings endpoint."""

    def test_list_holdings_returns_empty_list(self, client):
        """GET /api/v1/holdings returns empty list when no holdings."""
        from src.core.container import get_list_holdings_by_user_handler

        app.dependency_overrides[get_list_holdings_by_user_handler] = (
            lambda: MockListHoldingsHandler(holdings=[])
        )

        response = client.get("/api/v1/holdings")

        assert response.status_code == 200
        data = response.json()
        assert data["holdings"] == []
        assert data["total_count"] == 0

        app.dependency_overrides.pop(get_list_holdings_by_user_handler, None)

    def test_list_holdings_returns_holdings(self, client, mock_holding):
        """GET /api/v1/holdings returns holdings list."""
        from src.core.container import get_list_holdings_by_user_handler

        app.dependency_overrides[get_list_holdings_by_user_handler] = (
            lambda: MockListHoldingsHandler(holdings=[mock_holding])
        )

        response = client.get("/api/v1/holdings")

        assert response.status_code == 200
        data = response.json()
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["symbol"] == "AAPL"
        assert data["total_count"] == 1

        app.dependency_overrides.pop(get_list_holdings_by_user_handler, None)

    def test_list_holdings_with_filters(self, client, mock_holding):
        """GET /api/v1/holdings accepts filter parameters."""
        from src.core.container import get_list_holdings_by_user_handler

        app.dependency_overrides[get_list_holdings_by_user_handler] = (
            lambda: MockListHoldingsHandler(holdings=[mock_holding])
        )

        response = client.get("/api/v1/holdings?active_only=true&asset_type=equity")

        assert response.status_code == 200

        app.dependency_overrides.pop(get_list_holdings_by_user_handler, None)


# =============================================================================
# List Holdings by Account Tests (GET /api/v1/accounts/{id}/holdings)
# =============================================================================


@pytest.mark.api
class TestListHoldingsByAccount:
    """Tests for GET /api/v1/accounts/{id}/holdings endpoint."""

    def test_list_holdings_by_account_success(
        self, client, mock_account_id, mock_holding
    ):
        """GET /api/v1/accounts/{id}/holdings returns holdings."""
        from src.core.container import get_list_holdings_by_account_handler

        app.dependency_overrides[get_list_holdings_by_account_handler] = (
            lambda: MockListHoldingsHandler(holdings=[mock_holding])
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}/holdings")

        assert response.status_code == 200
        data = response.json()
        assert len(data["holdings"]) == 1
        assert data["total_count"] == 1

        app.dependency_overrides.pop(get_list_holdings_by_account_handler, None)

    def test_list_holdings_account_not_found(self, client, mock_account_id):
        """GET /api/v1/accounts/{id}/holdings returns 404 when not found."""
        from src.core.container import get_list_holdings_by_account_handler

        app.dependency_overrides[get_list_holdings_by_account_handler] = (
            lambda: MockListHoldingsHandler(error="Account not found")
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}/holdings")

        assert response.status_code == 404
        data = response.json()
        assert "not_found" in data["type"]

        app.dependency_overrides.pop(get_list_holdings_by_account_handler, None)

    def test_list_holdings_forbidden(self, client, mock_account_id):
        """GET /api/v1/accounts/{id}/holdings returns 403 when not owned."""
        from src.core.container import get_list_holdings_by_account_handler

        app.dependency_overrides[get_list_holdings_by_account_handler] = (
            lambda: MockListHoldingsHandler(error="Account not owned by user")
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}/holdings")

        assert response.status_code == 403

        app.dependency_overrides.pop(get_list_holdings_by_account_handler, None)


# =============================================================================
# Sync Holdings Tests (POST /api/v1/accounts/{id}/holdings/syncs)
# =============================================================================


@pytest.mark.api
class TestSyncHoldings:
    """Tests for POST /api/v1/accounts/{id}/holdings/syncs endpoint."""

    def test_sync_holdings_success(self, client, mock_account_id):
        """POST /api/v1/accounts/{id}/holdings/syncs syncs holdings."""
        from src.core.container import get_sync_holdings_handler

        app.dependency_overrides[get_sync_holdings_handler] = (
            lambda: MockSyncHoldingsHandler()
        )

        response = client.post(
            f"/api/v1/accounts/{mock_account_id}/holdings/syncs",
            json={"force": False},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 3
        assert data["updated"] == 2
        assert "message" in data

        app.dependency_overrides.pop(get_sync_holdings_handler, None)

    def test_sync_holdings_force(self, client, mock_account_id):
        """POST /api/v1/accounts/{id}/holdings/syncs with force=true."""
        from src.core.container import get_sync_holdings_handler

        app.dependency_overrides[get_sync_holdings_handler] = (
            lambda: MockSyncHoldingsHandler()
        )

        response = client.post(
            f"/api/v1/accounts/{mock_account_id}/holdings/syncs",
            json={"force": True},
        )

        assert response.status_code == 201

        app.dependency_overrides.pop(get_sync_holdings_handler, None)

    def test_sync_holdings_account_not_found(self, client, mock_account_id):
        """POST /api/v1/accounts/{id}/holdings/syncs returns 404."""
        from src.core.container import get_sync_holdings_handler

        app.dependency_overrides[get_sync_holdings_handler] = (
            lambda: MockSyncHoldingsHandler(error="Account not found")
        )

        response = client.post(
            f"/api/v1/accounts/{mock_account_id}/holdings/syncs",
            json={"force": False},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_sync_holdings_handler, None)

    def test_sync_holdings_rate_limited(self, client, mock_account_id):
        """POST /api/v1/accounts/{id}/holdings/syncs returns 429 when too soon."""
        from src.core.container import get_sync_holdings_handler

        app.dependency_overrides[get_sync_holdings_handler] = (
            lambda: MockSyncHoldingsHandler(error="Holdings were recently synced")
        )

        response = client.post(
            f"/api/v1/accounts/{mock_account_id}/holdings/syncs",
            json={"force": False},
        )

        assert response.status_code == 429

        app.dependency_overrides.pop(get_sync_holdings_handler, None)

    def test_sync_holdings_provider_error(self, client, mock_account_id):
        """POST /api/v1/accounts/{id}/holdings/syncs returns 502 on provider error."""
        from src.core.container import get_sync_holdings_handler

        app.dependency_overrides[get_sync_holdings_handler] = (
            lambda: MockSyncHoldingsHandler(error="Provider API error: timeout")
        )

        response = client.post(
            f"/api/v1/accounts/{mock_account_id}/holdings/syncs",
            json={"force": False},
        )

        # Provider errors should map to external service error (502)
        assert response.status_code == 502

        app.dependency_overrides.pop(get_sync_holdings_handler, None)
