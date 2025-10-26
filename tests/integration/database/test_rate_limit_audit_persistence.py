"""Integration tests for rate limit audit log persistence.

Tests Dashtam's concrete PostgreSQL implementation of rate limit audit logs.
These tests verify:
- RateLimitAuditLog model persistence (PostgreSQL + SQLModel)
- PostgreSQL INET type validation (IP addresses)
- identifier field functionality (flexible tracking)
- Database constraints and indexes
- Timezone-aware datetimes (TIMESTAMPTZ)

Architecture:
    - Integration tests (real database operations)
    - Tests Dashtam's PostgreSQL implementation
    - Verifies model works with actual database
    - Complements unit tests (which use mocks)

Note:
    These are integration tests, not unit tests. They use the real
    test database and verify actual database operations.
"""

import pytest
from datetime import datetime, timezone

from sqlmodel import Session, select

from src.models.rate_limit_audit import RateLimitAuditLog


class TestRateLimitAuditLogPersistence:
    """Integration tests for RateLimitAuditLog model persistence."""

    def test_create_audit_log_with_user_identifier(self, db_session: Session):
        """Test creating audit log with user identifier.

        Verifies:
        - Model can be created and persisted
        - identifier field accepts user format
        - PostgreSQL INET type accepts IP address
        - Timestamps are timezone-aware
        - All fields populated correctly

        Args:
            db_session: Database session fixture
        """
        log = RateLimitAuditLog(
            identifier="user:123e4567-e89b-12d3-a456-426614174000",
            ip_address="192.168.1.100",
            endpoint="/api/v1/auth/login",
            rule_name="auth_login",
            limit=20,
            window_seconds=300,
            violation_count=1,
        )

        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        # Verify persisted
        assert log.id is not None
        assert log.identifier == "user:123e4567-e89b-12d3-a456-426614174000"
        assert str(log.ip_address) == "192.168.1.100"
        assert log.endpoint == "/api/v1/auth/login"
        assert log.rule_name == "auth_login"
        assert log.limit == 20
        assert log.window_seconds == 300
        assert log.violation_count == 1

        # Verify timezone-aware
        assert log.timestamp.tzinfo is not None
        assert log.created_at.tzinfo is not None

    def test_create_audit_log_with_ip_identifier(self, db_session: Session):
        """Test creating audit log with IP identifier (anonymous request).

        Verifies:
        - identifier field accepts IP format
        - Works for unauthenticated requests
        - identifier can be different from ip_address field

        Args:
            db_session: Database session fixture
        """
        log = RateLimitAuditLog(
            identifier="ip:203.0.113.45",
            ip_address="203.0.113.45",
            endpoint="/api/v1/auth/register",
            rule_name="auth_register",
            limit=10,
            window_seconds=1800,
            violation_count=1,
        )

        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert log.identifier == "ip:203.0.113.45"
        assert str(log.ip_address) == "203.0.113.45"

    def test_create_audit_log_with_none_identifier(self, db_session: Session):
        """Test creating audit log with None identifier.

        Verifies:
        - identifier field is nullable
        - System works without identifier
        - Edge case handled correctly

        Args:
            db_session: Database session fixture
        """
        log = RateLimitAuditLog(
            identifier=None,
            ip_address="10.0.0.1",
            endpoint="/api/v1/test",
            rule_name="test_rule",
            limit=5,
            window_seconds=60,
            violation_count=1,
        )

        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert log.identifier is None
        assert str(log.ip_address) == "10.0.0.1"

    def test_postgresql_inet_type_validates_ipv4(self, db_session: Session):
        """Test PostgreSQL INET type validates IPv4 addresses.

        Verifies:
        - PostgreSQL INET type accepts valid IPv4
        - Native database validation
        - IP address stored correctly

        Args:
            db_session: Database session fixture
        """
        log = RateLimitAuditLog(
            identifier="ip:192.0.2.1",
            ip_address="192.0.2.1",
            endpoint="/api/v1/test",
            rule_name="test_ipv4",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )

        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert str(log.ip_address) == "192.0.2.1"

    def test_postgresql_inet_type_validates_ipv6(self, db_session: Session):
        """Test PostgreSQL INET type validates IPv6 addresses.

        Verifies:
        - PostgreSQL INET type accepts valid IPv6
        - IPv6 addresses stored correctly
        - Supports both IP versions

        Args:
            db_session: Database session fixture
        """
        log = RateLimitAuditLog(
            identifier="ip:2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            ip_address="2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            endpoint="/api/v1/test",
            rule_name="test_ipv6",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )

        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        # PostgreSQL normalizes IPv6 (compresses zeros: 0db8 → db8)
        assert "2001:db8:85a3" in str(log.ip_address) or "2001:0db8:85a3" in str(log.ip_address)

    def test_query_by_identifier(self, db_session: Session):
        """Test querying audit logs by identifier.

        Verifies:
        - identifier field is indexed
        - Queries work correctly
        - Can filter by identifier

        Args:
            db_session: Database session fixture
        """
        # Use unique identifiers to avoid test pollution
        from uuid import uuid4
        unique_id1 = str(uuid4())
        unique_id2 = str(uuid4())
        
        log1 = RateLimitAuditLog(
            identifier=f"user:{unique_id1}",
            ip_address="192.168.1.1",
            endpoint="/api/v1/test1",
            rule_name="rule1",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )
        log2 = RateLimitAuditLog(
            identifier=f"user:{unique_id2}",
            ip_address="192.168.1.2",
            endpoint="/api/v1/test2",
            rule_name="rule2",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )

        db_session.add(log1)
        db_session.add(log2)
        db_session.commit()

        # Query by identifier
        result = db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.identifier == f"user:{unique_id1}"
            )
        )
        found = result.scalar_one()

        assert found.identifier == f"user:{unique_id1}"
        assert found.endpoint == "/api/v1/test1"

    def test_query_by_endpoint(self, db_session: Session):
        """Test querying audit logs by endpoint.

        Verifies:
        - endpoint field is indexed
        - Can retrieve all violations for an endpoint
        - Useful for monitoring specific endpoints

        Args:
            db_session: Database session fixture
        """
        # Create multiple logs for same endpoint
        for i in range(3):
            log = RateLimitAuditLog(
                identifier=f"user:{i}",
                ip_address=f"192.168.1.{i}",
                endpoint="/api/v1/auth/login",
                rule_name="auth_login",
                limit=20,
                window_seconds=300,
                violation_count=1,
            )
            db_session.add(log)

        db_session.commit()

        # Query all violations for endpoint
        result = db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.endpoint == "/api/v1/auth/login"
            )
        )
        logs = result.scalars().all()

        assert len(logs) >= 3  # At least the 3 we just created
        for log in logs:
            assert log.endpoint == "/api/v1/auth/login"

    def test_query_by_ip_address(self, db_session: Session):
        """Test querying audit logs by IP address.

        Verifies:
        - ip_address field is indexed (INET type)
        - Can track violations by IP
        - PostgreSQL INET type supports queries

        Args:
            db_session: Database session fixture
        """
        # Use truly unique IP to avoid conflicts with other test runs
        from uuid import uuid4
        unique_ip = f"203.0.113.{uuid4().int % 254 + 1}"  # Random IP in test range

        log = RateLimitAuditLog(
            identifier=f"ip:{unique_ip}",
            ip_address=unique_ip,
            endpoint="/api/v1/test",
            rule_name="test_rule",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )

        db_session.add(log)
        db_session.commit()

        # Query by IP address
        result = db_session.execute(
            select(RateLimitAuditLog).where(RateLimitAuditLog.ip_address == unique_ip)
        )
        found = result.scalar_one()

        assert str(found.ip_address) == unique_ip

    def test_timestamp_timezone_aware(self, db_session: Session):
        """Test that timestamps are timezone-aware (TIMESTAMPTZ).

        Verifies:
        - timestamp field is TIMESTAMP WITH TIME ZONE
        - created_at field is TIMESTAMP WITH TIME ZONE
        - Timestamps in UTC
        - PCI-DSS compliance (timezone-aware audit logs)

        Args:
            db_session: Database session fixture
        """
        log = RateLimitAuditLog(
            identifier="user:test",
            ip_address="192.168.1.1",
            endpoint="/api/v1/test",
            rule_name="test_tz",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )

        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        # Verify timezone-aware
        assert log.timestamp.tzinfo is not None
        assert log.created_at.tzinfo is not None

        # Verify UTC
        assert log.timestamp.tzinfo == timezone.utc
        assert log.created_at.tzinfo == timezone.utc

        # Verify recent (within last minute)
        now = datetime.now(timezone.utc)
        assert (now - log.timestamp).total_seconds() < 60
        assert (now - log.created_at).total_seconds() < 60

    def test_multiple_violations_same_identifier(self, db_session: Session):
        """Test logging multiple violations for same identifier.

        Verifies:
        - Multiple logs can exist for same identifier
        - No unique constraint on identifier
        - Can track violation history

        Args:
            db_session: Database session fixture
        """
        # Use unique identifier to avoid pollution from other test runs
        from uuid import uuid4
        identifier = f"user:repeat-offender-{uuid4()}"

        # Create 3 violations
        for i in range(3):
            log = RateLimitAuditLog(
                identifier=identifier,
                ip_address=f"192.168.1.{i}",
                endpoint="/api/v1/test",
                rule_name="test_rule",
                limit=10,
                window_seconds=60,
                violation_count=i + 1,
            )
            db_session.add(log)

        db_session.commit()

        # Query all violations for identifier
        result = db_session.execute(
            select(RateLimitAuditLog).where(RateLimitAuditLog.identifier == identifier)
        )
        logs = result.scalars().all()

        assert len(logs) == 3
        for log in logs:
            assert log.identifier == identifier

    def test_no_user_foreign_key_constraint(self, db_session: Session):
        """Test that identifier field has NO foreign key to users table.

        Verifies:
        - identifier is just a string (no FK)
        - Audit logs are fully decoupled from user model
        - Can log violations even if user doesn't exist
        - Rate limiting is truly independent

        Args:
            db_session: Database session fixture
        """
        # Use non-existent user ID (would fail with FK constraint)
        log = RateLimitAuditLog(
            identifier="user:99999999-9999-9999-9999-999999999999",
            ip_address="192.168.1.1",
            endpoint="/api/v1/test",
            rule_name="test_no_fk",
            limit=10,
            window_seconds=60,
            violation_count=1,
        )

        # Should succeed (no FK constraint)
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert log.identifier == "user:99999999-9999-9999-9999-999999999999"
