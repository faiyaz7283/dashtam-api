"""API tests for account endpoints.

Tests the complete HTTP request/response cycle for account management:
- GET /api/v1/accounts (list user accounts)
- GET /api/v1/accounts/{id} (get account details)
- POST /api/v1/accounts/syncs (sync accounts from providers)
- GET /api/v1/providers/{id}/accounts (list accounts for provider connection)

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
class MockAccountResult:
    """Mock DTO matching AccountResult from get_account_handler.py."""

    id: UUID
    connection_id: UUID
    provider_account_id: str
    account_number_masked: str
    name: str
    account_type: str
    currency: str
    balance_amount: Decimal
    balance_currency: str
    available_balance_amount: Decimal | None
    available_balance_currency: str | None
    is_active: bool
    is_investment: bool
    is_bank: bool
    is_retirement: bool
    is_credit: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass
class MockSyncAccountsResult:
    """Mock result matching SyncAccountsResult from sync_accounts_handler.py."""

    created: int
    updated: int
    unchanged: int
    errors: int
    message: str


@dataclass
class MockAccountListResult:
    """Mock result matching AccountListResult from list_accounts_handler.py."""

    accounts: list[MockAccountResult]
    total_count: int
    active_count: int
    total_balance_by_currency: dict[str, str]


class MockListAccountsHandler:
    """Mock handler for listing accounts."""

    def __init__(
        self,
        accounts: list[MockAccountResult] | None = None,
        error: str | None = None,
    ) -> None:
        self._accounts = accounts or []
        self._error = error

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        result = MockAccountListResult(
            accounts=self._accounts,
            total_count=len(self._accounts),
            active_count=sum(1 for a in self._accounts if a.is_active),
            total_balance_by_currency={"USD": "1234.56"} if self._accounts else {},
        )
        return Success(value=result)


class MockGetAccountHandler:
    """Mock handler for getting a single account."""

    def __init__(
        self,
        account: MockAccountResult | None = None,
        error: str | None = None,
    ) -> None:
        self._account = account
        self._error = error

    async def handle(self, query: Any) -> Success[object] | Failure[str]:
        if self._error:
            return Failure(error=self._error)
        return Success(value=self._account)


class MockSyncAccountsHandler:
    """Mock handler for syncing accounts."""

    def __init__(
        self,
        result: MockSyncAccountsResult | None = None,
        error: str | None = None,
    ) -> None:
        self._result = result or MockSyncAccountsResult(
            created=2,
            updated=3,
            unchanged=0,
            errors=0,
            message="Synced 5 accounts: 2 created, 3 updated, 0 unchanged",
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
def mock_connection_id():
    """Provide consistent connection ID for tests."""
    return uuid7()


@pytest.fixture
def mock_account(mock_account_id, mock_connection_id):
    """Create a mock account result."""
    now = datetime.now(UTC)
    return MockAccountResult(
        id=mock_account_id,
        connection_id=mock_connection_id,
        provider_account_id="ACCT-123456",
        account_number_masked="****6789",
        name="My Checking Account",
        account_type="checking",
        currency="USD",
        balance_amount=Decimal("1234.56"),
        balance_currency="USD",
        available_balance_amount=Decimal("1200.00"),
        available_balance_currency="USD",
        is_active=True,
        is_investment=False,
        is_bank=True,
        is_retirement=False,
        is_credit=False,
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
# List Accounts Tests (GET /api/v1/accounts)
# =============================================================================


@pytest.mark.api
class TestListAccounts:
    """Tests for GET /api/v1/accounts endpoint."""

    def test_list_accounts_returns_empty_list(self, client):
        """GET /api/v1/accounts returns empty list when no accounts."""
        from src.core.container import get_list_accounts_by_user_handler

        app.dependency_overrides[get_list_accounts_by_user_handler] = (
            lambda: MockListAccountsHandler(accounts=[])
        )

        response = client.get("/api/v1/accounts")

        assert response.status_code == 200
        data = response.json()
        assert data["accounts"] == []

        app.dependency_overrides.pop(get_list_accounts_by_user_handler, None)

    def test_list_accounts_returns_accounts(self, client, mock_account):
        """GET /api/v1/accounts returns list of accounts."""
        from src.core.container import get_list_accounts_by_user_handler

        app.dependency_overrides[get_list_accounts_by_user_handler] = (
            lambda: MockListAccountsHandler(accounts=[mock_account])
        )

        response = client.get("/api/v1/accounts")

        assert response.status_code == 200
        data = response.json()
        assert len(data["accounts"]) == 1
        assert data["accounts"][0]["name"] == "My Checking Account"

        app.dependency_overrides.pop(get_list_accounts_by_user_handler, None)

    def test_list_accounts_handler_error_returns_rfc7807(self, client):
        """GET /api/v1/accounts returns RFC 7807 error on handler failure."""
        from src.core.container import get_list_accounts_by_user_handler

        app.dependency_overrides[get_list_accounts_by_user_handler] = (
            lambda: MockListAccountsHandler(error="Database unavailable")
        )

        response = client.get("/api/v1/accounts")

        assert response.status_code == 500
        data = response.json()
        assert "type" in data
        assert "title" in data
        assert data["status"] == 500

        app.dependency_overrides.pop(get_list_accounts_by_user_handler, None)


# =============================================================================
# Get Account Tests (GET /api/v1/accounts/{id})
# =============================================================================


@pytest.mark.api
class TestGetAccount:
    """Tests for GET /api/v1/accounts/{id} endpoint."""

    def test_get_account_returns_details(self, client, mock_account_id, mock_account):
        """GET /api/v1/accounts/{id} returns account details."""
        from src.core.container import get_get_account_handler

        app.dependency_overrides[get_get_account_handler] = (
            lambda: MockGetAccountHandler(account=mock_account)
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(mock_account_id)
        assert data["name"] == "My Checking Account"

        app.dependency_overrides.pop(get_get_account_handler, None)

    def test_get_account_not_found(self, client, mock_account_id):
        """GET /api/v1/accounts/{id} returns 404 when not found."""
        from src.core.container import get_get_account_handler

        app.dependency_overrides[get_get_account_handler] = (
            lambda: MockGetAccountHandler(error="Account not found")
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == 404

        app.dependency_overrides.pop(get_get_account_handler, None)

    def test_get_account_forbidden(self, client, mock_account_id):
        """GET /api/v1/accounts/{id} returns 403 when not owned by user."""
        from src.core.container import get_get_account_handler

        app.dependency_overrides[get_get_account_handler] = (
            lambda: MockGetAccountHandler(error="Account not owned by user")
        )

        response = client.get(f"/api/v1/accounts/{mock_account_id}")

        assert response.status_code == 403

        app.dependency_overrides.pop(get_get_account_handler, None)

    def test_get_account_invalid_uuid(self, client):
        """GET /api/v1/accounts/{id} returns 422 for invalid UUID."""
        response = client.get("/api/v1/accounts/not-a-uuid")

        assert response.status_code == 422


# =============================================================================
# Sync Accounts Tests (POST /api/v1/accounts/syncs)
# =============================================================================


@pytest.mark.api
class TestSyncAccounts:
    """Tests for POST /api/v1/accounts/syncs endpoint."""

    def test_sync_accounts_success(self, client, mock_connection_id):
        """POST /api/v1/accounts/syncs triggers account sync."""
        from src.core.container import get_sync_accounts_handler

        app.dependency_overrides[get_sync_accounts_handler] = (
            lambda: MockSyncAccountsHandler()
        )

        response = client.post(
            "/api/v1/accounts/syncs",
            json={"connection_id": str(mock_connection_id)},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["created"] == 2
        assert data["updated"] == 3

        app.dependency_overrides.pop(get_sync_accounts_handler, None)

    def test_sync_accounts_connection_not_found(self, client, mock_connection_id):
        """POST /api/v1/accounts/syncs returns 404 for invalid connection."""
        from src.core.container import get_sync_accounts_handler

        app.dependency_overrides[get_sync_accounts_handler] = (
            lambda: MockSyncAccountsHandler(error="Connection not found")
        )

        response = client.post(
            "/api/v1/accounts/syncs",
            json={"connection_id": str(mock_connection_id)},
        )

        assert response.status_code == 404

        app.dependency_overrides.pop(get_sync_accounts_handler, None)

    def test_sync_accounts_missing_connection_id(self, client):
        """POST /api/v1/accounts/syncs returns 422 when connection_id missing."""
        from src.core.container import get_sync_accounts_handler

        # Mock handler to prevent encryption init during validation
        app.dependency_overrides[get_sync_accounts_handler] = (
            lambda: MockSyncAccountsHandler()
        )

        response = client.post("/api/v1/accounts/syncs", json={})

        assert response.status_code == 422

        app.dependency_overrides.pop(get_sync_accounts_handler, None)


# =============================================================================
# Provider Accounts Tests (GET /api/v1/providers/{id}/accounts)
# =============================================================================


@pytest.mark.api
class TestProviderAccounts:
    """Tests for GET /api/v1/providers/{id}/accounts endpoint."""

    def test_list_provider_accounts(self, client, mock_connection_id, mock_account):
        """GET /api/v1/providers/{id}/accounts returns accounts for connection."""
        from src.core.container import get_list_accounts_by_connection_handler

        app.dependency_overrides[get_list_accounts_by_connection_handler] = (
            lambda: MockListAccountsHandler(accounts=[mock_account])
        )

        response = client.get(f"/api/v1/providers/{mock_connection_id}/accounts")

        assert response.status_code == 200
        data = response.json()
        assert len(data["accounts"]) == 1

        app.dependency_overrides.pop(get_list_accounts_by_connection_handler, None)

    def test_list_provider_accounts_empty(self, client, mock_connection_id):
        """GET /api/v1/providers/{id}/accounts returns empty when no accounts."""
        from src.core.container import get_list_accounts_by_connection_handler

        app.dependency_overrides[get_list_accounts_by_connection_handler] = (
            lambda: MockListAccountsHandler(accounts=[])
        )

        response = client.get(f"/api/v1/providers/{mock_connection_id}/accounts")

        assert response.status_code == 200
        data = response.json()
        assert data["accounts"] == []

        app.dependency_overrides.pop(get_list_accounts_by_connection_handler, None)

    def test_list_provider_accounts_connection_not_found(
        self, client, mock_connection_id
    ):
        """GET /api/v1/providers/{id}/accounts returns 404 for invalid connection."""
        from src.core.container import get_list_accounts_by_connection_handler

        app.dependency_overrides[get_list_accounts_by_connection_handler] = (
            lambda: MockListAccountsHandler(error="Connection not found")
        )

        response = client.get(f"/api/v1/providers/{mock_connection_id}/accounts")

        assert response.status_code == 404

        app.dependency_overrides.pop(get_list_accounts_by_connection_handler, None)
