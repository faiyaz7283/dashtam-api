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

import pytest
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
from tests.test_config import TestSettings, get_test_settings

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
def test_settings() -> TestSettings:
    """Provide test-specific settings loaded from .env file.

    Returns:
        TestSettings instance with all configuration loaded from environment
        variables, following the same patterns as main app.
    """
    return get_test_settings()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Set up test database schema once per test session.

    Creates all tables at start, drops them at end.
    This runs automatically for all test sessions.
    """
    # Create all tables
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
def db_session(db: Session) -> Generator[Session, None, None]:
    """Function-scoped database session for test isolation.

    Each test gets access to the session. Tests should create their own
    data using fixtures or within the test. Cleanup happens automatically
    via relationship cascades or can be done explicitly.

    Note: This is synchronous Session, not AsyncSession. Perfect for testing
    since TestClient handles the async/sync bridge internally.
    """
    yield db

    # Rollback any pending transaction (in case of errors)
    try:
        db.rollback()
    except Exception:
        pass

    # Optional: Explicit cleanup after each test
    # Deletes are cascaded based on model relationships
    try:
        db.execute(delete(ProviderAuditLog))
        db.execute(delete(ProviderToken))
        db.execute(delete(ProviderConnection))
        db.execute(delete(Provider))
        db.execute(delete(User))
        db.commit()
    except Exception:
        db.rollback()


@pytest.fixture(scope="session")
def client(db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient for making HTTP requests to the application.

    TestClient automatically handles the async/sync bridge, allowing
    synchronous test code to work with async FastAPI endpoints.

    This fixture overrides FastAPI's async dependencies with synchronous
    test-compatible versions to ensure consistent testing across all environments.

    Module-scoped for efficiency (creating client is expensive).
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

    # Apply dependency overrides
    app.dependency_overrides[get_session] = override_get_session
    # Note: get_current_user is NOT overridden here - JWT auth tests use real auth

    with TestClient(app) as c:
        yield c

    # Clean up overrides after test module
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client_no_auth(db: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient without authentication override.

    Used for testing public endpoints that don't require authentication,
    such as provider type catalog endpoints.

    This client has the database override but NOT the authentication override,
    allowing tests to verify that endpoints are truly public.
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

    # Clean up overrides after test module
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

    # Create access token
    access_token = jwt_service.create_access_token(
        user_id=verified_user.id, email=verified_user.email
    )

    # Create refresh token (plain)
    plain_refresh_token = secrets.token_urlsafe(32)
    token_hash = password_service.hash_password(plain_refresh_token)

    # Store refresh token in database
    refresh_token = RefreshToken(
        user_id=verified_user.id,
        token_hash=token_hash,
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
