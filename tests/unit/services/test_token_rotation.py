"""Unit tests for OAuth token rotation handling.

Tests cover all token rotation scenarios using synchronous test patterns:
1. Provider rotates refresh token (sends new one)
2. Provider does not rotate (omits refresh_token key)
3. Provider sends same token (edge case)
4. Rotation is correctly persisted
5. Audit logs capture rotation details

Following project conventions:
- Synchronous tests (regular def test_*(), NOT async def)
- asyncio.run() to call async service methods
- Mocked AsyncSession for database operations
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from src.models.provider import (
    Provider,
    ProviderAuditLog,
    ProviderConnection,
    ProviderStatus,
    ProviderToken,
)
from src.models.user import User
from src.services.token_service import TokenService


class TestTokenRotationScenarios:
    """Test different token rotation scenarios from OAuth providers."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.add = Mock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_encryption(self):
        """Create a mock encryption service."""
        with patch("src.services.token_service.get_encryption_service") as mock:
            encryption = Mock()
            encryption.encrypt = Mock(side_effect=lambda x: f"encrypted_{x}")
            encryption.decrypt = Mock(side_effect=lambda x: x.replace("encrypted_", ""))
            mock.return_value = encryption
            yield encryption

    @pytest.fixture
    def mock_provider_registry(self):
        """Create a mock provider registry."""
        with patch("src.services.token_service.ProviderRegistry") as mock:
            yield mock

    def create_test_provider_with_token(self, initial_refresh_token="initial_refresh"):
        """Create a provider with existing tokens for testing rotation."""
        user = User(
            id=uuid4(),
            email="test@example.com",
            name="Test User",
            external_id="test123",
            is_active=True,
        )

        provider = Provider(
            id=uuid4(),
            user_id=user.id,
            provider_key="schwab",
            alias="Test Schwab",
        )

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider.id,
            status=ProviderStatus.ACTIVE,
        )

        token = ProviderToken(
            id=uuid4(),
            connection_id=connection.id,
            access_token_encrypted=f"encrypted_{initial_refresh_token}",
            refresh_token_encrypted=f"encrypted_{initial_refresh_token}",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # Expired
            token_type="Bearer",
            refresh_count=0,
        )

        provider.connection = connection
        connection.token = token

        return {
            "user": user,
            "provider": provider,
            "connection": connection,
            "token": token,
            "initial_refresh": initial_refresh_token,
        }

    def test_token_rotation_with_new_refresh_token(
        self, mock_session, mock_encryption, mock_provider_registry
    ):
        """Test that rotation is detected when provider sends NEW refresh token."""
        # Arrange
        data = self.create_test_provider_with_token()
        provider = data["provider"]
        user = data["user"]

        # Mock database query to return our test provider
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock provider to return NEW refresh token
        mock_provider_impl = Mock()
        mock_provider_impl.refresh_authentication = AsyncMock(
            return_value={
                "access_token": "new_access_token",
                "refresh_token": "rotated_refresh_token",  # NEW token
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
        mock_provider_registry.create_provider_instance = Mock(
            return_value=mock_provider_impl
        )

        token_service = TokenService(mock_session)

        # Act
        asyncio.run(token_service.refresh_token(provider.id, user.id))

        # Assert - new refresh token was encrypted and stored
        assert mock_encryption.encrypt.call_count >= 2  # access + refresh tokens
        # Check that the new refresh token was encrypted
        encrypt_calls = [call[0][0] for call in mock_encryption.encrypt.call_args_list]
        assert "rotated_refresh_token" in encrypt_calls

        # Verify session operations
        mock_session.add.assert_called()  # Audit log added
        mock_session.flush.assert_called()

    def test_no_rotation_refresh_token_not_included(
        self, mock_session, mock_encryption, mock_provider_registry
    ):
        """Test that no rotation occurs when provider omits refresh_token key."""
        # Arrange
        data = self.create_test_provider_with_token()
        provider = data["provider"]
        user = data["user"]

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock provider to NOT return refresh_token (most common no-rotation case)
        mock_provider_impl = Mock()
        mock_provider_impl.refresh_authentication = AsyncMock(
            return_value={
                "access_token": "new_access_token",
                # NOTE: No "refresh_token" key at all
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
        mock_provider_registry.create_provider_instance = Mock(
            return_value=mock_provider_impl
        )

        token_service = TokenService(mock_session)

        # Act
        asyncio.run(token_service.refresh_token(provider.id, user.id))

        # Assert - only access token was encrypted (not refresh token)
        encrypt_calls = [call[0][0] for call in mock_encryption.encrypt.call_args_list]
        # Should encrypt new access token but NOT a new refresh token
        assert "new_access_token" in encrypt_calls
        # Should not try to encrypt a new refresh token since none was provided
        assert "rotated_refresh_token" not in encrypt_calls

    def test_same_refresh_token_returned(
        self, mock_session, mock_encryption, mock_provider_registry
    ):
        """Test edge case where provider returns SAME refresh token."""
        # Arrange
        data = self.create_test_provider_with_token()
        provider = data["provider"]
        user = data["user"]
        initial_refresh = data["initial_refresh"]

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock provider to return SAME refresh token (edge case)
        mock_provider_impl = Mock()
        mock_provider_impl.refresh_authentication = AsyncMock(
            return_value={
                "access_token": "new_access_token",
                "refresh_token": initial_refresh,  # SAME as input
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        )
        mock_provider_registry.create_provider_instance = Mock(
            return_value=mock_provider_impl
        )

        token_service = TokenService(mock_session)

        # Act
        asyncio.run(token_service.refresh_token(provider.id, user.id))

        # Assert - encryption called but for same token
        assert mock_encryption.encrypt.called
        # Verify flush was called (token updated)
        mock_session.flush.assert_called()

    def test_rotation_persistence_across_multiple_refreshes(
        self, mock_session, mock_encryption, mock_provider_registry
    ):
        """Test that rotated tokens persist correctly across multiple refreshes."""
        # Arrange
        data = self.create_test_provider_with_token()
        provider = data["provider"]
        user = data["user"]
        token = data["token"]

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock provider for first refresh
        mock_provider_impl = Mock()
        mock_provider_impl.refresh_authentication = AsyncMock(
            return_value={
                "access_token": "access_token_1",
                "refresh_token": "refresh_token_1",
                "expires_in": 3600,
            }
        )
        mock_provider_registry.create_provider_instance = Mock(
            return_value=mock_provider_impl
        )

        token_service = TokenService(mock_session)

        # Act - First refresh
        asyncio.run(token_service.refresh_token(provider.id, user.id))

        # Verify refresh count incremented
        assert token.refresh_count == 1

        # Mock provider for second refresh
        mock_provider_impl.refresh_authentication = AsyncMock(
            return_value={
                "access_token": "access_token_2",
                "refresh_token": "refresh_token_2",
                "expires_in": 3600,
            }
        )

        # Act - Second refresh
        asyncio.run(token_service.refresh_token(provider.id, user.id))

        # Assert - refresh count incremented again
        assert token.refresh_count == 2

    def test_rotation_updates_access_token_expiry(
        self, mock_session, mock_encryption, mock_provider_registry
    ):
        """Test that token refresh updates access token expiry correctly."""
        # Arrange
        data = self.create_test_provider_with_token()
        provider = data["provider"]
        user = data["user"]
        token = data["token"]

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock provider response
        mock_provider_impl = Mock()
        mock_provider_impl.refresh_authentication = AsyncMock(
            return_value={
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_in": 7200,  # 2 hours
            }
        )
        mock_provider_registry.create_provider_instance = Mock(
            return_value=mock_provider_impl
        )

        token_service = TokenService(mock_session)

        # Act
        before_refresh = datetime.now(timezone.utc)
        asyncio.run(token_service.refresh_token(provider.id, user.id))

        # Assert - expiry was updated (should be ~2 hours from now)
        assert token.expires_at is not None
        expected_expiry = before_refresh + timedelta(seconds=7200)

        # Allow 10 second tolerance for test execution time
        time_diff = abs((token.expires_at - expected_expiry).total_seconds())
        assert time_diff < 10

    def test_rotation_audit_log_includes_all_details(
        self, mock_session, mock_encryption, mock_provider_registry
    ):
        """Test that audit log captures comprehensive rotation details."""
        # Arrange
        data = self.create_test_provider_with_token()
        provider = data["provider"]
        user = data["user"]

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_provider_impl = Mock()
        mock_provider_impl.refresh_authentication = AsyncMock(
            return_value={
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 3600,
            }
        )
        mock_provider_registry.create_provider_instance = Mock(
            return_value=mock_provider_impl
        )

        token_service = TokenService(mock_session)

        # Act
        asyncio.run(token_service.refresh_token(provider.id, user.id))

        # Assert - audit log was created
        # Check that session.add was called with ProviderAuditLog
        add_calls = mock_session.add.call_args_list
        audit_logs = [
            call[0][0] for call in add_calls if isinstance(call[0][0], ProviderAuditLog)
        ]

        assert len(audit_logs) > 0
        audit_log = audit_logs[0]

        # Check audit log details
        assert audit_log.user_id == user.id
        assert audit_log.action == "token_refreshed"
        assert "provider_key" in audit_log.details
        assert "alias" in audit_log.details
        assert "refresh_count" in audit_log.details
        assert "token_rotated" in audit_log.details
        assert "rotation_type" in audit_log.details


class TestTokenRotationEdgeCases:
    """Test edge cases and error scenarios in token rotation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.add = Mock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_encryption(self):
        """Create a mock encryption service."""
        with patch("src.services.token_service.get_encryption_service") as mock:
            encryption = Mock()
            encryption.encrypt = Mock(side_effect=lambda x: f"encrypted_{x}")
            encryption.decrypt = Mock(side_effect=lambda x: x.replace("encrypted_", ""))
            mock.return_value = encryption
            yield encryption

    @pytest.fixture
    def mock_provider_registry(self):
        """Create a mock provider registry."""
        with patch("src.services.token_service.ProviderRegistry") as mock:
            yield mock

    def test_rotation_fails_gracefully_on_provider_error(
        self, mock_session, mock_encryption, mock_provider_registry
    ):
        """Test that rotation failure is handled properly."""
        # Arrange
        user = User(
            id=uuid4(),
            email="test@example.com",
            name="Test User",
            external_id="test123",
        )

        provider = Provider(
            id=uuid4(),
            user_id=user.id,
            provider_key="schwab",
            alias="Test",
        )

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider.id,
            status=ProviderStatus.ACTIVE,
            error_count=0,
        )

        token = ProviderToken(
            id=uuid4(),
            connection_id=connection.id,
            access_token_encrypted="encrypted_access",
            refresh_token_encrypted="encrypted_refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        provider.connection = connection
        connection.token = token

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock provider to raise error
        mock_provider_impl = Mock()
        mock_provider_impl.refresh_authentication = AsyncMock(
            side_effect=Exception("Provider API error")
        )
        mock_provider_registry.create_provider_instance = Mock(
            return_value=mock_provider_impl
        )

        token_service = TokenService(mock_session)

        # Act & Assert
        with pytest.raises(Exception, match="Token refresh failed"):
            asyncio.run(token_service.refresh_token(provider.id, user.id))

        # Verify error state was recorded
        assert connection.error_count > 0
        assert "Token refresh failed" in connection.error_message

        # Verify failure audit log was created
        add_calls = mock_session.add.call_args_list
        audit_logs = [
            call[0][0] for call in add_calls if isinstance(call[0][0], ProviderAuditLog)
        ]
        assert len(audit_logs) > 0
        failure_log = audit_logs[-1]
        assert failure_log.action == "token_refresh_failed"
        assert "error" in failure_log.details

    def test_rotation_without_initial_refresh_token_fails(
        self, mock_session, mock_encryption
    ):
        """Test that rotation fails gracefully if no refresh token exists."""
        # Arrange
        user = User(
            id=uuid4(),
            email="test@example.com",
            name="Test User",
            external_id="test123",
        )

        provider = Provider(
            id=uuid4(),
            user_id=user.id,
            provider_key="schwab",
            alias="Test",
        )

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider.id,
            status=ProviderStatus.ACTIVE,
        )

        token = ProviderToken(
            id=uuid4(),
            connection_id=connection.id,
            access_token_encrypted="encrypted_access",
            refresh_token_encrypted=None,  # No refresh token!
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        provider.connection = connection
        connection.token = token

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        token_service = TokenService(mock_session)

        # Act & Assert
        with pytest.raises(ValueError, match="No refresh token available"):
            asyncio.run(token_service.refresh_token(provider.id, user.id))
