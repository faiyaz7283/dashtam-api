# Testing Best Practices Guide

A comprehensive guide to testing patterns, conventions, and best practices for the Dashtam financial data aggregation platform.

## Overview

This guide teaches you how to write effective tests for Dashtam following established patterns and conventions. You'll learn testing strategies, code organization, fixture usage, mocking approaches, and common pitfalls to avoid.

### What You'll Learn

- How to write unit, integration, and API tests following project conventions
- Fixture and mocking strategies for different testing scenarios
- Coverage guidelines and what to test (and what not to test)
- Common testing pitfalls and how to avoid them
- Test structure and organization patterns
- Best practices for test isolation and determinism

### When to Use This Guide

Use this guide when:

- Writing new tests for features or bug fixes
- Refactoring existing tests to follow project conventions
- Reviewing test code during pull requests
- Troubleshooting flaky or failing tests
- Learning Dashtam's testing approach as a new contributor

## Prerequisites

Before using this guide, ensure you have:

- [ ] Development environment set up (`make dev-up` working)
- [ ] Test environment configured (`make test-up` working)
- [ ] Basic understanding of pytest and FastAPI testing
- [ ] Familiarity with async/await patterns in Python

**Required Knowledge:**

- Python 3.13+ features (especially timezone-aware datetimes)
- pytest fundamentals (fixtures, parametrize, markers)
- FastAPI TestClient usage
- SQLModel/SQLAlchemy basics
- Docker and docker-compose

**Required Tools:**

- Docker Desktop
- UV package manager (0.8.22+)
- pytest (installed via UV)

**Related Documentation:**

- [Testing Strategy](../../testing/strategy.md) - Overall testing philosophy
- [Testing Guide](../guides/testing-guide.md) - How to run and organize tests

## Step-by-Step Instructions

### Step 1: Understanding Testing Patterns

Dashtam uses three types of tests, each with a specific purpose:

- **Unit Tests (70%):** Fast, isolated tests for individual functions/classes
- **Integration Tests (20%):** Tests for component interactions (database, services)
- **API Tests (10%):** Tests for complete workflows through HTTP endpoints

### Step 2: Writing Unit Tests

**Purpose:** Test individual functions/methods in isolation without external dependencies.

**Characteristics:**

- Fast execution (< 100ms per test)
- No database connection
- Mock all external dependencies
- Test single units of code
- Focus on business logic

**Pattern Example:**

```python
# tests/unit/services/test_encryption_service.py
from src.services.encryption import EncryptionService

class TestEncryptionService:
    """Test suite for EncryptionService."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypted data can be decrypted back to original."""
        service = EncryptionService()
        plaintext = "sensitive_data"

        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        assert decrypted == plaintext
        assert encrypted != plaintext  # Ensure it was actually encrypted
```

**Best Practices:**

- ✅ Mock external dependencies (database, APIs, file system)
- ✅ Test edge cases (empty strings, None, special characters)
- ✅ Test error conditions (exceptions, validation failures)
- ✅ Use parametrized tests for multiple similar cases
- ❌ Don't test framework code or third-party libraries

### Step 3: Writing Integration Tests

**Purpose:** Test component interactions (database operations, service layer working together).

**Characteristics:**

- Use real PostgreSQL database (test environment)
- Transaction rollback for isolation
- Test CRUD operations and relationships
- Execution time < 500ms per test
- Test service layer with database

**Pattern Example:**

```python
# tests/integration/services/test_token_service.py
from sqlmodel import Session
from src.services.token_service import TokenService
from src.models import Provider, ProviderConnection

class TestTokenStorageIntegration:
    """Integration tests for token storage with database."""

    def test_store_and_retrieve_token(self, db_session: Session, test_user):
        """Test complete token storage workflow."""
        # Create provider and connection
        provider = Provider(
            user_id=test_user.id,
            provider_key="schwab",
            alias="Test"
        )
        db_session.add(provider)
        db_session.flush()

        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.commit()

        # Store token using service
        service = TokenService(db_session)
        token = service.store_token(
            connection_id=connection.id,
            access_token="test_token",
            expires_in=3600
        )

        # Verify retrieval
        assert token.id is not None
        assert token.connection_id == connection.id
```

**Best Practices:**

- ✅ Use real database (test database, not mocks)
- ✅ Clean up after each test (transactions/fixtures)
- ✅ Test relationships and cascades
- ✅ Test transaction rollback scenarios
- ❌ Don't mock the database itself

### Step 4: Writing API Tests

**Purpose:** Test HTTP endpoints end-to-end through the complete request/response cycle.

**Characteristics:**

- Use FastAPI's TestClient (synchronous)
- Test complete user flows
- Test authentication and authorization
- Test error handling and validation
- Execution time < 1s per test

**Pattern Example:**

```python
# tests/api/test_provider_endpoints.py
from fastapi.testclient import TestClient
from fastapi import status

class TestProviderEndpoints:
    """Test suite for provider API endpoints."""

    def test_create_provider(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str]
    ):
        """Test creating a new provider instance."""
        payload = {
            "provider_key": "schwab",
            "alias": "My Schwab Account"
        }

        response = client.post(
            "/api/v1/providers/",
            headers=superuser_token_headers,
            json=payload
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["provider_key"] == "schwab"
        assert data["alias"] == "My Schwab Account"
        assert "id" in data
```

**Best Practices:**

- ✅ Use FastAPI TestClient (synchronous, not AsyncClient)
- ✅ Test all HTTP methods (GET, POST, PATCH, DELETE)
- ✅ Test validation (missing fields, invalid data)
- ✅ Test authentication/authorization flows
- ✅ Test error responses (404, 403, 500)

### Step 5: Using Fixtures and Mocks

#### Common Fixtures

Dashtam uses pytest fixtures for test data setup. All shared fixtures are in `tests/conftest.py`.

#### Database Session Fixture

```python
@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a test database session with automatic cleanup."""
    session = Session(engine)
    yield session
    session.rollback()
    session.close()
```

#### Test User Fixture

```python
@pytest.fixture
def test_user(db_session: Session):
    """Create a test user for testing."""
    user = User(
        email="test@example.com",
        name="Test User",
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
```

#### Test Client Fixture

```python
@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a test client for API testing."""
    with TestClient(app) as c:
        yield c
```

#### Mocking Strategies

**When to Mock vs Use Real Objects:**

**Mock when:**

- External API calls (OAuth providers, third-party services)
- Time-dependent operations (`datetime.now()`)
- File system operations
- Network operations
- Slow operations (sleep, heavy computation)

**Use real objects when:**

- Database operations (use test database)
- Internal service calls
- Model creation and validation
- Encryption/decryption operations

**Mocking External APIs:**

```python
from unittest.mock import patch, AsyncMock

def test_oauth_callback(client: TestClient, test_provider):
    """Test OAuth callback with mocked provider response."""
    with patch("src.providers.registry.ProviderRegistry.get_provider") as mock:
        # Mock provider instance
        mock_provider = AsyncMock()
        mock_provider.authenticate.return_value = {
            "access_token": "test_token",
            "expires_in": 3600
        }
        mock.return_value = mock_provider

        response = client.get(
            f"/api/v1/providers/{test_provider.id}/callback",
            params={"code": "test_code"}
        )

        assert response.status_code == 200
        mock_provider.authenticate.assert_called_once()
```

**Mocking Services:**

```python
def test_token_refresh_failure(client: TestClient, test_provider):
    """Test handling of token refresh failure."""
    with patch("src.services.token_service.TokenService.refresh_token") as mock:
        mock.side_effect = Exception("Refresh failed")

        response = client.post(
            f"/api/v1/providers/{test_provider.id}/refresh"
        )

        assert response.status_code == 500
        assert "Failed to refresh tokens" in response.json()["detail"]
```

### Step 6: Meeting Coverage Guidelines

#### Target Coverage

**By Module Type:**

- Core utilities (database, config): **95-100%**
- Services (business logic): **85-95%**
- API endpoints: **80-90%**
- Models: **80-90%**
- Providers (OAuth implementations): **70-85%**

**Current Project Coverage:** 76% (target: 85%)

#### What to Test

**✅ Always test:**

- Happy path (normal usage scenarios)
- Error cases (exceptions, validation failures)
- Edge cases (empty values, None, extreme values)
- Boundary conditions (min/max values, limits)
- Critical user flows (authentication, data operations)

**⚠️ Sometimes test:**

- Private methods (if they contain complex logic)
- Properties (if they have logic beyond simple getters/setters)
- Utility functions (if widely used)

**❌ Don't test:**

- Third-party library code (trust the library's tests)
- Simple getters/setters without logic
- Framework code (FastAPI, SQLModel internals)
- Auto-generated code

## Examples

### Example 1: Complete Unit Test

```python
# tests/unit/services/test_encryption_service.py
from src.services.encryption import EncryptionService
import pytest

class TestEncryptionService:
    """Complete unit test example."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test encryption and decryption work correctly."""
        # Arrange
        service = EncryptionService()
        plaintext = "sensitive_data"

        # Act
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)

        # Assert
        assert decrypted == plaintext
        assert encrypted != plaintext
        assert encrypted.startswith("gAAAAA")  # Fernet format
```

### Example 2: Integration Test with Database

```python
# tests/integration/test_provider_operations.py
from sqlmodel import Session
from src.models import Provider, User

def test_create_provider_with_user(db_session: Session):
    """Complete integration test with database."""
    # Arrange
    user = User(email="test@example.com", name="Test User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Act
    provider = Provider(
        user_id=user.id,
        provider_key="schwab",
        alias="My Account"
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)

    # Assert
    assert provider.id is not None
    assert provider.user_id == user.id

    # Verify relationship
    assert provider.user.email == "test@example.com"
```

### Example 3: API Test with Authentication

```python
# tests/api/test_provider_endpoints.py
from fastapi.testclient import TestClient

def test_create_provider_authenticated(
    client: TestClient,
    superuser_token_headers: dict[str, str]
):
    """Complete API test with authentication."""
    # Arrange
    payload = {
        "provider_key": "schwab",
        "alias": "My Schwab Account"
    }

    # Act
    response = client.post(
        "/api/v1/providers/",
        headers=superuser_token_headers,
        json=payload
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["provider_key"] == "schwab"
    assert "id" in data
    assert "created_at" in data
```

## Verification

### Running Tests

**Run all tests:**

```bash
make test
```

**Run specific test categories:**

```bash
make test-unit         # Unit tests only
make test-integration  # Integration tests only
make test-smoke        # Smoke tests (critical paths)
```

**Run specific test file:**

```bash
pytest tests/unit/services/test_encryption_service.py -v
```

**Run specific test function:**

```bash
pytest tests/unit/services/test_encryption_service.py::test_encrypt_decrypt_cycle -xvs
```

**Run with coverage:**

```bash
make test  # Automatically includes coverage report
```

### Verifying Test Quality

**Check coverage:**

```bash
make test-coverage
open htmlcov/index.html  # View coverage report
```

**Expected results:**

- All tests pass (green checkmarks)
- Coverage meets target thresholds
- No flaky test failures
- Fast execution (< 30s for full suite)

## Troubleshooting

### Issue 1: Async/Sync Mismatch

**Problem:** Calling async functions without await

❌ **Wrong:**

```python
def test_async_function():
    result = some_async_function()  # Returns coroutine, not result
```

✅ **Correct:**

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
```

Or use `AsyncMock` for mocking:

```python
from unittest.mock import AsyncMock

mock_func = AsyncMock(return_value="result")
result = await mock_func()
```

### Issue 2: Database Session Issues

**Problem:** Data not committed/visible in tests

❌ **Wrong:**

```python
def test_with_session(db_session):
    user = User(email="test@test.com")
    db_session.add(user)
    # Not committed, might not be available in other queries
```

✅ **Correct:**

```python
def test_with_session(db_session):
    user = User(email="test@test.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)  # Reload from DB to get generated fields
```

### Issue 3: Test Isolation Problems

**Problem:** Tests affecting each other due to shared state

❌ **Wrong:**

```python
shared_user = None  # Module-level state

def test_create_user(db_session):
    global shared_user
    shared_user = User(email="test@test.com")
    # Test 2 might fail if test 1 runs first
```

✅ **Correct:**

```python
def test_create_user(db_session):
    user = User(email="test@test.com")  # Fresh instance per test
    # Each test is independent
```

### Issue 4: Over-Mocking

**Problem:** Mocking so much that tests don't verify anything meaningful

❌ **Wrong:**

```python
def test_token_storage(db_session):
    with patch("sqlmodel.Session.add"):  # Mocking the database!
        with patch("sqlmodel.Session.commit"):
            # This doesn't test anything meaningful
```

✅ **Correct:**

```python
def test_token_storage(db_session):
    # Use real database session
    token = ProviderToken(connection_id=1, access_token="test")
    db_session.add(token)
    db_session.commit()
    # Actually verify it was stored
    assert db_session.get(ProviderToken, token.id) is not None
```

### Issue 5: Timezone-Aware Datetimes

**Problem:** Using deprecated timezone-naive datetime methods

❌ **Wrong:**

```python
from datetime import datetime

expires_at = datetime.utcnow()  # Deprecated in Python 3.13
```

✅ **Correct:**

```python
from datetime import datetime, timezone

expires_at = datetime.now(timezone.utc)  # Timezone-aware
```

## Best Practices

### Testing Philosophy

**Test Pyramid Distribution:**

- 70% Unit Tests - Fast, isolated tests for individual functions/classes
- 20% Integration Tests - Tests for component interactions (database, services)
- 10% API/E2E Tests - Tests for complete workflows through HTTP endpoints
- Smoke Tests - Critical path validation (subset of API tests, run pre-deployment)

**Core Testing Principles:**

- ✅ **Fast:** Most tests should run in milliseconds
- ✅ **Isolated:** Each test should be independent
- ✅ **Deterministic:** Same input = same output, always
- ✅ **Readable:** Clear arrange-act-assert structure
- ✅ **Focused:** Test one thing per test function

### Test Structure Standards

**Directory Organization:**

```text
tests/
├── api/                    # API endpoint tests (TestClient)
├── integration/            # Integration tests (database, services)
├── unit/                   # Unit tests (isolated logic)
├── smoke/                  # Smoke tests (critical paths)
└── conftest.py            # Shared fixtures
```

**Test File Naming:**

- Test files: `test_<module_name>.py`
- Test classes: `Test<FeatureName>` (PascalCase)
- Test functions: `test_<what_it_tests>` (snake_case)

**Test Function Structure (AAA Pattern):**

```python
def test_feature_name():
    """Test description explaining what we're testing."""
    # Arrange: Set up test data and conditions
    user = User(email="test@example.com")

    # Act: Execute the code being tested
    result = some_function(user)

    # Assert: Verify the results
    assert result == expected_value
```

### Common Mistakes to Avoid

- ❌ **Testing implementation details** - Test behavior, not internals
- ❌ **Flaky tests** - Avoid non-determinism (random data, time dependencies)
- ❌ **Slow tests** - Keep unit tests under 100ms
- ❌ **Large test data** - Use minimal data needed to verify behavior
- ❌ **Shared mutable state** - Isolate test data per test
- ❌ **Over-mocking** - Use real objects for internal components
- ❌ **Ignoring CI failures** - Fix broken tests immediately

## Next Steps

After mastering these best practices, consider:

- [ ] Review [Testing Strategy](../../testing/strategy.md) for overall philosophy
- [ ] Read [Testing Guide](../guides/testing-guide.md) for running tests
- [ ] Study [Test Docstring Standards](test-docstring-standards.md)
- [ ] Explore [Smoke Test Design](../../research/smoke-test-design-comparison.md)
- [ ] Contribute to test coverage (target: 85%+)

## References

**Project Documentation:**

- [Testing Strategy](../../testing/strategy.md) - Overall testing philosophy
- [Testing Guide](../guides/testing-guide.md) - Running and organizing tests
- [Test Docstring Standards](test-docstring-standards.md) - Documenting tests

**External Resources:**

- [pytest Documentation](https://docs.pytest.org/) - Core testing framework
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/) - FastAPI TestClient guide
- [SQLModel Testing](https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/) - Database testing patterns
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html) - Python mocking library

---

## Document Information

**Template:** [guide-template.md](../../templates/guide-template.md)
**Created:** 2025-09-20
**Last Updated:** 2025-10-18
