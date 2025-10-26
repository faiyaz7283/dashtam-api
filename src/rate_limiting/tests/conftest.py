"""Rate Limiting Bounded Context Test Configuration.

This module provides test fixtures isolated to the rate limiting bounded context.
Following DDD principles, this bounded context manages its own test infrastructure
without coupling to application-level test configuration.

Architecture:
    - Bounded Context: Rate limiting is a self-contained domain
    - Test Isolation: Each test gets a clean database state
    - Zero Coupling: No dependencies on application-level conftest.py
    - Database Cleanup: Only rate limiting tables (RateLimitAuditLog)

Fixtures:
    - rate_limit_db_session: Synchronous database session for rate limiting tests
    - test_user: User fixture for authenticated rate limit tests

Usage:
    Tests in src/rate_limiting/tests/ automatically use these fixtures.
    
    Example:
        def test_audit_backend(rate_limit_db_session):
            backend = DatabaseAuditBackend(rate_limit_db_session)
            await backend.log_violation(...)
"""

import pytest
from typing import Generator
from sqlmodel import Session, create_engine, delete, select

from src.core.config import settings
from src.rate_limiting.models import RateLimitAuditLog
from src.models.user import User


# Convert async database URL to sync for synchronous testing
# This follows the same pattern as application-level tests
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg://"
)

# Create engine for rate limiting bounded context tests
# Note: Shares same database as application tests, but manages own cleanup
engine = create_engine(
    TEST_DATABASE_URL,
    echo=settings.DB_ECHO if hasattr(settings, "DB_ECHO") else False,
    pool_pre_ping=True,  # Verify connections before using
)


@pytest.fixture(scope="function")
def rate_limit_db_session() -> Generator[Session, None, None]:
    """Database session isolated to rate limiting bounded context.

    Provides a clean database session for each test function. Only manages
    cleanup of rate limiting tables (RateLimitAuditLog), ensuring zero
    coupling to application-level test infrastructure.

    Yields:
        Session: Synchronous SQLModel session for database operations

    Cleanup:
        - Rolls back any uncommitted transactions
        - Deletes all RateLimitAuditLog entries
        - Ensures next test starts with clean slate

    Example:
        >>> def test_audit_log(rate_limit_db_session):
        ...     backend = DatabaseAuditBackend(rate_limit_db_session)
        ...     await backend.log_violation(...)
        ...     # Audit log automatically cleaned up after test
    """
    with Session(engine) as session:
        yield session

        # Rollback any pending transaction (in case of errors)
        try:
            session.rollback()
        except Exception:
            pass

        # Cleanup only rate limiting bounded context tables
        # This maintains bounded context isolation
        try:
            session.execute(delete(RateLimitAuditLog))
            session.commit()
        except Exception:
            session.rollback()


@pytest.fixture(scope="function")
def test_user(rate_limit_db_session: Session) -> Generator[User, None, None]:
    """Create a test user for authenticated rate limit tests.

    Some rate limiting tests need to verify user_id foreign key relationships.
    This fixture provides a minimal user record for those tests.

    Args:
        rate_limit_db_session: Database session fixture

    Yields:
        User: Test user with verified email

    Cleanup:
        User is automatically deleted via CASCADE when rate_limit_db_session
        cleans up (ON DELETE CASCADE relationship).

    Example:
        >>> def test_with_user(rate_limit_db_session, test_user):
        ...     await backend.log_violation(user_id=test_user.id, ...)
        ...     # Verify user_id foreign key works
    """
    user = User(
        email="ratelimit-test@example.com",
        hashed_password="$2b$12$dummy_hash_for_testing",
        name="Rate Limit Test User",
        email_verified=True,  # Verified user for testing
    )
    rate_limit_db_session.add(user)
    rate_limit_db_session.commit()
    rate_limit_db_session.refresh(user)

    yield user

    # Cleanup: Delete user explicitly
    # (rate_limit_db_session cleanup will handle cascading to audit logs)
    try:
        rate_limit_db_session.execute(delete(User).where(User.id == user.id))
        rate_limit_db_session.commit()
    except Exception:
        rate_limit_db_session.rollback()
