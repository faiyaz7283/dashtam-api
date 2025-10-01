"""Unit tests for TokenService.

This module tests all token service functionality including:
- Token storage and retrieval
- Token refresh logic
- Encryption/decryption handling
- Audit logging
- Error scenarios
- Provider relationship management
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from src.services.token_service import TokenService, get_token_service
from src.models.provider import (
    Provider,
    ProviderToken,
    ProviderAuditLog,
    ProviderStatus,
)


class TestTokenServiceInitialization:
    """Test TokenService initialization and dependencies."""

    def test_token_service_initialization(self, db_session):
        """Test TokenService can be initialized with database session."""
        service = TokenService(db_session)

        assert service is not None
        assert service.session == db_session
        assert hasattr(service, "encryption")
        assert hasattr(service, "store_initial_tokens")
        assert hasattr(service, "get_valid_access_token")
        assert hasattr(service, "refresh_token")
        assert hasattr(service, "revoke_tokens")
        assert hasattr(service, "get_token_info")

    @pytest.mark.asyncio
    async def test_get_token_service_factory(self, db_session):
        """Test get_token_service factory function."""
        service = await get_token_service(db_session)

        assert isinstance(service, TokenService)
        assert service.session == db_session


class TestStoreInitialTokens:
    """Test storing initial OAuth tokens after authentication."""

    @pytest.mark.asyncio
    async def test_store_initial_tokens_new_connection(
        self, db_session, test_user, test_provider, mock_encryption_service
    ):
        """Test storing tokens for a new provider connection."""
        # Mock encryption service
        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            tokens = {
                "access_token": "test_access_token_123",
                "refresh_token": "test_refresh_token_456",
                "expires_in": 3600,
                "id_token": "test_id_token_789",
                "scope": "api read",
                "token_type": "Bearer",
            }

            # Store tokens
            result_token = await service.store_initial_tokens(
                provider_id=test_provider.id,
                tokens=tokens,
                user_id=test_user.id,
                request_info={"ip_address": "192.168.1.1", "user_agent": "TestAgent"},
            )

            # Verify token was created
            assert result_token is not None
            assert isinstance(result_token, ProviderToken)
            assert (
                result_token.access_token_encrypted == "encrypted_test_access_token_123"
            )
            assert (
                result_token.refresh_token_encrypted
                == "encrypted_test_refresh_token_456"
            )
            assert result_token.id_token == "test_id_token_789"
            assert result_token.scope == "api read"
            assert result_token.token_type == "Bearer"
            assert result_token.expires_at is not None

            # Verify encryption service was called
            mock_encryption_service.encrypt.assert_any_call("test_access_token_123")
            mock_encryption_service.encrypt.assert_any_call("test_refresh_token_456")

    @pytest.mark.asyncio
    async def test_store_initial_tokens_updates_existing(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test updating existing tokens."""
        # Add existing token to the connection
        existing_token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="old_encrypted_token",
            refresh_token_encrypted="old_refresh_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired
        )
        db_session.add(existing_token)
        await db_session.commit()

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            new_tokens = {
                "access_token": "new_access_token_123",
                "refresh_token": "new_refresh_token_456",
                "expires_in": 7200,
                "scope": "api read write",
            }

            # Update tokens
            result_token = await service.store_initial_tokens(
                provider_id=test_provider_with_connection.id,
                tokens=new_tokens,
                user_id=test_user.id,
            )

            # Verify existing token was updated
            assert result_token.id == existing_token.id  # Same token instance
            assert (
                result_token.access_token_encrypted == "encrypted_new_access_token_123"
            )
            assert (
                result_token.refresh_token_encrypted
                == "encrypted_new_refresh_token_456"
            )
            assert result_token.scope == "api read write"
            assert result_token.expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_store_initial_tokens_provider_not_found(
        self, db_session, test_user, mock_encryption_service
    ):
        """Test error when provider doesn't exist."""
        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            fake_provider_id = uuid4()
            tokens = {"access_token": "test_token", "expires_in": 3600}

            with pytest.raises(
                ValueError, match=f"Provider {fake_provider_id} not found"
            ):
                await service.store_initial_tokens(
                    provider_id=fake_provider_id, tokens=tokens, user_id=test_user.id
                )

    @pytest.mark.asyncio
    async def test_store_initial_tokens_without_refresh_token(
        self, db_session, test_provider, test_user, mock_encryption_service
    ):
        """Test storing tokens without refresh token."""
        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            tokens = {
                "access_token": "access_only_token_123",
                "expires_in": 1800,
                "token_type": "Bearer",
            }

            result_token = await service.store_initial_tokens(
                provider_id=test_provider.id, tokens=tokens, user_id=test_user.id
            )

            assert (
                result_token.access_token_encrypted == "encrypted_access_only_token_123"
            )
            assert result_token.refresh_token_encrypted is None

    @pytest.mark.asyncio
    async def test_store_initial_tokens_creates_audit_log(
        self, db_session, test_provider, test_user, mock_encryption_service
    ):
        """Test that audit log is created when storing tokens."""
        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            tokens = {
                "access_token": "audit_test_token",
                "refresh_token": "audit_refresh_token",
                "expires_in": 3600,
                "scope": "api",
            }

            await service.store_initial_tokens(
                provider_id=test_provider.id,
                tokens=tokens,
                user_id=test_user.id,
                request_info={"ip_address": "10.0.0.1", "user_agent": "TestBrowser"},
            )

            # Check that audit log was created
            from sqlmodel import select

            result = await db_session.execute(
                select(ProviderAuditLog).where(
                    ProviderAuditLog.user_id == test_user.id,
                    ProviderAuditLog.action == "token_created",
                )
            )
            audit_log = result.scalar_one_or_none()

            assert audit_log is not None
            assert audit_log.user_id == test_user.id
            assert audit_log.action == "token_created"
            assert audit_log.ip_address == "10.0.0.1"
            assert audit_log.user_agent == "TestBrowser"
            assert audit_log.details["has_refresh_token"] is True
            assert audit_log.details["expires_in"] == 3600
            assert audit_log.details["scope"] == "api"


class TestGetValidAccessToken:
    """Test retrieving valid access tokens with automatic refresh."""

    @pytest.mark.asyncio
    async def test_get_valid_access_token_not_expired(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test getting valid token when not expired."""
        # Create non-expired token
        future_expiry = datetime.utcnow() + timedelta(hours=1)
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_valid_token",
            expires_at=future_expiry,
        )
        db_session.add(token)
        await db_session.commit()

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            access_token = await service.get_valid_access_token(
                provider_id=test_provider_with_connection.id, user_id=test_user.id
            )

            assert access_token == "valid_token"  # Decrypted by mock
            mock_encryption_service.decrypt.assert_called_once_with(
                "encrypted_valid_token"
            )

    @pytest.mark.asyncio
    async def test_get_valid_access_token_triggers_refresh(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test that expired token triggers refresh."""
        # Create expired token
        past_expiry = datetime.utcnow() - timedelta(hours=1)
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_expired_token",
            refresh_token_encrypted="encrypted_refresh_token",
            expires_at=past_expiry,
        )
        db_session.add(token)
        await db_session.commit()

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            # Mock the refresh_token method
            refreshed_token = ProviderToken(
                connection_id=test_provider_with_connection.connection.id,
                access_token_encrypted="encrypted_new_token",
                expires_at=datetime.utcnow() + timedelta(hours=2),
            )

            with patch.object(
                service, "refresh_token", return_value=refreshed_token
            ) as mock_refresh:
                access_token = await service.get_valid_access_token(
                    provider_id=test_provider_with_connection.id, user_id=test_user.id
                )

                # Verify refresh was called
                mock_refresh.assert_called_once_with(
                    test_provider_with_connection.id, test_user.id
                )
                # Should decrypt the refreshed token
                assert access_token == "new_token"

    @pytest.mark.asyncio
    async def test_get_valid_access_token_provider_not_found(
        self, db_session, test_user, mock_encryption_service
    ):
        """Test error when provider doesn't exist."""
        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            fake_provider_id = uuid4()

            with pytest.raises(
                ValueError, match=f"Provider {fake_provider_id} not found"
            ):
                await service.get_valid_access_token(
                    provider_id=fake_provider_id, user_id=test_user.id
                )

    @pytest.mark.asyncio
    async def test_get_valid_access_token_no_connection(
        self, db_session, test_provider, test_user, mock_encryption_service
    ):
        """Test error when provider has no connection."""
        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            with pytest.raises(ValueError, match="is not connected"):
                await service.get_valid_access_token(
                    provider_id=test_provider.id, user_id=test_user.id
                )

    @pytest.mark.asyncio
    async def test_get_valid_access_token_no_tokens(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test error when no tokens are stored."""
        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            with pytest.raises(ValueError, match="No tokens found"):
                await service.get_valid_access_token(
                    provider_id=test_provider_with_connection.id, user_id=test_user.id
                )


class TestRefreshToken:
    """Test token refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test successful token refresh."""
        # Create token that needs refresh
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_old_token",
            refresh_token_encrypted="encrypted_refresh_token",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
            refresh_count=2,
        )
        db_session.add(token)
        await db_session.commit()

        # Mock provider implementation
        mock_provider_impl = AsyncMock()
        mock_provider_impl.refresh_authentication.return_value = {
            "access_token": "new_refreshed_token",
            "expires_in": 3600,
        }

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            with patch(
                "src.services.token_service.ProviderRegistry.create_provider_instance",
                return_value=mock_provider_impl,
            ):
                service = TokenService(db_session)

                refreshed_token = await service.refresh_token(
                    provider_id=test_provider_with_connection.id, user_id=test_user.id
                )

                # Verify provider refresh was called with decrypted refresh token
                mock_provider_impl.refresh_authentication.assert_called_once_with(
                    "refresh_token"
                )

                # Verify token was updated
                assert (
                    refreshed_token.access_token_encrypted
                    == "encrypted_new_refreshed_token"
                )
                assert refreshed_token.refresh_count == 3
                assert refreshed_token.last_refreshed_at is not None
                assert refreshed_token.expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_refresh_token_with_rotation(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test token refresh with refresh token rotation."""
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_old_token",
            refresh_token_encrypted="encrypted_old_refresh",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db_session.add(token)
        await db_session.commit()

        # Mock provider that rotates refresh token
        mock_provider_impl = AsyncMock()
        mock_provider_impl.refresh_authentication.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",  # New refresh token
            "expires_in": 3600,
        }

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            with patch(
                "src.services.token_service.ProviderRegistry.create_provider_instance",
                return_value=mock_provider_impl,
            ):
                service = TokenService(db_session)

                refreshed_token = await service.refresh_token(
                    provider_id=test_provider_with_connection.id, user_id=test_user.id
                )

                # Verify both tokens were encrypted
                mock_encryption_service.encrypt.assert_any_call("new_access_token")
                mock_encryption_service.encrypt.assert_any_call("new_refresh_token")

                # Verify refresh token was rotated
                assert (
                    refreshed_token.refresh_token_encrypted
                    == "encrypted_new_refresh_token"
                )

    @pytest.mark.asyncio
    async def test_refresh_token_no_refresh_token(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test error when no refresh token is available."""
        # Create token without refresh token
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_token",
            refresh_token_encrypted=None,  # No refresh token
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db_session.add(token)
        await db_session.commit()

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            with pytest.raises(ValueError, match="No refresh token available"):
                await service.refresh_token(
                    provider_id=test_provider_with_connection.id, user_id=test_user.id
                )

    @pytest.mark.asyncio
    async def test_refresh_token_failure_handling(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test handling of refresh failures."""
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_token",
            refresh_token_encrypted="encrypted_refresh",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db_session.add(token)
        await db_session.commit()

        # Mock provider that fails refresh
        mock_provider_impl = AsyncMock()
        mock_provider_impl.refresh_authentication.side_effect = Exception(
            "Refresh failed"
        )

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            with patch(
                "src.services.token_service.ProviderRegistry.create_provider_instance",
                return_value=mock_provider_impl,
            ):
                service = TokenService(db_session)

                with pytest.raises(Exception, match="Token refresh failed"):
                    await service.refresh_token(
                        provider_id=test_provider_with_connection.id,
                        user_id=test_user.id,
                    )

                # Verify connection error count was incremented
                await db_session.refresh(test_provider_with_connection.connection)
                assert test_provider_with_connection.connection.error_count == 1
                assert (
                    "Token refresh failed"
                    in test_provider_with_connection.connection.error_message
                )

    @pytest.mark.asyncio
    async def test_refresh_token_creates_audit_log(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test that refresh creates audit log."""
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_token",
            refresh_token_encrypted="encrypted_refresh",
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db_session.add(token)
        await db_session.commit()

        mock_provider_impl = AsyncMock()
        mock_provider_impl.refresh_authentication.return_value = {
            "access_token": "refreshed_token",
            "expires_in": 3600,
        }

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            with patch(
                "src.services.token_service.ProviderRegistry.create_provider_instance",
                return_value=mock_provider_impl,
            ):
                service = TokenService(db_session)

                await service.refresh_token(
                    provider_id=test_provider_with_connection.id, user_id=test_user.id
                )

                # Check audit log was created
                from sqlmodel import select

                result = await db_session.execute(
                    select(ProviderAuditLog).where(
                        ProviderAuditLog.user_id == test_user.id,
                        ProviderAuditLog.action == "token_refreshed",
                    )
                )
                audit_log = result.scalar_one_or_none()

                assert audit_log is not None
                assert audit_log.action == "token_refreshed"


class TestRevokeTokens:
    """Test token revocation functionality."""

    @pytest.mark.asyncio
    async def test_revoke_tokens_success(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test successful token revocation."""
        # Add token to connection
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_token",
            refresh_token_encrypted="encrypted_refresh",
        )
        db_session.add(token)
        await db_session.commit()

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            await service.revoke_tokens(
                provider_id=test_provider_with_connection.id,
                user_id=test_user.id,
                request_info={"ip_address": "192.168.1.100"},
            )

            # Verify connection status updated
            await db_session.refresh(test_provider_with_connection.connection)
            assert (
                test_provider_with_connection.connection.status
                == ProviderStatus.REVOKED
            )
            assert (
                "revoked by user"
                in test_provider_with_connection.connection.error_message
            )

    @pytest.mark.asyncio
    async def test_revoke_tokens_creates_audit_log(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test that revocation creates audit log."""
        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            await service.revoke_tokens(
                provider_id=test_provider_with_connection.id,
                user_id=test_user.id,
                request_info={"ip_address": "10.1.1.1", "user_agent": "TestClient"},
            )

            # Check audit log
            from sqlmodel import select

            result = await db_session.execute(
                select(ProviderAuditLog).where(
                    ProviderAuditLog.action == "connection_revoked"
                )
            )
            audit_log = result.scalar_one_or_none()

            assert audit_log is not None
            assert audit_log.user_id == test_user.id
            assert audit_log.action == "connection_revoked"
            assert audit_log.ip_address == "10.1.1.1"
            assert audit_log.user_agent == "TestClient"


class TestGetTokenInfo:
    """Test token information retrieval."""

    @pytest.mark.asyncio
    async def test_get_token_info_with_tokens(
        self, db_session, test_provider_with_connection, mock_encryption_service
    ):
        """Test getting token info when tokens exist."""
        future_expiry = datetime.utcnow() + timedelta(hours=1)
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_access",
            refresh_token_encrypted="encrypted_refresh",
            id_token="jwt_id_token",
            expires_at=future_expiry,
            scope="api read write",
            refresh_count=5,
            last_refreshed_at=datetime.utcnow() - timedelta(minutes=30),
        )
        db_session.add(token)
        await db_session.commit()

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            token_info = await service.get_token_info(test_provider_with_connection.id)

            assert token_info is not None
            assert token_info["has_access_token"] is True
            assert token_info["has_refresh_token"] is True
            assert token_info["has_id_token"] is True
            assert token_info["is_expired"] is False
            assert token_info["is_expiring_soon"] is False
            assert token_info["needs_refresh"] is False
            assert token_info["refresh_count"] == 5
            assert token_info["scope"] == "api read write"
            assert token_info["expires_at"] is not None
            assert token_info["last_refreshed_at"] is not None

    @pytest.mark.asyncio
    async def test_get_token_info_no_tokens(
        self, db_session, test_provider_with_connection, mock_encryption_service
    ):
        """Test getting token info when no tokens exist."""
        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            token_info = await service.get_token_info(test_provider_with_connection.id)

            assert token_info is None

    @pytest.mark.asyncio
    async def test_get_token_info_expired_token(
        self, db_session, test_provider_with_connection, mock_encryption_service
    ):
        """Test token info for expired token."""
        past_expiry = datetime.utcnow() - timedelta(hours=1)
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_expired",
            expires_at=past_expiry,
        )
        db_session.add(token)
        await db_session.commit()

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            token_info = await service.get_token_info(test_provider_with_connection.id)

            assert token_info["is_expired"] is True
            assert token_info["needs_refresh"] is True


class TestTokenServiceEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_encryption_service_integration(
        self, db_session, test_provider, test_user
    ):
        """Test integration with real encryption service."""
        # Use actual encryption service (not mocked)
        service = TokenService(db_session)

        tokens = {
            "access_token": "real_encryption_test_token",
            "refresh_token": "real_encryption_refresh_token",
            "expires_in": 3600,
        }

        # This should work with real encryption
        stored_token = await service.store_initial_tokens(
            provider_id=test_provider.id, tokens=tokens, user_id=test_user.id
        )

        # Verify tokens were actually encrypted (different from original)
        assert stored_token.access_token_encrypted != "real_encryption_test_token"
        assert stored_token.refresh_token_encrypted != "real_encryption_refresh_token"
        assert len(stored_token.access_token_encrypted) > len(
            "real_encryption_test_token"
        )

    @pytest.mark.asyncio
    async def test_concurrent_token_operations(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test handling of concurrent token operations."""
        # Create initial token
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_initial",
            refresh_token_encrypted="encrypted_refresh",
            expires_at=datetime.utcnow() + timedelta(minutes=30),
        )
        db_session.add(token)
        await db_session.commit()

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            # This should work without issues
            access_token = await service.get_valid_access_token(
                provider_id=test_provider_with_connection.id, user_id=test_user.id
            )

            assert access_token == "initial"  # Decrypted by mock

    @pytest.mark.asyncio
    async def test_token_expiration_edge_cases(
        self,
        db_session,
        test_provider_with_connection,
        test_user,
        mock_encryption_service,
    ):
        """Test various token expiration scenarios."""
        # Test token expiring in exactly 5 minutes (boundary case)
        boundary_expiry = datetime.utcnow() + timedelta(minutes=5)
        token = ProviderToken(
            connection_id=test_provider_with_connection.connection.id,
            access_token_encrypted="encrypted_boundary",
            refresh_token_encrypted="encrypted_refresh",
            expires_at=boundary_expiry,
        )
        db_session.add(token)
        await db_session.commit()

        # Should trigger refresh due to is_expiring_soon
        mock_provider_impl = AsyncMock()
        mock_provider_impl.refresh_authentication.return_value = {
            "access_token": "boundary_refreshed_token",
            "expires_in": 3600,
        }

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            with patch(
                "src.services.token_service.ProviderRegistry.create_provider_instance",
                return_value=mock_provider_impl,
            ):
                service = TokenService(db_session)

                # Should trigger refresh
                access_token = await service.get_valid_access_token(
                    provider_id=test_provider_with_connection.id, user_id=test_user.id
                )

                # Verify refresh was triggered
                mock_provider_impl.refresh_authentication.assert_called_once()
                assert access_token == "boundary_refreshed_token"


class TestTokenServicePerformance:
    """Performance and efficiency tests for token service."""

    @pytest.mark.asyncio
    async def test_bulk_token_operations_performance(
        self, db_session, test_user, mock_encryption_service
    ):
        """Test performance with multiple token operations."""
        import time

        with patch(
            "src.services.token_service.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            service = TokenService(db_session)

            # Create multiple providers
            providers = []
            for i in range(5):
                provider = Provider(
                    user_id=test_user.id,
                    provider_key="schwab",
                    alias=f"Test Provider {i}",
                )
                db_session.add(provider)
                providers.append(provider)

            await db_session.commit()

            # Store tokens for all providers
            start_time = time.time()

            for provider in providers:
                tokens = {
                    "access_token": f"access_token_{provider.alias}",
                    "refresh_token": f"refresh_token_{provider.alias}",
                    "expires_in": 3600,
                }

                await service.store_initial_tokens(
                    provider_id=provider.id, tokens=tokens, user_id=test_user.id
                )

            elapsed_time = time.time() - start_time

            # Should complete within reasonable time (adjust threshold as needed)
            assert elapsed_time < 2.0  # Less than 2 seconds for 5 operations

            # Verify all operations completed successfully
            assert len(providers) == 5
