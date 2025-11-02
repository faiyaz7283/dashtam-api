"""Pytest fixtures for session manager package tests.

These fixtures provide reusable test data and mock objects for
unit and integration testing.
"""

from datetime import timedelta

import pytest

from src.session_manager.models.config import SessionConfig
from src.session_manager.tests.fixtures.mock_models import (
    MockAuditLog,
    MockSession,
)


@pytest.fixture
def mock_session_model():
    """Fixture: MockSession class (not instance)."""
    return MockSession


@pytest.fixture
def mock_audit_model():
    """Fixture: MockAuditLog class (not instance)."""
    return MockAuditLog


@pytest.fixture
def mock_session():
    """Fixture: MockSession instance with default test data."""
    return MockSession(
        user_id="test-user-123",
        device_info="Chrome on macOS",
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    )


@pytest.fixture
def test_session_config():
    """Fixture: SessionConfig for testing (memory storage, no audit)."""
    return SessionConfig(
        session_ttl=timedelta(minutes=5),  # Short TTL for tests
        storage_type="memory",  # In-memory (fast, isolated)
        audit_type="noop",  # No audit noise in tests
        backend_type="jwt",  # JWT backend (no DB required)
        enable_enrichment=False,  # Skip enrichment in tests
    )


@pytest.fixture
def test_session_config_with_audit():
    """Fixture: SessionConfig with logger audit enabled."""
    return SessionConfig(
        session_ttl=timedelta(minutes=5),
        storage_type="memory",
        audit_type="logger",  # Enable logger audit
        backend_type="jwt",
        enable_enrichment=False,
    )
