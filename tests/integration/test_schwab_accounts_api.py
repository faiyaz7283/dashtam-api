"""Integration tests for SchwabAccountsAPI.

Tests cover:
- HTTP request construction (headers, params, URL)
- Response handling (success, error codes)
- Error translation to ProviderError types
- Timeout and connection error handling

Architecture:
- Uses pytest-httpx for HTTP mocking
- Tests API client in isolation (no mapper)
- Verifies raw JSON response handling
"""

import httpx
import pytest
from pytest_httpx import HTTPXMock

from src.core.enums import ErrorCode
from src.core.result import Failure, Success
from src.domain.errors import (
    ProviderAuthenticationError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from src.infrastructure.providers.schwab.api.accounts_api import SchwabAccountsAPI


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def api() -> SchwabAccountsAPI:
    """Create SchwabAccountsAPI instance with test base URL."""
    return SchwabAccountsAPI(
        base_url="https://api.schwabapi.test/trader/v1",
        timeout=5.0,
    )


def _build_schwab_account_response(
    *,
    account_number: str = "12345678",
    account_type: str = "INDIVIDUAL",
    liquidation_value: float = 50000.00,
) -> dict:
    """Build a Schwab account JSON response for testing."""
    return {
        "securitiesAccount": {
            "type": account_type,
            "accountNumber": account_number,
            "currentBalances": {
                "liquidationValue": liquidation_value,
                "availableFunds": 10000.00,
            },
        }
    }


# =============================================================================
# Test: get_accounts - Success
# =============================================================================


class TestGetAccountsSuccess:
    """Test get_accounts success scenarios."""

    @pytest.mark.asyncio
    async def test_returns_account_list_on_success(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Successful response returns list of account dicts."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            json=[
                _build_schwab_account_response(account_number="11111111"),
                _build_schwab_account_response(account_number="22222222"),
            ],
            status_code=200,
        )

        result = await api.get_accounts("test_access_token")

        assert isinstance(result, Success)
        accounts = result.value
        assert len(accounts) == 2
        assert accounts[0]["securitiesAccount"]["accountNumber"] == "11111111"
        assert accounts[1]["securitiesAccount"]["accountNumber"] == "22222222"

    @pytest.mark.asyncio
    async def test_sends_correct_authorization_header(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Request includes Bearer token in Authorization header."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            json=[],
            status_code=200,
        )

        await api.get_accounts("my_secret_token")

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["Authorization"] == "Bearer my_secret_token"
        assert request.headers["Accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_includes_positions_param_when_requested(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Request includes fields=positions when include_positions=True."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts?fields=positions",
            json=[],
            status_code=200,
        )

        await api.get_accounts("token", include_positions=True)

        request = httpx_mock.get_request()
        assert request is not None
        assert "fields=positions" in str(request.url)

    @pytest.mark.asyncio
    async def test_handles_empty_list_response(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Empty account list is returned successfully."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            json=[],
            status_code=200,
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Success)
        assert result.value == []

    @pytest.mark.asyncio
    async def test_handles_single_object_response(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Single object response is wrapped in list."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            json=_build_schwab_account_response(),  # Single object, not list
            status_code=200,
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Success)
        assert len(result.value) == 1


# =============================================================================
# Test: get_accounts - Error Responses
# =============================================================================


class TestGetAccountsErrors:
    """Test get_accounts error handling."""

    @pytest.mark.asyncio
    async def test_401_returns_authentication_error(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """401 response returns ProviderAuthenticationError."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            json={"error": "invalid_token"},
            status_code=401,
        )

        result = await api.get_accounts("invalid_token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderAuthenticationError)
        assert error.code == ErrorCode.PROVIDER_AUTHENTICATION_FAILED
        assert error.provider_name == "schwab"
        assert error.is_token_expired is True

    @pytest.mark.asyncio
    async def test_403_returns_authentication_error(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """403 response returns ProviderAuthenticationError (not expired)."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            json={"error": "forbidden"},
            status_code=403,
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderAuthenticationError)
        assert error.is_token_expired is False

    @pytest.mark.asyncio
    async def test_404_returns_invalid_response_error(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """404 response returns ProviderInvalidResponseError."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            json={"error": "not_found"},
            status_code=404,
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderInvalidResponseError)
        assert "not found" in error.message.lower()

    @pytest.mark.asyncio
    async def test_429_returns_rate_limit_error(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """429 response returns ProviderRateLimitError."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            json={"error": "rate_limit"},
            status_code=429,
            headers={"Retry-After": "60"},
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderRateLimitError)
        assert error.code == ErrorCode.PROVIDER_RATE_LIMITED
        assert error.retry_after == 60

    @pytest.mark.asyncio
    async def test_429_without_retry_after_header(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """429 without Retry-After header still works."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            json={"error": "rate_limit"},
            status_code=429,
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderRateLimitError)
        assert error.retry_after is None

    @pytest.mark.asyncio
    async def test_500_returns_unavailable_error(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """500 response returns ProviderUnavailableError."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            text="Internal Server Error",
            status_code=500,
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.code == ErrorCode.PROVIDER_UNAVAILABLE
        assert error.is_transient is True

    @pytest.mark.asyncio
    async def test_502_returns_unavailable_error(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """502 response returns ProviderUnavailableError."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            text="Bad Gateway",
            status_code=502,
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.is_transient is True

    @pytest.mark.asyncio
    async def test_unexpected_status_returns_invalid_response(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Unexpected status code returns ProviderInvalidResponseError."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            text="Created",
            status_code=201,
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderInvalidResponseError)
        assert "201" in error.message


# =============================================================================
# Test: get_accounts - Invalid JSON
# =============================================================================


class TestGetAccountsInvalidJson:
    """Test get_accounts with invalid JSON responses."""

    @pytest.mark.asyncio
    async def test_invalid_json_returns_error(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Invalid JSON response returns ProviderInvalidResponseError."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts",
            text="<html>Not JSON</html>",
            status_code=200,
        )

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderInvalidResponseError)
        assert "JSON" in error.message


# =============================================================================
# Test: get_accounts - Connection Errors
# =============================================================================


class TestGetAccountsConnectionErrors:
    """Test get_accounts connection error handling."""

    @pytest.mark.asyncio
    async def test_timeout_returns_unavailable(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Timeout returns ProviderUnavailableError."""
        httpx_mock.add_exception(httpx.TimeoutException("Connection timed out"))

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert "timed out" in error.message.lower()
        assert error.is_transient is True

    @pytest.mark.asyncio
    async def test_connection_error_returns_unavailable(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Connection error returns ProviderUnavailableError."""
        httpx_mock.add_exception(httpx.ConnectError("Failed to connect"))

        result = await api.get_accounts("token")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert "connect" in error.message.lower()
        assert error.is_transient is True


# =============================================================================
# Test: get_account (single account)
# =============================================================================


class TestGetSingleAccount:
    """Test get_account for fetching a specific account."""

    @pytest.mark.asyncio
    async def test_returns_single_account_on_success(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Successful response returns single account dict."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts/12345678",
            json=_build_schwab_account_response(account_number="12345678"),
            status_code=200,
        )

        result = await api.get_account("token", "12345678")

        assert isinstance(result, Success)
        account = result.value
        assert account["securitiesAccount"]["accountNumber"] == "12345678"

    @pytest.mark.asyncio
    async def test_includes_account_number_in_url(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Request URL includes account number."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts/98765432",
            json=_build_schwab_account_response(),
            status_code=200,
        )

        await api.get_account("token", "98765432")

        request = httpx_mock.get_request()
        assert request is not None
        assert "/accounts/98765432" in str(request.url)

    @pytest.mark.asyncio
    async def test_includes_positions_param(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Request includes fields=positions when requested."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts/12345678?fields=positions",
            json=_build_schwab_account_response(),
            status_code=200,
        )

        await api.get_account("token", "12345678", include_positions=True)

        request = httpx_mock.get_request()
        assert request is not None
        assert "fields=positions" in str(request.url)

    @pytest.mark.asyncio
    async def test_404_for_nonexistent_account(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """404 for nonexistent account returns error."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts/00000000",
            json={"error": "account_not_found"},
            status_code=404,
        )

        result = await api.get_account("token", "00000000")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderInvalidResponseError)

    @pytest.mark.asyncio
    async def test_non_dict_response_returns_error(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Non-dict response returns ProviderInvalidResponseError."""
        httpx_mock.add_response(
            method="GET",
            url="https://api.schwabapi.test/trader/v1/accounts/12345678",
            json=["unexpected", "list"],  # List instead of dict
            status_code=200,
        )

        result = await api.get_account("token", "12345678")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderInvalidResponseError)
        assert "Expected object" in error.message

    @pytest.mark.asyncio
    async def test_timeout_on_single_account(
        self, api: SchwabAccountsAPI, httpx_mock: HTTPXMock
    ):
        """Timeout on single account returns ProviderUnavailableError."""
        httpx_mock.add_exception(httpx.TimeoutException("Timed out"))

        result = await api.get_account("token", "12345678")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.is_transient is True
