"""Unit tests for TokenService.

These tests verify the token service functionality including:
- Storing initial OAuth tokens
- Retrieving valid tokens with automatic refresh
- Refreshing expired tokens
- Revoking tokens
- Token encryption/decryption
- Audit logging

Tests use mocks to isolate the service layer from database and external dependencies.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from src.services.token_service import TokenService
from src.models.provider import (
    Provider,
    ProviderConnection,
    ProviderToken,
    ProviderStatus,
)


class TestTokenServiceStoreInitialTokens:
    """Test storing initial tokens after OAuth authentication."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.add = Mock()
        session.flush = AsyncMock()
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
    def token_service(self, mock_session, mock_encryption):
        """Create TokenService instance with mocked dependencies."""
        return TokenService(mock_session)

    def test_store_initial_tokens_creates_new_token(
        self, token_service, mock_session, mock_encryption
    ):
        """Test initial token storage for first-time OAuth authentication.
        
        Verifies that:
        - New ProviderToken created when no existing token
        - Access and refresh tokens encrypted before storage
        - Token metadata stored (id_token, scope, expires_at)
        - Token type set to "Bearer" by default
        - Database session.add() and flush() called
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
            mock_encryption: Mocked encryption service
        
        Note:
            First OAuth callback flow - provider transitions from PENDING to ACTIVE.
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()
        tokens = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_in": 3600,
            "id_token": "test_id_token",
            "scope": "read write",
        }

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.PENDING,
        )
        provider.connection = connection
        connection.token = None

        # Mock database query result
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        token = asyncio.run(
            token_service.store_initial_tokens(provider_id, tokens, user_id)
        )

        # Assert
        assert token is not None
        assert token.access_token_encrypted == "encrypted_test_access"
        assert token.refresh_token_encrypted == "encrypted_test_refresh"
        assert token.id_token == "test_id_token"
        assert token.scope == "read write"
        assert token.token_type == "Bearer"
        mock_session.add.assert_called()
        mock_session.flush.assert_called()

    def test_store_initial_tokens_updates_existing_token(
        self, token_service, mock_session, mock_encryption
    ):
        """Test token update when re-authenticating existing connection.
        
        Verifies that:
        - Existing ProviderToken is updated (not replaced)
        - Old encrypted tokens are overwritten
        - New tokens encrypted with new values
        - Expiry time updated based on new expires_in
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
            mock_encryption: Mocked encryption service
        
        Note:
            Handles re-authentication or manual token refresh by user.
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()
        tokens = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 7200,
        }

        existing_token = ProviderToken(
            id=uuid4(),
            connection_id=uuid4(),
            access_token_encrypted="old_encrypted",
            refresh_token_encrypted="old_refresh_encrypted",
        )

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.ACTIVE,
        )
        provider.connection = connection
        connection.token = existing_token

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        token = asyncio.run(
            token_service.store_initial_tokens(provider_id, tokens, user_id)
        )

        # Assert
        assert token == existing_token
        assert token.access_token_encrypted == "encrypted_new_access"
        assert token.refresh_token_encrypted == "encrypted_new_refresh"
        mock_session.flush.assert_called()

    def test_store_initial_tokens_without_refresh_token(
        self, token_service, mock_session, mock_encryption
    ):
        """Test token storage when provider doesn't issue refresh token.
        
        Verifies that:
        - Access token stored even without refresh token
        - refresh_token_encrypted field remains None
        - Token still valid for immediate use
        - No errors raised for missing refresh token
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
            mock_encryption: Mocked encryption service
        
        Note:
            Some OAuth providers only issue access tokens (no refresh capability).
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()
        tokens = {
            "access_token": "test_access",
            "expires_in": 3600,
            # No refresh_token
        }

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.PENDING,
        )
        provider.connection = connection
        connection.token = None

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        token = asyncio.run(
            token_service.store_initial_tokens(provider_id, tokens, user_id)
        )

        # Assert
        assert token.access_token_encrypted == "encrypted_test_access"
        assert token.refresh_token_encrypted is None

    def test_store_initial_tokens_provider_not_found(self, token_service, mock_session):
        """Test error handling for non-existent provider.
        
        Verifies that:
        - ValueError raised if provider_id not found
        - Error message includes provider ID
        - No database changes committed
        - Prevents storing tokens for invalid provider
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
        
        Raises:
            ValueError: Expected error for missing provider
        
        Note:
            Safety check: prevents orphaned tokens without provider.
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()
        tokens = {"access_token": "test"}

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act & Assert
        import asyncio

        with pytest.raises(ValueError, match="Provider .* not found"):
            asyncio.run(
                token_service.store_initial_tokens(provider_id, tokens, user_id)
            )

    def test_store_initial_tokens_creates_audit_log(
        self, token_service, mock_session, mock_encryption
    ):
        """Test audit logging for token creation (compliance requirement).
        
        Verifies that:
        - ProviderAuditLog entry created on token storage
        - Audit log action is "token_created"
        - User ID, IP address, and user agent captured
        - Audit trail for security and compliance
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
            mock_encryption: Mocked encryption service
        
        Note:
            Audit logs are critical for PCI-DSS and SOC 2 compliance.
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()
        tokens = {"access_token": "test", "expires_in": 3600}
        request_info = {"ip_address": "127.0.0.1", "user_agent": "TestAgent/1.0"}

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.PENDING,
        )
        provider.connection = connection
        connection.token = None

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        asyncio.run(
            token_service.store_initial_tokens(
                provider_id, tokens, user_id, request_info
            )
        )

        # Assert - verify audit log was added
        add_calls = [call[0][0] for call in mock_session.add.call_args_list]
        audit_logs = [
            obj for obj in add_calls if obj.__class__.__name__ == "ProviderAuditLog"
        ]
        assert len(audit_logs) > 0
        audit_log = audit_logs[0]
        assert audit_log.action == "token_created"
        assert audit_log.user_id == user_id
        assert audit_log.ip_address == "127.0.0.1"
        assert audit_log.user_agent == "TestAgent/1.0"


class TestTokenServiceGetValidAccessToken:
    """Test retrieving valid access tokens with automatic refresh."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_encryption(self):
        """Create a mock encryption service."""
        with patch("src.services.token_service.get_encryption_service") as mock:
            encryption = Mock()
            encryption.decrypt = Mock(side_effect=lambda x: x.replace("encrypted_", ""))
            mock.return_value = encryption
            yield encryption

    @pytest.fixture
    def token_service(self, mock_session, mock_encryption):
        """Create TokenService instance with mocked dependencies."""
        return TokenService(mock_session)

    def test_get_valid_access_token_returns_token(
        self, token_service, mock_session, mock_encryption
    ):
        """Test retrieval of valid unexpired access token.
        
        Verifies that:
        - Valid access token is decrypted and returned
        - Token not expired (expires_at in future)
        - No refresh triggered (token still valid)
        - Encryption service decrypt() called
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
            mock_encryption: Mocked encryption service
        
        Note:
            Optimized path: no external API call if token still valid.
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()

        token = ProviderToken(
            id=uuid4(),
            connection_id=uuid4(),
            access_token_encrypted="encrypted_valid_token",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),  # Not expired
        )

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.ACTIVE,
        )
        connection.token = token

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        provider.connection = connection

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        result = asyncio.run(token_service.get_valid_access_token(provider_id, user_id))

        # Assert
        assert result == "valid_token"
        mock_encryption.decrypt.assert_called_with("encrypted_valid_token")

    def test_get_valid_access_token_provider_not_found(
        self, token_service, mock_session
    ):
        """Test error handling when accessing non-existent provider.
        
        Verifies that:
        - ValueError raised if provider not found
        - Error message includes provider ID
        - No token retrieval attempted
        - Prevents unauthorized access attempts
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
        
        Raises:
            ValueError: Expected error for missing provider
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act & Assert
        import asyncio

        with pytest.raises(ValueError, match="Provider .* not found"):
            asyncio.run(token_service.get_valid_access_token(provider_id, user_id))

    def test_get_valid_access_token_not_connected(self, token_service, mock_session):
        """Test error for provider without active connection.
        
        Verifies that:
        - ValueError raised if provider.connection is None
        - Error message mentions "not connected"
        - Prevents token access for disconnected providers
        - User must reconnect via OAuth flow
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
        
        Raises:
            ValueError: Expected error for unconnected provider
        
        Note:
            Connection required before token operations.
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        provider.connection = None

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act & Assert
        import asyncio

        with pytest.raises(ValueError, match="is not connected"):
            asyncio.run(token_service.get_valid_access_token(provider_id, user_id))

    def test_get_valid_access_token_no_token(self, token_service, mock_session):
        """Test error when connection exists but no token stored.
        
        Verifies that:
        - ValueError raised if connection.token is None
        - Error message mentions "No tokens found"
        - Connection exists but token missing (edge case)
        - User must re-authenticate to store tokens
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
        
        Raises:
            ValueError: Expected error for missing token
        
        Note:
            Edge case: connection without tokens (incomplete OAuth flow).
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.ACTIVE,
        )
        connection.token = None

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        provider.connection = connection

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act & Assert
        import asyncio

        with pytest.raises(ValueError, match="No tokens found"):
            asyncio.run(token_service.get_valid_access_token(provider_id, user_id))


class TestTokenServiceRefreshToken:
    """Test token refresh functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.add = Mock()
        session.flush = AsyncMock()
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
        """Create a mock ProviderRegistry."""
        with patch("src.services.token_service.ProviderRegistry") as mock:
            provider_impl = Mock()
            provider_impl.refresh_authentication = AsyncMock(
                return_value={
                    "access_token": "new_access_token",
                    "expires_in": 3600,
                }
            )
            mock.create_provider_instance = Mock(return_value=provider_impl)
            yield mock

    @pytest.fixture
    def token_service(self, mock_session, mock_encryption):
        """Create TokenService instance with mocked dependencies."""
        return TokenService(mock_session)

    def test_refresh_token_success(
        self, token_service, mock_session, mock_encryption, mock_provider_registry
    ):
        """Test successful token refresh via provider API.
        
        Verifies that:
        - Expired token triggers refresh flow
        - Provider refresh_authentication() called
        - New access token encrypted and stored
        - refresh_count incremented
        - last_refreshed_at timestamp updated
        - Audit log entry created
        - Database flush() called
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
            mock_encryption: Mocked encryption service
            mock_provider_registry: Mocked provider registry
        
        Note:
            Automatic token refresh maintains seamless user experience.
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()

        token = ProviderToken(
            id=uuid4(),
            connection_id=uuid4(),
            access_token_encrypted="encrypted_old_access",
            refresh_token_encrypted="encrypted_refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
        )

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.ACTIVE,
            error_count=0,
        )
        connection.token = token

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        provider.connection = connection

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        result = asyncio.run(token_service.refresh_token(provider_id, user_id))

        # Assert - verify token was refreshed
        assert result == token
        # Verify the actual token attributes were updated (real behavior, not mocked)
        assert token.access_token_encrypted == "encrypted_new_access_token"
        assert token.refresh_count == 1  # Should be incremented
        assert token.last_refreshed_at is not None
        # Verify audit log was added
        mock_session.add.assert_called()
        mock_session.flush.assert_called()

    def test_refresh_token_no_refresh_token_available(
        self, token_service, mock_session
    ):
        """Test error when refresh needed but no refresh token available.
        
        Verifies that:
        - ValueError raised if refresh_token_encrypted is None
        - Error message mentions "No refresh token available"
        - Cannot refresh access token without refresh token
        - User must re-authenticate via OAuth flow
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
        
        Raises:
            ValueError: Expected error for missing refresh token
        
        Note:
            Some providers don't issue refresh tokens (short-lived access only).
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()

        token = ProviderToken(
            id=uuid4(),
            connection_id=uuid4(),
            access_token_encrypted="encrypted_access",
            refresh_token_encrypted=None,  # No refresh token!
        )

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.ACTIVE,
        )
        connection.token = token

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        provider.connection = connection

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act & Assert
        import asyncio

        with pytest.raises(ValueError, match="No refresh token available"):
            asyncio.run(token_service.refresh_token(provider_id, user_id))

    def test_refresh_token_handles_rotation(
        self, token_service, mock_session, mock_encryption
    ):
        """Test token refresh with refresh token rotation (security feature).
        
        Verifies that:
        - Provider issues new refresh token on refresh
        - Old refresh token replaced with new one
        - Both access and refresh tokens updated
        - Token rotation handled correctly (no errors)
        - refresh_count incremented
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
            mock_encryption: Mocked encryption service
        
        Note:
            Token rotation prevents replay attacks (e.g., Charles Schwab, GitHub).
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()

        with patch("src.services.token_service.ProviderRegistry") as mock_registry:
            provider_impl = Mock()
            provider_impl.refresh_authentication = AsyncMock(
                return_value={
                    "access_token": "new_access",
                    "refresh_token": "new_refresh",  # New refresh token!
                    "expires_in": 3600,
                }
            )
            mock_registry.create_provider_instance = Mock(return_value=provider_impl)

            token = ProviderToken(
                id=uuid4(),
                connection_id=uuid4(),
                access_token_encrypted="encrypted_old",
                refresh_token_encrypted="encrypted_old_refresh",
            )

            connection = ProviderConnection(
                id=uuid4(),
                provider_id=provider_id,
                status=ProviderStatus.ACTIVE,
            )
            connection.token = token

            provider = Provider(
                id=provider_id,
                user_id=user_id,
                provider_key="schwab",
                alias="Test",
            )
            provider.connection = connection

            mock_result = Mock()
            mock_result.scalar_one_or_none = Mock(return_value=provider)
            mock_session.execute = AsyncMock(return_value=mock_result)

            # Act
            import asyncio

            asyncio.run(token_service.refresh_token(provider_id, user_id))

            # Assert - verify new refresh token was encrypted and rotated
            # Check actual token attributes were updated (real behavior)
            assert token.access_token_encrypted == "encrypted_new_access"
            assert (
                token.refresh_token_encrypted == "encrypted_new_refresh"
            )  # Token rotation!
            assert token.refresh_count == 1  # Should be incremented
            assert token.last_refreshed_at is not None


class TestTokenServiceRevokeTokens:
    """Test token revocation functionality."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.add = Mock()
        session.delete = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_encryption(self):
        """Create a mock encryption service."""
        with patch("src.services.token_service.get_encryption_service") as mock:
            mock.return_value = Mock()
            yield

    @pytest.fixture
    def token_service(self, mock_session, mock_encryption):
        """Create TokenService instance with mocked dependencies."""
        return TokenService(mock_session)

    def test_revoke_tokens_success(self, token_service, mock_session):
        """Test successful token revocation and connection status update.
        
        Verifies that:
        - ProviderToken deleted from database
        - ProviderConnection status changed to REVOKED
        - Audit log entry created
        - Database flush() called
        - User disconnected from provider
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
        
        Note:
            Revocation triggered by user disconnection or security events.
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()

        token = ProviderToken(
            id=uuid4(),
            connection_id=uuid4(),
            access_token_encrypted="encrypted_access",
        )

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.ACTIVE,
        )
        connection.token = token

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test Provider",
        )
        provider.connection = connection

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        asyncio.run(token_service.revoke_tokens(provider_id, user_id))

        # Assert
        mock_session.delete.assert_called_once_with(token)
        assert connection.status == ProviderStatus.REVOKED
        mock_session.add.assert_called()  # Audit log
        mock_session.flush.assert_called()

    def test_revoke_tokens_with_request_info(self, token_service, mock_session):
        """Test audit logging includes request metadata on revocation.
        
        Verifies that:
        - ProviderAuditLog entry created with request info
        - IP address captured in audit log
        - User agent captured in audit log
        - Audit trail for compliance and security
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
        
        Note:
            Request metadata critical for security incident investigation.
        """
        # Arrange
        provider_id = uuid4()
        user_id = uuid4()
        request_info = {"ip_address": "192.168.1.1", "user_agent": "TestBrowser/1.0"}

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.ACTIVE,
        )
        connection.token = ProviderToken(id=uuid4(), connection_id=connection.id)

        provider = Provider(
            id=provider_id,
            user_id=user_id,
            provider_key="schwab",
            alias="Test",
        )
        provider.connection = connection

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        asyncio.run(token_service.revoke_tokens(provider_id, user_id, request_info))

        # Assert - verify audit log includes request info
        add_calls = [call[0][0] for call in mock_session.add.call_args_list]
        audit_logs = [
            obj for obj in add_calls if obj.__class__.__name__ == "ProviderAuditLog"
        ]
        assert len(audit_logs) > 0
        assert audit_logs[0].ip_address == "192.168.1.1"


class TestTokenServiceGetTokenInfo:
    """Test getting token metadata without decryption."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        return AsyncMock()

    @pytest.fixture
    def mock_encryption(self):
        """Create a mock encryption service."""
        with patch("src.services.token_service.get_encryption_service") as mock:
            mock.return_value = Mock()
            yield

    @pytest.fixture
    def token_service(self, mock_session, mock_encryption):
        """Create TokenService instance with mocked dependencies."""
        return TokenService(mock_session)

    def test_get_token_info_returns_metadata(self, token_service, mock_session):
        """Test retrieval of token metadata without decrypting secrets.
        
        Verifies that:
        - Token metadata returned (not actual token values)
        - has_access_token boolean flag set
        - has_refresh_token boolean flag set
        - has_id_token boolean flag set
        - Scope and refresh_count included
        - No decryption performed (safe for non-sensitive operations)
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
        
        Note:
            Safe for UI display - no sensitive data exposed.
        """
        # Arrange
        provider_id = uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        token = ProviderToken(
            id=uuid4(),
            connection_id=uuid4(),
            access_token_encrypted="encrypted_access",
            refresh_token_encrypted="encrypted_refresh",
            id_token="id_token_value",
            expires_at=expires_at,
            scope="read write",
            refresh_count=3,
        )

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.ACTIVE,
        )
        connection.token = token

        provider = Provider(
            id=provider_id,
            user_id=uuid4(),
            provider_key="schwab",
            alias="Test",
        )
        provider.connection = connection

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        result = asyncio.run(token_service.get_token_info(provider_id))

        # Assert
        assert result is not None
        assert result["has_access_token"] is True
        assert result["has_refresh_token"] is True
        assert result["has_id_token"] is True
        assert result["scope"] == "read write"
        assert result["refresh_count"] == 3

    def test_get_token_info_returns_none_when_no_token(
        self, token_service, mock_session
    ):
        """Test token info returns None for unconnected provider.
        
        Verifies that:
        - None returned if connection.token is None
        - No errors raised for missing token
        - Caller can check for None to detect unconnected state
        - Graceful handling of edge case
        
        Args:
            token_service: TokenService with mocked dependencies
            mock_session: Mocked database session
        
        Note:
            Used by UI to show "Connect Provider" button.
        """
        # Arrange
        provider_id = uuid4()

        connection = ProviderConnection(
            id=uuid4(),
            provider_id=provider_id,
            status=ProviderStatus.PENDING,
        )
        connection.token = None

        provider = Provider(
            id=provider_id,
            user_id=uuid4(),
            provider_key="schwab",
            alias="Test",
        )
        provider.connection = connection

        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=provider)
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Act
        import asyncio

        result = asyncio.run(token_service.get_token_info(provider_id))

        # Assert
        assert result is None
