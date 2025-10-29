"""Unit tests for SessionManagementService.

Tests session listing, revocation, and bulk operations with cache integration.

Note: These are synchronous tests (regular def, not async def) following
the project testing strategy. We use asyncio.run() to call async service methods.
"""

import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from fastapi import HTTPException

from src.models.auth import RefreshToken
from src.models.user import User
from src.services.session_management_service import (
    SessionManagementService,
    SessionInfo,
)


class TestSessionManagementServiceListSessions:
    """Test suite for listing active sessions."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_cache(self):
        """Create a mock CacheBackend."""
        cache = Mock()
        cache.set = AsyncMock()
        cache.exists = AsyncMock(return_value=False)
        return cache

    @pytest.fixture
    def mock_geo_service(self):
        """Create a mock GeolocationService."""
        service = Mock()
        service.get_location = Mock(return_value="Mountain View, United States")
        return service

    @pytest.fixture
    def user_fixture(self):
        """Create a test user."""
        return User(
            id=uuid4(),
            email="test@example.com",
            password_hash="hash",
            email_verified=True,
            is_active=True,
        )

    @pytest.fixture
    def refresh_tokens_fixture(self, user_fixture):
        """Create multiple test refresh tokens."""
        now = datetime.now(timezone.utc)
        token1 = RefreshToken(
            id=uuid4(),
            user_id=user_fixture.id,
            token_hash="hash1",
            expires_at=now + timedelta(days=30),
            is_revoked=False,
            device_info="Chrome on macOS",
            location="San Francisco, USA",
            ip_address="192.168.1.1",
            last_used_at=now - timedelta(hours=1),
            created_at=now - timedelta(days=5),
            is_trusted_device=True,
        )
        token2 = RefreshToken(
            id=uuid4(),
            user_id=user_fixture.id,
            token_hash="hash2",
            expires_at=now + timedelta(days=30),
            is_revoked=False,
            device_info="Firefox on Windows",
            location="New York, USA",
            ip_address="192.168.1.2",
            last_used_at=now - timedelta(hours=5),
            created_at=now - timedelta(days=10),
            is_trusted_device=False,
        )
        token3 = RefreshToken(
            id=uuid4(),
            user_id=user_fixture.id,
            token_hash="hash3",
            expires_at=now + timedelta(days=30),
            is_revoked=True,  # Revoked
            device_info="Safari on iPhone",
            location="Los Angeles, USA",
            ip_address="192.168.1.3",
            last_used_at=now - timedelta(hours=2),
            created_at=now - timedelta(days=2),
            is_trusted_device=True,
        )
        return [token1, token2, token3]

    def test_list_sessions_returns_all_active(
        self,
        mock_session,
        mock_cache,
        mock_geo_service,
        user_fixture,
        refresh_tokens_fixture,
    ):
        """Test list_sessions returns only non-revoked tokens."""
        # Arrange
        active_tokens = [t for t in refresh_tokens_fixture if not t.is_revoked]
        result = Mock()
        result.scalars = Mock(return_value=Mock(all=Mock(return_value=active_tokens)))
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        sessions = asyncio.run(service.list_sessions(user_fixture.id))

        # Assert
        assert len(sessions) == 2  # Only non-revoked
        assert all(isinstance(s, SessionInfo) for s in sessions)
        assert sessions[0].device_info == "Chrome on macOS"
        assert sessions[1].device_info == "Firefox on Windows"

    def test_list_sessions_sorted_by_activity(
        self,
        mock_session,
        mock_cache,
        mock_geo_service,
        user_fixture,
        refresh_tokens_fixture,
    ):
        """Test list_sessions returns sessions sorted by last activity (DESC)."""
        # Arrange
        active_tokens = [t for t in refresh_tokens_fixture if not t.is_revoked]
        result = Mock()
        result.scalars = Mock(return_value=Mock(all=Mock(return_value=active_tokens)))
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        sessions = asyncio.run(service.list_sessions(user_fixture.id))

        # Assert - most recent first (1 hour ago before 5 hours ago)
        assert sessions[0].last_activity > sessions[1].last_activity

    def test_list_sessions_detects_current(
        self,
        mock_session,
        mock_cache,
        mock_geo_service,
        user_fixture,
        refresh_tokens_fixture,
    ):
        """Test list_sessions correctly identifies current session."""
        # Arrange
        active_tokens = [t for t in refresh_tokens_fixture if not t.is_revoked]
        current_token_id = active_tokens[0].id
        result = Mock()
        result.scalars = Mock(return_value=Mock(all=Mock(return_value=active_tokens)))
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        sessions = asyncio.run(service.list_sessions(user_fixture.id, current_token_id))

        # Assert
        assert sessions[0].is_current is True
        assert sessions[1].is_current is False

    def test_list_sessions_excludes_revoked(
        self,
        mock_session,
        mock_cache,
        mock_geo_service,
        user_fixture,
        refresh_tokens_fixture,
    ):
        """Test list_sessions excludes revoked tokens."""
        # Arrange
        active_tokens = [t for t in refresh_tokens_fixture if not t.is_revoked]
        result = Mock()
        result.scalars = Mock(return_value=Mock(all=Mock(return_value=active_tokens)))
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        sessions = asyncio.run(service.list_sessions(user_fixture.id))

        # Assert
        revoked_token = next(t for t in refresh_tokens_fixture if t.is_revoked)
        assert not any(s.id == revoked_token.id for s in sessions)

    def test_list_sessions_backfills_location(
        self, mock_session, mock_cache, mock_geo_service, user_fixture
    ):
        """Test list_sessions backfills missing location using geolocation service."""
        # Arrange - token with missing location
        now = datetime.now(timezone.utc)
        token_without_location = RefreshToken(
            id=uuid4(),
            user_id=user_fixture.id,
            token_hash="hash",
            expires_at=now + timedelta(days=30),
            is_revoked=False,
            device_info="Chrome on Linux",
            location=None,  # Missing location
            ip_address="8.8.8.8",
            last_used_at=now,
            created_at=now,
            is_trusted_device=True,
        )
        result = Mock()
        result.scalars = Mock(
            return_value=Mock(all=Mock(return_value=[token_without_location]))
        )
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        sessions = asyncio.run(service.list_sessions(user_fixture.id))

        # Assert - geolocation service called
        mock_geo_service.get_location.assert_called_once_with("8.8.8.8")
        assert sessions[0].location == "Mountain View, United States"
        mock_session.commit.assert_called_once()


class TestSessionManagementServiceRevokeSession:
    """Test suite for revoking specific session."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_cache(self):
        """Create a mock CacheBackend."""
        cache = Mock()
        cache.set = AsyncMock()
        cache.exists = AsyncMock(return_value=False)
        return cache

    @pytest.fixture
    def mock_geo_service(self):
        """Create a mock GeolocationService."""
        return Mock()

    @pytest.fixture
    def user_fixture(self):
        """Create a test user."""
        return User(
            id=uuid4(),
            email="test@example.com",
            password_hash="hash",
            email_verified=True,
            is_active=True,
        )

    @pytest.fixture
    def valid_token(self, user_fixture):
        """Create a valid refresh token."""
        now = datetime.now(timezone.utc)
        return RefreshToken(
            id=uuid4(),
            user_id=user_fixture.id,
            token_hash="hash",
            expires_at=now + timedelta(days=30),
            is_revoked=False,
            device_info="Chrome on macOS",
            location="San Francisco, USA",
            ip_address="192.168.1.1",
            last_used_at=now,
            created_at=now,
            is_trusted_device=True,
        )

    def test_revoke_session_success(
        self, mock_session, mock_cache, mock_geo_service, user_fixture, valid_token
    ):
        """Test revoke_session successfully revokes session."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=valid_token)
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        asyncio.run(
            service.revoke_session(
                user_id=user_fixture.id,
                session_id=valid_token.id,
                current_session_id=uuid4(),  # Different from target
                revoked_by_ip="192.168.1.100",
                revoked_by_device="Firefox on Windows",
            )
        )

        # Assert
        assert valid_token.is_revoked is True
        mock_session.commit.assert_called_once()

    def test_revoke_session_adds_to_cache(
        self, mock_session, mock_cache, mock_geo_service, user_fixture, valid_token
    ):
        """Test revoke_session adds token to cache blacklist."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=valid_token)
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        asyncio.run(
            service.revoke_session(
                user_id=user_fixture.id,
                session_id=valid_token.id,
                current_session_id=uuid4(),
                revoked_by_ip="192.168.1.100",
                revoked_by_device="Firefox on Windows",
            )
        )

        # Assert - cache set called with correct params
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert f"revoked_token:{valid_token.id}" in call_args[0][0]
        assert call_args[0][1] == "1"
        assert call_args[1]["ttl_seconds"] == 2592000  # 30 days

    def test_revoke_session_prevents_self_revocation(
        self, mock_session, mock_cache, mock_geo_service, user_fixture, valid_token
    ):
        """Test revoke_session raises 400 if trying to revoke current session."""
        # Arrange
        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                service.revoke_session(
                    user_id=user_fixture.id,
                    session_id=valid_token.id,
                    current_session_id=valid_token.id,  # Same as target
                    revoked_by_ip="192.168.1.100",
                    revoked_by_device="Chrome on macOS",
                )
            )

        assert exc_info.value.status_code == 400
        assert "cannot revoke current session" in exc_info.value.detail.lower()

    def test_revoke_session_not_found(
        self, mock_session, mock_cache, mock_geo_service, user_fixture
    ):
        """Test revoke_session raises 404 if session doesn't exist."""
        # Arrange
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                service.revoke_session(
                    user_id=user_fixture.id,
                    session_id=uuid4(),
                    current_session_id=uuid4(),
                    revoked_by_ip="192.168.1.100",
                    revoked_by_device="Chrome on macOS",
                )
            )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    def test_revoke_session_already_revoked(
        self, mock_session, mock_cache, mock_geo_service, user_fixture, valid_token
    ):
        """Test revoke_session raises 400 if session already revoked."""
        # Arrange - token already revoked
        valid_token.revoke()
        result = Mock()
        result.scalar_one_or_none = Mock(return_value=valid_token)
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                service.revoke_session(
                    user_id=user_fixture.id,
                    session_id=valid_token.id,
                    current_session_id=uuid4(),
                    revoked_by_ip="192.168.1.100",
                    revoked_by_device="Chrome on macOS",
                )
            )

        assert exc_info.value.status_code == 400
        assert "already revoked" in exc_info.value.detail.lower()


class TestSessionManagementServiceBulkRevocation:
    """Test suite for bulk session revocation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    @pytest.fixture
    def mock_cache(self):
        """Create a mock CacheBackend."""
        cache = Mock()
        cache.set = AsyncMock()
        cache.exists = AsyncMock(return_value=False)
        return cache

    @pytest.fixture
    def mock_geo_service(self):
        """Create a mock GeolocationService."""
        return Mock()

    @pytest.fixture
    def user_fixture(self):
        """Create a test user."""
        return User(
            id=uuid4(),
            email="test@example.com",
            password_hash="hash",
            email_verified=True,
            is_active=True,
        )

    @pytest.fixture
    def multiple_tokens(self, user_fixture):
        """Create multiple refresh tokens."""
        now = datetime.now(timezone.utc)
        tokens = []
        for i in range(3):
            token = RefreshToken(
                id=uuid4(),
                user_id=user_fixture.id,
                token_hash=f"hash{i}",
                expires_at=now + timedelta(days=30),
                is_revoked=False,
                device_info=f"Device {i}",
                location="Location",
                ip_address=f"192.168.1.{i}",
                last_used_at=now,
                created_at=now,
                is_trusted_device=True,
            )
            tokens.append(token)
        return tokens

    def test_revoke_other_sessions(
        self, mock_session, mock_cache, mock_geo_service, user_fixture, multiple_tokens
    ):
        """Test revoke_other_sessions keeps current, revokes others."""
        # Arrange
        current_session_id = multiple_tokens[0].id
        other_tokens = multiple_tokens[1:]
        result = Mock()
        result.scalars = Mock(return_value=Mock(all=Mock(return_value=other_tokens)))
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        count = asyncio.run(
            service.revoke_other_sessions(user_fixture.id, current_session_id)
        )

        # Assert
        assert count == 2
        assert all(t.is_revoked for t in other_tokens)
        mock_session.commit.assert_called_once()

    def test_revoke_other_sessions_count(
        self, mock_session, mock_cache, mock_geo_service, user_fixture, multiple_tokens
    ):
        """Test revoke_other_sessions returns correct count."""
        # Arrange
        current_session_id = multiple_tokens[0].id
        other_tokens = multiple_tokens[1:]
        result = Mock()
        result.scalars = Mock(return_value=Mock(all=Mock(return_value=other_tokens)))
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        count = asyncio.run(
            service.revoke_other_sessions(user_fixture.id, current_session_id)
        )

        # Assert
        assert count == len(other_tokens)

    def test_revoke_all_sessions(
        self, mock_session, mock_cache, mock_geo_service, user_fixture, multiple_tokens
    ):
        """Test revoke_all_sessions revokes everything including current."""
        # Arrange
        result = Mock()
        result.scalars = Mock(return_value=Mock(all=Mock(return_value=multiple_tokens)))
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        count = asyncio.run(service.revoke_all_sessions(user_fixture.id))

        # Assert
        assert count == 3
        assert all(t.is_revoked for t in multiple_tokens)
        mock_session.commit.assert_called_once()

    def test_revoke_all_sessions_count(
        self, mock_session, mock_cache, mock_geo_service, user_fixture, multiple_tokens
    ):
        """Test revoke_all_sessions returns correct count."""
        # Arrange
        result = Mock()
        result.scalars = Mock(return_value=Mock(all=Mock(return_value=multiple_tokens)))
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        count = asyncio.run(service.revoke_all_sessions(user_fixture.id))

        # Assert
        assert count == len(multiple_tokens)

    def test_revoke_all_sessions_blacklists_all(
        self, mock_session, mock_cache, mock_geo_service, user_fixture, multiple_tokens
    ):
        """Test revoke_all_sessions adds all tokens to cache blacklist."""
        # Arrange
        result = Mock()
        result.scalars = Mock(return_value=Mock(all=Mock(return_value=multiple_tokens)))
        mock_session.execute = AsyncMock(return_value=result)

        service = SessionManagementService(mock_session, mock_geo_service, mock_cache)

        # Act
        asyncio.run(service.revoke_all_sessions(user_fixture.id))

        # Assert - cache.set called for each token
        assert mock_cache.set.call_count == len(multiple_tokens)
