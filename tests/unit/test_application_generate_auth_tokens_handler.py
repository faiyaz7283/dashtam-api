"""Unit tests for GenerateAuthTokensHandler.

Tests cover:
- Successful token generation (returns AuthTokens)
- JWT access token generation
- Opaque refresh token generation
- Refresh token persistence to database
- Token service interaction

Architecture:
- Unit tests for application handler (mocked dependencies)
- Mock service protocols
- Test handler logic, not implementation details
- Async tests (handler uses async repository)

Note: This handler ONLY generates tokens. It does NOT authenticate users
or create sessions (CQRS separation).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from src.application.commands.handlers.generate_auth_tokens_handler import (
    GenerateAuthTokensHandler,
)
from src.application.commands.token_commands import AuthTokens, GenerateAuthTokens
from src.core.result import Success


@pytest.mark.unit
class TestGenerateAuthTokensHandlerSuccess:
    """Test successful token generation scenarios."""

    @pytest.mark.asyncio
    async def test_generate_tokens_returns_auth_tokens(self):
        """Test successful generation returns Success with AuthTokens."""
        # Arrange
        user_id = uuid4()
        session_id = uuid4()

        mock_token_service = Mock()
        mock_token_service.generate_access_token.return_value = "jwt_access_token_123"

        mock_refresh_token_service = Mock()
        mock_refresh_token_service.generate_token.return_value = (
            "opaque_refresh_token_456",
            "hashed_refresh_token",
        )
        mock_refresh_token_service.calculate_expiration.return_value = datetime.now(
            UTC
        ) + timedelta(days=30)

        mock_refresh_token_repo = AsyncMock()

        handler = GenerateAuthTokensHandler(
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            refresh_token_repo=mock_refresh_token_repo,
        )

        command = GenerateAuthTokens(
            user_id=user_id,
            email="test@example.com",
            roles=["user"],
            session_id=session_id,
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Success)
        assert isinstance(result.value, AuthTokens)
        assert result.value.access_token == "jwt_access_token_123"
        assert result.value.refresh_token == "opaque_refresh_token_456"

    @pytest.mark.asyncio
    async def test_generate_tokens_calls_jwt_service_correctly(self):
        """Test handler calls JWT service with correct parameters."""
        # Arrange
        user_id = uuid4()
        session_id = uuid4()
        email = "test@example.com"
        roles = ["user", "admin"]

        mock_token_service = Mock()
        mock_token_service.generate_access_token.return_value = "jwt_token"

        mock_refresh_token_service = Mock()
        mock_refresh_token_service.generate_token.return_value = ("refresh", "hash")
        mock_refresh_token_service.calculate_expiration.return_value = datetime.now(
            UTC
        ) + timedelta(days=30)

        mock_refresh_token_repo = AsyncMock()

        handler = GenerateAuthTokensHandler(
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            refresh_token_repo=mock_refresh_token_repo,
        )

        command = GenerateAuthTokens(
            user_id=user_id,
            email=email,
            roles=roles,
            session_id=session_id,
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_token_service.generate_access_token.assert_called_once_with(
            user_id=user_id,
            email=email,
            roles=roles,
            session_id=session_id,
        )

    @pytest.mark.asyncio
    async def test_generate_tokens_calls_refresh_service(self):
        """Test handler generates opaque refresh token."""
        # Arrange
        mock_token_service = Mock()
        mock_token_service.generate_access_token.return_value = "jwt_token"

        mock_refresh_token_service = Mock()
        mock_refresh_token_service.generate_token.return_value = (
            "opaque_token",
            "token_hash",
        )
        mock_refresh_token_service.calculate_expiration.return_value = datetime.now(
            UTC
        ) + timedelta(days=30)

        mock_refresh_token_repo = AsyncMock()

        handler = GenerateAuthTokensHandler(
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            refresh_token_repo=mock_refresh_token_repo,
        )

        command = GenerateAuthTokens(
            user_id=uuid4(),
            email="test@example.com",
            roles=["user"],
            session_id=uuid4(),
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_refresh_token_service.generate_token.assert_called_once()
        mock_refresh_token_service.calculate_expiration.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_tokens_persists_refresh_token(self):
        """Test handler persists refresh token hash to database."""
        # Arrange
        user_id = uuid4()
        session_id = uuid4()
        expires_at = datetime.now(UTC) + timedelta(days=30)

        mock_token_service = Mock()
        mock_token_service.generate_access_token.return_value = "jwt_token"

        mock_refresh_token_service = Mock()
        mock_refresh_token_service.generate_token.return_value = (
            "opaque_token",
            "hashed_token_value",
        )
        mock_refresh_token_service.calculate_expiration.return_value = expires_at

        mock_refresh_token_repo = AsyncMock()

        handler = GenerateAuthTokensHandler(
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            refresh_token_repo=mock_refresh_token_repo,
        )

        command = GenerateAuthTokens(
            user_id=user_id,
            email="test@example.com",
            roles=["user"],
            session_id=session_id,
        )

        # Act
        await handler.handle(command)

        # Assert
        mock_refresh_token_repo.save.assert_called_once_with(
            user_id=user_id,
            token_hash="hashed_token_value",
            session_id=session_id,
            expires_at=expires_at,
        )

    @pytest.mark.asyncio
    async def test_generate_tokens_with_multiple_roles(self):
        """Test token generation with multiple user roles."""
        # Arrange
        user_id = uuid4()
        session_id = uuid4()
        roles = ["user", "admin", "moderator"]

        mock_token_service = Mock()
        mock_token_service.generate_access_token.return_value = "jwt_token"

        mock_refresh_token_service = Mock()
        mock_refresh_token_service.generate_token.return_value = ("refresh", "hash")
        mock_refresh_token_service.calculate_expiration.return_value = datetime.now(
            UTC
        ) + timedelta(days=30)

        mock_refresh_token_repo = AsyncMock()

        handler = GenerateAuthTokensHandler(
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            refresh_token_repo=mock_refresh_token_repo,
        )

        command = GenerateAuthTokens(
            user_id=user_id,
            email="admin@example.com",
            roles=roles,
            session_id=session_id,
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert isinstance(result, Success)
        mock_token_service.generate_access_token.assert_called_once_with(
            user_id=user_id,
            email="admin@example.com",
            roles=roles,
            session_id=session_id,
        )


@pytest.mark.unit
class TestGenerateAuthTokensHandlerTokenContent:
    """Test token content and structure."""

    @pytest.mark.asyncio
    async def test_access_token_is_from_token_service(self):
        """Test access token is exactly what token service returns."""
        # Arrange
        expected_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"

        mock_token_service = Mock()
        mock_token_service.generate_access_token.return_value = expected_jwt

        mock_refresh_token_service = Mock()
        mock_refresh_token_service.generate_token.return_value = ("refresh", "hash")
        mock_refresh_token_service.calculate_expiration.return_value = datetime.now(
            UTC
        ) + timedelta(days=30)

        mock_refresh_token_repo = AsyncMock()

        handler = GenerateAuthTokensHandler(
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            refresh_token_repo=mock_refresh_token_repo,
        )

        command = GenerateAuthTokens(
            user_id=uuid4(),
            email="test@example.com",
            roles=["user"],
            session_id=uuid4(),
        )

        # Act
        result = await handler.handle(command)

        # Assert
        assert result.value.access_token == expected_jwt

    @pytest.mark.asyncio
    async def test_refresh_token_is_opaque_not_hash(self):
        """Test refresh token returned is opaque token, not the hash."""
        # Arrange
        opaque_token = "dXf9KjL2mNpQ3rStUvWxYz"
        token_hash = "sha256:hashed_value_stored_in_db"

        mock_token_service = Mock()
        mock_token_service.generate_access_token.return_value = "jwt"

        mock_refresh_token_service = Mock()
        mock_refresh_token_service.generate_token.return_value = (
            opaque_token,
            token_hash,
        )
        mock_refresh_token_service.calculate_expiration.return_value = datetime.now(
            UTC
        ) + timedelta(days=30)

        mock_refresh_token_repo = AsyncMock()

        handler = GenerateAuthTokensHandler(
            token_service=mock_token_service,
            refresh_token_service=mock_refresh_token_service,
            refresh_token_repo=mock_refresh_token_repo,
        )

        command = GenerateAuthTokens(
            user_id=uuid4(),
            email="test@example.com",
            roles=["user"],
            session_id=uuid4(),
        )

        # Act
        result = await handler.handle(command)

        # Assert - Client receives opaque token, NOT the hash
        assert result.value.refresh_token == opaque_token
        assert result.value.refresh_token != token_hash

        # Assert - Database receives hash, NOT opaque token
        mock_refresh_token_repo.save.assert_called_once()
        call_kwargs = mock_refresh_token_repo.save.call_args.kwargs
        assert call_kwargs["token_hash"] == token_hash
