"""Pytest configuration for async testing.

This configuration ensures:
1. Async tests run in isolated event loops
2. Proper cleanup between tests
3. No race conditions between async tests
4. Database fixtures are properly isolated
5. Cache fixtures bypass singleton for test isolation
"""

import pytest
import asyncio
import pytest_asyncio
from datetime import UTC, datetime, timedelta
from redis.asyncio import Redis, ConnectionPool

from src.domain.enums.credential_type import CredentialType
from src.domain.value_objects.provider_credentials import ProviderCredentials


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for all tests.

    Using the default policy ensures compatibility across platforms.
    """
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="function")
def event_loop(event_loop_policy):
    """Create a new event loop for each test function.

    This ensures complete isolation between tests:
    - No shared state between tests
    - Each test gets a fresh event loop
    - Proper cleanup after each test

    Scope is 'function' to ensure a new loop per test.
    """
    loop = event_loop_policy.new_event_loop()
    yield loop

    # Cleanup: Close the loop after test
    try:
        loop.close()
    except Exception:
        pass  # Loop might already be closed


# Test helper functions for domain entities
# Sentinel for "use default expiration"
_DEFAULT_EXPIRY = object()


def create_credentials(
    encrypted_data: bytes = b"encrypted_token_data",
    credential_type: CredentialType = CredentialType.OAUTH2,
    expires_at: datetime | None | object = _DEFAULT_EXPIRY,
) -> ProviderCredentials:
    """Helper to create ProviderCredentials for testing.

    Args:
        encrypted_data: Encrypted credential data (default: test data).
        credential_type: Type of credential (default: OAuth2).
        expires_at: Expiration time.
            - Default: 1 hour from now
            - None: Never expires
            - datetime: Specific expiration time

    Returns:
        ProviderCredentials instance for testing.

    Usage:
        # Default (OAuth2, expires in 1 hour)
        creds = create_credentials()

        # Never expires (explicit None)
        creds = create_credentials(expires_at=None)

        # Custom expiration
        creds = create_credentials(expires_at=datetime.now(UTC) + timedelta(days=1))
    """
    # Set default expiration if not provided
    if expires_at is _DEFAULT_EXPIRY:
        expires_at = datetime.now(UTC) + timedelta(hours=1)

    return ProviderCredentials(
        encrypted_data=encrypted_data,
        credential_type=credential_type,
        expires_at=expires_at,  # type: ignore[arg-type]
    )


# Pytest markers for different test types
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests with mocked dependencies")
    config.addinivalue_line(
        "markers", "integration: Integration tests with real database"
    )
    config.addinivalue_line("markers", "smoke: End-to-end smoke tests")
    config.addinivalue_line("markers", "asyncio: Async test that requires event loop")


# Test execution configuration
def pytest_collection_modifyitems(config, items):
    """Automatically add asyncio marker to async test functions.

    This ensures all async tests are properly marked even if
    the developer forgets to add @pytest.mark.asyncio.
    """
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)


# Database test isolation helper
@pytest_asyncio.fixture
async def isolated_database_session():
    """Provide an isolated database session for integration tests.

    Each test gets its own transaction that's rolled back after the test,
    ensuring no data persists between tests.

    This pattern prevents:
    - Data leakage between tests
    - Test order dependencies
    - Race conditions in parallel test execution
    """
    from src.infrastructure.persistence.database import Database
    from src.core.config import settings

    # Use test database (from settings)
    db = Database(
        database_url=settings.database_url  # Uses DATABASE_URL from .env.test
    )

    async with db.get_session() as session:
        # Start a transaction
        async with session.begin():
            # Create a savepoint for rollback
            savepoint = await session.begin_nested()

            yield session

            # Rollback to savepoint after test
            await savepoint.rollback()

    # Cleanup
    await db.close()


# Cache test isolation helpers (matches database pattern)
@pytest_asyncio.fixture
async def redis_test_client():
    """Provide a fresh Redis client for each test.

    This fixture bypasses the singleton pattern used in production
    to ensure complete isolation between tests. Each test gets its
    own Redis connection that's properly cleaned up.

    This matches the database test pattern where tests create fresh
    Database instances instead of using the singleton.

    Pattern:
    - Production: Singleton with connection pool (efficient)
    - Tests: Fresh instances per test (isolated)
    """
    from src.core.config import settings

    # Create fresh connection pool (bypass singleton)
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=10,  # Smaller pool for tests
        decode_responses=True,
        socket_keepalive=True,
        socket_connect_timeout=5,
        retry_on_timeout=True,
    )

    # Create fresh Redis client
    client = Redis(connection_pool=pool)

    # Verify connection
    await client.ping()  # type: ignore[misc]

    yield client

    # Cleanup: Close client and disconnect pool
    await client.aclose()
    await pool.disconnect()


@pytest_asyncio.fixture
async def cache_adapter(redis_test_client):
    """Provide a cache adapter for each test.

    Uses the redis_test_client fixture to ensure test isolation.
    Each test gets a fresh RedisAdapter instance with its own
    Redis connection.

    Usage:
        async def test_something(cache_adapter):
            result = await cache_adapter.set("key", "value", ttl=60)
            assert result.is_success
    """
    from src.infrastructure.cache.redis_adapter import RedisAdapter

    return RedisAdapter(redis_client=redis_test_client)


@pytest_asyncio.fixture
async def session_cache(cache_adapter):
    """Provide a RedisSessionCache for each test.

    Uses the cache_adapter fixture to ensure test isolation.
    Each test gets a fresh session cache instance.

    Usage:
        async def test_something(session_cache):
            await session_cache.set(session_data)
            result = await session_cache.get(session_id)
    """
    from src.infrastructure.cache.session_cache import RedisSessionCache

    return RedisSessionCache(redis_adapter=cache_adapter)


@pytest_asyncio.fixture
async def test_database():
    """Provide a test database instance for integration tests.

    Returns a Database instance that can create multiple independent sessions.
    Used for audit durability tests where separate sessions are required.

    This fixture provides the Database object (not a session), allowing
    tests to create multiple separate sessions as needed for testing
    session isolation scenarios.

    Usage:
        async def test_something(test_database):
            async with test_database.get_session() as session1:
                # Use session1
            async with test_database.get_session() as session2:
                # Use session2 (separate from session1)
    """
    from src.infrastructure.persistence.database import Database
    from src.core.config import settings

    db = Database(database_url=settings.database_url, echo=settings.db_echo)
    yield db
    await db.close()


# Async timeout configuration
@pytest.fixture
def async_timeout():
    """Default timeout for async operations in tests.

    Returns 5 seconds by default, but can be overridden in specific tests.
    This prevents tests from hanging indefinitely on async operations.
    """
    return 5.0


# Mock factory helpers for consistent test isolation
@pytest.fixture
def mock_async_context_manager():
    """Factory for creating mock async context managers.

    Useful for mocking database sessions, connections, etc.
    """
    from unittest.mock import AsyncMock, MagicMock

    def factory(return_value=None):
        """Create a mock that works as async context manager."""
        mock = MagicMock()
        mock.__aenter__ = AsyncMock(return_value=return_value or mock)
        mock.__aexit__ = AsyncMock(return_value=None)
        return mock

    return factory


# Container mocking (for unit tests that need to mock infrastructure)
@pytest.fixture
def mock_container_dependencies():
    """Mock all container dependencies for unit tests.

    Use this fixture in unit tests that need to mock infrastructure dependencies.
    Integration tests should NOT use this - they create fresh instances directly.

    Returns:
        dict: Dictionary of mock dependencies (cache, secrets, database)

    Example:
        @pytest.mark.asyncio
        async def test_handler(mock_container_dependencies):
            # Handler uses mocked container dependencies
            handler = RegisterUserHandler()
            result = await handler.handle(command)

            # Verify mock calls
            assert mock_container_dependencies["cache"].set.called
    """
    from unittest.mock import AsyncMock, Mock, patch
    from src.core.result import Success

    mocks = {
        "cache": AsyncMock(),
        "secrets": Mock(),
        "database": Mock(),
    }

    # Configure default mock behaviors
    mocks["cache"].get.return_value = Success(value=None)
    mocks["cache"].set.return_value = Success(value=None)
    mocks["secrets"].get_secret.return_value = "mock-secret"

    # Patch container functions
    with patch("src.core.container.get_cache", return_value=mocks["cache"]):
        with patch("src.core.container.get_secrets", return_value=mocks["secrets"]):
            with patch(
                "src.core.container.get_database", return_value=mocks["database"]
            ):
                yield mocks


# =============================================================================
# Reusable Mock Fixtures
# =============================================================================
# These mock fixtures are used across unit and integration tests.
# They provide consistent mock behavior for cross-cutting concerns.


@pytest.fixture
def mock_logger():
    """Provide a mock logger for testing.

    Returns a Mock object with standard logging methods (info, debug, error, warning).
    Use this when testing components that require a logger dependency.

    Usage:
        def test_something(mock_logger):
            service = MyService(logger=mock_logger)
            service.do_something()
            mock_logger.info.assert_called_once()
    """
    from unittest.mock import Mock

    logger = Mock()
    logger.info = Mock()
    logger.debug = Mock()
    logger.error = Mock()
    logger.warning = Mock()
    return logger


@pytest_asyncio.fixture
async def mock_audit():
    """Provide a mock audit service for testing.

    Returns an AsyncMock with standard audit methods.
    Use this when testing components that record audit logs.

    Usage:
        async def test_something(mock_audit):
            service = MyService(audit=mock_audit)
            await service.do_something()
            mock_audit.record.assert_called_once()
    """
    from unittest.mock import AsyncMock

    audit = AsyncMock()
    audit.record = AsyncMock(return_value=None)
    return audit


@pytest_asyncio.fixture
async def mock_event_bus():
    """Provide a mock event bus for testing.

    Returns an AsyncMock with standard event bus methods.
    Use this when testing components that publish domain events.

    Usage:
        async def test_something(mock_event_bus):
            service = MyService(event_bus=mock_event_bus)
            await service.do_something()
            mock_event_bus.publish.assert_called()
    """
    from unittest.mock import AsyncMock

    event_bus = AsyncMock()
    event_bus.publish = AsyncMock(return_value=None)
    event_bus.subscribe = AsyncMock(return_value=None)
    return event_bus


@pytest_asyncio.fixture
async def mock_cache():
    """Provide a mock cache for testing.

    Returns an AsyncMock with standard cache methods.
    Use this when testing components that use caching but don't need real Redis.

    For tests that need real Redis, use `cache_adapter` fixture instead.

    Usage:
        async def test_something(mock_cache):
            service = MyService(cache=mock_cache)
            await service.do_something()
            mock_cache.set.assert_called()
    """
    from unittest.mock import AsyncMock

    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)  # Cache miss by default
    cache.set = AsyncMock(return_value=None)
    cache.delete = AsyncMock(return_value=None)
    cache.delete_pattern = AsyncMock(return_value=None)
    return cache


# Test data cleanup tracker
@pytest.fixture
def cleanup_tracker():
    """Track items that need cleanup after test.

    Usage:
        def test_something(cleanup_tracker):
            resource = create_resource()
            cleanup_tracker.add(resource.cleanup)
            # test continues...
    """

    class CleanupTracker:
        def __init__(self):
            self.cleanups = []

        def add(self, cleanup_func):
            """Add a cleanup function to be called after test."""
            self.cleanups.append(cleanup_func)

        async def cleanup_all(self):
            """Execute all cleanup functions."""
            for cleanup in reversed(self.cleanups):
                try:
                    if asyncio.iscoroutinefunction(cleanup):
                        await cleanup()
                    else:
                        cleanup()
                except Exception as e:
                    # Log but don't fail test on cleanup errors
                    print(f"Cleanup error: {e}")

    tracker = CleanupTracker()  # type: ignore[no-untyped-call]
    yield tracker

    # Run cleanup after test
    asyncio.run(tracker.cleanup_all())  # type: ignore[no-untyped-call]
