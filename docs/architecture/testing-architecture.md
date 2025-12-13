# Testing Architecture

## Overview

This document defines the testing architecture for Dashtam's clean slate
implementation, establishing industry-standard best practices that align with
hexagonal architecture principles. The goal is to make testing **easy**,
**reliable**, and **maintainable** by providing clear patterns and reusable
fixtures.

**Core Philosophy**:

- Test the **right things** at the **right level**
- Avoid over-mocking (test with real dependencies when reasonable)
- Infrastructure adapters get integration tests (not unit tests)
- Clear fixtures in `conftest.py` for common patterns
- Async-first with proper isolation

---

## Test Pyramid

Our testing strategy follows the test pyramid with emphasis on integration
tests for infrastructure (hexagonal architecture pattern).

```mermaid
graph TB
    subgraph "E2E Tests (10%)"
        E2E[Complete user flows<br/>API + Database + Cache<br/>Real HTTP requests]
    end
    
    subgraph "Integration Tests (30%)"
        INT1[Infrastructure Layer<br/>Database adapters]
        INT2[Cache adapters<br/>Real PostgreSQL/Redis]
        INT3[Service interactions<br/>Multiple components]
    end
    
    subgraph "Unit Tests (60%)"
        UNIT1[Domain Entities<br/>Value Objects]
        UNIT2[Command/Query Handlers<br/>Mocked repositories]
        UNIT3[Core Logic<br/>Validation, errors]
    end
    
    E2E --> INT1
    E2E --> INT2
    INT1 --> UNIT1
    INT2 --> UNIT2
    INT3 --> UNIT3
```

**Coverage Targets**:

- **Domain layer**: 95%+ (business logic must be thoroughly tested)
- **Application layer**: 90%+ (command/query handlers)
- **Infrastructure layer**: 70%+ (integration tests, not unit tests)
- **Overall**: 85%+ (target for clean slate project)

---

## Testing Strategy by Layer

### Core Layer (Shared Kernel)

**What to test**: Result types, validation, error types, configuration

**How to test**: Unit tests with no mocking

**Example** (`tests/unit/core/test_config.py`):

```python
def test_settings_from_env():
    """Unit test for configuration loading."""
    with patch.dict(os.environ, {
        "ENVIRONMENT": "testing",
        "DATABASE_URL": "postgresql+asyncpg://test",
        # ... other required env vars
    }, clear=True):
        get_settings.cache_clear()
        settings = get_settings()
        
        assert settings.environment == Environment.TESTING
        assert settings.database_url == "postgresql+asyncpg://test"
```

**Pattern**: Use `patch.dict(os.environ)` for env vars, `clear=True` to
isolate tests.

### Domain Layer (Pure Business Logic)

**What to test**: Entities, value objects, domain services, protocols

**How to test**: Unit tests with NO infrastructure dependencies

**Pattern**: Mock protocols (if needed), test business logic in isolation

```python
# tests/unit/domain/test_user_entity.py
def test_user_validates_email():
    """Domain entity validation (pure logic)."""
    result = User.create(
        email="invalid-email",
        password="SecurePass123!"
    )
    
    assert isinstance(result, Failure)
    assert result.error.code == ErrorCode.INVALID_EMAIL
```

**What NOT to test**: Don't unit test protocols (they're interfaces)

**Coverage**: 95%+ (domain is our most valuable code)

### Application Layer (Use Cases)

**What to test**: Command handlers, query handlers, event handlers

**How to test**: Unit tests with mocked repositories

**Pattern**: Mock repository protocols, test handler logic

```python
# tests/unit/application/commands/test_register_user.py
@pytest.mark.asyncio
async def test_register_user_handler_success():
    """Test handler with mocked repository."""
    # Arrange
    mock_user_repo = AsyncMock(spec=UserRepository)
    mock_user_repo.find_by_email.return_value = None  # No existing user
    mock_user_repo.save = AsyncMock()  # Mock save
    
    handler = RegisterUserHandler(
        user_repository=mock_user_repo,
        event_bus=mock_event_bus
    )
    
    command = RegisterUser(
        email="test@example.com",
        password="SecurePass123!"
    )
    
    # Act
    result = await handler.handle(command)
    
    # Assert
    assert isinstance(result, Success)
    mock_user_repo.save.assert_called_once()
    # Verify event published
    mock_event_bus.publish.assert_called_once()
```

**Why mock repositories?** We want to test **handler logic** (validation,
business rules, event publishing), not database operations.

**Coverage**: 90%+ (handlers contain critical workflows)

### Infrastructure Layer (Adapters)

**What to test**: Database adapters, cache adapters, external API clients

**How to test**: **Integration tests ONLY** (no unit tests)

**Pattern**: Test against real services (PostgreSQL, Redis), use fixtures

**Why no unit tests?** Infrastructure adapters are thin wrappers around
external systems. Mocking SQLAlchemy or Redis would just test the mock.

```python
# tests/integration/test_infrastructure_cache_redis.py
@pytest.mark.integration
class TestCacheIntegration:
    """Integration tests for Redis cache."""
    
    @pytest.mark.asyncio
    async def test_set_and_get_string(self, cache_adapter):
        """Test with REAL Redis instance."""
        # Set value
        set_result = await cache_adapter.set("test_key", "test_value")
        assert isinstance(set_result, Success)
        
        # Get value
        get_result = await cache_adapter.get("test_key")
        assert isinstance(get_result, Success)
        assert get_result.value == "test_value"
```

**Fixtures used**: `cache_adapter` (from `conftest.py`) provides fresh Redis
connection per test.

**Coverage**: 70%+ (integration tests don't catch every edge case)

### Presentation Layer (API)

**What to test**: FastAPI endpoints, request/response validation

**How to test**: API tests (E2E) using FastAPI TestClient

**Pattern**: Test complete request/response flow, verify status codes

```python
# tests/api/test_auth_endpoints.py
def test_user_registration_flow(client):
    """E2E test with TestClient."""
    response = client.post("/api/v1/users", json={
        "email": "test@example.com",
        "password": "SecurePass123!"
    })
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["email"] == "test@example.com"
```

**Why TestClient?** FastAPI's TestClient is synchronous and works well with
pytest. No need for async client for API tests.

**Coverage**: Test critical user journeys (10-15 E2E tests)

---

## Async Testing Patterns

### Event Loop Management

**Problem**: Async tests need proper event loop isolation to prevent state
leakage between tests.

**Solution**: Fresh event loop per test (function scope)

```python
# tests/conftest.py
@pytest.fixture(scope="function")
def event_loop(event_loop_policy):
    """Create a new event loop for each test function."""
    loop = event_loop_policy.new_event_loop()
    yield loop
    
    # Cleanup: Close the loop after test
    try:
        loop.close()
    except Exception:
        pass  # Loop might already be closed
```

**Why function scope?** Complete isolation - each test gets fresh event loop.

### Automatic `@pytest.mark.asyncio`

**Problem**: Developers forget to add `@pytest.mark.asyncio` to async tests.

**Solution**: Automatically detect and mark async tests

```python
# tests/conftest.py
def pytest_collection_modifyitems(config, items):
    """Automatically add asyncio marker to async test functions."""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
```

**Benefit**: Write async tests without manual marker annotation.

### Async Context Manager Mocking

**Problem**: Mocking async context managers is tricky.

**Solution**: Factory fixture for creating async mocks

```python
# tests/conftest.py
@pytest.fixture
def mock_async_context_manager():
    """Factory for creating mock async context managers."""
    from unittest.mock import AsyncMock, MagicMock
    
    def factory(return_value=None):
        mock = MagicMock()
        mock.__aenter__ = AsyncMock(return_value=return_value or mock)
        mock.__aexit__ = AsyncMock(return_value=None)
        return mock
    
    return factory

# Usage in test
def test_something(mock_async_context_manager):
    mock_session = mock_async_context_manager(return_value=mock_data)
```

---

## Test Fixtures (conftest.py)

Our `tests/conftest.py` provides reusable fixtures following DRY principles.

### Database Fixtures

#### Pattern: Fresh Instances Per Test (Bypass Singleton)

**Production uses singleton** for connection pooling efficiency, but **tests
bypass singleton** for complete isolation.

```python
# tests/integration/test_infrastructure_persistence_database.py
@pytest_asyncio.fixture
async def test_database():
    """Provide fresh Database instance for each test."""
    # Bypass singleton - create fresh instance
    db = Database(
        database_url="postgresql+asyncpg://dashtam_user:password@postgres:5432/dashtam_test"
    )
    yield db
    await db.close()
```

**Why bypass singleton?** Each test gets independent database connection,
preventing state leakage.

#### Isolated Database Session (For Domain Tests)

**Pattern**: Transaction with rollback (no data persists)

```python
# tests/conftest.py
@pytest_asyncio.fixture
async def isolated_database_session():
    """Provide session that rolls back after test."""
    db = Database(database_url="postgresql+asyncpg://...")
    
    async with db.get_session() as session:
        async with session.begin():
            # Create savepoint for rollback
            savepoint = await session.begin_nested()
            
            yield session
            
            # Rollback to savepoint after test
            await savepoint.rollback()
    
    await db.close()
```

**Benefit**: Tests can insert data without affecting other tests.

### Cache Fixtures

#### Pattern: Fresh Redis Client Per Test (Bypass Singleton)

**Matches database pattern** - singleton in production, fresh instances in
tests.

```python
# tests/conftest.py
@pytest_asyncio.fixture
async def redis_test_client():
    """Provide fresh Redis client for each test."""
    from src.core.config import settings
    
    # Create fresh connection pool (bypass singleton)
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=10,  # Smaller pool for tests
        decode_responses=True,
    )
    
    client = Redis(connection_pool=pool)
    await client.ping()  # Verify connection
    
    yield client
    
    # Cleanup: Close client and disconnect pool
    await client.aclose()
    await pool.disconnect()
```

#### Cache Adapter Fixture

```python
# tests/conftest.py
@pytest_asyncio.fixture
async def cache_adapter(redis_test_client):
    """Provide cache adapter with fresh Redis client."""
    from src.infrastructure.cache.redis_adapter import RedisAdapter
    
    return RedisAdapter(redis_client=redis_test_client)
```

**Usage in tests**:

```python
async def test_cache_operation(cache_adapter):
    result = await cache_adapter.set("key", "value", ttl=60)
    assert result.is_success
```

### Cleanup Tracker

**Pattern**: Track resources that need cleanup after test

```python
# tests/conftest.py
@pytest.fixture
def cleanup_tracker():
    """Track cleanup functions to run after test."""
    class CleanupTracker:
        def __init__(self):
            self.cleanups = []
        
        def add(self, cleanup_func):
            self.cleanups.append(cleanup_func)
        
        async def cleanup_all(self):
            for cleanup in reversed(self.cleanups):
                try:
                    if asyncio.iscoroutinefunction(cleanup):
                        await cleanup()
                    else:
                        cleanup()
                except Exception as e:
                    print(f"Cleanup error: {e}")
    
    tracker = CleanupTracker()
    yield tracker
    asyncio.run(tracker.cleanup_all())
```

**Usage**:

```python
async def test_something(cleanup_tracker):
    resource = await create_resource()
    cleanup_tracker.add(resource.cleanup)
    # Test continues...
    # Cleanup runs automatically after test
```

---

## Testing with Centralized Dependency Injection

### Container Pattern (see `dependency-injection-architecture.md`)

**Production**: All dependencies managed by `src/core/container.py`

**Testing Challenge**: Need to mock container dependencies without
affecting production code

### Strategy 1: Mock Container Functions

**Pattern**: Patch container functions to return mocked dependencies

```python
# tests/unit/application/test_register_user_handler.py
from unittest.mock import Mock, patch, AsyncMock
import pytest

@pytest.mark.asyncio
async def test_register_user_with_mocked_container():
    """Test handler by mocking container dependencies."""
    # Arrange: Create mocks
    mock_cache = AsyncMock()
    mock_secrets = Mock()
    mock_cache.set.return_value = Success(None)
    mock_secrets.get_secret.return_value = "mock-secret"
    
    # Patch container functions
    with patch("src.core.container.get_cache", return_value=mock_cache):
        with patch("src.core.container.get_secrets", return_value=mock_secrets):
            # Act: Instantiate handler (uses mocked container)
            from src.application.commands.handlers.register_user_handler import RegisterUserHandler
            handler = RegisterUserHandler()
            
            # Handler internally calls get_cache() and get_secrets()
            # which now return our mocks
            result = await handler.handle(command)
    
    # Assert
    assert isinstance(result, Success)
    mock_cache.set.assert_called_once()
```

**Benefits**:

- Tests handler logic without real dependencies
- Clear which dependencies are being mocked
- Easy to verify mock calls

### Strategy 2: Override Container for Test Module

**Pattern**: Create test-specific container module

```python
# tests/mocks/test_container.py
"""Test container with mocked dependencies."""
from functools import lru_cache
from unittest.mock import AsyncMock, Mock

@lru_cache()
def get_cache():
    """Return mock cache for tests."""
    return AsyncMock()

@lru_cache()
def get_secrets():
    """Return mock secrets for tests."""
    return Mock()

@lru_cache()
def get_database():
    """Return mock database for tests."""
    return Mock()
```

**Usage**:

```python
# tests/unit/application/test_user_service.py
import sys
from unittest.mock import patch

# Replace production container with test container
with patch.dict(sys.modules, {"src.core.container": __import__("tests.mocks.test_container")}):
    from src.application.services.user_service import UserService
    
    # UserService now uses mocked container
    service = UserService()
```

### Strategy 3: Container Fixture (Recommended)

**Pattern**: Fixture that patches container for entire test

```python
# tests/conftest.py
from unittest.mock import AsyncMock, Mock, patch
import pytest

@pytest.fixture
def mock_container_dependencies():
    """Mock all container dependencies for unit tests.
    
    Returns:
        dict: Dictionary of mock dependencies
    """
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
            with patch("src.core.container.get_database", return_value=mocks["database"]):
                yield mocks

# Usage in tests
@pytest.mark.asyncio
async def test_handler_with_mocked_container(mock_container_dependencies):
    """Test with all container dependencies mocked."""
    from src.application.commands.handlers.register_user_handler import RegisterUserHandler
    
    handler = RegisterUserHandler()
    result = await handler.handle(command)
    
    # Access mocks to verify calls
    assert mock_container_dependencies["cache"].set.called
```

**Benefits**:

- Single fixture for all unit tests
- Consistent mocking across test suite
- Easy to extend with new dependencies
- Reusable via conftest.py

### Strategy 4: Fresh Instances (Infrastructure Integration Tests)

**Pattern**: Create fresh adapter instances directly (bypass container)

```python
# tests/integration/test_cache_redis.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_operation(cache_adapter):
    """Integration test with REAL Redis."""
    # cache_adapter fixture provides fresh RedisAdapter
    # Bypasses container singleton for test isolation
    result = await cache_adapter.set("key", "value", ttl=60)
    assert isinstance(result, Success)

# Fixture in conftest.py
@pytest_asyncio.fixture
async def cache_adapter(redis_test_client):
    """Fresh RedisAdapter per test (bypasses container)."""
    from src.infrastructure.cache.redis_adapter import RedisAdapter
    return RedisAdapter(redis_client=redis_test_client)
```

**Why bypass container?**

- Complete isolation between tests
- No singleton state leakage
- Fresh connections per test
- Matches industry best practice

**When to use**: Infrastructure adapter integration tests (database, cache, secrets)

### Strategy 5: FastAPI Dependency Overrides (API Tests)

**Pattern**: Override FastAPI dependencies with test implementations

```python
# tests/api/test_users_endpoints.py
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

def test_create_user_endpoint():
    """Test endpoint with overridden dependencies."""
    from src.main import app
    from src.core.container import get_cache
    
    # Create mock
    mock_cache = AsyncMock()
    
    # Override dependency
    app.dependency_overrides[get_cache] = lambda: mock_cache
    
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/users", json={
                "email": "test@example.com",
                "password": "SecurePass123!"
            })
        
        assert response.status_code == 201
        assert mock_cache.set.called
    finally:
        # Clean up override
        app.dependency_overrides.clear()
```

**Benefits**:

- FastAPI's built-in dependency injection system
- Clean separation of test and production dependencies
- Easy to override specific dependencies per test

### Container Testing Guidelines

**Unit Tests** (Application/Domain):

- ✅ Mock container functions (`patch("src.core.container.get_cache")`)
- ✅ Use `mock_container_dependencies` fixture
- ✅ Verify mock calls
- ❌ Don't use real infrastructure
- ❌ Don't call container functions directly

**Integration Tests** (Infrastructure):

- ✅ Create fresh adapter instances directly (bypass container)
- ✅ Use fixtures that provide fresh instances (`cache_adapter`, `test_database`)
- ✅ Test actual database, cache, secrets behavior
- ❌ Don't use container singletons (`get_cache()`, `get_database()`)
- ❌ Don't mock infrastructure adapters (use real implementations)

**API Tests** (E2E):

- ✅ Use FastAPI dependency overrides for selective mocking
- ✅ Override specific dependencies per test
- ✅ Test complete request/response flow
- ✅ Can use real container for full integration scenarios

### Container Fixture for Unit Tests

```python
# tests/conftest.py
from unittest.mock import AsyncMock, Mock, patch
import pytest

@pytest.fixture
def mock_container_dependencies():
    """Mock all container dependencies for unit tests.
    
    Use this fixture in unit tests that need to mock infrastructure.
    Integration tests should NOT use this - they use fresh instances.
    
    Returns:
        dict: Dictionary of mock dependencies
    """
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
            with patch("src.core.container.get_database", return_value=mocks["database"]):
                yield mocks
```

**Usage**: Unit tests for application/domain layer that need infrastructure dependencies.

### Testing Container Itself

**Do we test `src/core/container.py`?** Generally NO - it's integration glue.

**Exception**: Test that container returns correct types

```python
# tests/unit/core/test_container.py
def test_container_returns_protocol_types():
    """Verify container returns protocol implementations."""
    from src.core.container import get_cache, get_secrets
    from src.domain.protocols.cache import CacheProtocol
    from src.domain.protocols.secrets_protocol import SecretsProtocol
    
    # Verify types (structural typing with Protocol)
    cache = get_cache()
    secrets = get_secrets()
    
    # Check that returned objects satisfy protocol
    assert hasattr(cache, 'get')
    assert hasattr(cache, 'set')
    assert hasattr(secrets, 'get_secret')
```

---

## Common Testing Mistakes & Solutions

### Mistake 1: Unit Testing Infrastructure Adapters

**Problem**: Trying to unit test database repositories with mocked SQLAlchemy

```python
# ❌ DON'T DO THIS
def test_user_repository_save():
    mock_session = MagicMock()
    # ... complex mocking of SQLAlchemy internals
    # This just tests the mock, not the repository
```

**Solution**: Use integration tests with real database

```python
# ✅ DO THIS
@pytest.mark.integration
async def test_user_repository_save(test_database):
    """Integration test with REAL database."""
    repo = UserRepository(test_database)
    user = User(email="test@example.com", ...)
    
    await repo.save(user)
    found = await repo.find_by_email("test@example.com")
    
    assert found is not None
    assert found.id == user.id
```

### Mistake 2: Not Isolating Tests

**Problem**: Tests share state via singleton connections

**Solution**: Bypass singletons in tests, use fresh instances

```python
# ❌ DON'T: Using production singleton in tests
cache = get_cache()  # Singleton - shared state!

# ✅ DO: Use fixture that creates fresh instance
async def test_cache(cache_adapter):  # Fresh instance per test
    ...
```

### Mistake 3: Over-Mocking

**Problem**: Mocking everything makes tests fragile and meaningless

```python
# ❌ DON'T: Mock everything
mock_db = MagicMock()
mock_cache = MagicMock()
mock_event_bus = MagicMock()
# ... testing what exactly?
```

**Solution**: Only mock what you must (dependencies at layer boundaries)

```python
# ✅ DO: Mock only external dependencies
mock_user_repo = AsyncMock(spec=UserRepository)  # Mock repository interface
# Handler logic tested, database operations not needed
```

### Mistake 4: Not Using Result Types

**Problem**: Testing exceptions instead of Result types

```python
# ❌ DON'T: Test exceptions
with pytest.raises(ValueError):
    user = User(email="invalid")
```

**Solution**: Test Result types (railway-oriented programming)

```python
# ✅ DO: Test Result types
result = User.create(email="invalid")
assert isinstance(result, Failure)
assert result.error.code == ErrorCode.INVALID_EMAIL
```

### Mistake 5: Forgetting Async Fixtures

**Problem**: Using `@pytest.fixture` instead of `@pytest_asyncio.fixture`

```python
# ❌ DON'T: Regular fixture for async code
@pytest.fixture
async def cache_adapter():  # Won't work properly
    ...
```

**Solution**: Use `@pytest_asyncio.fixture` for async fixtures

```python
# ✅ DO: Async fixture for async code
@pytest_asyncio.fixture
async def cache_adapter():
    ...
```

---

## Test Organization

### Directory Structure

**Flat structure with descriptive file names** - no nested subdirectories
within test type directories.

```text
tests/
├── conftest.py                                 # Global fixtures
├── unit/                                       # Unit tests (60%)
│   ├── test_core_config.py                     # Core: Configuration
│   ├── test_core_result.py                     # Core: Result types
│   ├── test_core_validation.py                 # Core: Validation
│   ├── test_domain_user_entity.py              # Domain: User entity
│   ├── test_domain_email_value_object.py       # Domain: Email VO
│   ├── test_application_register_user.py       # App: RegisterUser cmd
│   └── test_application_get_user_query.py      # App: GetUser query
├── integration/                                # Integration tests (30%)
│   ├── test_cache_redis.py                     # Redis cache adapter
│   ├── test_database_postgres.py               # PostgreSQL adapter
│   └── test_provider_schwab.py                 # Schwab API adapter
├── api/                                        # API tests (10%)
│   ├── test_auth_endpoints.py                  # Auth endpoints
│   └── test_user_endpoints.py                  # User endpoints
└── smoke/                                      # E2E smoke tests
    └── test_user_registration_flow.py          # Complete user journey
```

**Naming Convention**:

- **Unit tests**: `test_<layer>_<component>_<type>.py`
  - `test_core_config.py` (core layer, config module)
  - `test_domain_user_entity.py` (domain layer, user entity)
  - `test_application_register_user.py` (application layer, command)

- **Integration tests**: `test_<component>_<technology>.py`
  - `test_cache_redis.py` (cache component, Redis tech)
  - `test_database_postgres.py` (database component, PostgreSQL)
  - `test_provider_schwab.py` (provider component, Schwab API)

- **API tests**: `test_<domain>_endpoints.py`
  - `test_auth_endpoints.py` (authentication domain)
  - `test_user_endpoints.py` (user management domain)

- **Smoke tests**: `test_<feature>_flow.py`
  - `test_user_registration_flow.py` (complete registration journey)

**Benefits of flat structure**:

- Easier to find tests (no nested navigation)
- Clear naming shows what's being tested
- Follows pytest discovery patterns
- Simpler to maintain (no empty directory management)

### Test Class Organization

```python
@pytest.mark.unit
class TestUserEntity:
    """Unit tests for User domain entity."""
    
    def test_user_validates_email(self):
        """Test email validation."""
        ...
    
    def test_user_hashes_password(self):
        """Test password hashing."""
        ...

@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations."""
    
    @pytest.mark.asyncio
    async def test_database_connection_works(self, test_database):
        """Test database connectivity."""
        ...
```

---

## Pytest Configuration

### pytest.ini

```ini
[pytest]
# Test discovery
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Output
addopts =
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    -p no:cacheprovider

# Async support
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function

# Markers
markers =
    unit: Unit tests with mocked dependencies
    integration: Integration tests with real database/cache
    smoke: End-to-end smoke tests
    asyncio: Async test that requires event loop
    slow: Tests that take > 1 second

# Coverage
[coverage:run]
source = src
omit =
    */tests/*
    */migrations/*
    */__pycache__/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False

[coverage:html]
directory = htmlcov
```

---

## Running Tests

### Makefile Commands

```makefile
# Run all tests with coverage
make test

# Run specific test types
make test-unit           # Unit tests only
make test-integration    # Integration tests only
make test-smoke          # E2E smoke tests

# Run with verbose output
make test-verbose

# Run specific test file
make test-file FILE=tests/unit/core/test_config.py

# Run specific test function
pytest tests/unit/core/test_config.py::TestSettings::test_from_env -v
```

### Docker Environment

**Tests run in isolated Docker environment**:

- **Test database**: `dashtam-test-postgres` (port 5433)
- **Test Redis**: `dashtam-test-redis` (port 6380)
- **Test app**: `dashtam-test-app`

**Ephemeral storage** (tmpfs) ensures clean state for each test run.

### CI Pipeline

```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Start test environment
        run: make test-up
      
      - name: Run tests
        run: make test
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

---

## Coverage Guidelines

### What to Measure

- **Line coverage**: Every line executed at least once
- **Branch coverage**: Every condition (if/else) tested both ways
- **Path coverage**: All execution paths tested

### Coverage Targets by Layer

| Layer              | Target  | Reasoning                                   |
|--------------------|---------|---------------------------------------------|
| Core (Shared)      | 95%     | Critical shared utilities                   |
| Domain             | 95%     | Business logic must be thoroughly tested    |
| Application        | 90%     | Command/query handlers are critical         |
| Infrastructure     | 70%     | Integration tests (not every edge case)     |
| Presentation (API) | 85%     | E2E tests cover critical journeys           |
| **Overall**        | **85%** | Clean slate target                          |

### Measuring Coverage

```bash
# Generate coverage report
make test  # Automatically includes coverage

# View HTML report
open htmlcov/index.html

# View terminal report
make test-coverage
```

---

## Established Patterns

**Context**: These patterns represent our production testing practices and have
been validated through extensive use across the codebase.

### Session Management for Domain Events

**Critical Pattern**: When testing domain events that trigger event handlers
requiring database access (e.g., audit handlers), always pass the database
session explicitly to `event_bus.publish()`.

**Why**: Event handlers that perform database operations need an active session.
Without explicit session passing, handlers would create their own sessions,
which can cause "Event loop is closed" errors during test teardown due to
improper session lifecycle management.

**Example** (from `tests/integration/test_domain_events_flow.py`):

```python
@pytest.mark.integration
class TestEventFlowEndToEnd:
    """Test complete event flow with real infrastructure."""

    @pytest.mark.asyncio
    async def test_user_registration_succeeded_creates_audit_record(
        self, test_database
    ):
        """Test UserRegistrationSucceeded → audit record created."""
        # Arrange
        event_bus = get_event_bus()
        user_id = uuid7()
        event = UserRegistrationSucceeded(
            user_id=user_id, email="integration@example.com"
        )

        # Act - Pass session to avoid "Event loop is closed" error
        async with test_database.get_session() as session:
            await event_bus.publish(event, session=session)  # ← CRITICAL

        # Assert - Audit record created in database
        async with test_database.get_session() as session:
            stmt = select(AuditLogModel).where(AuditLogModel.user_id == user_id)
            result = await session.execute(stmt)
            logs = result.scalars().all()

            assert len(logs) == 1
            assert logs[0].action == AuditAction.USER_REGISTERED
```

**Pattern Summary**:

1. Use `test_database` fixture for tests involving event handlers with database operations
2. Wrap event publishing in `async with test_database.get_session()` context
3. Pass session explicitly: `event_bus.publish(event, session=session)`
4. Use separate session contexts for querying verification data

### Test File Naming Conventions

**Unit Tests** (`tests/unit/`):

- `test_core_config.py` - Configuration management
- `test_core_container_logger.py` - Logger container
- `test_core_container_secrets.py` - Secrets container
- `test_domain_enums_audit_action.py` - Domain enums
- `test_domain_events_authentication_events.py` - Domain events
- `test_domain_events_event_bus.py` - Event bus protocol
- `test_infrastructure_audit_postgres_adapter.py` - Audit adapter
- `test_infrastructure_event_handlers.py` - Event handlers
- `test_infrastructure_logging_cloudwatch_adapter.py` - CloudWatch logging
- `test_infrastructure_logging_console_adapter.py` - Console logging
- `test_infrastructure_secrets_aws_adapter.py` - AWS secrets
- `test_infrastructure_secrets_env_adapter.py` - Environment secrets
- `test_presentation_middleware_trace.py` - Trace middleware

**Integration Tests** (`tests/integration/`):

- `test_audit_durability.py` - Audit persistence guarantees
- `test_audit_postgres_adapter.py` - Audit database operations
- `test_cache_redis.py` - Redis cache operations
- `test_database_postgres.py` - PostgreSQL database operations
- `test_domain_events_flow.py` - Event bus end-to-end flows
- `test_logging_cloudwatch_adapter.py` - CloudWatch integration
- `test_logging_console_adapter.py` - Console logging integration
- `test_secrets_env_adapter.py` - Environment secrets integration

**Naming Convention**:

- `test_<layer>_<component>.py` for unit tests
- `test_<component>_<technology>.py` for integration tests
- `test_<feature>_flow.py` for end-to-end flow tests

### Fixture Patterns

**Source**: `tests/conftest.py` provides reusable fixtures for all test types.

#### 1. Function-Scoped Event Loop

```python
@pytest.fixture(scope="function")
def event_loop(event_loop_policy):
    """Create a new event loop for each test function.
    
    Ensures complete isolation between tests.
    """
    loop = event_loop_policy.new_event_loop()
    yield loop
    
    try:
        loop.close()
    except Exception:
        pass  # Loop might already be closed
```

**Why function scope**: Each test gets fresh event loop - prevents state
leakage between async tests.

#### 2. Automatic Asyncio Marker

```python
def pytest_collection_modifyitems(config, items):
    """Automatically add asyncio marker to async test functions."""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
```

**Benefit**: No need to manually add `@pytest.mark.asyncio` decorator.

#### 3. Fresh Redis Client Per Test

```python
@pytest_asyncio.fixture
async def redis_test_client():
    """Provide fresh Redis client for each test.
    
    Bypasses singleton pattern for complete test isolation.
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
    
    client = Redis(connection_pool=pool)
    await client.ping()  # Verify connection
    
    yield client
    
    # Cleanup
    await client.aclose()
    await pool.disconnect()
```

**Pattern**: Bypass singleton for tests, fresh instances for isolation.

#### 4. Test Database Fixture

```python
@pytest_asyncio.fixture
async def test_database():
    """Provide test database instance for integration tests.
    
    Returns Database object (not session) for creating multiple
    independent sessions as needed.
    """
    from src.infrastructure.persistence.database import Database
    from src.core.config import settings
    
    db = Database(database_url=settings.database_url, echo=settings.db_echo)
    yield db
    await db.close()
```

**Usage**: For tests that need multiple separate sessions (e.g., audit
durability, event bus tests).

#### 5. Mock Container Dependencies

```python
@pytest.fixture
def mock_container_dependencies():
    """Mock all container dependencies for unit tests.
    
    Returns:
        dict: Dictionary of mock dependencies
    """
    from unittest.mock import AsyncMock, Mock, patch
    from src.core.result import Success
    
    mocks = {
        "cache": AsyncMock(),
        "secrets": Mock(),
        "database": Mock(),
    }
    
    # Configure default behaviors
    mocks["cache"].get.return_value = Success(None)
    mocks["cache"].set.return_value = Success(None)
    mocks["secrets"].get_secret.return_value = "mock-secret"
    
    # Patch container functions
    with patch("src.core.container.get_cache", return_value=mocks["cache"]):
        with patch("src.core.container.get_secrets", return_value=mocks["secrets"]):
            with patch("src.core.container.get_database", return_value=mocks["database"]):
                yield mocks
```

**Use**: Unit tests for application/domain layer that need mocked
infrastructure.

### Result Type Assertion Patterns

**Pattern**: Consistent use of `isinstance()` for Result type checking:

**Success Assertions**:

```python
# From test_cache_redis.py
result = await cache_adapter.set("test_key", "test_value")
assert isinstance(result, Success)
assert result.value is None  # set() returns None on success

get_result = await cache_adapter.get("test_key")
assert isinstance(get_result, Success)
assert get_result.value == "test_value"
```

**Failure Assertions**:

```python
# From test_cache_redis.py
result = await cache_adapter.get_json("invalid_json")
assert isinstance(result, Failure)
assert isinstance(result.error, CacheError)
assert "parse json" in result.error.message.lower()
```

**Pattern**: Always use `isinstance()` for Result type checking, never
direct comparison.

### Test Class Structure Pattern

```python
@pytest.mark.integration
class TestCacheIntegration:
    """Integration tests for cache infrastructure.
    
    Uses fixtures from conftest.py:
    - cache_adapter: Fresh RedisAdapter per test
    - redis_test_client: Fresh Redis client per test
    """
    
    @pytest.mark.asyncio
    async def test_cache_connection_works(self, cache_adapter):
        """Test description with clear intent."""
        result = await cache_adapter.ping()
        assert isinstance(result, Success)
```

**Pattern Elements**:

1. Mark class with test type (`@pytest.mark.integration` or `@pytest.mark.unit`)
2. Descriptive class docstring listing fixtures used
3. Each method marked `@pytest.mark.asyncio` if async
4. Descriptive test method names with docstrings

### Test Distribution Guidelines

**Target distribution** (following test pyramid):

- **Unit tests**: 60-70% (fast, isolated, mock dependencies)
- **Integration tests**: 25-35% (real infrastructure, test interactions)
- **Flow tests**: 5-10% (end-to-end, critical user journeys)

**Coverage targets**:

- **Overall**: 85%+ across all code
- **Critical components**: 95%+ (authentication, audit, security)
- **Infrastructure adapters**: 90%+ (database, cache, secrets)
- **Domain logic**: 100% (pure business logic, no excuses)

---

## Best Practices

### Do's ✅

1. **Test behavior, not implementation**
   - Test what the code does, not how it does it
   - Don't test private methods

2. **Use descriptive test names**
   - `test_user_registration_requires_valid_email()` ✅
   - `test_user()` ❌

3. **Follow AAA pattern** (Arrange, Act, Assert)

   ```python
   def test_something():
       # Arrange
       user = User(email="test@example.com")
       
       # Act
       result = user.validate()
       
       # Assert
       assert result.is_success
   ```

4. **One assertion per test** (when reasonable)
   - Each test should verify one thing
   - Exception: Related assertions can be grouped

5. **Use fixtures for setup**
   - DRY principle - reuse common setup

6. **Test edge cases**
   - Empty strings, None values, boundary conditions
   - Invalid inputs, error paths

7. **Keep tests fast**
   - Unit tests: < 100ms
   - Integration tests: < 1s
   - E2E tests: < 5s

### Don'ts ❌

1. **Don't test external libraries**
   - Don't test SQLAlchemy, Redis, FastAPI internals

2. **Don't use time.sleep() in tests**
   - Use proper async patterns

3. **Don't share state between tests**
   - Each test must be independent

4. **Don't test multiple scenarios in one test**
   - Split into separate tests

5. **Don't mock everything**
   - Only mock external dependencies

6. **Don't test generated code**
   - Alembic migrations, Pydantic models

7. **Don't commit failing tests**
   - Fix or skip with `@pytest.mark.skip(reason="...")`

### Time-Dependent Tests

**Use `freezegun` for deterministic time-dependent tests** - avoid flaky
tolerance-based assertions.

**Problem** (flaky):

```python
# ❌ Fragile: Relies on test execution speed
def test_token_expiration():
    before = datetime.now(UTC)
    expires_at = service.calculate_expiration()  # 24 hours from now
    
    # Tolerance range can still fail
    assert expires_at >= before + timedelta(hours=24) - timedelta(seconds=1)
```

**Solution** (deterministic):

```python
# ✅ Deterministic: Frozen time = exact assertions
from freezegun import freeze_time

@freeze_time("2024-01-01 12:00:00")
def test_token_expiration():
    expires_at = service.calculate_expiration()  # 24 hours from frozen time
    expected = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)
    assert expires_at == expected  # Exact match, no tolerance
```

**When to use**:

- ✅ Token/session expiration tests
- ✅ Cache TTL tests
- ✅ Timestamp comparison tests
- ❌ Tests measuring actual duration (use `time.perf_counter()`)

**Pattern**: Apply decorator to test/class, use fixed timestamps, exact assertions.

---

## Troubleshooting

### Common Issues

#### Issue: Tests fail with "RuntimeError: Event loop is closed"

**Cause**: Async fixture scope mismatch

**Solution**: Use `scope="function"` for async fixtures

```python
@pytest_asyncio.fixture(scope="function")  # Not "session"
async def cache_adapter():
    ...
```

#### Issue: Database tests fail with "relation does not exist"

**Cause**: Alembic migrations not run

**Solution**: Ensure migrations run on test environment startup

```yaml
# compose/docker-compose.test.yml
command: >
  sh -c "
    uv run alembic upgrade head &&
    tail -f /dev/null
  "
```

#### Issue: Tests pass individually but fail when run together

**Cause**: Shared state via singleton

**Solution**: Bypass singleton in tests, use fresh instances

#### Issue: "fixture 'event_loop' not found"

**Cause**: Missing pytest-asyncio configuration

**Solution**: Add to `conftest.py`:

```python
pytest_plugins = ("pytest_asyncio",)
```

---

## Summary

This testing architecture provides:

- **Clear patterns** for each hexagonal layer
- **Reusable fixtures** in `conftest.py`
- **Async testing** with proper isolation
- **Integration over unit** for infrastructure
- **Railway-oriented** testing with Result types
- **Centralized DI testing** with container mocking strategies

**Key Takeaways**:

1. Test the right things at the right level
2. Infrastructure = integration tests (not unit tests)
3. Mock container dependencies for unit tests
4. Use real container for integration tests
5. Clear container cache between tests to prevent state leakage
6. Fresh event loops per test
7. Use fixtures from conftest.py
8. Target 85%+ overall coverage

**See also**: `dependency-injection-architecture.md` for container pattern details.

---

**Created**: 2025-11-12 | **Last Updated**: 2025-12-07
