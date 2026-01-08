"""API tests for transaction endpoints.

Tests the complete HTTP request/response cycle for transaction management:
- GET /api/v1/transactions/{id} (get transaction details)
- POST /api/v1/transactions/syncs (sync transactions from providers)
- GET /api/v1/accounts/{id}/transactions (list transactions for account)

Architecture:
- Uses FastAPI TestClient with real app + dependency overrides
- Tests validation, authorization, and RFC 7807 error responses
- Mocks handlers to test HTTP layer behavior
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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
class MockTransactionResult:
    """Mock DTO matching TransactionResult from get_transaction_handler.py."""

    id: UUID
    account_id: UUID
    provider_transaction_id: str
    transaction_type: str
    subtype: str
    status: str
    amount_value: Decimal
    amount_currency: str
    description: str
    asset_type: str | None
    symbol: str | None
    security_name: str | None
    quantity: Decimal | None
    unit_price_amount: Decimal | None
    unit_price_currency: str | None
    commission_amount: Decimal | None
    commission_currency: str | None
    transaction_date: date
    settlement_date: date | None
    is_trade: bool
    is_transfer: bool
    is_income: bool
    is_fee: bool
    is_debit: bool
    is_credit: bool
    is_settled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class MockTransactionListResult:
    """Mock result for transaction list queries."""

    transactions: list[MockTransactionResult]
    total_count: int
    has_more: bool


@dataclass
class MockSyncTransactionsResult:
    """Mock result matching SyncTransactionsResult from sync_transactions_handler.py."""

    created: int
    updated: int
    unchanged: int
    errors: int
    accounts_synced: int
    message: str


class MockGetTransactionHandler:
    """Mock handler for getting a single transaction."""

    def __init__(
        self,
        transaction: MockTransactionResult | None = None,
        error: str | None = None,
    ) -> None:
        self._transaction = transaction
        self._error = error

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        return Success(value=self._transaction)


class MockListTransactionsHandler:
    """Mock handler for listing transactions."""

    def __init__(
        self,
        result: MockTransactionListResult | None = None,
        error: str | None = None,
    ) -> None:
        self._result = result or MockTransactionListResult(
            transactions=[],
            total_count=0,
            has_more=False,
        )
        self._error = error

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        return Success(value=self._result)


class MockSyncTransactionsHandler:
    """Mock handler for syncing transactions."""

    def __init__(
        self,
        result: MockSyncTransactionsResult | None = None,
        error: str | None = None,
    ) -> None:
        self._result = result or MockSyncTransactionsResult(
            created=25,
            updated=25,
            unchanged=0,
            errors=0,
            accounts_synced=1,
            message="Synced 50 transactions: 25 created, 25 updated",
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
def mock_transaction_id():
    """Provide consistent transaction ID for tests."""
    return uuid7()


@pytest.fixture
def mock_account_id():
    """Provide consistent account ID for tests."""
    return uuid7()


@pytest.fixture
def mock_connection_id():
    """Provide consistent connection ID for tests."""
    return uuid7()


@pytest.fixture
def mock_transaction(mock_transaction_id, mock_account_id):
    """Create a mock transaction result."""
    now = datetime.now(UTC)
    today = date.today()
    return MockTransactionResult(
        id=mock_transaction_id,
        account_id=mock_account_id,
        provider_transaction_id="TXN-123456789",
        transaction_type="trade",
        subtype="buy",
        status="settled",
        amount_value=Decimal("-1500.00"),
        amount_currency="USD",
        description="BUY AAPL @ 150.00",
        asset_type="equity",
        symbol="AAPL",
        security_name="Apple Inc.",
        quantity=Decimal("10"),
        unit_price_amount=Decimal("150.00"),
        unit_price_currency="USD",
        commission_amount=Decimal("0.00"),
        commission_currency="USD",
        transaction_date=today - timedelta(days=1),
        settlement_date=today,
        is_trade=True,
        is_transfer=False,
        is_income=False,
        is_fee=False,
        is_debit=True,
        is_credit=False,
        is_settled=True,
        created_at=now - timedelta(hours=12),
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
# Get Transaction Tests (GET /api/v1/transactions/{id})
# =============================================================================


@pytest.mark.api
class TestGetTransaction:
    """Tests for GET /api/v1/transactions/{id} endpoint."""

    def test_get_transaction_returns_details(
        self, client, mock_transaction_id, mock_transaction
    ):
        """GET /api/v1/transactions/{id} returns transaction details."""
        from src.core.container import get_get_transaction_handler

        app.dependency_overrides[get_get_transaction_handler] = (
            lambda: MockGetTransactionHandler(transaction=mock_transaction)
        )

        response = client.get(f"/api/v1/transactions/{mock_transaction_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(mock_transaction_id)
        assert data["transaction_type"] == "trade"
        assert data["symbol"] == "AAPL"

        app.dependency_overrides.pop(get_get_transaction_handler, None)

    def test_get_transaction_not_found(self, client, mock_transaction_id):
        """GET /api/v1/transactions/{id} returns 404 when not found."""
        from src.core.container import get_get_transaction_handler

        app.dependency_overrides[get_get_transaction_handler] = (
            lambda: MockGetTransactionHandler(error="Transaction not found")
        )

        response = client.get(f"/api/v1/transactions/{mock_transaction_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == 404

        app.dependency_overrides.pop(get_get_transaction_handler, None)

    def test_get_transaction_forbidden(self, client, mock_transaction_id):
        """GET /api/v1/transactions/{id} returns 403 when not owned by user."""
        from src.core.container import get_get_transaction_handler

        app.dependency_overrides[get_get_transaction_handler] = (
            lambda: MockGetTransactionHandler(error="Transaction not owned by user")
        )

        response = client.get(f"/api/v1/transactions/{mock_transaction_id}")

        assert response.status_code == 403

        app.dependency_overrides.pop(get_get_transaction_handler, None)

    def test_get_transaction_invalid_uuid(self, client):
        """GET /api/v1/transactions/{id} returns 422 for invalid UUID."""
        response = client.get("/api/v1/transactions/not-a-uuid")

        assert response.status_code == 422


# =============================================================================
# Sync Transactions Tests (POST /api/v1/transactions/syncs)
# =============================================================================


@pytest.mark.api
class TestSyncTransactions:
    """Tests for POST /api/v1/transactions/syncs endpoint."""

    def test_sync_transactions_success(self, client, mock_connection_id):
        """POST /api/v1/transactions/syncs triggers transaction sync."""
        from src.core.container import get_sync_transactions_handler

        app.dependency_overrides[get_sync_transactions_handler] = (
            lambda: MockSyncTransactionsHandler()
        )

        response = client.post(
            "/api/v1/transactions/syncs",
            json={"connection_id": str(mock_connection_id)},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 25
        assert data["updated"] == 25

        app.dependency_overrides.pop(get_sync_transactions_handler, None)

    def test_sync_transactions_connection_not_found(self, client, mock_connection_id):
        """POST /api/v1/transactions/syncs returns 404 for invalid connection."""
        from src.core.container import get_sync_transactions_handler

        app.dependency_overrides[get_sync_transactions_handler] = (
            lambda: MockSyncTransactionsHandler(error="Connection not found")
        )

        response = client.post(
            "/api/v1/transactions/syncs",
            json={"connection_id": str(mock_connection_id)},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_sync_transactions_handler, None)

    def test_sync_transactions_missing_connection_id(self, client):
        """POST /api/v1/transactions/syncs returns 422 when connection_id missing."""
        from src.core.container import get_sync_transactions_handler

        # Mock handler to prevent encryption init during validation
        app.dependency_overrides[get_sync_transactions_handler] = (
            lambda: MockSyncTransactionsHandler()
        )

        response = client.post("/api/v1/transactions/syncs", json={})

        assert response.status_code == 422

        app.dependency_overrides.pop(get_sync_transactions_handler, None)


# =============================================================================
# List Transactions by Account (GET /api/v1/accounts/{id}/transactions)
# =============================================================================


@pytest.mark.api
class TestListTransactionsByAccount:
    """Tests for GET /api/v1/accounts/{id}/transactions endpoint."""

    def test_list_transactions_returns_empty_list(self, client, mock_account_id):
        """GET /api/v1/accounts/{id}/transactions returns empty list."""
        from src.core.container import get_list_transactions_by_account_handler

        app.dependency_overrides[get_list_transactions_by_account_handler] = (
            lambda: MockListTransactionsHandler()
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}/transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["transactions"] == []

        app.dependency_overrides.pop(get_list_transactions_by_account_handler, None)

    def test_list_transactions_returns_transactions(
        self, client, mock_account_id, mock_transaction
    ):
        """GET /api/v1/accounts/{id}/transactions returns list."""
        from src.core.container import get_list_transactions_by_account_handler

        result = MockTransactionListResult(
            transactions=[mock_transaction],
            total_count=1,
            has_more=False,
        )
        app.dependency_overrides[get_list_transactions_by_account_handler] = (
            lambda: MockListTransactionsHandler(result=result)
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}/transactions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["symbol"] == "AAPL"

        app.dependency_overrides.pop(get_list_transactions_by_account_handler, None)

    def test_list_transactions_account_not_found(self, client, mock_account_id):
        """GET /api/v1/accounts/{id}/transactions returns 404."""
        from src.core.container import get_list_transactions_by_account_handler

        app.dependency_overrides[get_list_transactions_by_account_handler] = (
            lambda: MockListTransactionsHandler(error="Account not found")
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}/transactions")

        assert response.status_code == 404

        app.dependency_overrides.pop(get_list_transactions_by_account_handler, None)

    def test_list_transactions_invalid_uuid(self, client):
        """GET /api/v1/accounts/{id}/transactions returns 422 for invalid UUID."""
        response = client.get("/api/v1/accounts/not-a-uuid/transactions")

        assert response.status_code == 422
