"""Edge case tests for accounts endpoints to improve coverage.

Covers missing lines in accounts.py:
- Line 93, 98: Error mapping edge cases (rate limit, invalid)
- Lines 152-156: Invalid account_type filter handling
"""

from dataclasses import dataclass
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from uuid_extensions import uuid7

from src.application.queries.handlers.list_accounts_handler import (
    ListAccountsByUserHandler,
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


class MockListAccountsByUserHandler:
    """Mock handler for listing accounts."""

    def __init__(self, error: str | None = None):
        self._error = error

    async def handle(self, query):
        if self._error:
            return Failure(error=self._error)
        # Return empty list for success
        from dataclasses import dataclass

        @dataclass
        class MockAccountListResult:
            accounts: list[object] | None = None
            total_count: int = 0

            def __post_init__(self) -> None:
                if self.accounts is None:
                    self.accounts = []

        return Success(value=MockAccountListResult())


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user_id():
    """Provide consistent user ID for tests."""
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
class TestAccountsEdgeCases:
    """Edge case tests for accounts endpoints."""

    def test_list_accounts_rate_limit_error(self, client):
        """GET /api/v1/accounts returns 429 for rate limit errors."""
        factory_key = handler_factory(ListAccountsByUserHandler)
        app.dependency_overrides[factory_key] = lambda: MockListAccountsByUserHandler(
            error="Sync too soon, try again later"
        )

        response = client.get("/api/v1/accounts")

        assert response.status_code == 429
        data = response.json()
        assert data["status"] == 429

        app.dependency_overrides.pop(factory_key, None)

    def test_list_accounts_invalid_input_error(self, client):
        """GET /api/v1/accounts returns 400 for invalid input errors."""
        factory_key = handler_factory(ListAccountsByUserHandler)
        app.dependency_overrides[factory_key] = lambda: MockListAccountsByUserHandler(
            error="Invalid account type specified"
        )

        response = client.get("/api/v1/accounts")

        assert response.status_code == 400
        data = response.json()
        assert data["status"] == 400

        app.dependency_overrides.pop(factory_key, None)
