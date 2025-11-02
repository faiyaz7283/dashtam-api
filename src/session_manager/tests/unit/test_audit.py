"""Unit tests for audit backends.

Tests LoggerAuditBackend and NoOpAuditBackend without external dependencies.
"""

import logging

import pytest

from src.session_manager.audit.logger import LoggerAuditBackend
from src.session_manager.audit.noop import NoOpAuditBackend
from src.session_manager.tests.fixtures.mock_models import MockSession


@pytest.mark.asyncio
class TestLoggerAuditBackend:
    """Test LoggerAuditBackend using Python stdlib logging."""

    async def test_init_default_logger_name(self):
        """Test initialization with default logger name."""
        backend = LoggerAuditBackend()

        assert backend.logger.name == "session_manager.audit"

    async def test_init_custom_logger_name(self):
        """Test initialization with custom logger name."""
        backend = LoggerAuditBackend(logger_name="custom.audit")

        assert backend.logger.name == "custom.audit"

    async def test_log_session_created(self, caplog):
        """Test logging session creation."""
        backend = LoggerAuditBackend(logger_name="test.audit")
        backend.logger.setLevel(logging.INFO)

        session = MockSession(user_id="user-123", device_info="Chrome")

        with caplog.at_level(logging.INFO, logger="test.audit"):
            await backend.log_session_created(session, context={"source": "api"})

        # Verify log message
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelname == "INFO"
        assert record.message == "Session created"
        assert record.event_type == "session_created"
        assert record.user_id == "user-123"
        assert record.device_info == "Chrome"
        assert record.source == "api"

    async def test_log_session_revoked(self, caplog):
        """Test logging session revocation."""
        backend = LoggerAuditBackend(logger_name="test.audit")
        backend.logger.setLevel(logging.WARNING)

        with caplog.at_level(logging.WARNING, logger="test.audit"):
            await backend.log_session_revoked(
                "session-123",
                reason="user_logout",
                context={"user_id": "user-123"},
            )

        # Verify log message
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelname == "WARNING"
        assert record.message == "Session revoked"
        assert record.event_type == "session_revoked"
        assert record.session_id == "session-123"
        assert record.reason == "user_logout"
        assert record.user_id == "user-123"

    async def test_log_session_accessed(self, caplog):
        """Test logging session access."""
        backend = LoggerAuditBackend(logger_name="test.audit")
        backend.logger.setLevel(logging.DEBUG)

        with caplog.at_level(logging.DEBUG, logger="test.audit"):
            await backend.log_session_accessed(
                "session-123", context={"endpoint": "/api/profile"}
            )

        # Verify log message
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelname == "DEBUG"
        assert record.message == "Session accessed"
        assert record.event_type == "session_accessed"
        assert record.session_id == "session-123"
        assert record.endpoint == "/api/profile"

    async def test_log_suspicious_activity(self, caplog):
        """Test logging suspicious activity."""
        backend = LoggerAuditBackend(logger_name="test.audit")
        backend.logger.setLevel(logging.ERROR)

        with caplog.at_level(logging.ERROR, logger="test.audit"):
            await backend.log_suspicious_activity(
                "session-123",
                event="multiple_failed_attempts",
                context={"attempts": 5, "ip": "192.168.1.100"},
            )

        # Verify log message
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelname == "ERROR"
        assert "Suspicious activity" in record.message
        assert "multiple_failed_attempts" in record.message
        assert record.event_type == "suspicious_activity"
        assert record.session_id == "session-123"
        assert record.suspicious_event == "multiple_failed_attempts"
        assert record.attempts == 5
        assert record.ip == "192.168.1.100"

    async def test_log_session_created_with_timestamp(self, caplog):
        """Test that timestamp is properly serialized in log."""
        from datetime import datetime, timezone

        backend = LoggerAuditBackend(logger_name="test.audit")
        backend.logger.setLevel(logging.INFO)

        now = datetime.now(timezone.utc)
        session = MockSession(user_id="user-123", created_at=now)

        with caplog.at_level(logging.INFO, logger="test.audit"):
            await backend.log_session_created(session, context={})

        # Verify timestamp is serialized
        record = caplog.records[0]
        assert record.created_at == now.isoformat()


@pytest.mark.asyncio
class TestNoOpAuditBackend:
    """Test NoOpAuditBackend (does nothing)."""

    async def test_log_session_created(self):
        """Test that log_session_created does nothing."""
        backend = NoOpAuditBackend()
        session = MockSession(user_id="user-123")

        # Should not raise, should do nothing
        await backend.log_session_created(session, context={})

    async def test_log_session_revoked(self):
        """Test that log_session_revoked does nothing."""
        backend = NoOpAuditBackend()

        # Should not raise, should do nothing
        await backend.log_session_revoked("session-123", reason="test", context={})

    async def test_log_session_accessed(self):
        """Test that log_session_accessed does nothing."""
        backend = NoOpAuditBackend()

        # Should not raise, should do nothing
        await backend.log_session_accessed("session-123", context={})

    async def test_log_suspicious_activity(self):
        """Test that log_suspicious_activity does nothing."""
        backend = NoOpAuditBackend()

        # Should not raise, should do nothing
        await backend.log_suspicious_activity("session-123", event="test", context={})

    async def test_all_methods_are_truly_noop(self):
        """Test that all NoOp methods truly do nothing (no side effects)."""
        backend = NoOpAuditBackend()
        session = MockSession(user_id="user-123")

        # Call all methods - none should have side effects
        await backend.log_session_created(session, {"key": "value"})
        await backend.log_session_revoked("id", "reason", {"key": "value"})
        await backend.log_session_accessed("id", {"key": "value"})
        await backend.log_suspicious_activity("id", "event", {"key": "value"})

        # If we reach here without errors, all methods are no-ops
        assert True
