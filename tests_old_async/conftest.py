"""Global pytest configuration and fixtures for Dashtam tests.

This module implements the official best practices for async testing with:
- pytest-asyncio 1.2.0+ 
- SQLAlchemy 2.0 AsyncEngine
- asyncpg connections

Key Principles (Per Official Documentation):
1. Function-scoped event loops (pytest-asyncio default)
2. Session-scoped engine with NullPool for async compatibility
3. Transaction rollback pattern for test isolation
4. Proper connection lifecycle management
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncConnection
from sqlalchemy.pool import NullPool
from sqlalchemy import event
from sqlmodel import SQLModel

from tests.test_config import TestSettings, get_test_settings
from src.core.database import get_session
from src.main import app
from src.models.user import User
from src.models.provider import Provider, ProviderConnection, ProviderStatus


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    """Provide test-specific settings loaded from .env.test file.
    
    Returns:
        TestSettings instance with all configuration loaded from environment
        variables and .env.test file.
    """
    return get_test_settings()


# ============================================================================
# Database Engine and Setup Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_engine(test_settings: TestSettings):
    """Create test database engine using SQLAlchemy 2.0 best practices.
    
    Per official SQLAlchemy async testing documentation:
    - Engine is session-scoped for resource efficiency
    - NullPool prevents connection reuse across event loops
    - Each test gets a fresh connection via connect()
    
    Args:
        test_settings: Test configuration loaded from .env.test
    
    Returns:
        AsyncEngine configured for testing
    """
    # Ensure we're using test database
    assert test_settings.is_test_environment, "Must be in test environment"
    assert "dashtam_test" in test_settings.DATABASE_URL, "Must use test database"
    
    # Create engine with NullPool - critical for async testing
    # This prevents "attached to different loop" errors with asyncpg
    engine = create_async_engine(
        test_settings.test_database_url,
        echo=test_settings.DB_ECHO,
        poolclass=NullPool,  # No connection pooling for async tests
    )
    
    yield engine
    
    # Cleanup: dispose engine after all tests
    # Run in new event loop since session fixtures don't have active loop
    async def dispose():
        await engine.dispose()
    
    asyncio.run(dispose())


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(test_engine, test_settings):
    """Set up test database schema once per session.
    
    This fixture runs automatically before any tests and:
    - Creates all database tables
    - Verifies table structure
    - Cleans up after all tests complete
    
    Per best practices: Schema setup uses its own event loop, separate
    from test event loops, to avoid asyncpg binding issues.
    
    Args:
        test_engine: Test database engine
        test_settings: Test configuration
    """
    # Import here to avoid circular imports
    from src.core.init_test_db import (
        check_test_database_connection,
        create_test_tables,
        verify_test_tables,
        prepare_test_database_constraints,
    )
    
    # Safety check
    assert test_settings.is_test_environment, "Safety check: must be test environment"
    
    async def setup():
        """Setup routine running in its own event loop."""
        # Check connection
        if not await check_test_database_connection(test_engine, test_settings):
            pytest.fail("Test database connection failed during fixture setup")
        
        # Apply optimizations
        await prepare_test_database_constraints(test_engine)
        
        # Create tables
        await create_test_tables(test_engine, test_settings)
        
        # Verify
        await verify_test_tables(test_engine)
    
    # Run setup in dedicated event loop
    asyncio.run(setup())
    
    yield
    
    # Cleanup: drop all tables after tests
    async def cleanup():
        async with test_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
    
    asyncio.run(cleanup())


# ============================================================================
# Database Session Fixtures  
# ============================================================================

@pytest_asyncio.fixture
async def db_session(
    test_engine, setup_test_database
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for testing.
    
    This implements a clean async testing pattern that works reliably with
    asyncpg and SQLAlchemy 2.0:
    
    1. Create a fresh async session from the engine (NullPool ensures isolation)
    2. Let the session work normally - commits persist to database
    3. After test, explicitly rollback any uncommitted work
    4. Tables are reset between test runs by setup_test_database fixture
    
    This approach avoids complex transaction nesting that can cause greenlet
    errors with asyncpg, while still providing test isolation through NullPool
    and database cleanup.
    
    Args:
        test_engine: Test database engine (with NullPool for isolation)
        setup_test_database: Ensures database schema is ready
    
    Yields:
        AsyncSession for database operations in tests
    """
    # Create a fresh session from the engine
    # NullPool ensures this gets a brand new connection not shared with other tests
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            # Rollback any uncommitted changes
            await session.rollback()
            # Session close is handled by context manager


# ============================================================================
# Test Data Fixtures
# ============================================================================

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


# ============================================================================
# API Testing Fixtures
# ============================================================================

@pytest.fixture
def override_get_session(db_session: AsyncSession):
    """Override the get_session dependency for API testing.
    
    This fixture replaces the main app's database dependency with our
    test session, following FastAPI dependency injection patterns.
    
    Args:
        db_session: Test database session
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


# ============================================================================
# Mock Fixtures
# ============================================================================

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


# ============================================================================
# Pytest Configuration
# ============================================================================

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
        # Add unit marker to tests in unit/ directory
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add integration marker to tests in integration/ directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add database marker to tests using db_session
        if "db_session" in item.fixturenames:
            item.add_marker(pytest.mark.database)
