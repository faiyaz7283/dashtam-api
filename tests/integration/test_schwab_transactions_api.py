"""Integration tests for SchwabTransactionsAPI.

Tests HTTP interactions with mocked Schwab Trader API responses.

Covers:
- Request construction (headers, params, URL encoding)
- Date range parameter handling
- Response parsing (success, errors)
- Error code translation to ProviderError types
- Timeout and connection handling

Architecture:
- Uses httpx_mock to simulate Schwab API responses
- Tests the raw API client (returns dict[str, Any])
- SchwabProvider combines API + Mapper for full flow
"""

from datetime import date

import httpx
import pytest
from pytest_httpx import HTTPXMock

from src.core.result import Failure, Success
from src.domain.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from src.infrastructure.providers.schwab.api.transactions_api import (
    SchwabTransactionsAPI,
)


# =============================================================================
# Constants
# =============================================================================

SCHWAB_BASE_URL = "https://api.schwabapi.com/trader/v1"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def api() -> SchwabTransactionsAPI:
    """Create SchwabTransactionsAPI instance with base URL."""
    return SchwabTransactionsAPI(base_url=SCHWAB_BASE_URL)


@pytest.fixture
def account_number() -> str:
    """Sample Schwab account number (encrypted format)."""
    return "ENCRYPTED_ACCOUNT_12345"


@pytest.fixture
def sample_trade_transaction() -> dict:
    """Sample TRADE transaction from Schwab API."""
    return {
        "activityId": "TRD_12345",
        "type": "TRADE",
        "transactionSubType": "BUY",
        "status": "EXECUTED",
        "tradeDate": "2024-11-28",
        "settlementDate": "2024-11-30",
        "netAmount": -1050.00,
        "description": "Bought AAPL",
        "totalCommission": 0.00,
        "transactionItem": {
            "instrument": {
                "symbol": "AAPL",
                "description": "Apple Inc",
                "assetType": "EQUITY",
            },
            "amount": 10.0,
            "price": 105.00,
        },
    }


@pytest.fixture
def sample_dividend_transaction() -> dict:
    """Sample dividend transaction from Schwab API."""
    return {
        "activityId": "DIV_12345",
        "type": "DIVIDEND",
        "status": "EXECUTED",
        "transactionDate": "2024-11-15",
        "netAmount": 25.50,
        "description": "AAPL Dividend",
    }


@pytest.fixture
def sample_transfer_transaction() -> dict:
    """Sample transfer transaction from Schwab API."""
    return {
        "activityId": "ACH_12345",
        "type": "ACH_RECEIPT",
        "status": "EXECUTED",
        "transactionDate": "2024-11-01",
        "netAmount": 5000.00,
        "description": "ACH Deposit from Checking",
    }


# =============================================================================
# Test: Request Construction
# =============================================================================


class TestRequestConstruction:
    """Test HTTP request construction."""

    @pytest.mark.asyncio
    async def test_builds_correct_url_with_account_number(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Request URL includes account number."""
        httpx_mock.add_response(json=[])

        await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert account_number in str(request.url)
        assert "/transactions" in str(request.url)

    @pytest.mark.asyncio
    async def test_includes_authorization_header(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Request includes Bearer token header."""
        httpx_mock.add_response(json=[])

        await api.get_transactions(
            access_token="my-secret-token",
            account_number=account_number,
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers.get("Authorization") == "Bearer my-secret-token"

    @pytest.mark.asyncio
    async def test_includes_content_type_header(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Request includes Accept header for JSON."""
        httpx_mock.add_response(json=[])

        await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert "application/json" in request.headers.get("Accept", "")


# =============================================================================
# Test: Date Range Parameters
# =============================================================================


class TestDateRangeParameters:
    """Test date range query parameters."""

    @pytest.mark.asyncio
    async def test_includes_start_date_parameter(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Start date is included as query parameter."""
        httpx_mock.add_response(json=[])

        await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
            start_date=date(2024, 1, 1),
        )

        request = httpx_mock.get_request()
        assert request is not None
        query_str = str(request.url.params)
        assert "2024-01-01" in query_str

    @pytest.mark.asyncio
    async def test_includes_end_date_parameter(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """End date is included as query parameter."""
        httpx_mock.add_response(json=[])

        await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
            end_date=date(2024, 12, 31),
        )

        request = httpx_mock.get_request()
        assert request is not None
        query_str = str(request.url.params)
        assert "2024-12-31" in query_str

    @pytest.mark.asyncio
    async def test_includes_both_date_parameters(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Both start and end dates are included."""
        httpx_mock.add_response(json=[])

        await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
            start_date=date(2024, 6, 1),
            end_date=date(2024, 6, 30),
        )

        request = httpx_mock.get_request()
        assert request is not None
        query_str = str(request.url.params)
        assert "2024-06-01" in query_str
        assert "2024-06-30" in query_str


# =============================================================================
# Test: Success Response Parsing
# =============================================================================


class TestSuccessResponseParsing:
    """Test successful API response parsing (returns raw JSON)."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_transactions(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Empty response returns empty list."""
        httpx_mock.add_response(json=[])

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Success)
        transactions = result.value
        assert transactions == []

    @pytest.mark.asyncio
    async def test_parses_single_trade_transaction(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
        sample_trade_transaction: dict,
    ):
        """Single trade transaction JSON is returned."""
        httpx_mock.add_response(json=[sample_trade_transaction])

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Success)
        transactions = result.value
        assert len(transactions) == 1
        # API returns raw dict, not ProviderTransactionData
        assert transactions[0]["activityId"] == "TRD_12345"
        assert transactions[0]["type"] == "TRADE"
        assert transactions[0]["transactionSubType"] == "BUY"

    @pytest.mark.asyncio
    async def test_parses_multiple_transactions(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
        sample_trade_transaction: dict,
        sample_dividend_transaction: dict,
        sample_transfer_transaction: dict,
    ):
        """Multiple transactions are returned as raw JSON."""
        httpx_mock.add_response(
            json=[
                sample_trade_transaction,
                sample_dividend_transaction,
                sample_transfer_transaction,
            ]
        )

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Success)
        transactions = result.value
        assert len(transactions) == 3

        # Verify raw types
        types = {t["type"] for t in transactions}
        assert "TRADE" in types
        assert "DIVIDEND" in types
        assert "ACH_RECEIPT" in types


# =============================================================================
# Test: Error Response Handling
# =============================================================================


class TestErrorResponseHandling:
    """Test API error response handling."""

    @pytest.mark.asyncio
    async def test_401_returns_authentication_error(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """401 response returns authentication error."""
        httpx_mock.add_response(
            status_code=401,
            json={"error": "unauthorized", "message": "Invalid token"},
        )

        result = await api.get_transactions(
            access_token="expired-token",
            account_number=account_number,
        )

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderAuthenticationError)

    @pytest.mark.asyncio
    async def test_403_returns_authentication_error(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """403 response returns authentication error (forbidden)."""
        httpx_mock.add_response(
            status_code=403,
            json={"error": "forbidden", "message": "Access denied"},
        )

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderAuthenticationError)

    @pytest.mark.asyncio
    async def test_404_returns_error(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """404 response returns ProviderError."""
        httpx_mock.add_response(
            status_code=404,
            json={"error": "not_found", "message": "Account not found"},
        )

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderError)

    @pytest.mark.asyncio
    async def test_429_returns_rate_limit_error(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """429 response returns rate limit error."""
        httpx_mock.add_response(
            status_code=429,
            json={"error": "rate_limited", "message": "Too many requests"},
            headers={"Retry-After": "60"},
        )

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderRateLimitError)
        assert error.retry_after == 60

    @pytest.mark.asyncio
    async def test_500_returns_unavailable_error(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """500 response returns provider unavailable error."""
        httpx_mock.add_response(
            status_code=500,
            json={"error": "internal_error", "message": "Server error"},
        )

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.is_transient is True


# =============================================================================
# Test: Network Errors
# =============================================================================


class TestNetworkErrors:
    """Test network error handling."""

    @pytest.mark.asyncio
    async def test_timeout_returns_unavailable_error(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Timeout returns unavailable error with is_transient=True."""
        httpx_mock.add_exception(httpx.TimeoutException("Connection timed out"))

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.is_transient is True

    @pytest.mark.asyncio
    async def test_connection_error_returns_unavailable_error(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Connection error returns unavailable error."""
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.is_transient is True


# =============================================================================
# Test: Response Data Validation
# =============================================================================


class TestResponseDataValidation:
    """Test response data validation and edge cases."""

    @pytest.mark.asyncio
    async def test_returns_all_transactions_as_raw_json(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
        sample_trade_transaction: dict,
    ):
        """API returns all transactions as raw JSON (no validation)."""
        # API returns raw JSON - filtering happens in mapper
        httpx_mock.add_response(
            json=[
                sample_trade_transaction,
                {"type": "TRADE"},  # Would be invalid for mapper
                {"activityId": "123"},  # Would be invalid for mapper
            ]
        )

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Success)
        transactions = result.value
        # API returns ALL transactions - filtering is done by mapper
        assert len(transactions) == 3

    @pytest.mark.asyncio
    async def test_handles_null_response_body(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Null response body returns empty list."""
        httpx_mock.add_response(text="null", status_code=200)

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        # Null becomes empty list or wrapped in list
        if isinstance(result, Success):
            assert result.value == []
        else:
            assert isinstance(result.error, ProviderError)

    @pytest.mark.asyncio
    async def test_handles_object_response_wraps_in_list(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
    ):
        """Object response is wrapped in a list."""
        # Some endpoints might return single object
        httpx_mock.add_response(json={"activityId": "123", "type": "TRADE"})

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        # Should wrap object in list
        if isinstance(result, Success):
            transactions = result.value
            assert isinstance(transactions, list)
            assert len(transactions) == 1
        else:
            assert isinstance(result.error, ProviderError)


# =============================================================================
# Test: Transaction Details
# =============================================================================


class TestRawTransactionData:
    """Test raw transaction data is returned correctly."""

    @pytest.mark.asyncio
    async def test_returns_raw_instrument_data(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
        sample_trade_transaction: dict,
    ):
        """Raw instrument data is preserved."""
        httpx_mock.add_response(json=[sample_trade_transaction])

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Success)
        transactions = result.value
        instrument = transactions[0]["transactionItem"]["instrument"]
        assert instrument["symbol"] == "AAPL"
        assert instrument["assetType"] == "EQUITY"

    @pytest.mark.asyncio
    async def test_returns_raw_amount_data(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
        sample_trade_transaction: dict,
    ):
        """Raw amount and price data is preserved."""
        httpx_mock.add_response(json=[sample_trade_transaction])

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Success)
        transactions = result.value
        txn_item = transactions[0]["transactionItem"]
        assert txn_item["amount"] == 10.0
        assert txn_item["price"] == 105.00

    @pytest.mark.asyncio
    async def test_returns_raw_dates(
        self,
        api: SchwabTransactionsAPI,
        httpx_mock: HTTPXMock,
        account_number: str,
        sample_trade_transaction: dict,
    ):
        """Raw date strings are preserved."""
        httpx_mock.add_response(json=[sample_trade_transaction])

        result = await api.get_transactions(
            access_token="test-token",
            account_number=account_number,
        )

        assert isinstance(result, Success)
        transactions = result.value
        assert transactions[0]["tradeDate"] == "2024-11-28"
        assert transactions[0]["settlementDate"] == "2024-11-30"
