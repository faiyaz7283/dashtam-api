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
from redis.asyncio import Redis, ConnectionPool


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
    await client.ping()

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
    mocks["cache"].get.return_value = Success(None)
    mocks["cache"].set.return_value = Success(None)
    mocks["secrets"].get_secret.return_value = "mock-secret"

    # Patch container functions
    with patch("src.core.container.get_cache", return_value=mocks["cache"]):
        with patch("src.core.container.get_secrets", return_value=mocks["secrets"]):
            with patch(
                "src.core.container.get_database", return_value=mocks["database"]
            ):
                yield mocks


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

    tracker = CleanupTracker()
    yield tracker

    # Run cleanup after test
    asyncio.run(tracker.cleanup_all())
