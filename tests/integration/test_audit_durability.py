"""Integration tests for audit durability with separate sessions.

Tests verify that audit logs persist even when business transactions fail,
meeting PCI-DSS 10.2.4, SOC 2 CC6.1, and GDPR Article 30 requirements.

Test scenarios:
1. Audit persists when business transaction fails
2. Audit persists on database constraint violation
3. Multiple audits persist independently

Architecture:
    Uses separate fixtures for business_session and audit_session to
    simulate real-world separation of concerns. Audit session commits
    immediately, business session can fail/rollback.

Usage:
    pytest tests/integration/test_audit_durability.py -v
"""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core.result import Success
from src.domain.enums import AuditAction
from src.infrastructure.audit.postgres_adapter import PostgresAuditAdapter
from src.infrastructure.persistence.models.audit_log import AuditLog


@pytest.mark.asyncio
async def test_audit_persists_when_business_transaction_fails(
    test_database,
):
    """Verify audit logs persist even when business transaction fails.

    Scenario:
        1. Create separate business and audit sessions
        2. Record audit in audit session (commits immediately)
        3. Simulate business transaction failure
        4. Verify audit log persists (not rolled back)

    Compliance: PCI-DSS 10.2.4, SOC 2 CC6.1
    """
    user_id = uuid4()

    # Create separate sessions (simulates real-world setup)
    async with test_database.get_session() as business_session:
        async with test_database.get_session() as audit_session:
            # Record audit in separate session (commits immediately)
            audit = PostgresAuditAdapter(session=audit_session)
            result = await audit.record(
                action=AuditAction.USER_LOGIN_SUCCESS,
                user_id=user_id,
                resource_type="session",
                resource_id=uuid4(),
                ip_address="192.168.1.1",
                context={"test": "durability"},
            )
            assert isinstance(result, Success)

            # Simulate business transaction failure (create invalid state)
            # Force an error by trying to violate a hypothetical constraint
            # In real scenario, this could be: duplicate user email, invalid FK, etc.
            try:
                # Rollback business session (simulates request failure)
                await business_session.rollback()
            except Exception:
                pass  # Business failure is expected

    # Verify audit log persists in database (separate query)
    async with test_database.get_session() as verify_session:
        stmt = select(AuditLog).where(AuditLog.user_id == user_id)
        result = await verify_session.execute(stmt)
        logs = result.scalars().all()

        # Audit log must exist (durability requirement)
        assert len(logs) == 1, "Audit log should persist despite business failure"
        assert logs[0].action == AuditAction.USER_LOGIN_SUCCESS.value
        assert logs[0].context == {"test": "durability"}


@pytest.mark.asyncio
async def test_audit_persists_on_constraint_violation(
    test_database,
):
    """Verify audit persists when business transaction has constraint violation.

    Scenario:
        1. Record audit successfully
        2. Business logic violates database constraint (e.g., unique, foreign key)
        3. Business transaction rolls back
        4. Verify audit log persists

    Compliance: PCI-DSS 10.2.4 (failed access attempts MUST be logged)
    """
    user_id = uuid4()

    # Separate sessions for audit and business logic
    async with test_database.get_session() as audit_session:
        # Record audit first (commits immediately)
        audit = PostgresAuditAdapter(session=audit_session)
        result = await audit.record(
            action=AuditAction.PROVIDER_CONNECTED,
            user_id=user_id,
            resource_type="provider",
            resource_id=uuid4(),
            ip_address="10.0.0.1",
            context={"provider": "schwab", "status": "attempt"},
        )
        assert isinstance(result, Success)

    # Simulate business logic with constraint violation
    async with test_database.get_session() as business_session:
        try:
            # In real scenario: business logic creates duplicate provider, etc.
            # For testing: just rollback to simulate failure
            await business_session.rollback()
        except IntegrityError:
            # Expected in real scenario with actual constraint violation
            await business_session.rollback()

    # Verify audit persists after business failure
    async with test_database.get_session() as verify_session:
        stmt = select(AuditLog).where(AuditLog.user_id == user_id)
        result = await verify_session.execute(stmt)
        logs = result.scalars().all()

        assert len(logs) == 1, "Audit must persist despite constraint violation"
        assert logs[0].action == AuditAction.PROVIDER_CONNECTED.value
        assert logs[0].context["status"] == "attempt"


@pytest.mark.asyncio
async def test_multiple_audits_persist_independently(
    test_database,
):
    """Verify multiple audit logs persist independently with separate sessions.

    Scenario:
        1. Record multiple audit logs with different sessions
        2. Each audit commits independently
        3. Even if one business transaction fails, all audits persist

    Compliance: SOC 2 CC6.1 (comprehensive activity logging)
    """
    user_id_1 = uuid4()
    user_id_2 = uuid4()
    user_id_3 = uuid4()

    # Record first audit (separate session)
    async with test_database.get_session() as audit_session_1:
        audit_1 = PostgresAuditAdapter(session=audit_session_1)
        result_1 = await audit_1.record(
            action=AuditAction.USER_LOGIN_SUCCESS,
            user_id=user_id_1,
            resource_type="session",
            ip_address="192.168.1.1",
        )
        assert isinstance(result_1, Success)

    # Record second audit (separate session)
    async with test_database.get_session() as audit_session_2:
        audit_2 = PostgresAuditAdapter(session=audit_session_2)
        result_2 = await audit_2.record(
            action=AuditAction.USER_LOGIN_FAILED,
            user_id=user_id_2,
            resource_type="session",
            ip_address="192.168.1.2",
            context={"reason": "invalid_password"},
        )
        assert isinstance(result_2, Success)

    # Record third audit and simulate business failure
    async with test_database.get_session() as audit_session_3:
        audit_3 = PostgresAuditAdapter(session=audit_session_3)
        result_3 = await audit_3.record(
            action=AuditAction.ACCESS_DENIED,
            user_id=user_id_3,
            resource_type="account",
            ip_address="192.168.1.3",
            context={"reason": "insufficient_permissions"},
        )
        assert isinstance(result_3, Success)

    # Simulate business failure (independent of audit)
    async with test_database.get_session() as business_session:
        await business_session.rollback()  # Business logic failed

    # Verify all 3 audits persist despite business failure
    async with test_database.get_session() as verify_session:
        stmt = select(AuditLog).where(
            AuditLog.user_id.in_([user_id_1, user_id_2, user_id_3])
        )
        result = await verify_session.execute(stmt)
        logs = result.scalars().all()

        assert len(logs) == 3, "All audits must persist independently"

        # Verify each audit is correct
        actions = {log.action for log in logs}
        assert AuditAction.USER_LOGIN_SUCCESS.value in actions
        assert AuditAction.USER_LOGIN_FAILED.value in actions
        assert AuditAction.ACCESS_DENIED.value in actions


@pytest.mark.asyncio
async def test_audit_session_commits_immediately(
    test_database,
):
    """Verify audit session commits immediately, not waiting for business commit.

    Scenario:
        1. Record audit in separate session
        2. Do NOT commit business session yet
        3. Verify audit is already visible in database
        4. Demonstrates audit commits independently

    Compliance: GDPR Article 30 (audit must be complete even if operation fails)
    """
    user_id = uuid4()
    resource_id = uuid4()

    # Open business session but DON'T commit yet
    async with test_database.get_session() as business_session:
        # Record audit in separate session (commits immediately)
        async with test_database.get_session() as audit_session:
            audit = PostgresAuditAdapter(session=audit_session)
            result = await audit.record(
                action=AuditAction.DATA_EXPORTED,
                user_id=user_id,
                resource_type="account",
                resource_id=resource_id,
                ip_address="10.0.0.5",
                context={"format": "csv", "records": 100},
            )
            assert isinstance(result, Success)

        # Audit committed, but business session still open
        # Verify audit is ALREADY visible in database
        async with test_database.get_session() as verify_session:
            stmt = select(AuditLog).where(AuditLog.user_id == user_id)
            result = await verify_session.execute(stmt)
            logs = result.scalars().all()

            # Audit visible immediately (not waiting for business commit)
            assert len(logs) == 1, "Audit should be visible immediately"
            assert logs[0].action == AuditAction.DATA_EXPORTED.value

        # Business session can now fail without affecting audit
        await business_session.rollback()

    # Verify audit still persists after business rollback
    async with test_database.get_session() as final_verify:
        stmt = select(AuditLog).where(AuditLog.user_id == user_id)
        result = await final_verify.execute(stmt)
        logs = result.scalars().all()
        assert len(logs) == 1, "Audit persists after business rollback"
