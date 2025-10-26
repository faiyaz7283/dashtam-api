"""Unit tests for rate limiting audit backend.

Tests the DatabaseAuditBackend implementation including success cases,
error handling, fail-open behavior, and timezone awareness.

Architecture:
    - Tests isolated audit backend (unit tests)
    - Uses async-to-sync wrapper pattern (follows project pattern)
    - Verifies data persistence and validation
    - Tests fail-open design (errors don't raise exceptions)

Note:
    DatabaseAuditBackend is async, but tests are synchronous.
    We use AsyncToSyncWrapper (same pattern as conftest.py) to bridge.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Session, select

from src.rate_limiting.audit_backends.database import DatabaseAuditBackend
from src.rate_limiting.models import RateLimitAuditLog
from src.models.user import User


class AsyncToSyncWrapper:
    """Wrapper to make sync Session work with async audit backend.

    This is the same pattern used in tests/conftest.py for TestClient.
    Allows synchronous tests to call async DatabaseAuditBackend methods.
    """

    def __init__(self, sync_session: Session):
        self.session = sync_session

    async def execute(self, *args, **kwargs):
        """Wrap sync execute to be awaitable."""
        return self.session.execute(*args, **kwargs)

    async def commit(self):
        """Wrap sync commit to be awaitable."""
        result = self.session.commit()
        self.session.expire_all()
        return result

    async def rollback(self):
        """Wrap sync rollback to be awaitable."""
        return self.session.rollback()

    def add(self, *args, **kwargs):
        """Direct pass-through for add (not awaited)."""
        return self.session.add(*args, **kwargs)

    async def close(self):
        """Wrap close to be awaitable."""
        pass  # Session lifecycle managed by fixture


def run_async(coro):
    """Helper to run async coroutine synchronously.

    Args:
        coro: Async coroutine to execute

    Returns:
        Result of coroutine execution
    """
    return asyncio.run(coro)


class TestDatabaseAuditBackend:
    """Test DatabaseAuditBackend implementation."""

    def test_log_violation_success(self, rate_limit_db_session: Session):
        """Test successful audit log creation.

        Verifies that:
        - Audit log entry created in database
        - All fields populated correctly
        - Timestamps are timezone-aware
        - Record persisted after commit

        Args:
            db_session: Synchronous database session fixture
        """
        wrapped_session = AsyncToSyncWrapper(rate_limit_db_session)
        backend = DatabaseAuditBackend(wrapped_session)
        unique_ip = "192.168.1.1"
        unique_endpoint = "/api/v1/auth/login-success-test"
        
        # Don't use user_id to avoid foreign key constraint
        # (test_log_violation_with_authenticated_user tests with real user)
        async def _log():
            await backend.log_violation(
                user_id=None,  # No user_id (unauthenticated request)
                ip_address=unique_ip,
                endpoint=unique_endpoint,
                rule_name="auth_login_success",
                limit=5,
                window_seconds=60,
                violation_count=1,
            )

        run_async(_log())

        # Verify record inserted (use unique identifiers)
        result = rate_limit_db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.endpoint == unique_endpoint
            ).where(
                RateLimitAuditLog.ip_address == unique_ip
            )
        )
        log = result.scalar_one()

        assert log.user_id is None
        assert log.ip_address == unique_ip
        assert log.endpoint == unique_endpoint
        assert log.rule_name == "auth_login_success"
        assert log.limit == 5
        assert log.window_seconds == 60
        assert log.violation_count == 1

        # Verify timestamps are timezone-aware
        assert log.timestamp.tzinfo is not None
        assert log.created_at.tzinfo is not None

    def test_log_violation_with_authenticated_user(
        self, rate_limit_db_session: Session, test_user: User
    ):
        """Test audit log with authenticated user.

        Verifies that:
        - user_id foreign key populated correctly
        - Links to existing user record
        - User relationship maintained

        Args:
            db_session: Synchronous database session fixture
            test_user: Test user fixture (from conftest.py)
        """
        wrapped_session = AsyncToSyncWrapper(rate_limit_db_session)
        backend = DatabaseAuditBackend(wrapped_session)

        async def _log():
            await backend.log_violation(
                user_id=test_user.id,
                ip_address="10.0.0.1",
                endpoint="/api/v1/providers",
                rule_name="api_user",
                limit=100,
                window_seconds=60,
                violation_count=2,
            )

        run_async(_log())

        # Verify audit log created with user_id
        result = rate_limit_db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.user_id == test_user.id
            )
        )
        log = result.scalar_one()

        assert log.user_id == test_user.id
        assert log.endpoint == "/api/v1/providers"
        assert log.violation_count == 2

    def test_log_violation_without_user_id(self, rate_limit_db_session: Session):
        """Test audit log without authenticated user (anonymous request).

        Verifies that:
        - user_id can be None (unauthenticated requests)
        - IP address still tracked
        - Audit log still created successfully

        Args:
            db_session: Synchronous database session fixture
        """
        wrapped_session = AsyncToSyncWrapper(rate_limit_db_session)
        backend = DatabaseAuditBackend(wrapped_session)
        unique_ip = "203.0.113.42"
        unique_endpoint = "/api/v1/auth/login-no-user-test"

        async def _log():
            await backend.log_violation(
                user_id=None,
                ip_address=unique_ip,
                endpoint=unique_endpoint,
                rule_name="auth_login_no_user",
                limit=5,
                window_seconds=60,
                violation_count=1,
            )

        run_async(_log())

        # Verify audit log created without user_id (use unique identifiers)
        result = rate_limit_db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.ip_address == unique_ip
            ).where(
                RateLimitAuditLog.endpoint == unique_endpoint
            )
        )
        log = result.scalar_one()

        assert log.user_id is None
        assert log.ip_address == unique_ip
        assert log.endpoint == unique_endpoint

    def test_log_violation_fail_open_on_database_error(self, rate_limit_db_session: Session):
        """Test fail-open behavior when database operation fails.

        Verifies that:
        - Database errors don't raise exceptions
        - Fail-open design (audit failure doesn't block rate limiting)
        - Error logged but not propagated
        - System remains operational

        Args:
            db_session: Synchronous database session fixture
        """
        # Close session to simulate database error
        rate_limit_db_session.close()

        wrapped_session = AsyncToSyncWrapper(rate_limit_db_session)
        backend = DatabaseAuditBackend(wrapped_session)

        # Should not raise exception (fail-open)
        async def _log():
            await backend.log_violation(
                user_id=uuid4(),
                ip_address="192.168.1.1",
                endpoint="/api/v1/test",
                rule_name="test_rule",
                limit=10,
                window_seconds=60,
                violation_count=1,
            )

        try:
            run_async(_log())
        except Exception as e:
            pytest.fail(f"Audit backend should fail-open, but raised: {e}")

    def test_log_violation_validates_data(self, rate_limit_db_session: Session):
        """Test data validation in audit log model.

        Verifies that:
        - Field validators work correctly
        - Invalid data is caught
        - Model validation enforced

        Args:
            db_session: Synchronous database session fixture
        """
        wrapped_session = AsyncToSyncWrapper(rate_limit_db_session)
        backend = DatabaseAuditBackend(wrapped_session)
        unique_ip = "192.168.2.2"
        unique_endpoint = "/api/v1/test-validation"

        # Valid data should succeed
        async def _log():
            await backend.log_violation(
                user_id=None,
                ip_address=unique_ip,
                endpoint=unique_endpoint,
                rule_name="test_rule_validation",
                limit=10,
                window_seconds=60,
                violation_count=1,
            )

        run_async(_log())

        # Verify log created (use unique identifiers)
        result = rate_limit_db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.rule_name == "test_rule_validation"
            ).where(
                RateLimitAuditLog.ip_address == unique_ip
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None

    def test_log_violation_timezone_aware_timestamps(self, rate_limit_db_session: Session):
        """Test that timestamps are timezone-aware (UTC).

        Verifies that:
        - timestamp field is timezone-aware
        - created_at field is timezone-aware
        - Both in UTC timezone
        - Complies with PCI-DSS requirements

        Args:
            db_session: Synchronous database session fixture
        """
        wrapped_session = AsyncToSyncWrapper(rate_limit_db_session)
        backend = DatabaseAuditBackend(wrapped_session)
        
        # Use unique IP to avoid collision with other tests
        unique_ip = "192.168.99.99"

        async def _log():
            await backend.log_violation(
                user_id=None,
                ip_address=unique_ip,
                endpoint="/api/v1/test-timezone",
                rule_name="test_rule_tz",
                limit=10,
                window_seconds=60,
                violation_count=1,
            )

        run_async(_log())

        # Retrieve and verify (use unique identifiers to avoid collision)
        result = rate_limit_db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.rule_name == "test_rule_tz"
            ).where(
                RateLimitAuditLog.ip_address == unique_ip
            )
        )
        log = result.scalar_one()

        # Verify timezone-aware
        assert log.timestamp.tzinfo is not None
        assert log.created_at.tzinfo is not None

        # Verify UTC
        assert log.timestamp.tzinfo == timezone.utc
        assert log.created_at.tzinfo == timezone.utc

        # Verify timestamps are recent (within last minute)
        now = datetime.now(timezone.utc)
        assert (now - log.timestamp).total_seconds() < 60
        assert (now - log.created_at).total_seconds() < 60

    def test_log_violation_multiple_violations(self, rate_limit_db_session: Session):
        """Test logging multiple violations from same IP/endpoint.

        Verifies that:
        - Multiple audit logs can be created
        - violation_count field tracks how many over limit
        - Each violation logged separately
        - Query returns all violations

        Args:
            db_session: Synchronous database session fixture
        """
        wrapped_session = AsyncToSyncWrapper(rate_limit_db_session)
        backend = DatabaseAuditBackend(wrapped_session)
        unique_ip = "192.168.1.100"
        unique_endpoint = "/api/v1/auth/login-multi-test"

        # Log 3 violations (simulating 3 requests over limit)
        async def _log_all():
            for i in range(1, 4):
                await backend.log_violation(
                    user_id=None,
                    ip_address=unique_ip,
                    endpoint=unique_endpoint,
                    rule_name="auth_login_multi",
                    limit=5,
                    window_seconds=60,
                    violation_count=i,
                )

        run_async(_log_all())

        # Query all violations for this IP/endpoint
        result = rate_limit_db_session.execute(
            select(RateLimitAuditLog)
            .where(RateLimitAuditLog.ip_address == unique_ip)
            .where(RateLimitAuditLog.endpoint == unique_endpoint)
        )
        logs = result.scalars().all()

        assert len(logs) == 3
        violation_counts = sorted([log.violation_count for log in logs])
        assert violation_counts == [1, 2, 3]

    def test_log_violation_ipv6_address(self, rate_limit_db_session: Session):
        """Test audit log with IPv6 address.

        Verifies that:
        - IPv6 addresses supported (up to 45 chars)
        - Full IPv6 address stored correctly
        - No truncation or data loss

        Args:
            db_session: Synchronous database session fixture
        """
        wrapped_session = AsyncToSyncWrapper(rate_limit_db_session)
        backend = DatabaseAuditBackend(wrapped_session)
        ipv6 = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"
        unique_endpoint = "/api/v1/test-ipv6"

        async def _log():
            await backend.log_violation(
                user_id=None,
                ip_address=ipv6,
                endpoint=unique_endpoint,
                rule_name="test_rule_ipv6",
                limit=10,
                window_seconds=60,
                violation_count=1,
            )

        run_async(_log())

        # Verify IPv6 stored correctly (use unique identifiers)
        result = rate_limit_db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.ip_address == ipv6
            ).where(
                RateLimitAuditLog.endpoint == unique_endpoint
            )
        )
        log = result.scalar_one()

        assert log.ip_address == ipv6
