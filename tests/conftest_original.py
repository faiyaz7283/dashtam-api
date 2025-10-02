"""Global pytest configuration and fixtures for Dashtam tests.

This module provides test configuration, fixtures, and utilities used across
all test modules in the Dashtam project. It follows the same configuration
patterns as the main application while providing test-specific overrides.
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlmodel import SQLModel

from tests.test_config import TestSettings, get_test_settings
from src.core.database import get_session
from src.main import app
from src.models.user import User
from src.models.provider import Provider, ProviderConnection, ProviderStatus


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop.
    
    This ensures all async fixtures and tests share the same event loop,
    which is critical for asyncpg connections that are bound to a specific loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    """Provide test-specific settings loaded from .env.test file.

    Returns:
        TestSettings instance with all configuration loaded from environment
        variables and .env.test file, following the same patterns as main app.
    """
    return get_test_settings()


@pytest.fixture(scope="session")
def test_engine(test_settings: TestSettings):
    """Create test database engine using settings from .env.test.
    
    Note: Session-scoped for efficiency, but connections are made per-test
    to avoid event loop conflicts.

    Args:
        test_settings: Test configuration loaded from .env.test

    Returns:
        AsyncEngine configured for testing with proper connection pooling
    """
    # Ensure we're using test database
    assert test_settings.is_test_environment, "Must be in test environment"
    assert "dashtam_test" in test_settings.DATABASE_URL, "Must use test database"

    engine = create_async_engine(
        test_settings.test_database_url,
        echo=test_settings.DB_ECHO,
        future=True,
        pool_pre_ping=True,
        # Use smaller pool for testing but allow event loop flexibility
        pool_size=2,
        max_overflow=5,
    )

    return engine


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database(test_engine, test_settings, event_loop):
    """Set up test database with tables using our initialization script approach.

    This fixture integrates with our init_test_db.py script to ensure consistent
    database setup patterns across manual runs and automated testing.
    
    Note: Now async and session-scoped, sharing the same event loop as tests
    to prevent "attached to different loop" errors with asyncpg.
    """
    # Import here to avoid circular imports
    from src.core.init_test_db import (
        check_test_database_connection,
        create_test_tables,
        verify_test_tables,
        prepare_test_database_constraints,
    )

    # Safety check - ensure we're working with test database
    assert test_settings.is_test_environment, "Safety check: must be test environment"

    # Use the same initialization logic as our script for consistency
    if not await check_test_database_connection(test_engine, test_settings):
        pytest.fail("Test database connection failed during fixture setup")

    # Apply test database optimizations
    await prepare_test_database_constraints(test_engine)

    # Create tables using our standardized approach
    await create_test_tables(test_engine, test_settings)

    # Verify setup
    await verify_test_tables(test_engine)

    yield

    # Cleanup after all tests - drop all tables for clean slate
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    test_engine, setup_test_database, test_settings
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for testing with transaction rollback.

    Each test gets a fresh session with automatic rollback for isolation.
    This follows the same async session patterns as the main application.
    
    Note: We use a simpler pattern without manual transaction management to
    avoid conflicts with commit() calls in test fixtures. The session's
    context manager handles cleanup automatically.

    Args:
        test_engine: Test database engine
        setup_test_database: Ensures database is set up
        test_settings: Test configuration

    Yields:
        AsyncSession for database operations in tests
    """
    # Create session maker following the same pattern as main app
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_maker() as session:
        try:
            yield session
        finally:
            # Rollback any uncommitted changes for test isolation
            await session.rollback()
            await session.close()


@pytest.fixture
def override_get_session(db_session: AsyncSession, test_settings: TestSettings):
    """Override the get_session dependency for testing.

    This fixture replaces the main app's database dependency with our
    test session, following the same dependency injection patterns.
    """

    async def _override_get_session():
        yield db_session

    # Store original dependency
    original_dependency = app.dependency_overrides.get(get_session)

    # Override with test session
    app.dependency_overrides[get_session] = _override_get_session

    yield

    # Restore original dependency or clear override
    if original_dependency:
        app.dependency_overrides[get_session] = original_dependency
    else:
        app.dependency_overrides.pop(get_session, None)


@pytest_asyncio.fixture
async def async_client(
    override_get_session, test_settings: TestSettings
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for API testing.

    This client is configured to work with the test application instance
    and uses the test database session.

    Args:
        override_get_session: Ensures test database session is used
        test_settings: Test configuration

    Yields:
        AsyncClient for making HTTP requests to test app
    """
    async with AsyncClient(
        app=app, base_url=f"http://test:{test_settings.PORT}"
    ) as client:
        yield client


@pytest.fixture
def sync_client(
    override_get_session, test_settings: TestSettings
) -> Generator[TestClient, None, None]:
    """Provide a synchronous HTTP client for API testing.

    Args:
        override_get_session: Ensures test database session is used
        test_settings: Test configuration

    Yields:
        TestClient for making synchronous HTTP requests
    """
    with TestClient(app) as client:
        yield client


# Test data fixtures following Dashtam patterns
@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user following Dashtam user model patterns.

    Args:
        db_session: Test database session

    Returns:
        User instance saved to test database
    """
    user = User(email="test@example.com", name="Test User", is_verified=True)
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_provider(db_session: AsyncSession, test_user: User) -> Provider:
    """Create a test provider instance following Dashtam provider patterns.

    Args:
        db_session: Test database session
        test_user: Test user who owns this provider

    Returns:
        Provider instance saved to test database
    """
    provider = Provider(
        user_id=test_user.id, provider_key="schwab", alias="Test Schwab Account"
    )
    db_session.add(provider)
    await db_session.flush()
    await db_session.refresh(provider)
    return provider


@pytest_asyncio.fixture
async def test_provider_with_connection(
    db_session: AsyncSession, test_provider: Provider
) -> Provider:
    """Create a test provider with active connection.

    Args:
        db_session: Test database session
        test_provider: Base provider instance

    Returns:
        Provider with active connection relationship loaded
    """
    connection = ProviderConnection(
        provider_id=test_provider.id,
        status=ProviderStatus.ACTIVE,
        accounts_count=2,
        accounts_list=["test_account_1", "test_account_2"],
    )
    db_session.add(connection)
    await db_session.flush()

    # Refresh to load the relationship
    await db_session.refresh(test_provider)
    return test_provider


@pytest.fixture
def mock_encryption_service(test_settings: TestSettings):
    """Provide a mock encryption service for testing.

    Uses fast, deterministic encryption suitable for testing.

    Args:
        test_settings: Test configuration

    Returns:
        Mock encryption service with predictable behavior
    """
    service = AsyncMock()

    # Provide deterministic encryption for testing
    service.encrypt.side_effect = lambda data: f"encrypted_{data}"
    service.decrypt.side_effect = (
        lambda data: data.replace("encrypted_", "")
        if data.startswith("encrypted_")
        else data
    )

    return service


@pytest.fixture
def mock_schwab_api_responses(test_settings: TestSettings):
    """Provide mock responses for Schwab API calls.

    Args:
        test_settings: Test configuration

    Returns:
        Dictionary of mock API responses for testing
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
            f"{test_settings.SCHWAB_API_BASE_URL}/oauth/authorize"
            f"?response_type=code&client_id={test_settings.SCHWAB_API_KEY}"
            f"&redirect_uri={test_settings.SCHWAB_REDIRECT_URI}"
            f"&scope=api&state=test_state"
        ),
        "user_info": {
            "user_id": "test_schwab_user_123",
            "account_numbers": ["12345678", "87654321"],
        },
    }


@pytest.fixture
def sample_test_data(test_settings: TestSettings):
    """Provide sample test data following Dashtam data patterns.

    Args:
        test_settings: Test configuration

    Returns:
        Dictionary of sample data for various test scenarios
    """
    return {
        "user_data": {
            "email": "testuser@example.com",
            "name": "Test User",
            "is_verified": True,
        },
        "provider_data": {
            "provider_key": "schwab",
            "alias": "Personal Brokerage Account",
        },
        "token_data": {
            "access_token": "sample_access_token_testing_123",
            "refresh_token": "sample_refresh_token_testing_456",
            "expires_in": 3600,
            "id_token": "sample_id_token_testing_789",
            "scope": "api",
            "token_type": "Bearer",
        },
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers and settings.

    This follows pytest best practices and sets up test environment.
    """
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "database: mark test as requiring database")

    # Set test environment variables
    os.environ["TESTING"] = "1"
    os.environ["ENVIRONMENT"] = "testing"


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location.

    This provides automatic test categorization based on directory structure.
    """
    for item in items:
        # Auto-mark tests based on directory structure
        item_path = str(item.fspath)

        if "unit" in item_path:
            item.add_marker(pytest.mark.unit)
        elif "integration" in item_path:
            item.add_marker(pytest.mark.integration)
            item.add_marker(
                pytest.mark.database
            )  # Integration tests typically need database
        elif "e2e" in item_path:
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)  # E2E tests are typically slower
            item.add_marker(pytest.mark.database)  # E2E tests need database
