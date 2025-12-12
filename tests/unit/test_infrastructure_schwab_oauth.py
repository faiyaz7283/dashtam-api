"""Unit tests for SchwabProvider OAuth flows.

Tests cover:
- exchange_code_for_tokens: success, 400, 401, 429, 5xx, invalid JSON
- refresh_access_token: success with/without rotation, error paths
- Connection errors (timeout, DNS failure)

Architecture:
- Uses pytest-httpx for HTTP mocking (respx alternative)
- Tests Result pattern (Success/Failure)
- Tests specific error types (ProviderAuthenticationError, etc.)
"""

import base64

import httpx
import pytest
from pytest_httpx import HTTPXMock

from src.core.config import Settings
from src.core.enums import ErrorCode
from src.core.result import Failure, Success
from src.domain.errors import (
    ProviderAuthenticationError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from src.domain.protocols.provider_protocol import OAuthTokens
from src.infrastructure.providers.schwab.schwab_provider import SchwabProvider


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_settings(test_settings: Settings) -> Settings:
    """Create mock settings for SchwabProvider.

    Uses test_settings from .env.test as base (includes SECRET_KEY and ENCRYPTION_KEY),
    overriding only Schwab-specific fields for testing.
    """
    # Get base settings excluding Schwab fields we want to override
    # Also exclude cors_origins which has a validator that converts str -> list[str]
    settings_dict = test_settings.model_dump(
        exclude={
            "schwab_api_key",
            "schwab_api_secret",
            "schwab_api_base_url",
            "schwab_redirect_uri",
            "cors_origins",  # Validator changes type, keep original
        }
    )
    # Get cors_origins as comma-separated string (reverse the parse_cors_origins validator)
    if hasattr(test_settings, "cors_origins") and isinstance(
        test_settings.cors_origins, list
    ):
        settings_dict["cors_origins"] = ",".join(test_settings.cors_origins)
    else:
        settings_dict["cors_origins"] = "https://test.dashtam.local"
    # Add test-specific Schwab configuration
    settings_dict.update(
        {
            "schwab_api_key": "test_client_id",
            "schwab_api_secret": "test_client_secret",
            "schwab_api_base_url": "https://api.schwabapi.test",
            "schwab_redirect_uri": "https://dashtam.local/oauth/schwab/callback",
        }
    )
    return Settings(**settings_dict)


@pytest.fixture
def provider(mock_settings: Settings) -> SchwabProvider:
    """Create SchwabProvider instance."""
    return SchwabProvider(settings=mock_settings, timeout=5.0)


def _expected_auth_header(client_id: str, client_secret: str) -> str:
    """Generate expected Basic Auth header."""
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


# =============================================================================
# Test: exchange_code_for_tokens - Success
# =============================================================================


class TestExchangeCodeSuccess:
    """Test exchange_code_for_tokens success scenarios."""

    @pytest.mark.asyncio
    async def test_exchange_returns_tokens_on_success(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Successful exchange should return OAuthTokens."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={
                "access_token": "at_1234567890",
                "refresh_token": "rt_abcdefghij",
                "expires_in": 1800,
                "token_type": "Bearer",
                "scope": "api",
            },
            status_code=200,
        )

        result = await provider.exchange_code_for_tokens("auth_code_xyz")

        assert isinstance(result, Success)
        tokens = result.value
        assert isinstance(tokens, OAuthTokens)
        assert tokens.access_token == "at_1234567890"
        assert tokens.refresh_token == "rt_abcdefghij"
        assert tokens.expires_in == 1800
        assert tokens.token_type == "Bearer"
        assert tokens.scope == "api"

    @pytest.mark.asyncio
    async def test_exchange_sends_correct_request(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Exchange should send properly formatted request."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 1800,
                "token_type": "Bearer",
            },
            status_code=200,
        )

        await provider.exchange_code_for_tokens("test_code")

        # Verify request
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"

        # Check Authorization header
        expected_auth = _expected_auth_header("test_client_id", "test_client_secret")
        assert request.headers["Authorization"] == expected_auth
        assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"

        # Check form data
        content = request.content.decode()
        assert "grant_type=authorization_code" in content
        assert "code=test_code" in content
        assert (
            "redirect_uri=https%3A%2F%2Fdashtam.local%2Foauth%2Fschwab%2Fcallback"
            in content
        )

    @pytest.mark.asyncio
    async def test_exchange_handles_optional_fields(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Exchange should handle responses without optional fields."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={
                "access_token": "at_minimal",
                "expires_in": 3600,
                # No refresh_token, token_type, scope
            },
            status_code=200,
        )

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Success)
        tokens = result.value
        assert tokens.access_token == "at_minimal"
        assert tokens.refresh_token is None
        assert tokens.expires_in == 3600
        assert tokens.token_type == "Bearer"  # Default
        assert tokens.scope is None


# =============================================================================
# Test: exchange_code_for_tokens - Error Responses
# =============================================================================


class TestExchangeCodeErrors:
    """Test exchange_code_for_tokens error handling."""

    @pytest.mark.asyncio
    async def test_exchange_400_returns_auth_error(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """400 response should return ProviderAuthenticationError."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={"error": "invalid_grant", "error_description": "Code has expired"},
            status_code=400,
        )

        result = await provider.exchange_code_for_tokens("expired_code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderAuthenticationError)
        assert error.code == ErrorCode.PROVIDER_AUTHENTICATION_FAILED
        assert error.provider_name == "schwab"
        assert "expired" in error.message.lower()
        assert error.is_token_expired is True

    @pytest.mark.asyncio
    async def test_exchange_401_returns_auth_error(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """401 response should return ProviderAuthenticationError."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={"error": "invalid_client"},
            status_code=401,
        )

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderAuthenticationError)
        assert error.code == ErrorCode.PROVIDER_AUTHENTICATION_FAILED
        assert error.provider_name == "schwab"

    @pytest.mark.asyncio
    async def test_exchange_429_returns_rate_limit_error(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """429 response should return ProviderRateLimitError."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={"error": "too_many_requests"},
            status_code=429,
            headers={"Retry-After": "60"},
        )

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderRateLimitError)
        assert error.code == ErrorCode.PROVIDER_RATE_LIMITED
        assert error.provider_name == "schwab"
        assert error.retry_after == 60

    @pytest.mark.asyncio
    async def test_exchange_429_without_retry_after(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """429 without Retry-After header should still work."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={"error": "too_many_requests"},
            status_code=429,
        )

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderRateLimitError)
        assert error.retry_after is None

    @pytest.mark.asyncio
    async def test_exchange_500_returns_unavailable_error(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """500 response should return ProviderUnavailableError."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            text="Internal Server Error",
            status_code=500,
        )

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.code == ErrorCode.PROVIDER_UNAVAILABLE
        assert error.provider_name == "schwab"
        assert error.is_transient is True

    @pytest.mark.asyncio
    async def test_exchange_502_returns_unavailable_error(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """502 response should return ProviderUnavailableError."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            text="Bad Gateway",
            status_code=502,
        )

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.is_transient is True

    @pytest.mark.asyncio
    async def test_exchange_unexpected_status_returns_invalid_response(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Unexpected status code should return ProviderInvalidResponseError."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            text="Created",
            status_code=201,  # Unexpected for token endpoint
        )

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderInvalidResponseError)
        assert "201" in error.message


# =============================================================================
# Test: exchange_code_for_tokens - Invalid JSON
# =============================================================================


class TestExchangeCodeInvalidJson:
    """Test exchange_code_for_tokens with invalid JSON responses."""

    @pytest.mark.asyncio
    async def test_exchange_invalid_json_returns_error(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Invalid JSON response should return ProviderInvalidResponseError."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            text="<html>Not JSON</html>",
            status_code=200,
        )

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderInvalidResponseError)
        assert "Invalid JSON" in error.message or "JSON" in error.message

    @pytest.mark.asyncio
    async def test_exchange_missing_required_field_returns_error(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Missing required field should return ProviderInvalidResponseError."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={
                # Missing access_token
                "refresh_token": "rt",
                "expires_in": 1800,
            },
            status_code=200,
        )

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderInvalidResponseError)
        assert "Missing" in error.message or "access_token" in error.message


# =============================================================================
# Test: exchange_code_for_tokens - Connection Errors
# =============================================================================


class TestExchangeCodeConnectionErrors:
    """Test exchange_code_for_tokens connection error handling."""

    @pytest.mark.asyncio
    async def test_exchange_timeout_returns_unavailable(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Timeout should return ProviderUnavailableError."""
        httpx_mock.add_exception(httpx.TimeoutException("Connection timed out"))

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.code == ErrorCode.PROVIDER_UNAVAILABLE
        assert "timed out" in error.message.lower()
        assert error.is_transient is True

    @pytest.mark.asyncio
    async def test_exchange_connection_error_returns_unavailable(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Connection error should return ProviderUnavailableError."""
        httpx_mock.add_exception(httpx.ConnectError("Failed to connect"))

        result = await provider.exchange_code_for_tokens("code")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert "connect" in error.message.lower()
        assert error.is_transient is True


# =============================================================================
# Test: refresh_access_token - Success
# =============================================================================


class TestRefreshTokenSuccess:
    """Test refresh_access_token success scenarios."""

    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Successful refresh should return new tokens."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={
                "access_token": "new_at_123",
                "refresh_token": "new_rt_456",  # Rotated
                "expires_in": 1800,
                "token_type": "Bearer",
            },
            status_code=200,
        )

        result = await provider.refresh_access_token("old_refresh_token")

        assert isinstance(result, Success)
        tokens = result.value
        assert tokens.access_token == "new_at_123"
        assert tokens.refresh_token == "new_rt_456"
        assert tokens.expires_in == 1800

    @pytest.mark.asyncio
    async def test_refresh_sends_correct_request(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Refresh should send properly formatted request."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={
                "access_token": "at",
                "expires_in": 1800,
            },
            status_code=200,
        )

        await provider.refresh_access_token("rt_xyz789")

        request = httpx_mock.get_request()
        assert request is not None

        content = request.content.decode()
        assert "grant_type=refresh_token" in content
        assert "refresh_token=rt_xyz789" in content

    @pytest.mark.asyncio
    async def test_refresh_without_token_rotation(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Refresh without new refresh_token should preserve None."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={
                "access_token": "new_at",
                "expires_in": 1800,
                # No refresh_token - provider doesn't rotate
            },
            status_code=200,
        )

        result = await provider.refresh_access_token("old_rt")

        assert isinstance(result, Success)
        tokens = result.value
        assert tokens.access_token == "new_at"
        assert tokens.refresh_token is None  # Not rotated


# =============================================================================
# Test: refresh_access_token - Error Responses
# =============================================================================


class TestRefreshTokenErrors:
    """Test refresh_access_token error handling."""

    @pytest.mark.asyncio
    async def test_refresh_401_returns_auth_error(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """401 on refresh should return ProviderAuthenticationError."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={
                "error": "invalid_grant",
                "error_description": "Refresh token expired",
            },
            status_code=401,
        )

        result = await provider.refresh_access_token("expired_rt")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderAuthenticationError)
        assert error.code == ErrorCode.PROVIDER_AUTHENTICATION_FAILED

    @pytest.mark.asyncio
    async def test_refresh_400_expired_token(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """400 with expired message should set is_token_expired=True."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={"error": "invalid_grant", "error_description": "Token has expired"},
            status_code=400,
        )

        result = await provider.refresh_access_token("old_rt")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderAuthenticationError)
        assert error.is_token_expired is True

    @pytest.mark.asyncio
    async def test_refresh_429_rate_limited(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """429 on refresh should return rate limit error."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            json={"error": "rate_limit"},
            status_code=429,
            headers={"Retry-After": "120"},
        )

        result = await provider.refresh_access_token("rt")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderRateLimitError)
        assert error.retry_after == 120

    @pytest.mark.asyncio
    async def test_refresh_server_error(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Server error on refresh should return unavailable."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.schwabapi.test/v1/oauth/token",
            text="Service Unavailable",
            status_code=503,
        )

        result = await provider.refresh_access_token("rt")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)

    @pytest.mark.asyncio
    async def test_refresh_timeout(
        self, provider: SchwabProvider, httpx_mock: HTTPXMock
    ):
        """Timeout on refresh should return unavailable."""
        httpx_mock.add_exception(httpx.TimeoutException("Request timed out"))

        result = await provider.refresh_access_token("rt")

        assert isinstance(result, Failure)
        error = result.error
        assert isinstance(error, ProviderUnavailableError)
        assert error.is_transient is True


# =============================================================================
# Test: Provider Initialization
# =============================================================================


class TestProviderInitialization:
    """Test SchwabProvider initialization."""

    def test_provider_slug_is_schwab(self, provider: SchwabProvider):
        """Provider slug should be 'schwab'."""
        assert provider.slug == "schwab"

    def test_missing_api_key_raises_error(self):
        """Missing API key should raise ValueError."""
        settings = Settings(
            schwab_api_key="",  # Empty
            schwab_api_secret="secret",
            schwab_api_base_url="https://api.test",
            schwab_redirect_uri="https://redirect",
            database_url="postgresql+asyncpg://test@localhost/test",
            redis_url="redis://localhost:6379/0",
            encryption_key="test-encryption-exactly-32!!!!!!",
            secret_key="test-secret-key-minlen-32!!!****",
            api_base_url="https://test.com",
            callback_base_url="https://callback.com",
            cors_origins="https://test.com",
            verification_url_base="https://test.com",
        )

        with pytest.raises(ValueError, match="schwab_api_key"):
            SchwabProvider(settings=settings)

    def test_missing_api_secret_raises_error(self):
        """Missing API secret should raise ValueError."""
        settings = Settings(
            schwab_api_key="key",
            schwab_api_secret="",  # Empty
            schwab_api_base_url="https://api.test",
            schwab_redirect_uri="https://redirect",
            database_url="postgresql+asyncpg://test@localhost/test",
            redis_url="redis://localhost:6379/0",
            encryption_key="test-encryption-exactly-32!!!!!!",
            secret_key="test-secret-key-minlen-32!!!****",
            api_base_url="https://test.com",
            callback_base_url="https://callback.com",
            cors_origins="https://test.com",
            verification_url_base="https://test.com",
        )

        with pytest.raises(ValueError, match="schwab_api_secret"):
            SchwabProvider(settings=settings)

    def test_missing_redirect_uri_raises_error(self):
        """Missing redirect URI should raise ValueError."""
        settings = Settings(
            schwab_api_key="key",
            schwab_api_secret="secret",
            schwab_api_base_url="https://api.test",
            schwab_redirect_uri="",  # Empty
            database_url="postgresql+asyncpg://test@localhost/test",
            redis_url="redis://localhost:6379/0",
            encryption_key="test-encryption-exactly-32!!!!!!",
            secret_key="test-secret-key-minlen-32!!!****",
            api_base_url="https://test.com",
            callback_base_url="https://callback.com",
            cors_origins="https://test.com",
            verification_url_base="https://test.com",
        )

        with pytest.raises(ValueError, match="schwab_redirect_uri"):
            SchwabProvider(settings=settings)
