# Async vs Sync Testing Architecture Decision

Architectural decision record documenting the choice of synchronous testing with FastAPI TestClient over async testing patterns for the Dashtam testing infrastructure.

---

## Table of Contents

- [Overview](#overview)
  - [Why This Approach?](#why-this-approach)
- [Context](#context)
  - [Research Sources](#research-sources)
  - [Problems Encountered](#problems-encountered)
- [Architecture Goals](#architecture-goals)
- [Design Decisions](#design-decisions)
  - [Decision 1: Synchronous Testing with TestClient](#decision-1-synchronous-testing-with-testclient)
  - [Alternative 1: Async Testing with pytest-asyncio (Rejected)](#alternative-1-async-testing-with-pytest-asyncio-rejected)
  - [Alternative 2: Mixed Approach (Rejected)](#alternative-2-mixed-approach-rejected)
  - [Alternative 3: Synchronous Testing (Selected)](#alternative-3-synchronous-testing-selected)
- [Components](#components)
  - [Component 1: FastAPI TestClient](#component-1-fastapi-testclient)
  - [Component 2: SQLModel Synchronous Session](#component-2-sqlmodel-synchronous-session)
  - [Component 3: Test Fixtures](#component-3-test-fixtures)
- [Implementation Details](#implementation-details)
  - [Key Patterns Used](#key-patterns-used)
    - [Pattern 1: Synchronous Test Functions](#pattern-1-synchronous-test-functions)
    - [Pattern 2: TestClient for API Tests](#pattern-2-testclient-for-api-tests)
    - [Pattern 3: Synchronous Session for Database Tests](#pattern-3-synchronous-session-for-database-tests)
  - [Code Organization](#code-organization)
  - [Configuration](#configuration)
  - [Application vs Test Code](#application-vs-test-code)
  - [How TestClient Works Internally](#how-testclient-works-internally)
- [Security Considerations](#security-considerations)
- [Performance Considerations](#performance-considerations)
  - [Testing Performance Metrics](#testing-performance-metrics)
  - [Comparison to Async Testing](#comparison-to-async-testing)
- [Testing Strategy](#testing-strategy)
  - [Unit Tests](#unit-tests)
  - [Integration Tests](#integration-tests)
  - [End-to-End Tests](#end-to-end-tests)
- [Future Enhancements](#future-enhancements)
  - [If Async Testing Becomes Necessary](#if-async-testing-becomes-necessary)
  - [Potential Scenarios](#potential-scenarios)
- [References](#references)
- [Document Information](#document-information)

---

## Overview

Dashtam's testing architecture uses synchronous testing with FastAPI's TestClient and SQLModel's Session, despite the application being fully async. This architectural decision completely avoids async testing complexity while maintaining comprehensive test coverage.

### Why This Approach?

The FastAPI official template and core team recommend synchronous testing with TestClient. This pattern:

- Eliminates greenlet and event loop errors
- Simplifies test code (no async/await needed)
- Maintains reliability with 295+ tests passing consistently
- Follows official FastAPI patterns used by thousands of projects
- Allows async application code to work perfectly with sync tests

## Context

Dashtam is built with async FastAPI and uses SQLAlchemy's AsyncSession for database operations. During initial testing implementation (September 2025), we encountered significant complexity and errors when attempting to test async code with async test patterns.

### Research Sources

1. **PDF Guide:** "A Comprehensive Guide to Testing FastAPI and SQLAlchemy 2.0 with pytest-asyncio"
2. **FastAPI Official Template:** https://github.com/fastapi/full-stack-fastapi-template
3. **Our Experience:** Greenlet errors and async complexity documented in prior troubleshooting

### Problems Encountered

- **Greenlet spawn errors:** "greenlet_spawn has not been called"
- **Event loop conflicts:** "attached to different loop" errors
- **Pytest-asyncio complexity:** Managing event loops, fixtures, and session scopes
- **Unreliable tests:** Flaky failures due to async timing issues
- **Development friction:** Difficult to write and maintain tests

## Architecture Goals

1. **Reliability:** Tests should be deterministic and never flaky
2. **Simplicity:** Test code should be simple and easy to understand
3. **Speed:** Test suite should execute quickly (< 30 seconds total)
4. **Official Pattern:** Follow FastAPI core team recommendations
5. **Maintainability:** Easy for new contributors to write tests

## Design Decisions

### Decision 1: Synchronous Testing with TestClient

**Rationale:** The FastAPI official template uses **synchronous testing** with `TestClient` and `Session` (not async), which completely avoids the greenlet/event loop issues we encountered. This is the official, supported pattern recommended by the FastAPI core team.

**Key Features:**

- Uses **synchronous** `TestClient` from FastAPI
- Uses **synchronous** `Session` from SQLModel
- Tests are regular `def test_*()` functions (NOT `async def`)
- No pytest-asyncio complexity
- No greenlet errors
- **Tests still work perfectly with async application code**

**Alternatives Considered:**

### Alternative 1: Async Testing with pytest-asyncio (Rejected)

**Approach:** Use `@pytest.mark.asyncio`, `AsyncSession`, and `AsyncClient`

**Pros:**

- Tests async code paths directly
- Matches production runtime more closely

**Cons:**

- Complex event loop management
- Greenlet spawn errors
- Requires `NullPool` for engines
- Needs `join_transaction_mode="create_savepoint"` for isolation
- Pytest-xdist conflicts with session-scoped async fixtures
- Significantly more code and complexity
- Flaky tests due to timing issues

**Verdict:** ❌ Rejected due to excessive complexity and reliability issues

### Alternative 2: Mixed Approach (Rejected)

**Approach:** Use sync tests for most, async for specific cases

**Pros:**

- Flexibility to test async paths when needed

**Cons:**

- Inconsistent patterns across test suite
- Maintenance burden of two approaches
- Still inherits async testing complexity

**Verdict:** ❌ Rejected in favor of consistency

### Alternative 3: Synchronous Testing (Selected)

**Approach:** Use `TestClient` with synchronous `Session`

**Pros:**

- ✅ Zero async complexity
- ✅ No greenlet errors
- ✅ Official FastAPI pattern
- ✅ Fast and reliable
- ✅ Easy to write and maintain
- ✅ Works perfectly with async application code

**Cons:**

- ⚠️ Not testing async code paths directly
- ⚠️ Different from production (but functionality identical)
- ⚠️ May miss rare async-specific bugs

**Trade-offs:**

- ✅ **Pros:** Zero async complexity, no greenlet errors, official pattern, fast execution, easy to write/maintain, reliable, proven in production
- ⚠️ **Cons:** Not testing async paths directly (but FastAPI handles internally), different from production (but functionality identical), may miss rare async-specific bugs (rare in practice)

**Mitigation:** The rare async-specific bugs are typically in custom async code (which we can test separately if needed) or event loop edge cases (which FastAPI TestClient handles). Our testing has proven reliable with 295+ tests passing consistently.

**Verdict:** ✅ **Selected** - Benefits far outweigh drawbacks

## Components

### Component 1: FastAPI TestClient

**Purpose:** Bridges async application code and synchronous tests

**Responsibilities:**

- Internally manages the async event loop
- Converts async endpoints to synchronous calls for tests
- Handles all async/sync bridging automatically
- Provides synchronous HTTP client interface

**Interfaces:**

- **Input:** Synchronous method calls (`client.post()`, `client.get()`, etc.)
- **Output:** Synchronous HTTP responses

**Dependencies:**

- FastAPI application instance
- Async endpoint handlers (application code)

**Usage Example:**

```python
from fastapi.testclient import TestClient

def test_endpoint(client: TestClient):
    """Test async endpoint with sync test."""
    response = client.post("/api/v1/endpoint", json=data)
    assert response.status_code == 200
```

### Component 2: SQLModel Synchronous Session

**Purpose:** Provides database access in tests

**Responsibilities:**

- Execute database queries synchronously
- Manage transactions for test isolation
- Provide ORM interface for test data

**Interfaces:**

- **Input:** SQLModel operations (add, query, commit)
- **Output:** Database records

**Dependencies:**

- Test database (SQLite in-memory or PostgreSQL)
- SQLModel/SQLAlchemy engine

**Configuration:**

```python
from sqlmodel import Session, create_engine
from sqlalchemy.pool import StaticPool

# In-memory SQLite for fast tests
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # Keep connection alive
)
```

**Usage Example:**

```python
def test_database_operation(db: Session):
    """Test with synchronous session."""
    user = User(email="test@example.com")
    db.add(user)
    db.commit()
    assert user.id is not None
```

### Component 3: Test Fixtures

**Purpose:** Provide reusable test dependencies and setup/teardown

**Responsibilities:**

- Create test database and session
- Provide TestClient instance
- Set up authentication headers
- Clean up test data after tests

**Session-scoped database:**

```python
@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    """Session-scoped database fixture."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)
```

**Function-scoped session:**

```python
@pytest.fixture(scope="function")
def db_session(db: Session) -> Generator[Session, None, None]:
    """Function-scoped session for test isolation."""
    yield db
```

## Implementation Details

### Key Patterns Used

#### Pattern 1: Synchronous Test Functions

All tests are regular `def` functions (not `async def`). No `@pytest.mark.asyncio` decorators needed.

```python
def test_example():  # NOT async def
    """Regular synchronous test function."""
    assert True
```

#### Pattern 2: TestClient for API Tests

FastAPI's TestClient bridges async application code with synchronous tests automatically.

```python
def test_api(client: TestClient):
    """TestClient handles async/sync bridge."""
    response = client.get("/endpoint")  # Sync call, async endpoint
    assert response.status_code == 200
```

#### Pattern 3: Synchronous Session for Database Tests

Use SQLModel's synchronous `Session` in tests, even though application uses `AsyncSession`.

```python
def test_db(db: Session):  # Sync Session in test
    """Database operations are synchronous in tests."""
    user = User(email="test@example.com")
    db.add(user)  # Sync operations
    db.commit()
```

### Code Organization

```text
tests/
├── conftest.py          # Global fixtures (Session, TestClient)
├── unit/                # Unit tests (no database)
│   ├── services/        # Service layer tests
│   └── utils/           # Utility function tests
├── integration/         # Integration tests (with database)
│   ├── crud/            # CRUD operation tests
│   └── services/        # Service integration tests
└── api/                 # API endpoint tests (TestClient)
    └── routes/          # Route-specific tests
```

### Configuration

**Test Database:** In-memory SQLite or isolated PostgreSQL

**Test Session:** Function-scoped for isolation between tests

**Test Client:** Module-scoped for performance (reused across test module)

**Pytest Configuration (`pytest.ini`):**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
```

### Application vs Test Code

**Application Code:** Fully async with `AsyncSession`

```python
@router.post("/users")
async def create_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session)
):
    """Async endpoint (production code)."""
    user = User(**user_in.dict())
    session.add(user)
    await session.commit()
    return user
```

**Test Code:** Synchronous with `TestClient`

```python
def test_create_user(client: TestClient):
    """Sync test (test code)."""
    response = client.post(
        "/users",
        json={"email": "test@example.com"}
    )
    assert response.status_code == 200
```

### How TestClient Works Internally

**FastAPI's TestClient internal mechanism:**

1. Test calls `client.post()` (synchronous)
2. TestClient creates a new event loop internally
3. TestClient runs async endpoint in that loop
4. TestClient awaits all async operations
5. TestClient returns synchronous response to test
6. Test continues synchronously

**Result:** Your async application code runs correctly, but your tests are simple and synchronous.

## Security Considerations

**No security implications** - This is purely a testing architecture decision that doesn't affect production code or security posture.

## Performance Considerations

### Testing Performance Metrics

- **Unit tests:** < 100ms each (no database)
- **Integration tests:** < 500ms each (with database)
- **API tests:** < 1s each (full request cycle)
- **Full suite:** < 30s (295+ tests)

### Comparison to Async Testing

- **Synchronous:** Fast, predictable, no overhead
- **Async:** Slower due to event loop management, fixture complexity

**Verdict:** Synchronous testing is faster and more predictable.

## Testing Strategy

### Unit Tests

Test individual functions and classes in isolation with no database or external dependencies.

**Coverage:** Core business logic, utility functions, encryption services

**Example:**

```python
def test_encrypt_decrypt_cycle():
    """Test encryption service."""
    service = EncryptionService()
    encrypted = service.encrypt("token")
    assert service.decrypt(encrypted) == "token"
```

### Integration Tests

Test component interactions with real database operations.

**Coverage:** CRUD operations, service layer, database relationships

**Example:**

```python
def test_create_user(db: Session):
    """Test user creation with database."""
    user = User(email="test@example.com")
    db.add(user)
    db.commit()
    assert user.id is not None
```

### End-to-End Tests

Test complete API workflows through TestClient.

**Coverage:** API endpoints, authentication flows, error handling

**Example:**

```python
def test_api_endpoint(client: TestClient):
    """Test POST endpoint."""
    response = client.post("/api/v1/endpoint", json=data)
    assert response.status_code == 200
```

## Future Enhancements

### If Async Testing Becomes Necessary

Should we need to test async code paths directly in the future:

1. **Hybrid approach:** Keep most tests synchronous, add async for specific cases
2. **Follow PDF guide patterns:**
   - Use `NullPool` for async engines
   - Use `join_transaction_mode="create_savepoint"` for isolation
   - Avoid pytest-xdist with session-scoped async fixtures
   - Let pytest-asyncio manage event loops

3. **Document rationale:** Clear documentation on when to use each approach

### Potential Scenarios

- Testing custom async context managers
- Testing async generators
- Testing async middleware with specific timing requirements
- Integration with async third-party libraries requiring async test patterns

**Current stance:** Cross this bridge if/when we reach it. Synchronous testing has served us well.

## References

- [FastAPI Testing Documentation](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI Official Template](https://github.com/fastapi/full-stack-fastapi-template)
- [Testing Strategy](../testing/strategy.md) - Overall testing approach
- [Async Testing Migration](../historical/async-to-sync-testing-migration.md) - Migration history
- [Pytest Documentation](https://docs.pytest.org/)
- [SQLModel Testing Guide](https://sqlmodel.tiangolo.com/tutorial/testing/)

---

## Document Information

**Template:** [architecture-template.md](../../templates/architecture-template.md)
**Created:** 2025-09-20
**Last Updated:** 2025-10-18
