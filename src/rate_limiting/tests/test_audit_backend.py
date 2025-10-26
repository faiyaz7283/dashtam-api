"""Unit tests for rate limiting audit backend.

Tests the DatabaseAuditBackend implementation including success cases,
error handling, fail-open behavior, and database-agnostic design.

Architecture:
    - Tests use MOCKS (no real database operations)
    - Database-agnostic (tests bounded context isolation)
    - Verifies audit backend calls model correctly
    - Tests fail-open design (errors don't raise exceptions)

Design Philosophy:
    These tests verify the rate limiting audit backend in isolation,
    without coupling to Dashtam's database models or PostgreSQL.
    The backend accepts any model implementing RateLimitAuditLogBase.

Note:
    No AsyncToSyncWrapper needed - tests mock session operations.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock

from src.rate_limiting.audit_backends.database import DatabaseAuditBackend
from src.rate_limiting.models.base import RateLimitAuditLogBase


@pytest.fixture
def mock_session():
    """Create a mock database session.

    Returns:
        AsyncMock session with commit, rollback, close, add, execute methods.
    """
    session = AsyncMock()
    session.add = Mock()  # Synchronous (not awaited)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_model_class():
    """Create a mock model class implementing RateLimitAuditLogBase.

    Returns:
        Mock model class that can be instantiated.
    """
    mock_class = Mock()
    mock_instance = Mock(spec=RateLimitAuditLogBase)
    mock_class.return_value = mock_instance
    return mock_class


class TestDatabaseAuditBackend:
    """Test DatabaseAuditBackend implementation (database-agnostic with mocks).

    Tests verify:
    - Audit backend works with ANY model implementing RateLimitAuditLogBase
    - No coupling to Dashtam's PostgreSQL or SQLModel
    - Fail-open error handling
    - Correct model instantiation and session usage
    """

    @pytest.mark.asyncio
    async def test_log_violation_success(self, mock_session, mock_model_class):
        """Test successful audit log creation.

        Verifies that:
        - Model instantiated with correct parameters
        - Session.add called with model instance
        - Session.commit called
        - identifier parameter used correctly

        Args:
            mock_session: Mock database session fixture
            mock_model_class: Mock model class fixture
        """
        backend = DatabaseAuditBackend(
            session=mock_session,
            model_class=mock_model_class,
        )

        # Log a violation
        await backend.log_violation(
            identifier="user:123e4567-e89b-12d3-a456-426614174000",
            ip_address="192.168.1.1",
            endpoint="/api/v1/auth/login",
            rule_name="auth_login",
            limit=5,
            window_seconds=60,
            violation_count=1,
        )

        # Verify model instantiated with correct parameters
        mock_model_class.assert_called_once()
        call_kwargs = mock_model_class.call_args[1]
        
        assert call_kwargs["identifier"] == "user:123e4567-e89b-12d3-a456-426614174000"
        assert call_kwargs["ip_address"] == "192.168.1.1"
        assert call_kwargs["endpoint"] == "/api/v1/auth/login"
        assert call_kwargs["rule_name"] == "auth_login"
        assert call_kwargs["limit"] == 5
        assert call_kwargs["window_seconds"] == 60
        assert call_kwargs["violation_count"] == 1
        assert "timestamp" in call_kwargs  # Auto-generated

        # Verify session operations
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_violation_with_ip_identifier(self, mock_session, mock_model_class):
        """Test audit log with IP-based identifier (anonymous request).

        Verifies that:
        - IP identifier format supported ("ip:address")
        - identifier field populated correctly
        - Works for unauthenticated requests

        Args:
            mock_session: Mock database session fixture
            mock_model_class: Mock model class fixture
        """
        backend = DatabaseAuditBackend(
            session=mock_session,
            model_class=mock_model_class,
        )

        await backend.log_violation(
            identifier="ip:203.0.113.42",
            ip_address="203.0.113.42",
            endpoint="/api/v1/auth/login",
            rule_name="auth_login_anonymous",
            limit=5,
            window_seconds=60,
            violation_count=1,
        )

        # Verify identifier format
        call_kwargs = mock_model_class.call_args[1]
        assert call_kwargs["identifier"] == "ip:203.0.113.42"
        assert call_kwargs["ip_address"] == "203.0.113.42"

    @pytest.mark.asyncio
    async def test_log_violation_fail_open_on_database_error(self, mock_session, mock_model_class):
        """Test fail-open behavior when database operation fails.

        Verifies that:
        - Database errors don't raise exceptions
        - Fail-open design (audit failure doesn't block rate limiting)
        - Error logged but not propagated
        - System remains operational

        Args:
            mock_session: Mock database session fixture
            mock_model_class: Mock model class fixture
        """
        # Simulate database error on commit
        mock_session.commit.side_effect = Exception("Database connection lost")

        backend = DatabaseAuditBackend(
            session=mock_session,
            model_class=mock_model_class,
        )

        # Should not raise exception (fail-open)
        try:
            await backend.log_violation(
                identifier="user:123e4567-e89b-12d3-a456-426614174000",
                ip_address="192.168.1.1",
                endpoint="/api/v1/test",
                rule_name="test_rule",
                limit=10,
                window_seconds=60,
                violation_count=1,
            )
        except Exception as e:
            pytest.fail(f"Audit backend should fail-open, but raised: {e}")

        # Verify model was created (attempt was made)
        mock_model_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_violation_timestamp_generation(self, mock_session, mock_model_class):
        """Test that timestamps are auto-generated.

        Verifies that:
        - timestamp parameter passed to model
        - Timestamp is timezone-aware (UTC)
        - Timestamp is recent (within last few seconds)

        Args:
            mock_session: Mock database session fixture
            mock_model_class: Mock model class fixture
        """
        backend = DatabaseAuditBackend(
            session=mock_session,
            model_class=mock_model_class,
        )

        before_log = datetime.now(timezone.utc)
        
        await backend.log_violation(
            identifier="user:123e4567-e89b-12d3-a456-426614174000",
            ip_address="192.168.1.1",
            endpoint="/api/v1/test",
            rule_name="test_rule",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )

        after_log = datetime.now(timezone.utc)

        # Verify timestamp parameter
        call_kwargs = mock_model_class.call_args[1]
        assert "timestamp" in call_kwargs
        
        timestamp = call_kwargs["timestamp"]
        
        # Verify timezone-aware
        assert timestamp.tzinfo is not None
        assert timestamp.tzinfo == timezone.utc
        
        # Verify recent (within test execution time)
        assert before_log <= timestamp <= after_log

    @pytest.mark.asyncio
    async def test_log_violation_multiple_calls(self, mock_session, mock_model_class):
        """Test logging multiple violations (verifies no state pollution).

        Verifies that:
        - Multiple calls work correctly
        - Each call creates separate model instance
        - No state pollution between calls
        - Session operations called for each violation

        Args:
            mock_session: Mock database session fixture
            mock_model_class: Mock model class fixture
        """
        backend = DatabaseAuditBackend(
            session=mock_session,
            model_class=mock_model_class,
        )

        # Log first violation
        await backend.log_violation(
            identifier="user:111e1111-e11b-11d1-a111-111111111111",
            ip_address="192.168.1.1",
            endpoint="/api/v1/endpoint1",
            rule_name="rule1",
            limit=5,
            window_seconds=60,
            violation_count=1,
        )

        # Log second violation
        await backend.log_violation(
            identifier="user:222e2222-e22b-22d2-a222-222222222222",
            ip_address="10.0.0.1",
            endpoint="/api/v1/endpoint2",
            rule_name="rule2",
            limit=10,
            window_seconds=120,
            violation_count=2,
        )

        # Verify two separate model instances created
        assert mock_model_class.call_count == 2

        # Verify session operations called twice
        assert mock_session.add.call_count == 2
        assert mock_session.commit.await_count == 2

    @pytest.mark.asyncio
    async def test_log_violation_with_none_identifier(self, mock_session, mock_model_class):
        """Test audit log with None identifier (edge case).

        Verifies that:
        - None identifier is handled correctly
        - System doesn't break
        - Model still instantiated

        Args:
            mock_session: Mock database session fixture
            mock_model_class: Mock model class fixture
        """
        backend = DatabaseAuditBackend(
            session=mock_session,
            model_class=mock_model_class,
        )

        await backend.log_violation(
            identifier=None,
            ip_address="192.168.1.1",
            endpoint="/api/v1/test",
            rule_name="test_rule",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )

        # Verify model created with None identifier
        call_kwargs = mock_model_class.call_args[1]
        assert call_kwargs["identifier"] is None
        assert call_kwargs["ip_address"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_backend_works_with_any_model_class(self, mock_session):
        """Test backend accepts any model class (database-agnostic design).

        Verifies that:
        - Backend doesn't import concrete model
        - Works with any model class passed to constructor
        - True dependency inversion

        Args:
            mock_session: Mock database session fixture
        """
        # Create custom mock model class (simulating different ORM)
        custom_model_class = Mock()
        custom_instance = Mock()
        custom_model_class.return_value = custom_instance

        # Backend should accept ANY model class
        backend = DatabaseAuditBackend(
            session=mock_session,
            model_class=custom_model_class,
        )

        await backend.log_violation(
            identifier="user:123e4567-e89b-12d3-a456-426614174000",
            ip_address="192.168.1.1",
            endpoint="/api/v1/test",
            rule_name="test_rule",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )

        # Verify custom model class was used
        custom_model_class.assert_called_once()
        mock_session.add.assert_called_once_with(custom_instance)
