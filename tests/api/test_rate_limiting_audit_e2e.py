"""End-to-end API tests for rate limiting audit trail.

Tests verify the complete audit logging flow from API consumer perspective:
- HTTP 429 responses create database audit records
- Multiple violations create multiple audit records
- Audit data is queryable and usable for monitoring
- Different endpoints are logged separately

Architecture:
    - E2E tests (API → Middleware → Service → Database)
    - Uses FastAPI TestClient (synchronous)
    - Verifies complete request-to-audit-log flow
    - Tests from external API consumer perspective

Note:
    These tests verify the audit trail works end-to-end, complementing
    the unit tests (mocks) and integration tests (database only).
"""

from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session, select, delete

from src.models.rate_limit_audit import RateLimitAuditLog


class TestRateLimitAuditEndToEnd:
    """E2E tests for rate limiting audit trail from API perspective."""

    def test_http_429_creates_audit_record(
        self, client: TestClient, db_session: Session
    ):
        """Test that HTTP 429 response creates audit log in database.

        Verifies complete flow:
        1. Make requests to trigger rate limit
        2. Receive HTTP 429
        3. Audit log created in database
        4. Audit log has correct data

        Args:
            client: FastAPI test client
            db_session: Database session fixture
        """
        # Clean up any existing audit logs for this test
        db_session.execute(delete(RateLimitAuditLog))
        db_session.commit()

        # Trigger rate limit on auth/register (limit: 10 requests)
        endpoint = "/api/v1/auth/register"
        responses = []

        # Send 12 requests (10 allowed + 2 rate limited)
        for _ in range(12):
            response = client.post(
                endpoint,
                json={
                    "email": "test@example.com",
                    "password": "ValidPassword123!",
                    "name": "Test User",
                },
            )
            responses.append(response.status_code)

        # Verify we got at least one 429
        assert status.HTTP_429_TOO_MANY_REQUESTS in responses

        # Verify audit log was created
        result = db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.endpoint == "POST /api/v1/auth/register"
            )
        )
        audit_logs = result.scalars().all()

        # Should have at least one audit log
        assert len(audit_logs) > 0

        # Verify audit log data
        log = audit_logs[0]
        assert log.endpoint == "POST /api/v1/auth/register"
        assert log.rule_name == "POST /api/v1/auth/register"
        assert log.limit == 10  # From config
        assert log.window_seconds == 300  # Calculated from refill_rate
        assert log.violation_count == 1
        assert log.identifier is not None  # Should have identifier
        # TestClient uses "testclient" IP which gets sanitized to 127.0.0.1
        assert str(log.ip_address) == "127.0.0.1"

    def test_multiple_violations_create_multiple_records(
        self, client: TestClient, db_session: Session
    ):
        """Test that multiple rate limit violations create separate audit records.

        Verifies:
        - Each violation creates a new audit log
        - Violations are tracked independently
        - Can see violation history

        Args:
            client: FastAPI test client
            db_session: Database session fixture
        """
        # Clean up any existing audit logs
        db_session.execute(delete(RateLimitAuditLog))
        db_session.commit()

        endpoint = "/api/v1/auth/register"

        # First violation burst (exceed limit of 10)
        for _ in range(12):
            client.post(
                endpoint,
                json={
                    "email": "test1@example.com",
                    "password": "ValidPassword123!",
                    "name": "Test User 1",
                },
            )

        # Check audit logs after first burst
        result = db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.endpoint == "POST /api/v1/auth/register"
            )
        )
        logs_after_first = result.scalars().all()
        first_count = len(logs_after_first)

        # Second violation burst
        for _ in range(5):
            client.post(
                endpoint,
                json={
                    "email": "test2@example.com",
                    "password": "ValidPassword123!",
                    "name": "Test User 2",
                },
            )

        # Check audit logs after second burst
        result = db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.endpoint == "POST /api/v1/auth/register"
            )
        )
        logs_after_second = result.scalars().all()
        second_count = len(logs_after_second)

        # Should have more logs after second burst
        assert second_count > first_count
        assert first_count > 0

        # All logs should be for same endpoint
        for log in logs_after_second:
            assert log.endpoint == "POST /api/v1/auth/register"

    def test_different_endpoints_logged_separately(
        self, client: TestClient, db_session: Session
    ):
        """Test that different endpoints are logged separately.

        Verifies:
        - Each endpoint has independent audit logs
        - Can filter logs by endpoint
        - Endpoint isolation in audit trail

        Args:
            client: FastAPI test client
            db_session: Database session fixture
        """
        # Clean up any existing audit logs
        db_session.execute(delete(RateLimitAuditLog))
        db_session.commit()

        # Trigger rate limit on login endpoint (limit: 20 requests)
        login_endpoint = "/api/v1/auth/login"
        for _ in range(22):
            client.post(
                login_endpoint,
                json={"email": "test@example.com", "password": "wrong"},
            )

        # Trigger rate limit on register endpoint (limit: 10 requests)
        register_endpoint = "/api/v1/auth/register"
        for _ in range(12):
            client.post(
                register_endpoint,
                json={
                    "email": "test@example.com",
                    "password": "ValidPassword123!",
                    "name": "Test User",
                },
            )

        # Query logs for login endpoint
        result = db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.endpoint == "POST /api/v1/auth/login"
            )
        )
        login_logs = result.scalars().all()

        # Query logs for register endpoint
        result = db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.endpoint == "POST /api/v1/auth/register"
            )
        )
        register_logs = result.scalars().all()

        # Both endpoints should have audit logs
        assert len(login_logs) > 0
        assert len(register_logs) > 0

        # Logs should be separate
        for log in login_logs:
            assert log.endpoint == "POST /api/v1/auth/login"
            assert log.rule_name == "POST /api/v1/auth/login"

        for log in register_logs:
            assert log.endpoint == "POST /api/v1/auth/register"
            assert log.rule_name == "POST /api/v1/auth/register"

    def test_audit_logs_queryable_by_ip(self, client: TestClient, db_session: Session):
        """Test that audit logs can be queried by IP address.

        Verifies:
        - Can filter logs by IP address
        - Useful for tracking violations by source
        - IP address indexed and searchable

        Args:
            client: FastAPI test client
            db_session: Database session fixture
        """
        # Clean up any existing audit logs
        db_session.execute(delete(RateLimitAuditLog))
        db_session.commit()

        # Trigger rate limit
        endpoint = "/api/v1/auth/register"
        for _ in range(12):
            client.post(
                endpoint,
                json={
                    "email": "test@example.com",
                    "password": "ValidPassword123!",
                    "name": "Test User",
                },
            )

        # Query by IP address (TestClient IP gets sanitized to 127.0.0.1)
        result = db_session.execute(
            select(RateLimitAuditLog).where(RateLimitAuditLog.ip_address == "127.0.0.1")
        )
        logs = result.scalars().all()

        # Should find logs
        assert len(logs) > 0

        # All logs should be from sanitized IP
        for log in logs:
            assert str(log.ip_address) == "127.0.0.1"

    def test_audit_logs_queryable_by_identifier(
        self, client: TestClient, db_session: Session
    ):
        """Test that audit logs can be queried by identifier.

        Verifies:
        - Can filter logs by identifier (IP-based for unauthenticated)
        - identifier field is indexed and searchable
        - Useful for tracking specific users/IPs

        Args:
            client: FastAPI test client
            db_session: Database session fixture
        """
        # Clean up any existing audit logs
        db_session.execute(delete(RateLimitAuditLog))
        db_session.commit()

        # Trigger rate limit
        endpoint = "/api/v1/auth/register"
        for _ in range(12):
            client.post(
                endpoint,
                json={
                    "email": "test@example.com",
                    "password": "ValidPassword123!",
                    "name": "Test User",
                },
            )

        # Query by identifier (should be "ip:testclient")
        result = db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.identifier == "ip:testclient"
            )
        )
        logs = result.scalars().all()

        # Should find logs
        assert len(logs) > 0

        # All logs should have same identifier
        for log in logs:
            assert log.identifier == "ip:testclient"

    def test_audit_logs_contain_complete_violation_data(
        self, client: TestClient, db_session: Session
    ):
        """Test that audit logs contain all required violation data.

        Verifies:
        - All fields populated correctly
        - Timestamps are present
        - Rule configuration captured
        - Useful for analysis and monitoring

        Args:
            client: FastAPI test client
            db_session: Database session fixture
        """
        # Clean up any existing audit logs
        db_session.execute(delete(RateLimitAuditLog))
        db_session.commit()

        # Trigger rate limit
        endpoint = "/api/v1/auth/register"
        for _ in range(12):
            client.post(
                endpoint,
                json={
                    "email": "test@example.com",
                    "password": "ValidPassword123!",
                    "name": "Test User",
                },
            )

        # Get audit log
        result = db_session.execute(
            select(RateLimitAuditLog).where(
                RateLimitAuditLog.endpoint == "POST /api/v1/auth/register"
            )
        )
        log = result.scalars().first()

        # Verify all required fields present
        assert log is not None
        assert log.id is not None
        assert log.timestamp is not None
        assert log.created_at is not None
        assert log.identifier is not None
        assert log.ip_address is not None
        assert log.endpoint == "POST /api/v1/auth/register"
        assert log.rule_name == "POST /api/v1/auth/register"
        assert log.limit == 10
        assert log.window_seconds == 300  # From config
        assert log.violation_count == 1

        # Verify timestamps are timezone-aware
        assert log.timestamp.tzinfo is not None
        assert log.created_at.tzinfo is not None
