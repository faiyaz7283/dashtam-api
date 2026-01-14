"""Edge case tests for transactions endpoints to improve coverage.

Covers missing lines in transactions.py:
- Lines 94-106: Error mapping edge cases (rate limit, invalid, default)
- Lines 308-314: Date range query path
"""

from dataclasses import dataclass
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.application.commands.handlers.sync_transactions_handler import (
    SyncTransactionsHandler,
)
from src.application.queries.handlers.list_transactions_handler import (
    ListTransactionsByDateRangeHandler,
)
from src.core.container.handler_factory import handler_factory
from src.core.result import Failure, Success
from src.main import app


# =============================================================================
# Test Doubles
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


class MockListTransactionsByDateRangeHandler:
    """Mock handler for listing transactions by date range."""

    def __init__(self, error: str | None = None):
        self._error = error

    async def handle(self, query):
        if self._error:
            return Failure(error=self._error)
        # Return empty list for success
        from dataclasses import dataclass

        @dataclass
        class MockTransactionListResult:
            transactions: list[object] | None = None
            total_count: int = 0

            def __post_init__(self) -> None:
                if self.transactions is None:
                    self.transactions = []

        return Success(value=MockTransactionListResult())


class MockSyncTransactionsHandler:
    """Mock handler for syncing transactions."""

    def __init__(self, error: str | None = None):
        self._error = error

    async def handle(self, command):
        if self._error:
            return Failure(error=self._error)
        return Success(value=None)


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
    return TestClient(app, raise_server_exceptions=False)


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.api
class TestTransactionsEdgeCases:
    """Edge case tests for transactions endpoints."""

    def test_sync_transactions_rate_limit_error(self, client, mock_account_id):
        """POST /api/v1/transactions/syncs returns 429 for rate limit errors."""
        factory_key = handler_factory(SyncTransactionsHandler)
        app.dependency_overrides[factory_key] = lambda: MockSyncTransactionsHandler(
            error="Sync recently synced, wait before retrying"
        )

        response = client.post(
            "/api/v1/transactions/syncs",
            json={"connection_id": str(uuid7()), "account_id": str(mock_account_id)},
        )

        assert response.status_code == 429
        data = response.json()
        assert data["status"] == 429

        app.dependency_overrides.pop(factory_key, None)

    def test_sync_transactions_invalid_input_error(self, client, mock_account_id):
        """POST /api/v1/transactions/syncs returns 400 for invalid input errors."""
        factory_key = handler_factory(SyncTransactionsHandler)
        app.dependency_overrides[factory_key] = lambda: MockSyncTransactionsHandler(
            error="Invalid date range specified"
        )

        response = client.post(
            "/api/v1/transactions/syncs",
            json={"connection_id": str(uuid7()), "account_id": str(mock_account_id)},
        )

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == 400

        app.dependency_overrides.pop(factory_key, None)

    def test_sync_transactions_default_error_mapping(self, client, mock_account_id):
        """POST /api/v1/transactions/syncs returns 500 for unmapped errors."""
        factory_key = handler_factory(SyncTransactionsHandler)
        app.dependency_overrides[factory_key] = lambda: MockSyncTransactionsHandler(
            error="Unknown database error occurred"
        )

        response = client.post(
            "/api/v1/transactions/syncs",
            json={"connection_id": str(uuid7()), "account_id": str(mock_account_id)},
        )

        assert response.status_code == 500
        data = response.json()
        assert data["status"] == 500

        app.dependency_overrides.pop(factory_key, None)

    def test_list_transactions_by_account_date_range_error(
        self, client, mock_account_id
    ):
        """GET /api/v1/accounts/{id}/transactions handles date range errors."""
        factory_key = handler_factory(ListTransactionsByDateRangeHandler)
        app.dependency_overrides[factory_key] = (
            lambda: MockListTransactionsByDateRangeHandler(error="Account not found")
        )

        # Provide dates to trigger date range path, expect error
        response = client.get(
            f"/api/v1/accounts/{mock_account_id}/transactions?"
            f"start_date=2024-01-01&end_date=2024-12-31"
        )

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == 404

        app.dependency_overrides.pop(factory_key, None)
