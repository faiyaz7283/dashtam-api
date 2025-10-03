# Dashtam Testing Strategy - Complete Restructure

## Executive Summary

Based on comprehensive research of:
1. **PDF Guide**: "A Comprehensive Guide to Testing FastAPI and SQLAlchemy 2.0 with pytest-asyncio"
2. **FastAPI Official Template**: https://github.com/fastapi/full-stack-fastapi-template
3. **Our Experience**: Greenlet errors and async complexity documented in `docs/research/async-testing.md`

**Key Finding**: The FastAPI official template uses **synchronous testing** with `TestClient` and `Session` (not async), which completely avoids the greenlet/event loop issues we encountered.

## ✅ Implementation Status: **COMPLETE**

**Current State** (as of Phase 2 CI/CD completion):
- ✅ Synchronous testing strategy fully implemented
- ✅ 39 tests passing (9 unit, 11 integration, 19 API)
- ✅ 51% code coverage
- ✅ All tests passing in local and CI environments
- ✅ Zero async/greenlet issues
- ✅ FastAPI TestClient with synchronous SQLModel Session
- ✅ Docker-based test environment with isolated PostgreSQL
- ✅ GitHub Actions CI/CD with automated testing
- ✅ Codecov integration for coverage tracking

**Next Phase**: Expand test coverage to 85%+ (see Phase 2+ in implementation plan below)

## Critical Decision: Sync vs Async Testing

### FastAPI Official Approach (Recommended)
- Uses **synchronous** `TestClient` from FastAPI
- Uses **synchronous** `Session` from SQLModel
- Tests are regular `def test_*()` functions (NOT `async def`)
- No pytest-asyncio complexity
- No greenlet errors
- **Tests still work perfectly with async application code**

### Why This Works
FastAPI's `TestClient` handles the async/sync bridge internally. Your application code remains async, but tests are sync. This is the **official, supported pattern**.

## Recommended Testing Architecture

### Three-Tier Testing Strategy

```
tests/
├── unit/             # Pure logic, no database
├── integration/      # Database operations, service layer
└── api/              # End-to-end API tests
```

### 1. Unit Tests (Fast, Isolated)
**Purpose**: Test business logic without external dependencies
**Characteristics**:
- No database connection
- Mock all external services
- Test pure functions and class methods
- Run in milliseconds

**Example Pattern**:
```python
def test_encrypt_token(mock_encryption_service):
    """Test token encryption logic"""
    result = mock_encryption_service.encrypt("test_token")
    assert result == "encrypted_test_token"
```

### 2. Integration Tests (Database, Services)
**Purpose**: Test database operations and service layer
**Characteristics**:
- Use real PostgreSQL database
- Transaction rollback for isolation
- Test CRUD operations
- Test service layer business logic

**Example Pattern (Sync)**:
```python
def test_create_provider(db: Session):
    """Test provider creation with database"""
    provider = crud.create_provider(
        session=db,
        user_id=test_user.id,
        provider_key="schwab"
    )
    assert provider.id is not None
    assert provider.provider_key == "schwab"
```

### 3. API Tests (End-to-End)
**Purpose**: Test complete request/response cycle
**Characteristics**:
- Use FastAPI's `TestClient`
- Test authentication flows
- Test API endpoints
- Test error handling

**Example Pattern**:
```python
def test_create_provider_endpoint(client: TestClient, superuser_token_headers):
    """Test POST /api/v1/providers endpoint"""
    data = {"provider_key": "schwab", "alias": "My Account"}
    response = client.post(
        f"{settings.API_V1_STR}/providers/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["provider_key"] == "schwab"
```

## Implementation Plan

### Phase 1: Core Test Infrastructure (2-3 hours)

#### File: `tests/conftest.py`
```python
from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, create_engine
from sqlalchemy.pool import StaticPool

from src.core.config import settings
from src.core.db import init_db
from src.main import app
from src.models import User, Provider, ProviderConnection, ProviderToken

# Use in-memory SQLite for fast tests, or test PostgreSQL for production parity
TEST_DATABASE_URL = "sqlite:///:memory:"  # Fast
# TEST_DATABASE_URL = settings.test_database_url  # Production parity

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite specific
    poolclass=StaticPool,  # Keep connection alive for in-memory DB
)

@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    """Session-scoped database fixture.
    
    Creates tables once, cleans up after all tests.
    Uses DELETE for cleanup (fast) rather than DROP/CREATE.
    """
    from sqlmodel import SQLModel
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        init_db(session)  # Initialize with test data if needed
        yield session
        
        # Cleanup - delete all data
        session.exec(delete(ProviderToken))
        session.exec(delete(ProviderConnection))
        session.exec(delete(Provider))
        session.exec(delete(User))
        session.commit()
    
    # Drop tables after session
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db: Session) -> Generator[Session, None, None]:
    """Function-scoped session for test isolation.
    
    Each test gets a fresh session. Changes are visible across
    the test but can be cleaned up if needed.
    """
    yield db


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Test client for API requests."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    """Headers with superuser authentication."""
    return get_superuser_token_headers(client)
```

#### Key Patterns from PDF Guide:

**1. Function-Scoped Engine with NullPool (If Using Async)**
```python
@pytest.fixture(scope="function")
def test_engine(test_settings):
    engine = create_async_engine(
        test_settings.test_database_url,
        poolclass=NullPool,  # Critical for async testing
    )
    yield engine
    asyncio.run(engine.dispose())
```

**2. Transactional Isolation with Savepoints (PostgreSQL)**
```python
@pytest_asyncio.fixture
async def db_session(test_engine):
    async with test_engine.connect() as connection:
        await connection.begin()
        
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint"  # KEY PATTERN
        )
        
        yield session
        
        await session.close()
        await connection.rollback()  # Rollback everything
```

### Phase 2: Refactor Service Layer (1-2 hours)

**Current Problem**: Services call `await session.commit()` which causes issues in test transactions.

**Solution**: Remove commits from services, handle in API layer.

#### Before (Problematic):
```python
# src/services/token_service.py
async def store_initial_tokens(self, ...):
    # ... business logic ...
    self.session.add(token)
    await self.session.commit()  # ❌ Problematic in tests
    return token
```

#### After (Clean):
```python
# src/services/token_service.py
async def store_initial_tokens(self, ...):
    # ... business logic ...
    self.session.add(token)
    await self.session.flush()  # ✅ Persist in transaction
    await self.session.refresh(token)  # Load relationships
    return token

# src/api/endpoints/providers.py
@router.post("/providers/tokens")
async def store_tokens(...):
    token = await token_service.store_initial_tokens(...)
    await session.commit()  # ✅ Commit at API boundary
    return token
```

**Benefits**:
- Services are now testable with simple flush()
- API layer controls transactions
- Follows separation of concerns
- Matches industry best practices

### Phase 3: Write Tests (3-4 hours)

#### Directory Structure:
```
tests/
├── __init__.py
├── conftest.py                 # Global fixtures
├── pytest.ini                  # Pytest configuration
│
├── unit/                       # Unit tests (no DB)
│   ├── __init__.py
│   ├── services/
│   │   ├── test_encryption_service.py
│   │   └── test_token_validation.py
│   └── utils/
│       └── test_helpers.py
│
├── integration/                # Integration tests (with DB)
│   ├── __init__.py
│   ├── conftest.py             # Integration-specific fixtures
│   ├── crud/
│   │   ├── test_user_crud.py
│   │   ├── test_provider_crud.py
│   │   └── test_token_crud.py
│   └── services/
│       ├── test_token_service.py
│       └── test_provider_service.py
│
└── api/                       # API/E2E tests
    ├── __init__.py
    ├── conftest.py            # API-specific fixtures
    └── routes/
        ├── test_auth.py
        ├── test_providers.py
        └── test_health.py
```

#### Example: Unit Test
```python
# tests/unit/services/test_encryption_service.py
import pytest
from src.services.encryption import EncryptionService

def test_encrypt_decrypt_cycle():
    """Test encryption and decryption works correctly"""
    service = EncryptionService()
    original = "my_secret_token"
    
    encrypted = service.encrypt(original)
    assert encrypted != original
    assert encrypted.startswith("gAAAAA")  # Fernet format
    
    decrypted = service.decrypt(encrypted)
    assert decrypted == original
```

#### Example: Integration Test (Sync Pattern)
```python
# tests/integration/crud/test_provider_crud.py
import pytest
from sqlmodel import Session
from src import crud
from src.models import ProviderCreate

def test_create_provider(db: Session, test_user):
    """Test creating a provider in database"""
    provider_in = ProviderCreate(
        user_id=test_user.id,
        provider_key="schwab",
        alias="Test Account"
    )
    
    provider = crud.create_provider(session=db, provider_in=provider_in)
    
    assert provider.id is not None
    assert provider.user_id == test_user.id
    assert provider.provider_key == "schwab"
    
    # Verify it's in database
    db_provider = db.get(Provider, provider.id)
    assert db_provider is not None
    assert db_provider.alias == "Test Account"
```

#### Example: API Test
```python
# tests/api/routes/test_providers.py
from fastapi.testclient import TestClient

def test_create_provider_endpoint(
    client: TestClient,
    superuser_token_headers: dict[str, str]
):
    """Test POST /api/v1/providers/ endpoint"""
    data = {
        "provider_key": "schwab",
        "alias": "My Schwab Account"
    }
    
    response = client.post(
        "/api/v1/providers/",
        headers=superuser_token_headers,
        json=data,
    )
    
    assert response.status_code == 200
    content = response.json()
    assert content["provider_key"] == "schwab"
    assert content["alias"] == "My Schwab Account"
    assert "id" in content


def test_oauth_flow_charles_schwab(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    mock_schwab_oauth
):
    """Test complete OAuth flow for Charles Schwab"""
    # Step 1: Get authorization URL
    response = client.get(
        "/api/v1/auth/schwab/authorize",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    auth_url = response.json()["authorization_url"]
    assert "schwab.com" in auth_url
    
    # Step 2: Simulate callback (mocked)
    callback_response = client.get(
        f"/api/v1/auth/schwab/callback?code=mock_code&state={state}",
        headers=superuser_token_headers,
    )
    assert callback_response.status_code == 200
    
    # Step 3: Verify token stored
    tokens = callback_response.json()
    assert "access_token" in tokens
    assert tokens["provider_key"] == "schwab"
```

### Phase 4: Advanced Patterns (Optional, 1-2 hours)

#### Testcontainers for Production Parity
```python
# tests/integration/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres_container():
    """Spin up real PostgreSQL in Docker for tests"""
    with PostgresContainer("postgres:17.6") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def db_engine(postgres_container):
    """Engine connected to test PostgreSQL"""
    database_url = postgres_container.get_connection_url()
    engine = create_engine(database_url)
    return engine
```

#### Parallel Testing with pytest-xdist
```ini
# pytest.ini
[pytest]
addopts = -n auto  # Use all CPU cores
```

```python
# Use unique database per worker
@pytest.fixture(scope="session")
def test_db_url(worker_id):
    """Create isolated database per pytest-xdist worker"""
    if worker_id == "master":
        return f"postgresql://user:pass@localhost/test_db"
    return f"postgresql://user:pass@localhost/test_db_{worker_id}"
```

## Configuration Files

### `pytest.ini`
```ini
[pytest]
# Test discovery
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# pytest-asyncio (only if using async tests)
asyncio_mode = auto

# Output
addopts = 
    --strict-markers
    --verbose
    --tb=short
    --cov=src
    --cov-report=term-missing
    --cov-report=html

# Test paths
testpaths = tests

# Markers
markers =
    unit: Unit tests (fast, no DB)
    integration: Integration tests (with DB)
    api: API/E2E tests
    slow: Slow-running tests
    
# Minimum version
minversion = 7.0
```

### `pyproject.toml` (Testing Section)
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.coverage.run]
source = ["src"]
omit = [
    "src/migrations/*",
    "tests/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

## Migration Path

### Step 1: Backup Current Tests
```bash
mv tests/conftest.py tests/conftest_old_async.py
mv tests/unit tests/unit_old_async
```

### Step 2: Implement New conftest.py
- Use sync Session pattern from FastAPI template
- Remove all async fixtures
- Use TestClient instead of AsyncClient

### Step 3: Migrate Tests One Category at a Time
1. **Start with Unit Tests** (easiest)
   - Remove `@pytest.mark.asyncio`
   - Change `async def` to `def`
   - Change `await` calls to sync calls

2. **Then Integration Tests**
   - Use `db: Session` fixture
   - Remove async session operations
   - Keep database operations

3. **Finally API Tests**
   - Use `TestClient` sync API
   - No async/await needed

### Step 4: Run and Verify
```bash
# Run unit tests (fast)
pytest tests/unit -v

# Run integration tests
pytest tests/integration -v

# Run API tests
pytest tests/api -v

# Run all with coverage
pytest --cov=src --cov-report=html
```

## Benefits of This Approach

### ✅ Advantages
1. **No async complexity** - Tests are simple sync functions
2. **No greenlet errors** - TestClient handles async/sync bridge
3. **Official pattern** - Used by FastAPI core team
4. **Fast execution** - Especially with in-memory SQLite
5. **Easy to write** - No async/await mental overhead
6. **Reliable** - No event loop management issues
7. **Maintainable** - Clear, simple test code

### ⚠️ Trade-offs
1. **Not testing async paths** - But FastAPI handles this internally
2. **Different from production** - But functionality is identical
3. **May miss async-specific bugs** - Rare in practice

## Key Takeaways from PDF Guide

1. **Never create session-scoped event loops** - Causes "attached to different loop" errors
2. **Use `NullPool` for async engines** - Prevents connection reuse across loops
3. **Use `join_transaction_mode="create_savepoint"`** - For transactional isolation
4. **Avoid `pytest-xdist` with session-scoped async fixtures** - Creates conflicts
5. **Let pytest-asyncio manage loops** - Don't create custom event_loop fixtures

## Recommended Tools

- **pytest**: Core testing framework
- **pytest-cov**: Coverage reporting
- **pytest-xdist**: Parallel test execution (optional)
- **faker**: Generate test data
- **factory-boy**: Test data factories (optional)
- **testcontainers**: Docker containers for tests (optional)

## Success Metrics

- **Unit Tests**: < 100ms per test, 80%+ coverage
- **Integration Tests**: < 500ms per test, 90%+ coverage  
- **API Tests**: < 1s per test, 95%+ coverage
- **Total Suite**: < 30s for full run
- **CI Pipeline**: < 2 minutes including linting

## Conclusion

**Primary Recommendation**: Follow the FastAPI official template pattern using **synchronous tests** with `TestClient` and `Session`. This avoids all the async complexity while providing complete test coverage.

**Alternative (If Needed)**: If you must test async paths directly, use the patterns from the PDF guide with `NullPool`, `join_transaction_mode="create_savepoint"`, and careful event loop management.

The sync approach is proven, official, and will save significant development time while providing excellent test coverage.
