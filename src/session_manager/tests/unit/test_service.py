"""Unit tests for SessionManagerService.

Tests orchestration of backend, storage, audit, and enrichers.
Uses mocks to test service logic in isolation.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.session_manager.models.filters import SessionFilters
from src.session_manager.service import SessionManagerService
from src.session_manager.tests.fixtures.mock_models import MockSession


@pytest.fixture
def mock_backend():
    """Mock session backend."""
    backend = AsyncMock()
    return backend


@pytest.fixture
def mock_storage():
    """Mock session storage."""
    storage = AsyncMock()
    return storage


@pytest.fixture
def mock_audit():
    """Mock audit backend."""
    audit = AsyncMock()
    return audit


@pytest.fixture
def mock_enricher():
    """Mock session enricher."""
    enricher = AsyncMock()
    return enricher


@pytest.fixture
def service(mock_backend, mock_storage, mock_audit):
    """Create service with mocked dependencies."""
    return SessionManagerService(
        backend=mock_backend,
        storage=mock_storage,
        audit=mock_audit,
    )


@pytest.fixture
def sample_session():
    """Create sample session for testing."""
    return MockSession(
        id=uuid4(),
        user_id="user123",
        ip_address="192.168.1.1",
        device_info="Mozilla/5.0",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    )


class TestServiceInitialization:
    """Test service initialization."""

    def test_init_with_all_dependencies(self, mock_backend, mock_storage, mock_audit):
        """Test service initialization with all dependencies."""
        enrichers = [AsyncMock()]

        service = SessionManagerService(
            backend=mock_backend,
            storage=mock_storage,
            audit=mock_audit,
            enrichers=enrichers,
        )

        assert service.backend == mock_backend
        assert service.storage == mock_storage
        assert service.audit == mock_audit
        assert service.enrichers == enrichers

    def test_init_defaults_to_noop_audit(self, mock_backend, mock_storage):
        """Test that audit defaults to NoOp if not provided."""
        service = SessionManagerService(
            backend=mock_backend,
            storage=mock_storage,
        )

        # Should default to NoOpAuditBackend
        assert service.audit is not None
        assert service.audit.__class__.__name__ == "NoOpAuditBackend"

    def test_init_defaults_to_empty_enrichers(self, mock_backend, mock_storage):
        """Test that enrichers default to empty list."""
        service = SessionManagerService(
            backend=mock_backend,
            storage=mock_storage,
        )

        assert service.enrichers == []


class TestCreateSession:
    """Test session creation flow."""

    @pytest.mark.asyncio
    async def test_create_session_success(
        self, service, mock_backend, mock_storage, mock_audit, sample_session
    ):
        """Test successful session creation with all steps."""
        # Arrange
        mock_backend.create_session.return_value = sample_session
        mock_storage.save_session.return_value = None
        mock_audit.log_session_created.return_value = None

        # Act
        result = await service.create_session(
            user_id="user123",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )

        # Assert
        assert result == sample_session

        # Verify backend called
        mock_backend.create_session.assert_awaited_once_with(
            user_id="user123",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )

        # Verify storage called
        mock_storage.save_session.assert_awaited_once_with(sample_session)

        # Verify audit called
        mock_audit.log_session_created.assert_awaited_once()
        call_args = mock_audit.log_session_created.call_args
        assert call_args[0][0] == sample_session  # First positional arg
        assert "device" in call_args[1]["context"]  # Keyword arg 'context'

    @pytest.mark.asyncio
    async def test_create_session_with_enrichers(
        self, mock_backend, mock_storage, mock_audit, sample_session
    ):
        """Test that enrichers are called during session creation."""
        # Arrange
        enricher1 = AsyncMock()
        enricher2 = AsyncMock()

        # Enrichers modify session
        enriched_session_1 = MagicMock()
        enriched_session_2 = MagicMock()
        enricher1.enrich.return_value = enriched_session_1
        enricher2.enrich.return_value = enriched_session_2

        service = SessionManagerService(
            backend=mock_backend,
            storage=mock_storage,
            audit=mock_audit,
            enrichers=[enricher1, enricher2],
        )

        mock_backend.create_session.return_value = sample_session

        # Act
        result = await service.create_session(
            user_id="user123",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.1",
        )

        # Assert
        # Enricher 1 called with original session
        enricher1.enrich.assert_awaited_once_with(sample_session)

        # Enricher 2 called with enriched session from enricher 1
        enricher2.enrich.assert_awaited_once_with(enriched_session_1)

        # Storage receives final enriched session
        mock_storage.save_session.assert_awaited_once_with(enriched_session_2)

        # Service returns final enriched session
        assert result == enriched_session_2

    @pytest.mark.asyncio
    async def test_create_session_enricher_failure_non_critical(
        self, mock_backend, mock_storage, mock_audit, sample_session
    ):
        """Test that enricher failures don't block session creation."""
        # Arrange
        failing_enricher = AsyncMock()
        failing_enricher.enrich.side_effect = Exception("Enricher failed")

        service = SessionManagerService(
            backend=mock_backend,
            storage=mock_storage,
            audit=mock_audit,
            enrichers=[failing_enricher],
        )

        mock_backend.create_session.return_value = sample_session

        # Act
        result = await service.create_session(
            user_id="user123",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.1",
        )

        # Assert - session created despite enricher failure
        assert result == sample_session
        mock_storage.save_session.assert_awaited_once_with(sample_session)
        mock_audit.log_session_created.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_session_with_metadata(
        self, service, mock_backend, sample_session
    ):
        """Test that additional metadata is passed to backend."""
        # Arrange
        mock_backend.create_session.return_value = sample_session

        # Act
        await service.create_session(
            user_id="user123",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.1",
            custom_field="custom_value",
            another_field=123,
        )

        # Assert - metadata passed through
        mock_backend.create_session.assert_awaited_once_with(
            user_id="user123",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.1",
            user_agent=None,
            custom_field="custom_value",
            another_field=123,
        )


class TestGetSession:
    """Test get session."""

    @pytest.mark.asyncio
    async def test_get_session_found(self, service, mock_storage, sample_session):
        """Test getting existing session."""
        # Arrange
        mock_storage.get_session.return_value = sample_session

        # Act
        result = await service.get_session(str(sample_session.id))

        # Assert
        assert result == sample_session
        mock_storage.get_session.assert_awaited_once_with(str(sample_session.id))

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, service, mock_storage):
        """Test getting non-existent session."""
        # Arrange
        mock_storage.get_session.return_value = None

        # Act
        result = await service.get_session("nonexistent")

        # Assert
        assert result is None
        mock_storage.get_session.assert_awaited_once_with("nonexistent")


class TestValidateSession:
    """Test session validation."""

    @pytest.mark.asyncio
    async def test_validate_session_valid(
        self, service, mock_storage, mock_backend, sample_session
    ):
        """Test validating active session."""
        # Arrange
        mock_storage.get_session.return_value = sample_session
        mock_backend.validate_session.return_value = True

        # Act
        result = await service.validate_session(str(sample_session.id))

        # Assert
        assert result is True
        mock_storage.get_session.assert_awaited_once_with(str(sample_session.id))
        mock_backend.validate_session.assert_awaited_once_with(sample_session)

    @pytest.mark.asyncio
    async def test_validate_session_invalid(
        self, service, mock_storage, mock_backend, sample_session
    ):
        """Test validating invalid session."""
        # Arrange
        mock_storage.get_session.return_value = sample_session
        mock_backend.validate_session.return_value = False

        # Act
        result = await service.validate_session(str(sample_session.id))

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_session_not_found(self, service, mock_storage):
        """Test validating non-existent session."""
        # Arrange
        mock_storage.get_session.return_value = None

        # Act
        result = await service.validate_session("nonexistent")

        # Assert
        assert result is False
        mock_storage.get_session.assert_awaited_once_with("nonexistent")


class TestListSessions:
    """Test listing sessions."""

    @pytest.mark.asyncio
    async def test_list_sessions_without_filters(self, service, mock_storage):
        """Test listing sessions without filters."""
        # Arrange
        sessions = [MagicMock(), MagicMock()]
        mock_storage.list_sessions.return_value = sessions

        # Act
        result = await service.list_sessions("user123")

        # Assert
        assert result == sessions
        mock_storage.list_sessions.assert_awaited_once_with("user123", None)

    @pytest.mark.asyncio
    async def test_list_sessions_with_filters(self, service, mock_storage):
        """Test listing sessions with filters."""
        # Arrange
        filters = SessionFilters(active_only=True, device_type="mobile", limit=10)
        sessions = [MagicMock()]
        mock_storage.list_sessions.return_value = sessions

        # Act
        result = await service.list_sessions("user123", filters)

        # Assert
        assert result == sessions
        mock_storage.list_sessions.assert_awaited_once_with("user123", filters)


class TestRevokeSession:
    """Test session revocation."""

    @pytest.mark.asyncio
    async def test_revoke_session_success(
        self, service, mock_storage, mock_audit, sample_session
    ):
        """Test successful session revocation."""
        # Arrange
        mock_storage.get_session.return_value = sample_session
        mock_storage.revoke_session.return_value = True

        # Act
        result = await service.revoke_session(
            str(sample_session.id),
            reason="user_logout",
            context={"ip": "192.168.1.1"},
        )

        # Assert
        assert result is True
        mock_storage.get_session.assert_awaited_once_with(str(sample_session.id))
        mock_storage.revoke_session.assert_awaited_once_with(
            str(sample_session.id), "user_logout"
        )
        mock_audit.log_session_revoked.assert_awaited_once_with(
            str(sample_session.id), "user_logout", context={"ip": "192.168.1.1"}
        )

    @pytest.mark.asyncio
    async def test_revoke_session_not_found(self, service, mock_storage, mock_audit):
        """Test revoking non-existent session."""
        # Arrange
        mock_storage.get_session.return_value = None

        # Act
        result = await service.revoke_session("nonexistent", reason="test")

        # Assert
        assert result is False
        mock_storage.get_session.assert_awaited_once_with("nonexistent")
        mock_storage.revoke_session.assert_not_awaited()
        mock_audit.log_session_revoked.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_revoke_session_without_context(
        self, service, mock_storage, mock_audit, sample_session
    ):
        """Test revoking session without context."""
        # Arrange
        mock_storage.get_session.return_value = sample_session
        mock_storage.revoke_session.return_value = True

        # Act
        result = await service.revoke_session(str(sample_session.id), reason="test")

        # Assert
        assert result is True
        # Context should default to empty dict
        mock_audit.log_session_revoked.assert_awaited_once_with(
            str(sample_session.id), "test", context={}
        )


class TestDeleteSession:
    """Test session deletion."""

    @pytest.mark.asyncio
    async def test_delete_session_success(self, service, mock_storage):
        """Test successful session deletion."""
        # Arrange
        mock_storage.delete_session.return_value = True

        # Act
        result = await service.delete_session("session123")

        # Assert
        assert result is True
        mock_storage.delete_session.assert_awaited_once_with("session123")

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, service, mock_storage):
        """Test deleting non-existent session."""
        # Arrange
        mock_storage.delete_session.return_value = False

        # Act
        result = await service.delete_session("nonexistent")

        # Assert
        assert result is False


class TestRevokeAllUserSessions:
    """Test revoking all sessions for user."""

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_success(self, service, mock_storage, mock_audit):
        """Test revoking all user sessions."""
        # Arrange
        session1 = MagicMock()
        session1.id = uuid4()
        session2 = MagicMock()
        session2.id = uuid4()

        mock_storage.list_sessions.return_value = [session1, session2]
        mock_storage.get_session.return_value = session1  # For first call
        mock_storage.revoke_session.return_value = True

        # Act
        count = await service.revoke_all_user_sessions(
            "user123", reason="security_breach"
        )

        # Assert
        assert count == 2
        mock_storage.list_sessions.assert_awaited_once_with("user123")
        assert mock_storage.revoke_session.await_count == 2

    @pytest.mark.asyncio
    async def test_revoke_all_except_current(self, service, mock_storage, mock_audit):
        """Test revoking all sessions except current."""
        # Arrange
        session1 = MagicMock()
        session1.id = uuid4()
        session2 = MagicMock()
        session2.id = uuid4()
        current_session_id = str(session1.id)

        mock_storage.list_sessions.return_value = [session1, session2]
        mock_storage.get_session.return_value = session2  # For second call only
        mock_storage.revoke_session.return_value = True

        # Act
        count = await service.revoke_all_user_sessions(
            "user123", reason="password_change", except_session_id=current_session_id
        )

        # Assert
        assert count == 1  # Only session2 revoked
        # Should only revoke session2, not session1 (current)
        mock_storage.revoke_session.assert_awaited_once_with(
            str(session2.id), "password_change"
        )

    @pytest.mark.asyncio
    async def test_revoke_all_sessions_empty_list(self, service, mock_storage):
        """Test revoking when user has no sessions."""
        # Arrange
        mock_storage.list_sessions.return_value = []

        # Act
        count = await service.revoke_all_user_sessions("user123", reason="test")

        # Assert
        assert count == 0
        mock_storage.revoke_session.assert_not_awaited()


class TestLogSuspiciousActivity:
    """Test logging suspicious activity."""

    @pytest.mark.asyncio
    async def test_log_suspicious_activity(self, service, mock_audit):
        """Test logging suspicious activity."""
        # Act
        await service.log_suspicious_activity(
            session_id="session123",
            event="multiple_failed_logins",
            context={"attempts": 5, "ip": "192.168.1.1"},
        )

        # Assert
        mock_audit.log_suspicious_activity.assert_awaited_once_with(
            "session123",
            "multiple_failed_logins",
            {"attempts": 5, "ip": "192.168.1.1"},
        )
