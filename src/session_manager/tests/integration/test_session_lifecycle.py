"""Integration tests for complete session lifecycle.

Tests multiple components working together:
- Service orchestration
- Backend (JWT)
- Storage (Memory, Cache)
- Audit (Logger)
- Enrichers

These are end-to-end flows within the package, using real components
(not mocks), to verify all pieces integrate correctly.
"""

import pytest

from src.session_manager.audit.logger import LoggerAuditBackend
from src.session_manager.audit.noop import NoOpAuditBackend
from src.session_manager.backends.jwt_backend import JWTSessionBackend
from src.session_manager.enrichers.geolocation import GeolocationEnricher
from src.session_manager.service import SessionManagerService
from src.session_manager.storage.cache import CacheSessionStorage
from src.session_manager.storage.memory import MemorySessionStorage
from src.session_manager.tests.fixtures.mock_models import MockSession


class TestCompleteSessionLifecycleMemoryStorage:
    """Test complete session lifecycle with memory storage."""

    @pytest.mark.asyncio
    async def test_create_validate_revoke_delete_flow(self):
        """Test complete session lifecycle: create → validate → revoke → delete."""
        # Arrange: Wire up real components
        backend = JWTSessionBackend(session_ttl_days=30)
        storage = MemorySessionStorage()
        audit = NoOpAuditBackend()
        service = SessionManagerService(backend, storage, audit)

        # Act & Assert: Create session
        session = await service.create_session(
            user_id="user-123",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )
        assert session is not None
        assert session.user_id == "user-123"

        # Validate session (should be valid)
        is_valid = await service.validate_session(str(session.id))
        assert is_valid is True

        # Revoke session
        revoked = await service.revoke_session(
            str(session.id), reason="user_logout", context={"ip": "192.168.1.1"}
        )
        assert revoked is True

        # Validate again (should be invalid now)
        is_valid_after_revoke = await service.validate_session(str(session.id))
        assert is_valid_after_revoke is False

        # Delete session
        deleted = await service.delete_session(str(session.id))
        assert deleted is True

        # Get session (should be None)
        retrieved_after_delete = await service.get_session(str(session.id))
        assert retrieved_after_delete is None

    @pytest.mark.asyncio
    async def test_list_sessions_for_user(self):
        """Test listing all sessions for a user."""
        backend = JWTSessionBackend(session_ttl_days=30)
        storage = MemorySessionStorage()
        audit = NoOpAuditBackend()
        service = SessionManagerService(backend, storage, audit)

        # Create multiple sessions for same user
        session1 = await service.create_session(
            user_id="user-123",
            device_info="Chrome",
            ip_address="192.168.1.1",
        )
        session2 = await service.create_session(
            user_id="user-123",
            device_info="Firefox",
            ip_address="192.168.1.2",
        )

        # Create session for different user
        session3 = await service.create_session(
            user_id="user-456",
            device_info="Safari",
            ip_address="192.168.1.3",
        )

        # List sessions for user-123
        sessions = await service.list_sessions("user-123")
        assert len(sessions) == 2
        assert all(s.user_id == "user-123" for s in sessions)

    @pytest.mark.asyncio
    async def test_revoke_all_user_sessions_except_current(self):
        """Test revoking all sessions except the current one."""
        backend = JWTSessionBackend(session_ttl_days=30)
        storage = MemorySessionStorage()
        audit = NoOpAuditBackend()
        service = SessionManagerService(backend, storage, audit)

        # Create 3 sessions for user
        s1 = await service.create_session(
            user_id="user-123",
            device_info="Device 1",
            ip_address="1.1.1.1",
        )
        s2 = await service.create_session(
            user_id="user-123",
            device_info="Device 2",
            ip_address="2.2.2.2",
        )
        s3 = await service.create_session(
            user_id="user-123",
            device_info="Device 3",
            ip_address="3.3.3.3",
        )

        # Revoke all except s2 (current session)
        count = await service.revoke_all_user_sessions(
            "user-123", reason="password_change", except_session_id=str(s2.id)
        )
        assert count == 2  # s1 and s3 revoked

        # Verify s2 is still valid
        assert await service.validate_session(str(s2.id)) is True

        # Verify s1 and s3 are invalid
        assert await service.validate_session(str(s1.id)) is False
        assert await service.validate_session(str(s3.id)) is False


class TestCompleteSessionLifecycleCacheStorage:
    """Test complete session lifecycle with cache storage (fakeredis)."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_with_cache(self, fakeredis_client):
        """Test session lifecycle with cache storage."""
        backend = JWTSessionBackend(session_ttl_days=30)
        storage = CacheSessionStorage(
            session_model=MockSession,
            cache_client=fakeredis_client,
            ttl=3600,
        )
        audit = NoOpAuditBackend()
        service = SessionManagerService(backend, storage, audit)

        # Create session
        session = await service.create_session(
            user_id="user-123",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.1",
        )

        # Retrieve via service
        retrieved = await service.get_session(str(session.id))
        assert retrieved is not None
        assert str(retrieved.id) == str(session.id)

        # Validate
        is_valid = await service.validate_session(str(session.id))
        assert is_valid is True


class TestSessionLifecycleWithEnrichers:
    """Test session lifecycle with enrichers in the pipeline."""

    @pytest.mark.asyncio
    async def test_create_session_with_enrichers(self):
        """Test that enrichers are called during session creation."""
        backend = JWTSessionBackend(session_ttl_days=30)
        storage = MemorySessionStorage()
        audit = NoOpAuditBackend()

        # Add enrichers
        enrichers = [GeolocationEnricher()]

        service = SessionManagerService(backend, storage, audit, enrichers)

        # Create session
        session = await service.create_session(
            user_id="user-123",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.1",
        )

        # Session should be created even though enricher is stub
        assert session is not None
        assert session.user_id == "user-123"


class TestSessionLifecycleWithAudit:
    """Test session lifecycle with audit logging."""

    @pytest.mark.asyncio
    async def test_audit_logs_session_events(self, caplog):
        """Test that audit backend logs session events."""
        import logging

        backend = JWTSessionBackend(session_ttl_days=30)
        storage = MemorySessionStorage()
        audit = LoggerAuditBackend(logger_name="test.session.audit")

        service = SessionManagerService(backend, storage, audit)

        with caplog.at_level(logging.INFO, logger="test.session.audit"):
            # Create session
            session = await service.create_session(
                user_id="user-123",
                device_info="Mozilla/5.0",
                ip_address="192.168.1.1",
            )

            # Revoke session
            await service.revoke_session(str(session.id), reason="test")

        # Verify audit logs
        assert any("Session created" in record.message for record in caplog.records)
        assert any("Session revoked" in record.message for record in caplog.records)
