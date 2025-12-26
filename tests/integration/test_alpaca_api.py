"""Integration tests for Alpaca API clients.

Tests for:
- AlpacaAccountsAPI: HTTP client for account and positions endpoints
- AlpacaTransactionsAPI: HTTP client for activities endpoint

Uses pytest-httpx to mock HTTP responses.
"""

import re

import pytest

from src.core.result import Failure, Success
from src.domain.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from src.infrastructure.providers.alpaca.api.accounts_api import AlpacaAccountsAPI
from src.infrastructure.providers.alpaca.api.transactions_api import (
    AlpacaTransactionsAPI,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def accounts_api() -> AlpacaAccountsAPI:
    """Create AlpacaAccountsAPI instance."""
    return AlpacaAccountsAPI(
        base_url="https://paper-api.alpaca.markets",
        timeout=30.0,
    )


@pytest.fixture
def transactions_api() -> AlpacaTransactionsAPI:
    """Create AlpacaTransactionsAPI instance."""
    return AlpacaTransactionsAPI(
        base_url="https://paper-api.alpaca.markets",
        timeout=30.0,
    )


@pytest.fixture
def api_credentials() -> tuple[str, str]:
    """Return test API credentials."""
    return ("PKTEST123", "secret456")


# =============================================================================
# AlpacaAccountsAPI - get_account Tests
# =============================================================================


@pytest.mark.integration
class TestAlpacaAccountsAPIGetAccount:
    """Tests for AlpacaAccountsAPI.get_account."""

    async def test_get_account_success(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Successful account fetch returns JSON dict."""
        api_key, api_secret = api_credentials
        response_json = {
            "account_number": "PA3CRCJ7QUIR",
            "status": "ACTIVE",
            "equity": "150000.50",
        }
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            json=response_json,
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Success)
        assert result.value["account_number"] == "PA3CRCJ7QUIR"

    async def test_get_account_auth_failure_401(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """401 response returns ProviderAuthenticationError."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            status_code=401,
            json={"message": "Invalid credentials"},
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderAuthenticationError)

    async def test_get_account_auth_failure_403(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """403 response returns ProviderAuthenticationError."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            status_code=403,
            json={"message": "Forbidden"},
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderAuthenticationError)

    async def test_get_account_rate_limited_429(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """429 response returns ProviderRateLimitError."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            status_code=429,
            headers={"Retry-After": "60"},
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderRateLimitError)
        assert result.error.retry_after == 60

    async def test_get_account_server_error_500(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """500 response returns ProviderUnavailableError."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            status_code=500,
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)

    async def test_get_account_sends_correct_headers(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Request includes correct API key headers."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            json={"account_number": "PA123"},
        )

        await accounts_api.get_account(api_key, api_secret)

        request = httpx_mock.get_request()
        assert request.headers["APCA-API-KEY-ID"] == api_key
        assert request.headers["APCA-API-SECRET-KEY"] == api_secret


# =============================================================================
# AlpacaAccountsAPI - get_positions Tests
# =============================================================================


@pytest.mark.integration
class TestAlpacaAccountsAPIGetPositions:
    """Tests for AlpacaAccountsAPI.get_positions."""

    async def test_get_positions_success(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Successful positions fetch returns list of dicts."""
        api_key, api_secret = api_credentials
        response_json = [
            {"symbol": "AAPL", "qty": "100", "market_value": "15500"},
            {"symbol": "GOOGL", "qty": "50", "market_value": "70000"},
        ]
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/positions",
            json=response_json,
        )

        result = await accounts_api.get_positions(api_key, api_secret)

        assert isinstance(result, Success)
        assert len(result.value) == 2
        assert result.value[0]["symbol"] == "AAPL"

    async def test_get_positions_empty(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Empty positions returns empty list."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/positions",
            json=[],
        )

        result = await accounts_api.get_positions(api_key, api_secret)

        assert isinstance(result, Success)
        assert result.value == []

    async def test_get_positions_auth_failure(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Auth failure returns ProviderAuthenticationError."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/positions",
            status_code=401,
        )

        result = await accounts_api.get_positions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderAuthenticationError)


# =============================================================================
# AlpacaTransactionsAPI Tests
# =============================================================================


@pytest.mark.integration
class TestAlpacaTransactionsAPI:
    """Tests for AlpacaTransactionsAPI."""

    async def test_get_transactions_success(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Successful activities fetch returns list of dicts."""
        api_key, api_secret = api_credentials
        response_json = [
            {
                "id": "txn1",
                "activity_type": "FILL",
                "symbol": "AAPL",
            },
            {
                "id": "txn2",
                "activity_type": "DIV",
                "net_amount": "100",
            },
        ]
        # Use url pattern to match any query params (page_size is always added)
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            json=response_json,
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Success)
        assert len(result.value) == 2

    async def test_get_transactions_with_date_params(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Date parameters are included in request."""
        from datetime import date

        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            json=[],
        )

        await transactions_api.get_transactions(
            api_key,
            api_secret,
            start_date=date(2021, 1, 1),
            end_date=date(2021, 12, 31),
        )

        request = httpx_mock.get_request()
        assert "after=2021-01-01" in str(request.url)
        assert "until=2021-12-31" in str(request.url)

    async def test_get_transactions_empty(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Empty activities returns empty list."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            json=[],
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Success)
        assert result.value == []

    async def test_get_transactions_auth_failure(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Auth failure returns ProviderAuthenticationError."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            status_code=401,
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderAuthenticationError)

    async def test_get_transactions_rate_limited(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """429 response returns ProviderRateLimitError."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            status_code=429,
            headers={"Retry-After": "30"},
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderRateLimitError)

    async def test_get_transactions_server_error(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """500 response returns ProviderUnavailableError."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            status_code=503,
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)

    async def test_get_transactions_sends_correct_headers(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Request includes correct API key headers."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            json=[],
        )

        await transactions_api.get_transactions(api_key, api_secret)

        request = httpx_mock.get_request()
        assert request.headers["APCA-API-KEY-ID"] == api_key
        assert request.headers["APCA-API-SECRET-KEY"] == api_secret

    async def test_get_transactions_with_activity_types_filter(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Activity types filter is included in request."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            json=[],
        )

        await transactions_api.get_transactions(
            api_key,
            api_secret,
            activity_types=["FILL", "DIV"],
        )

        request = httpx_mock.get_request()
        assert "activity_types=FILL%2CDIV" in str(
            request.url
        ) or "activity_types=FILL,DIV" in str(request.url)


# =============================================================================
# AlpacaAccountsAPI - Timeout and Connection Error Tests
# =============================================================================


@pytest.mark.integration
class TestAlpacaAccountsAPIErrorHandling:
    """Tests for AlpacaAccountsAPI error handling."""

    async def test_get_account_timeout(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Timeout returns ProviderUnavailableError."""
        import httpx

        api_key, api_secret = api_credentials
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url="https://paper-api.alpaca.markets/v2/account",
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)
        assert "timed out" in result.error.message.lower()

    async def test_get_account_connection_error(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Connection error returns ProviderUnavailableError."""
        import httpx

        api_key, api_secret = api_credentials
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url="https://paper-api.alpaca.markets/v2/account",
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)

    async def test_get_account_invalid_json(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Invalid JSON response returns ProviderInvalidResponseError."""
        from src.domain.errors import ProviderInvalidResponseError

        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            content=b"not valid json",
            status_code=200,
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)

    async def test_get_account_unexpected_list_response(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """List response (expected dict) returns ProviderInvalidResponseError."""
        from src.domain.errors import ProviderInvalidResponseError

        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            json=[{"account_number": "PA123"}],  # List instead of dict
            status_code=200,
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)

    async def test_get_account_404_not_found(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """404 response returns ProviderInvalidResponseError."""
        from src.domain.errors import ProviderInvalidResponseError

        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            status_code=404,
            json={"message": "Not found"},
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)

    async def test_get_account_unexpected_status_code(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Unexpected status code returns ProviderInvalidResponseError."""
        from src.domain.errors import ProviderInvalidResponseError

        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            status_code=418,  # I'm a teapot
            json={"message": "Unexpected"},
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)

    async def test_get_positions_timeout(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Positions timeout returns ProviderUnavailableError."""
        import httpx

        api_key, api_secret = api_credentials
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url="https://paper-api.alpaca.markets/v2/positions",
        )

        result = await accounts_api.get_positions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)

    async def test_get_positions_connection_error(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Positions connection error returns ProviderUnavailableError."""
        import httpx

        api_key, api_secret = api_credentials
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url="https://paper-api.alpaca.markets/v2/positions",
        )

        result = await accounts_api.get_positions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)

    async def test_get_positions_invalid_json(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Positions invalid JSON returns ProviderInvalidResponseError."""
        from src.domain.errors import ProviderInvalidResponseError

        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/positions",
            content=b"not valid json",
            status_code=200,
        )

        result = await accounts_api.get_positions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)

    async def test_get_positions_dict_response_wrapped_as_list(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Dict response is wrapped as single-item list."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/positions",
            json={"symbol": "AAPL", "qty": "100"},  # Single dict instead of list
            status_code=200,
        )

        result = await accounts_api.get_positions(api_key, api_secret)

        assert isinstance(result, Success)
        assert len(result.value) == 1
        assert result.value[0]["symbol"] == "AAPL"

    async def test_get_account_rate_limited_no_retry_after(
        self,
        accounts_api: AlpacaAccountsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """429 without Retry-After header returns None for retry_after."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url="https://paper-api.alpaca.markets/v2/account",
            status_code=429,
            # No Retry-After header
        )

        result = await accounts_api.get_account(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderRateLimitError)
        assert result.error.retry_after is None


# =============================================================================
# AlpacaTransactionsAPI - Error Handling Tests
# =============================================================================


@pytest.mark.integration
class TestAlpacaTransactionsAPIErrorHandling:
    """Tests for AlpacaTransactionsAPI error handling."""

    async def test_get_transactions_timeout(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Timeout returns ProviderUnavailableError."""
        import httpx

        api_key, api_secret = api_credentials
        httpx_mock.add_exception(
            httpx.TimeoutException("Connection timed out"),
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)

    async def test_get_transactions_connection_error(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Connection error returns ProviderUnavailableError."""
        import httpx

        api_key, api_secret = api_credentials
        httpx_mock.add_exception(
            httpx.ConnectError("Connection refused"),
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)

    async def test_get_transactions_invalid_json(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Invalid JSON returns ProviderInvalidResponseError."""
        from src.domain.errors import ProviderInvalidResponseError

        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            content=b"not valid json",
            status_code=200,
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)

    async def test_get_transactions_unexpected_status_code(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Unexpected status code returns ProviderInvalidResponseError."""
        from src.domain.errors import ProviderInvalidResponseError

        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            status_code=418,
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)

    async def test_get_transactions_dict_response_wrapped_as_list(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """Dict response is wrapped as single-item list."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            json={"id": "txn123", "activity_type": "DIV"},  # Single dict
            status_code=200,
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Success)
        assert len(result.value) == 1

    async def test_get_transactions_rate_limited_no_retry_after(
        self,
        transactions_api: AlpacaTransactionsAPI,
        api_credentials: tuple[str, str],
        httpx_mock,
    ):
        """429 without Retry-After returns None."""
        api_key, api_secret = api_credentials
        httpx_mock.add_response(
            url=re.compile(
                r"https://paper-api\.alpaca\.markets/v2/account/activities.*"
            ),
            status_code=429,
        )

        result = await transactions_api.get_transactions(api_key, api_secret)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderRateLimitError)
        assert result.error.retry_after is None
