"""Pytest configuration for async testing.

This configuration ensures:
1. Async tests run in isolated event loops
2. Proper cleanup between tests
3. No race conditions between async tests
4. Database fixtures are properly isolated
"""

import pytest
import asyncio
import pytest_asyncio


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

    # Use test database
    db = Database(
        database_url="postgresql+asyncpg://dashtam_user:secure_password_change_me@postgres:5432/dashtam_test"
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
