"""Unit tests for session manager factory.

Tests dependency injection and configuration-based component wiring.
"""

from datetime import timedelta

import pytest

from src.session_manager.audit.logger import LoggerAuditBackend
from src.session_manager.audit.noop import NoOpAuditBackend
from src.session_manager.backends.jwt_backend import JWTSessionBackend
from src.session_manager.enrichers.geolocation import GeolocationEnricher
from src.session_manager.factory import (
    get_session_manager,
    get_session_manager_for_development,
    get_session_manager_for_testing,
)
from src.session_manager.models.config import SessionConfig
from src.session_manager.service import SessionManagerService
from src.session_manager.storage.memory import MemorySessionStorage
from src.session_manager.tests.fixtures.mock_models import MockSession


class TestGetSessionManager:
    """Test get_session_manager factory function."""

    def test_create_with_memory_storage(self):
        """Test creating session manager with memory storage."""
        config = SessionConfig(storage_type="memory", audit_type="noop")

        manager = get_session_manager(
            session_model=MockSession,
            config=config,
        )

        assert isinstance(manager, SessionManagerService)
        assert isinstance(manager.backend, JWTSessionBackend)
        assert isinstance(manager.storage, MemorySessionStorage)
        assert isinstance(manager.audit, NoOpAuditBackend)
        assert manager.enrichers == []

    def test_create_with_logger_audit(self):
        """Test creating session manager with logger audit."""
        config = SessionConfig(storage_type="memory", audit_type="logger")

        manager = get_session_manager(
            session_model=MockSession,
            config=config,
        )

        assert isinstance(manager.audit, LoggerAuditBackend)

    def test_create_with_enrichers(self):
        """Test creating session manager with enrichers."""
        config = SessionConfig(storage_type="memory")
        enrichers = [GeolocationEnricher()]

        manager = get_session_manager(
            session_model=MockSession,
            config=config,
            enrichers=enrichers,
        )

        assert manager.enrichers == enrichers
        assert len(manager.enrichers) == 1

    def test_create_with_custom_session_ttl(self):
        """Test that custom session TTL is passed to backend."""
        config = SessionConfig(
            session_ttl=timedelta(days=60),
            storage_type="memory",
        )

        manager = get_session_manager(
            session_model=MockSession,
            config=config,
        )

        # Verify backend has correct TTL
        assert manager.backend.session_ttl_days == 60

    def test_create_with_database_storage_missing_db_session(self):
        """Test that database storage requires db_session."""
        config = SessionConfig(storage_type="database")

        with pytest.raises(
            ValueError, match="db_session is required for 'database' storage"
        ):
            get_session_manager(
                session_model=MockSession,
                config=config,
                db_session=None,  # Missing required dependency
            )

    def test_create_with_cache_storage_missing_cache_client(self):
        """Test that cache storage requires cache_client."""
        config = SessionConfig(storage_type="cache")

        with pytest.raises(
            ValueError,
            match="cache_client is required for 'cache' storage",
        ):
            get_session_manager(
                session_model=MockSession,
                config=config,
                cache_client=None,  # Missing required dependency
            )

    def test_create_with_database_backend_missing_db_session(self):
        """Test that database backend requires db_session."""
        config = SessionConfig(
            backend_type="database",
            storage_type="memory",
        )

        with pytest.raises(
            ValueError, match="db_session is required for 'database' backend"
        ):
            get_session_manager(
                session_model=MockSession,
                config=config,
                db_session=None,  # Missing required dependency
            )

    def test_create_with_invalid_backend_type(self):
        """Test that invalid backend_type raises ValueError."""
        config = SessionConfig(storage_type="memory")
        config.backend_type = "invalid"  # Force invalid value

        with pytest.raises(ValueError, match="Invalid backend_type"):
            get_session_manager(
                session_model=MockSession,
                config=config,
            )

    def test_create_with_invalid_storage_type(self):
        """Test that invalid storage_type raises ValueError."""
        config = SessionConfig(storage_type="memory")
        config.storage_type = "invalid"  # Force invalid value

        with pytest.raises(ValueError, match="Invalid storage_type"):
            get_session_manager(
                session_model=MockSession,
                config=config,
            )

    def test_create_with_invalid_audit_type(self):
        """Test that invalid audit_type raises ValueError."""
        config = SessionConfig(storage_type="memory")
        config.audit_type = "invalid"  # Force invalid value

        with pytest.raises(ValueError, match="Invalid audit_type"):
            get_session_manager(
                session_model=MockSession,
                config=config,
            )

    def test_create_with_metrics_audit_falls_back_to_noop(self, caplog):
        """Test that metrics audit falls back to NoOp with warning."""
        import logging

        config = SessionConfig(
            storage_type="memory",
            audit_type="metrics",
        )

        with caplog.at_level(logging.WARNING):
            manager = get_session_manager(
                session_model=MockSession,
                config=config,
            )

        # Should fall back to NoOp
        assert isinstance(manager.audit, NoOpAuditBackend)

        # Should log warning
        assert any("not implemented" in record.message for record in caplog.records)


class TestGetSessionManagerForTesting:
    """Test convenience function for testing."""

    def test_creates_testing_configuration(self):
        """Test that testing convenience function uses TESTING_CONFIG."""
        manager = get_session_manager_for_testing(MockSession)

        assert isinstance(manager, SessionManagerService)
        assert isinstance(manager.storage, MemorySessionStorage)
        assert isinstance(manager.audit, NoOpAuditBackend)
        assert manager.enrichers == []

    def test_uses_short_ttl(self):
        """Test that testing config uses short TTL."""
        manager = get_session_manager_for_testing(MockSession)

        # TESTING_CONFIG has session_ttl=5 minutes
        # Convert to days for comparison with backend
        # Backend should have TTL of 0 days (since 5 minutes < 1 day)
        assert manager.backend.session_ttl_days == 0


class TestGetSessionManagerForDevelopment:
    """Test convenience function for development."""

    def test_creates_development_configuration(self):
        """Test that development convenience function uses DEVELOPMENT_CONFIG."""
        manager = get_session_manager_for_development(MockSession)

        assert isinstance(manager, SessionManagerService)
        assert isinstance(manager.storage, MemorySessionStorage)
        assert isinstance(manager.audit, LoggerAuditBackend)

    def test_uses_development_ttl(self):
        """Test that development config uses 7 day TTL."""
        manager = get_session_manager_for_development(MockSession)

        # DEVELOPMENT_CONFIG has session_ttl=7 days
        assert manager.backend.session_ttl_days == 7
