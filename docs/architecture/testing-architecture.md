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
    repo = PostgresUserRepository(test_database)
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

**Key Takeaways**:

1. Test the right things at the right level
2. Infrastructure = integration tests (not unit tests)
3. Bypass singletons in tests for isolation
4. Fresh event loops per test
5. Use fixtures from conftest.py
6. Target 85%+ overall coverage

---

**Created**: 2025-11-12 | **Last Updated**: 2025-11-12
