"""Tests for src/infrastructure/providers/base_api_client.py.

Verifies the BaseProviderAPIClient handles HTTP requests, errors, and
JSON parsing correctly for all provider API clients.

Reference:
    - src/infrastructure/providers/base_api_client.py
"""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.constants import PROVIDER_TIMEOUT_DEFAULT
from src.core.enums import ErrorCode
from src.core.result import Failure, Success
from src.domain.errors import (
    ProviderAuthenticationError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from src.infrastructure.providers.base_api_client import BaseProviderAPIClient


class ConcreteAPIClient(BaseProviderAPIClient):
    """Concrete implementation for testing."""

    def __init__(self, *, base_url: str, timeout: float = PROVIDER_TIMEOUT_DEFAULT):
        super().__init__(
            base_url=base_url,
            provider_name="test_provider",
            timeout=timeout,
        )


class TestBaseProviderAPIClientInit:
    """Tests for BaseProviderAPIClient initialization."""

    def test_strips_trailing_slash_from_base_url(self) -> None:
        """Base URL should have trailing slash removed."""
        client = ConcreteAPIClient(base_url="https://api.test.com/")
        assert client._base_url == "https://api.test.com"

    def test_preserves_url_without_trailing_slash(self) -> None:
        """Base URL without trailing slash should be preserved."""
        client = ConcreteAPIClient(base_url="https://api.test.com")
        assert client._base_url == "https://api.test.com"

    def test_stores_provider_name(self) -> None:
        """Provider name should be stored for logging."""
        client = ConcreteAPIClient(base_url="https://api.test.com")
        assert client._provider_name == "test_provider"

    def test_uses_default_timeout(self) -> None:
        """Should use PROVIDER_TIMEOUT_DEFAULT when timeout not specified."""
        client = ConcreteAPIClient(base_url="https://api.test.com")
        assert client._timeout == PROVIDER_TIMEOUT_DEFAULT

    def test_uses_custom_timeout(self) -> None:
        """Should use custom timeout when specified."""
        client = ConcreteAPIClient(base_url="https://api.test.com", timeout=60.0)
        assert client._timeout == 60.0


class TestCheckErrorResponse:
    """Tests for _check_error_response method."""

    @pytest.fixture
    def client(self) -> ConcreteAPIClient:
        return ConcreteAPIClient(base_url="https://api.test.com")

    def test_returns_none_for_200_status(self, client: ConcreteAPIClient) -> None:
        """Should return None for successful 200 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200

        result = client._check_error_response(response, "test_op")

        assert result is None

    def test_returns_rate_limit_error_for_429(self, client: ConcreteAPIClient) -> None:
        """Should return ProviderRateLimitError for 429 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        response.headers = {"Retry-After": "60"}

        result = client._check_error_response(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderRateLimitError)
        assert result.error.code == ErrorCode.PROVIDER_RATE_LIMITED
        assert result.error.retry_after == 60

    def test_returns_rate_limit_error_without_retry_after(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should handle 429 without Retry-After header."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        response.headers = {}

        result = client._check_error_response(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderRateLimitError)
        assert result.error.retry_after is None

    def test_returns_auth_error_for_401(self, client: ConcreteAPIClient) -> None:
        """Should return ProviderAuthenticationError for 401 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401

        result = client._check_error_response(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderAuthenticationError)
        assert result.error.code == ErrorCode.PROVIDER_AUTHENTICATION_FAILED
        assert result.error.is_token_expired is True

    def test_returns_auth_error_for_403(self, client: ConcreteAPIClient) -> None:
        """Should return ProviderAuthenticationError for 403 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 403

        result = client._check_error_response(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderAuthenticationError)
        assert result.error.is_token_expired is False

    def test_returns_invalid_response_for_404(self, client: ConcreteAPIClient) -> None:
        """Should return ProviderInvalidResponseError for 404 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 404
        response.text = "Not Found"

        result = client._check_error_response(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)
        assert "not found" in result.error.message.lower()

    def test_returns_unavailable_error_for_500(self, client: ConcreteAPIClient) -> None:
        """Should return ProviderUnavailableError for 500 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 500

        result = client._check_error_response(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)
        assert result.error.is_transient is True

    def test_returns_unavailable_error_for_502(self, client: ConcreteAPIClient) -> None:
        """Should return ProviderUnavailableError for 502 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 502

        result = client._check_error_response(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)

    def test_returns_invalid_response_for_unexpected_status(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should return ProviderInvalidResponseError for unexpected status."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 418  # I'm a teapot
        response.text = "Short body"

        result = client._check_error_response(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)


class TestParseJsonObject:
    """Tests for _parse_json_object method."""

    @pytest.fixture
    def client(self) -> ConcreteAPIClient:
        return ConcreteAPIClient(base_url="https://api.test.com")

    def test_returns_dict_for_valid_json_object(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should return Success with dict for valid JSON object."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {"key": "value", "count": 42}

        result = client._parse_json_object(response, "test_op")

        assert isinstance(result, Success)
        assert result.value == {"key": "value", "count": 42}

    def test_returns_error_for_invalid_json(self, client: ConcreteAPIClient) -> None:
        """Should return Failure for invalid JSON."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.side_effect = ValueError("Invalid JSON")
        response.text = "not valid json"

        result = client._parse_json_object(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)

    def test_returns_error_for_non_dict_json(self, client: ConcreteAPIClient) -> None:
        """Should return Failure when JSON is not a dict."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = ["list", "not", "dict"]
        response.text = '["list", "not", "dict"]'

        result = client._parse_json_object(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)


class TestParseJsonList:
    """Tests for _parse_json_list method."""

    @pytest.fixture
    def client(self) -> ConcreteAPIClient:
        return ConcreteAPIClient(base_url="https://api.test.com")

    def test_returns_list_for_valid_json_array(self, client: ConcreteAPIClient) -> None:
        """Should return Success with list for valid JSON array."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = [{"id": 1}, {"id": 2}]

        result = client._parse_json_list(response, "test_op")

        assert isinstance(result, Success)
        assert result.value == [{"id": 1}, {"id": 2}]

    def test_wraps_single_object_in_list(self, client: ConcreteAPIClient) -> None:
        """Should wrap single object in list if response is dict."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = {"id": 1, "name": "single"}

        result = client._parse_json_list(response, "test_op")

        assert isinstance(result, Success)
        assert result.value == [{"id": 1, "name": "single"}]

    def test_returns_empty_list_for_empty_response(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should return empty list for None/empty response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = None

        result = client._parse_json_list(response, "test_op")

        assert isinstance(result, Success)
        assert result.value == []

    def test_returns_error_for_invalid_json(self, client: ConcreteAPIClient) -> None:
        """Should return Failure for invalid JSON."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.side_effect = ValueError("Invalid JSON")
        response.text = "not valid json"

        result = client._parse_json_list(response, "test_op")

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderInvalidResponseError)


class TestExecuteRequest:
    """Tests for _execute_request method."""

    @pytest.fixture
    def client(self) -> ConcreteAPIClient:
        return ConcreteAPIClient(base_url="https://api.test.com")

    @pytest.mark.asyncio
    async def test_returns_response_on_success(self, client: ConcreteAPIClient) -> None:
        """Should return Success with response for successful request."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await client._execute_request(
                method="GET",
                path="/accounts",
                headers={"Authorization": "Bearer token"},
                operation="test_op",
            )

        assert isinstance(result, Success)
        assert result.value == mock_response

    @pytest.mark.asyncio
    async def test_returns_unavailable_on_timeout(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should return ProviderUnavailableError on timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await client._execute_request(
                method="GET",
                path="/accounts",
                headers={},
                operation="test_op",
            )

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)
        assert result.error.is_transient is True
        assert "timed out" in result.error.message.lower()

    @pytest.mark.asyncio
    async def test_returns_unavailable_on_connection_error(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should return ProviderUnavailableError on connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.RequestError("Connection failed")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await client._execute_request(
                method="GET",
                path="/accounts",
                headers={},
                operation="test_op",
            )

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)
        assert result.error.is_transient is True


class TestExecuteAndParseObject:
    """Tests for _execute_and_parse_object method."""

    @pytest.fixture
    def client(self) -> ConcreteAPIClient:
        return ConcreteAPIClient(base_url="https://api.test.com")

    @pytest.mark.asyncio
    async def test_returns_parsed_object_on_success(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should return parsed JSON object for successful request."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123", "name": "Test"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await client._execute_and_parse_object(
                method="GET",
                path="/account/123",
                headers={"Authorization": "Bearer token"},
                operation="get_account",
            )

        assert isinstance(result, Success)
        assert result.value == {"id": "123", "name": "Test"}

    @pytest.mark.asyncio
    async def test_returns_failure_on_request_error(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should propagate Failure from _execute_request."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await client._execute_and_parse_object(
                method="GET",
                path="/account/123",
                headers={},
                operation="get_account",
            )

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)


class TestExecuteAndParseList:
    """Tests for _execute_and_parse_list method."""

    @pytest.fixture
    def client(self) -> ConcreteAPIClient:
        return ConcreteAPIClient(base_url="https://api.test.com")

    @pytest.mark.asyncio
    async def test_returns_parsed_list_on_success(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should return parsed JSON list for successful request."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": "1"}, {"id": "2"}]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await client._execute_and_parse_list(
                method="GET",
                path="/accounts",
                headers={"Authorization": "Bearer token"},
                operation="get_accounts",
            )

        assert isinstance(result, Success)
        assert result.value == [{"id": "1"}, {"id": "2"}]

    @pytest.mark.asyncio
    async def test_returns_failure_on_request_error(
        self, client: ConcreteAPIClient
    ) -> None:
        """Should propagate Failure from _execute_request."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await client._execute_and_parse_list(
                method="GET",
                path="/accounts",
                headers={},
                operation="get_accounts",
            )

        assert isinstance(result, Failure)
        assert isinstance(result.error, ProviderUnavailableError)
