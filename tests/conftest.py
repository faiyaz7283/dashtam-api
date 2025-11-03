"""Global pytest configuration and fixtures for Dashtam tests.

This module implements the FastAPI official testing pattern using synchronous
tests with TestClient and Session. This avoids async/greenlet complexity while
providing complete test coverage.

Key Principles:
- Synchronous tests (regular def test_*(), NOT async def)
- FastAPI's TestClient handles async/sync bridge internally
- Real PostgreSQL database for production parity
- Session-scoped setup with function-scoped sessions for isolation
"""

from collections.abc import Generator
import asyncio

import pytest
import redis.asyncio as redis
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, delete

from src.core.config import settings
from src.main import app
from src.models.provider import (
    Provider,
    ProviderConnection,
    ProviderToken,
    ProviderAuditLog,
)
from src.models.user import User
from tests.test_config import _TestSettings, get_test_settings

# Use test PostgreSQL database (production parity)
# Database is managed by docker-compose.test.yml
# In test environment, DATABASE_URL points to test database
# Convert from asyncpg to psycopg (v3) for synchronous testing
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg://"
)

# Create engine for test database
# Note: Using sync engine for sync tests (no async complexity)
engine = create_engine(
    TEST_DATABASE_URL,
    echo=settings.DB_ECHO if hasattr(settings, "DB_ECHO") else False,
    pool_pre_ping=True,  # Verify connections before using
)


@pytest.fixture(scope="session")
def test_settings() -> _TestSettings:
    """Provide test-specific settings loaded from .env file.

    Returns:
        _TestSettings instance with all configuration loaded from environment
        variables, following the same patterns as main app.
    """
    return get_test_settings()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up test database schema once per test session.

    This fixture ensures database schema is ready before any tests run.
    In CI/test environments, Alembic migrations run first (docker-compose.test.yml).
    In local development, creates tables from SQLModel if migrations haven't run.

    By using autouse=True, this blocks all tests until schema is ready,
    ensuring consistent behavior across all environments.
    """
    # Check if Alembic migrations have already run (CI environment)
    # If alembic_version table exists, skip create_all (migrations handle schema)
    from sqlalchemy import inspect
    import os

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # In CI, migrations handle everything - skip setup
    if os.getenv("CI") == "true" or "alembic_version" in existing_tables:
        yield
        return  # Skip cleanup too

    # Local test environment: create tables from SQLModel metadata
    SQLModel.metadata.create_all(engine)

    yield

    # Cleanup: Drop all tables after test session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="session")
def db() -> Generator[Session, None, None]:
    """Session-scoped database session.

    Provides a database connection that persists across all tests in the session.
    Individual tests use db_session for isolation.
    """
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="function")
def db_session(db: Session, request) -> Generator[Session, None, None]:
    """Function-scoped database session for test isolation.

    Each test gets access to the session. Tests should create their own
    data using fixtures or within the test. Cleanup happens automatically
    via relationship cascades or can be done explicitly.

    Note: This is synchronous Session, not AsyncSession. Perfect for testing
    since TestClient handles the async/sync bridge internally.

    Smoke tests marked with `@pytest.mark.smoke_test` skip database cleanup
    to allow state to persist across sequential test functions.
    """
    yield db

    # Rollback any pending transaction (in case of errors)
    try:
        db.rollback()
    except Exception:
        pass

    # Skip cleanup for smoke tests (they need state to persist)
    if request.node.get_closest_marker("smoke_test"):
        return

    # Optional: Explicit cleanup after each test
    # Deletes are cascaded based on model relationships
    # Note: Rate limiting tests manage their own cleanup (bounded context)
    try:
        db.execute(delete(ProviderAuditLog))  # Provider audit logs
        db.execute(delete(ProviderToken))
        db.execute(delete(ProviderConnection))
        db.execute(delete(Provider))
        db.execute(delete(User))
        db.commit()
    except Exception:
        db.rollback()


@pytest.fixture(scope="function", autouse=True)
def reset_cache_singleton():
    """Reset cache singleton before each test to prevent state issues.

    The cache factory uses a singleton pattern that persists across tests.
    When function-scoped TestClient fixtures create/destroy app contexts,
    the Redis connection can get into an inconsistent state.

    This fixture ensures each test starts with a fresh cache instance.
    """
    from src.core.cache import factory

    # Reset singleton before test
    factory._cache_instance = None

    yield  # Run test

    # Reset singleton after test (cleanup)
    factory._cache_instance = None


@pytest.fixture(scope="function", autouse=True)
def reset_rate_limits():
    """Reset Redis rate limit buckets before each test for isolation.

    This fixture ensures test isolation by clearing all rate limit state
    from Redis between tests. Without this, rate limit buckets persist
    across tests causing failures when tests expect fresh buckets.

    Why autouse=True:
        - Ensures all tests start with clean rate limit state
        - Prevents test order dependencies
        - Matches pytest best practices for test isolation

    Redis Key Pattern:
        rate_limit:* (all rate limiting keys)

    Examples of keys deleted:
        - rate_limit:ip:ip:testclient:POST /api/v1/auth/register:tokens
        - rate_limit:ip:ip:testclient:POST /api/v1/auth/register:time
        - rate_limit:user:uuid:GET /api/v1/providers:tokens

    Note:
        This fixture uses SCAN + DEL pattern (production-safe) instead of
        FLUSHDB to avoid affecting other test data in Redis.

        This is a synchronous fixture that wraps async Redis operations
        using asyncio.run() to work with synchronous pytest tests.
    """

    async def _cleanup_redis():
        """Async function to cleanup Redis rate limit keys."""
        # Connect to test Redis (Docker service in test environment)
        redis_client = redis.Redis(
            host="redis",  # Docker service name in test environment
            port=6379,
            db=0,
            decode_responses=True,
        )

        try:
            # Delete all rate limit keys using SCAN pattern (production-safe)
            # SCAN is preferred over KEYS in production, but both work in tests
            cursor = 0
            pattern = "rate_limit:*"

            while True:
                # Scan for rate limit keys (returns cursor and batch of keys)
                cursor, keys = await redis_client.scan(
                    cursor=cursor, match=pattern, count=100
                )

                # Delete keys if any found
                if keys:
                    await redis_client.delete(*keys)

                # Break when cursor returns to 0 (full scan complete)
                if cursor == 0:
                    break

        except Exception as e:
            # Log but don't fail tests if Redis cleanup fails
            # Tests should still pass even if rate limiter is unavailable (fail-open)
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to reset rate limits in Redis: {e}")

        finally:
            # Clean up Redis connection
            await redis_client.aclose()

    # Run async cleanup synchronously (compatible with sync pytest tests)
    asyncio.run(_cleanup_redis())

    yield  # Run test

    # No cleanup needed after test (cleanup happens before next test)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient for making HTTP requests to the application.

    TestClient automatically handles the async/sync bridge, allowing
    synchronous test code to work with async FastAPI endpoints.

    This fixture overrides FastAPI's async dependencies with synchronous
    test-compatible versions to ensure consistent testing across all environments.

    Function-scoped for full test isolation (prevents state pollution).
    """
    from src.core.database import get_session

    # Create wrapper class to handle async-to-sync conversion
    class AsyncToSyncWrapper:
        """Wrapper to make sync Session work with async endpoints.

        CRITICAL: Expires session state after commit to ensure fresh data
        is visible in subsequent requests (required for CI environment).
        """

        def __init__(self, sync_session: Session):
            self.session = sync_session

        async def execute(self, *args, **kwargs):
            """Wrap sync execute to be awaitable."""
            return self.session.execute(*args, **kwargs)

        async def commit(self):
            """Wrap sync commit to be awaitable.

            After commit, expire all session state to force fresh queries.
            This ensures data committed in one request is visible in the next.
            """
            result = self.session.commit()
            # Expire all objects in session to force refresh on next access
            self.session.expire_all()
            return result

        async def rollback(self):
            """Wrap sync rollback to be awaitable."""
            return self.session.rollback()

        async def refresh(self, *args, **kwargs):
            """Wrap sync refresh to be awaitable."""
            return self.session.refresh(*args, **kwargs)

        async def flush(self, *args, **kwargs):
            """Wrap sync flush to be awaitable."""
            return self.session.flush(*args, **kwargs)

        def add(self, *args, **kwargs):
            """Direct pass-through for add (not awaited)."""
            return self.session.add(*args, **kwargs)

        async def delete(self, *args, **kwargs):
            """Wrap sync delete to be awaitable."""
            return self.session.delete(*args, **kwargs)

        async def close(self):
            """Wrap close to be awaitable."""
            pass  # Session lifecycle managed by fixture

    # Override async database session with wrapped sync session
    async def override_get_session():
        """Provide wrapped synchronous session for async endpoints.

        Expires all session objects at start of each request to ensure
        fresh data is queried (required for CI environment).
        """
        wrapper = AsyncToSyncWrapper(db)
        # Expire all cached objects to force fresh queries
        db.expire_all()
        try:
            yield wrapper
        finally:
            pass

    # Apply dependency overrides
    app.dependency_overrides[get_session] = override_get_session
    # Note: get_current_user is NOT overridden here - JWT auth tests use real auth

    with TestClient(app) as c:
        yield c

    # Clean up overrides after test
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client_with_mock_auth(db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with mocked authentication.

    Used for testing authenticated endpoints with a mock user.
    This client overrides both the database session and the authentication,
    allowing tests to bypass JWT authentication while still testing
    authorization logic.

    Function-scoped for full test isolation (prevents auth override pollution).
    """
    from src.core.database import get_session
    from src.api.dependencies import get_current_user
    from src.models.user import User

    # Create wrapper class to handle async-to-sync conversion
    class AsyncToSyncWrapper:
        """Wrapper to make sync Session work with async endpoints.

        CRITICAL: Expires session state after commit to ensure fresh data
        is visible in subsequent requests (required for CI environment).
        """

        def __init__(self, sync_session: Session):
            self.session = sync_session

        async def execute(self, *args, **kwargs):
            """Wrap sync execute to be awaitable."""
            return self.session.execute(*args, **kwargs)

        async def commit(self):
            """Wrap sync commit to be awaitable.

            After commit, expire all session state to force fresh queries.
            This ensures data committed in one request is visible in the next.
            """
            result = self.session.commit()
            # Expire all objects in session to force refresh on next access
            self.session.expire_all()
            return result

        async def rollback(self):
            """Wrap sync rollback to be awaitable."""
            return self.session.rollback()

        async def refresh(self, *args, **kwargs):
            """Wrap sync refresh to be awaitable."""
            return self.session.refresh(*args, **kwargs)

        async def flush(self, *args, **kwargs):
            """Wrap sync flush to be awaitable."""
            return self.session.flush(*args, **kwargs)

        def add(self, *args, **kwargs):
            """Direct pass-through for add (not awaited)."""
            return self.session.add(*args, **kwargs)

        async def delete(self, *args, **kwargs):
            """Wrap sync delete to be awaitable."""
            return self.session.delete(*args, **kwargs)

        async def close(self):
            """Wrap close to be awaitable."""
            pass  # Session lifecycle managed by fixture

    # Override async database session with wrapped sync session
    async def override_get_session():
        """Provide wrapped synchronous session for async endpoints.

        Expires all session objects at start of each request to ensure
        fresh data is queried (required for CI environment).
        """
        wrapper = AsyncToSyncWrapper(db)
        # Expire all cached objects to force fresh queries
        db.expire_all()
        try:
            yield wrapper
        finally:
            pass

    # Mock the authentication dependency to return a test user
    async def override_get_current_user():
        """Provide a mock authenticated user."""
        from sqlmodel import select

        # Try to get existing test user
        result = db.execute(select(User).where(User.email == "test@example.com"))
        user = result.scalar_one_or_none()

        # If no test user exists, create one
        if not user:
            user = User(
                email="test@example.com",
                name="Test User",
                email_verified=True,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user

    # Apply dependency overrides for both database and authentication
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as c:
        yield c

    # Clean up overrides after test
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client_no_auth(db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient without authentication override.

    Used for testing endpoints that require authentication enforcement.
    Auth tests use this fixture to verify 401 responses are returned.

    This client has the database override but NOT the authentication override,
    allowing tests to verify that authentication is properly enforced.

    Function-scoped for full test isolation (prevents auth override pollution).
    """
    from src.core.database import get_session

    # Create wrapper class to handle async-to-sync conversion
    class AsyncToSyncWrapper:
        """Wrapper to make sync Session work with async endpoints."""

        def __init__(self, sync_session: Session):
            self.session = sync_session

        async def execute(self, *args, **kwargs):
            """Wrap sync execute to be awaitable."""
            return self.session.execute(*args, **kwargs)

        async def commit(self):
            """Wrap sync commit to be awaitable."""
            return self.session.commit()

        async def rollback(self):
            """Wrap sync rollback to be awaitable."""
            return self.session.rollback()

        async def refresh(self, *args, **kwargs):
            """Wrap sync refresh to be awaitable."""
            return self.session.refresh(*args, **kwargs)

        async def flush(self, *args, **kwargs):
            """Wrap sync flush to be awaitable."""
            return self.session.flush(*args, **kwargs)

        def add(self, *args, **kwargs):
            """Direct pass-through for add (not awaited)."""
            return self.session.add(*args, **kwargs)

        async def delete(self, *args, **kwargs):
            """Wrap sync delete to be awaitable."""
            return self.session.delete(*args, **kwargs)

        async def close(self):
            """Wrap close to be awaitable."""
            pass  # Session lifecycle managed by fixture

    # Override async database session with wrapped sync session
    async def override_get_session():
        """Provide wrapped synchronous session for async endpoints."""
        wrapper = AsyncToSyncWrapper(db)
        try:
            yield wrapper
        finally:
            pass

    # Apply ONLY database override, NOT authentication override
    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as c:
        yield c

    # Clean up overrides after test
    app.dependency_overrides.clear()


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user.

    Returns a user instance that's persisted in the database.
    Cleaned up automatically after test via db_session cleanup.
    """
    from sqlmodel import select

    # Try to get existing test user first
    result = db_session.execute(select(User).where(User.email == "test@example.com"))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email="test@example.com",
            name="Test User",
            email_verified=True,
            is_active=True,
            min_token_version=1,  # Initial token version
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    return user


@pytest.fixture
def test_user_2(db_session: Session) -> User:
    """Create a second test user for multi-user scenarios."""
    user = User(
        email="test2@example.com",
        name="Test User 2",
        email_verified=True,
        is_active=True,
        min_token_version=1,  # Initial token version
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_provider(db_session: Session, test_user: User) -> Provider:
    """Create a test provider instance.

    Returns a provider associated with test_user.
    """
    provider = Provider(
        user_id=test_user.id,
        provider_key="schwab",
        alias="Test Schwab Account",
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    return provider


@pytest.fixture
def test_provider_with_connection(
    db_session: Session, test_provider: Provider
) -> Provider:
    """Create a provider with an active connection.

    Useful for testing scenarios where provider is already connected.
    """
    from src.models.provider import ProviderStatus

    connection = ProviderConnection(
        provider_id=test_provider.id,
        status=ProviderStatus.ACTIVE,
        accounts_count=2,
        accounts_list=["account_1", "account_2"],
    )
    db_session.add(connection)
    db_session.commit()
    db_session.refresh(test_provider)
    return test_provider


# ============================================================================
# Authentication Fixtures
# ============================================================================


@pytest.fixture
def verified_user(db_session: Session) -> User:
    """Create a verified user with password for JWT authentication tests."""
    from src.services.password_service import PasswordService

    password_service = PasswordService()
    user = User(
        email="verified@example.com",
        name="Verified User",
        password_hash=password_service.hash_password("TestPassword123!"),
        email_verified=True,
        is_active=True,
        min_token_version=1,  # Initial token version
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session: Session) -> User:
    """Create an inactive user for testing inactive account scenarios."""
    from src.services.password_service import PasswordService

    password_service = PasswordService()
    user = User(
        email="inactive@example.com",
        name="Inactive User",
        password_hash=password_service.hash_password("TestPassword123!"),
        email_verified=True,
        is_active=False,  # Inactive
        min_token_version=1,  # Initial token version
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_tokens(db_session: Session, verified_user: User) -> dict:
    """Create JWT access and refresh tokens for authenticated tests.

    Returns dictionary with access_token, refresh_token, and user.
    """
    from src.services.jwt_service import JWTService
    from src.services.password_service import PasswordService
    from src.models.auth import RefreshToken
    from datetime import datetime, timedelta, timezone
    import secrets

    jwt_service = JWTService()
    password_service = PasswordService()

    # Create access token with version
    access_token = jwt_service.create_access_token(
        user_id=verified_user.id,
        email=verified_user.email,
        token_version=verified_user.min_token_version,
    )

    # Create refresh token (plain)
    plain_refresh_token = secrets.token_urlsafe(32)
    token_hash = password_service.hash_password(plain_refresh_token)

    # Get current global version from database
    from sqlmodel import select
    from src.models.security_config import SecurityConfig

    result = db_session.execute(select(SecurityConfig))
    security_config = result.scalar_one()
    current_global_version = security_config.global_min_token_version

    # Store refresh token in database with current versions
    refresh_token = RefreshToken(
        user_id=verified_user.id,
        token_hash=token_hash,
        token_version=verified_user.min_token_version,  # User's current version
        global_version_at_issuance=current_global_version,  # Current global version
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db_session.add(refresh_token)
    db_session.commit()
    db_session.refresh(refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": plain_refresh_token,
        "user": verified_user,
    }


@pytest.fixture
def authenticated_user(db_session: Session, verified_user: User) -> dict:
    """Create authenticated user with JWT tokens for API tests.

    This fixture creates a complete authentication session including:
    - Session record (device/browser connection)
    - Access token (JWT with jti claim linking to refresh token)
    - Refresh token (opaque, stored in database)
    - Refresh token ID (UUID for session management)
    - User object

    Returns:
        Dictionary with:
        - access_token: JWT access token for Authorization header
        - refresh_token: Opaque refresh token (plain, not hashed)
        - refresh_token_id: UUID of refresh token record in database
        - session_id: UUID of session record in database
        - user: User object

    Example:
        >>> def test_protected_endpoint(client, authenticated_user):
        ...     response = client.get(
        ...         "/api/v1/auth/me",
        ...         headers={"Authorization": f"Bearer {authenticated_user['access_token']}"}
        ...     )
        ...     assert response.status_code == 200

    Note:
        This fixture is for session management API tests that need jti claim.
        For simpler auth tests, use auth_tokens fixture instead.

        This fixture now creates a proper Session record to support session
        management endpoint tests (list/revoke sessions).
    """
    from src.services.jwt_service import JWTService
    from src.services.password_service import PasswordService
    from src.models.auth import RefreshToken
    from src.models.session import Session as SessionModel
    from datetime import datetime, timedelta, timezone
    import secrets

    jwt_service = JWTService()
    password_service = PasswordService()

    # Get current time
    now = datetime.now(timezone.utc)

    # Step 1: Create Session record first
    session = SessionModel(
        user_id=verified_user.id,
        device_info="Test Device",
        ip_address="127.0.0.1",
        user_agent="Test Client",
        location="Test Location",
        is_trusted=False,
        last_activity=now,
        expires_at=now + timedelta(days=30),
        is_revoked=False,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    # Step 2: Create refresh token (plain)
    plain_refresh_token = secrets.token_urlsafe(32)
    token_hash = password_service.hash_password(plain_refresh_token)

    # Get current global version from database
    from sqlmodel import select
    from src.models.security_config import SecurityConfig

    result = db_session.execute(select(SecurityConfig))
    security_config = result.scalar_one()
    current_global_version = security_config.global_min_token_version

    # Step 3: Store refresh token in database linked to session
    refresh_token = RefreshToken(
        user_id=verified_user.id,
        session_id=session.id,  # Link to session
        token_hash=token_hash,
        token_version=verified_user.min_token_version,  # User's current version
        global_version_at_issuance=current_global_version,  # Current global version
        expires_at=now + timedelta(days=30),
    )
    db_session.add(refresh_token)
    db_session.commit()
    db_session.refresh(refresh_token)

    # Step 4: Create access token with jti claim (links to refresh token for session management) and version
    access_token = jwt_service.create_access_token(
        user_id=verified_user.id,
        email=verified_user.email,
        refresh_token_id=refresh_token.id,  # This adds jti claim
        token_version=verified_user.min_token_version,
    )

    return {
        "access_token": access_token,
        "refresh_token": plain_refresh_token,
        "refresh_token_id": refresh_token.id,
        "session_id": session.id,  # Include session_id for tests
        "user": verified_user,
    }


@pytest.fixture
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    """Get authentication headers for superuser.

    TODO: Implement actual authentication flow once auth endpoints exist.
    For now, returns empty dict or mock headers.
    """
    # Placeholder - implement once auth is built
    return {"Authorization": "Bearer mock_superuser_token"}


@pytest.fixture
def normal_user_token_headers(client: TestClient, test_user: User) -> dict[str, str]:
    """Get authentication headers for normal user.

    TODO: Implement actual authentication flow once auth endpoints exist.
    """
    # Placeholder - implement once auth is built
    return {"Authorization": f"Bearer mock_user_token_{test_user.id}"}


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_encryption_service():
    """Mock encryption service for testing without real encryption.

    Returns a mock that provides predictable encrypt/decrypt behavior.
    """
    from unittest.mock import MagicMock

    service = MagicMock()
    service.encrypt.side_effect = lambda data: f"encrypted_{data}"
    service.decrypt.side_effect = (
        lambda data: data.replace("encrypted_", "")
        if isinstance(data, str) and data.startswith("encrypted_")
        else data
    )
    return service


@pytest.fixture
def mock_schwab_api_responses():
    """Mock responses for Charles Schwab API calls.

    Returns dict of mock API responses for OAuth flow testing.
    """
    return {
        "token_response": {
            "access_token": "mock_access_token_12345",
            "refresh_token": "mock_refresh_token_67890",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "api",
        },
        "auth_url": (
            "https://api.schwabapi.com/v1/oauth/authorize"
            "?response_type=code&client_id=test_client"
            "&redirect_uri=https://127.0.0.1:8182"
        ),
        "user_info": {
            "user_id": "test_schwab_user_123",
            "account_numbers": ["12345678", "87654321"],
        },
    }


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests (fast, no database)")
    config.addinivalue_line("markers", "integration: Integration tests (with database)")
    config.addinivalue_line("markers", "api: API/E2E tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location.

    Tests in unit/ directory → marked as unit
    Tests in integration/ directory → marked as integration
    Tests in api/ directory → marked as api
    """
    for item in items:
        # Get test file path
        test_path = str(item.fspath)

        # Auto-mark based on directory
        if "/unit/" in test_path:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in test_path:
            item.add_marker(pytest.mark.integration)
        elif "/api/" in test_path:
            item.add_marker(pytest.mark.api)


# ============================================================================
# HTTPS/SSL Fixtures for Test Environments
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def disable_ssl_warnings():
    """Disable SSL warnings for self-signed certs in test environments.

    Test and CI environments use self-signed SSL certificates for HTTPS testing.
    This fixture suppresses SSL verification warnings to keep test output clean
    while still testing HTTPS functionality.

    Note: This is safe for test environments. Production uses proper certificates.
    """
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
