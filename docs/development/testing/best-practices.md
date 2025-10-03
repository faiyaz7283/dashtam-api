# Testing Best Practices for Dashtam

This guide documents testing patterns, strategies, and best practices for the Dashtam project.

## Table of Contents
- [Testing Philosophy](#testing-philosophy)
- [Test Structure](#test-structure)
- [Testing Patterns](#testing-patterns)
- [Fixtures and Mocks](#fixtures-and-mocks)
- [Coverage Guidelines](#coverage-guidelines)
- [Common Pitfalls](#common-pitfalls)

---

## Testing Philosophy

### Test Pyramid
Dashtam follows the testing pyramid approach:
- **70% Unit Tests**: Fast, isolated tests for individual functions/classes
- **20% Integration Tests**: Tests for component interactions (database, services)
- **10% API/E2E Tests**: Tests for complete workflows through HTTP endpoints

### Testing Principles
1. **Tests should be fast**: Most tests should run in milliseconds
2. **Tests should be isolated**: Each test should be independent
3. **Tests should be deterministic**: Same input = same output, always
4. **Tests should be readable**: Clear arrange-act-assert structure
5. **Tests should test one thing**: Single responsibility per test

---

## Test Structure

### Directory Organization
```
tests/
├── api/                    # API endpoint tests (TestClient)
│   ├── test_provider_endpoints.py
│   └── test_auth_endpoints.py
├── integration/            # Integration tests (database, services)
│   ├── services/
│   │   └── test_token_service.py
│   └── test_provider_operations.py
├── unit/                   # Unit tests (isolated logic)
│   ├── core/
│   │   └── test_database.py
│   └── services/
│       ├── test_encryption_service.py
│       └── test_token_service.py
├── conftest.py            # Shared fixtures
└── test_config.py         # Configuration tests
```

### Test File Naming
- Test files: `test_<module_name>.py`
- Test classes: `Test<FeatureName>` (PascalCase)
- Test functions: `test_<what_it_tests>` (snake_case)

### Test Function Structure (AAA Pattern)
```python
def test_feature_name():
    """Test description explaining what we're testing."""
    # Arrange: Set up test data and conditions
    user = User(email="test@example.com", name="Test User")
    
    # Act: Execute the code being tested
    result = some_function(user)
    
    # Assert: Verify the results
    assert result == expected_value
```

---

## Testing Patterns

### 1. Unit Tests

**Purpose**: Test individual functions/methods in isolation

**Pattern**:
```python
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

**Best Practices**:
- Mock external dependencies
- Test edge cases (empty strings, None, special characters)
- Test error conditions (exceptions, validation failures)
- Use parameterized tests for multiple similar cases

### 2. Integration Tests

**Purpose**: Test component interactions (database, services working together)

**Pattern**:
```python
class TestTokenStorageIntegration:
    """Integration tests for token storage with database."""
    
    def test_store_and_retrieve_token(self, db_session, test_user):
        """Test complete token storage workflow."""
        # Create provider and connection
        provider = Provider(user_id=test_user.id, provider_key="schwab", alias="Test")
        db_session.add(provider)
        db_session.flush()
        
        connection = ProviderConnection(provider_id=provider.id)
        db_session.add(connection)
        db_session.commit()
        
        # Store token
        encryption = EncryptionService()
        token = ProviderToken(
            connection_id=connection.id,
            access_token_encrypted=encryption.encrypt("test_token")
        )
        db_session.add(token)
        db_session.commit()
        
        # Verify retrieval
        db_session.refresh(token)
        assert token.access_token_encrypted is not None
```

**Best Practices**:
- Use real database (test database, not mocks)
- Clean up after each test (transactions/fixtures)
- Test relationships and cascades
- Test transaction rollback scenarios

### 3. API Tests

**Purpose**: Test HTTP endpoints end-to-end

**Pattern**:
```python
class TestProviderEndpoints:
    """Test suite for provider API endpoints."""
    
    def test_create_provider(self, client: TestClient):
        """Test creating a new provider instance."""
        payload = {
            "provider_key": "schwab",
            "alias": "My Schwab Account"
        }
        
        response = client.post("/api/v1/providers/create", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["provider_key"] == "schwab"
        assert data["alias"] == "My Schwab Account"
        assert "id" in data
```

**Best Practices**:
- Use FastAPI TestClient (synchronous)
- Test all HTTP methods (GET, POST, PUT, DELETE)
- Test validation (missing fields, invalid data)
- Test authentication/authorization
- Test error responses (404, 403, 500)

---

## Fixtures and Mocks

### Common Fixtures (in conftest.py)

#### Database Session Fixture
```python
@pytest.fixture
def db_session():
    """Provide a test database session with automatic cleanup."""
    # Create session
    session = Session(engine)
    
    yield session
    
    # Cleanup
    session.rollback()
    session.close()
```

#### Test User Fixture
```python
@pytest.fixture
def test_user(db_session):
    """Create a test user for testing."""
    user = User(email="test@example.com", name="Test User", is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
```

#### Test Client Fixture
```python
@pytest.fixture
def client():
    """Provide a test client for API testing."""
    return TestClient(app)
```

### Mocking Strategies

#### 1. Mocking External APIs
```python
def test_oauth_callback(self, client, test_provider):
    """Test OAuth callback with mocked provider response."""
    with patch("src.api.v1.auth.ProviderRegistry.create_provider_instance") as mock_registry:
        # Mock provider instance
        mock_provider = AsyncMock()
        mock_provider.authenticate = AsyncMock(return_value={
            "access_token": "test_token",
            "expires_in": 3600
        })
        mock_registry.return_value = mock_provider
        
        response = client.get(
            f"/api/v1/auth/{test_provider.id}/callback",
            params={"code": "test_code"}
        )
        
        assert response.status_code == 200
        mock_provider.authenticate.assert_called_once()
```

#### 2. Mocking Services
```python
def test_token_refresh_failure(self, client, test_provider):
    """Test handling of token refresh failure."""
    with patch("src.services.token_service.TokenService.refresh_token") as mock_refresh:
        mock_refresh.side_effect = Exception("Refresh failed")
        
        response = client.post(f"/api/v1/auth/{test_provider.id}/refresh")
        
        assert response.status_code == 500
        assert "Failed to refresh tokens" in response.json()["detail"]
```

#### 3. When to Mock vs Use Real Objects

**Mock when**:
- External API calls (OAuth providers, third-party services)
- Time-dependent operations (`datetime.now()`)
- File system operations
- Network operations
- Slow operations (sleep, heavy computation)

**Use real objects when**:
- Database operations (use test database)
- Internal service calls
- Model creation and validation
- Encryption/decryption operations

---

## Coverage Guidelines

### Target Coverage by Module Type
- **Core utilities** (database, config): **95-100%**
- **Services** (business logic): **85-95%**
- **API endpoints**: **80-90%**
- **Models**: **80-90%**
- **Providers** (OAuth implementations): **70-85%**

### Current Coverage Status
```
✅ src/core/database.py: 100%
✅ src/services/encryption.py: 84%
✅ src/services/token_service.py: 86%
✅ src/api/v1/auth.py: 82%
✅ src/api/v1/providers.py: 90%
⚠️ src/providers/schwab.py: 30% (needs improvement)
```

### What to Test

**✅ Always test**:
- Happy path (normal usage)
- Error cases (exceptions, validation failures)
- Edge cases (empty, None, extreme values)
- Boundary conditions (min/max values)

**⚠️ Sometimes test**:
- Private methods (if complex logic)
- Properties (if they have logic)
- Utility functions

**❌ Don't test**:
- Third-party library code
- Simple getters/setters without logic
- Framework code (FastAPI, SQLModel)

---

## Common Pitfalls

### 1. Async/Sync Mismatch
❌ **Wrong**:
```python
def test_async_function():
    result = some_async_function()  # Returns coroutine, not result
```

✅ **Correct**:
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
```

Or use `AsyncMock` for mocking:
```python
mock_func = AsyncMock(return_value="result")
result = await mock_func()
```

### 2. Database Session Issues
❌ **Wrong**:
```python
def test_with_session(db_session):
    user = User(email="test@test.com")
    db_session.add(user)
    # Not committed, might not be available in other queries
```

✅ **Correct**:
```python
def test_with_session(db_session):
    user = User(email="test@test.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)  # Reload from DB
```

### 3. Test Isolation
❌ **Wrong**:
```python
shared_user = None  # Module-level state

def test_create_user(db_session):
    global shared_user
    shared_user = User(email="test@test.com")
    # Test 2 might fail if test 1 runs first
```

✅ **Correct**:
```python
def test_create_user(db_session):
    user = User(email="test@test.com")  # Fresh instance per test
```

### 4. Over-Mocking
❌ **Wrong**:
```python
def test_token_storage(db_session):
    with patch("sqlmodel.Session.add"):  # Mocking the database!
        with patch("sqlmodel.Session.commit"):
            # This doesn't test anything meaningful
```

✅ **Correct**:
```python
def test_token_storage(db_session):
    # Use real database session
    token = ProviderToken(...)
    db_session.add(token)
    db_session.commit()
    # Actually verify it was stored
```

### 5. Timezone-Aware Datetimes
❌ **Wrong**:
```python
expires_at = datetime.utcnow()  # Deprecated in Python 3.13
```

✅ **Correct**:
```python
from datetime import datetime, timezone

expires_at = datetime.now(timezone.utc)  # Timezone-aware
```

---

## Running Tests

### Run All Tests
```bash
make test
```

### Run Specific Test File
```bash
make test-unit ARGS="tests/unit/core/test_database.py"
```

### Run Specific Test
```bash
docker compose -f docker-compose.test.yml exec -T app \
  uv run pytest tests/unit/core/test_database.py::TestGetEngine::test_get_engine_creates_new_engine -xvs
```

### Run Tests with Coverage
```bash
make test  # Automatically includes coverage
```

### Run Tests in Watch Mode (for development)
```bash
docker compose -f docker-compose.test.yml exec app \
  uv run pytest-watch tests/
```

---

## CI/CD Integration

Tests automatically run in GitHub Actions on:
- Every push to feature branches
- Every pull request to `development` or `main`
- Manual workflow trigger

**CI Requirements**:
- ✅ All tests must pass
- ✅ Code quality checks (ruff lint, ruff format)
- ✅ Coverage report uploaded to Codecov

---

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLModel Testing Guide](https://sqlmodel.tiangolo.com/tutorial/fastapi/tests/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)

---

## Contributing

When adding new features:
1. Write tests first (TDD approach recommended)
2. Ensure tests cover happy path and error cases
3. Aim for >85% coverage on new code
4. Run `make test` before committing
5. Verify CI passes before merging PR

---

**Last Updated**: 2025-10-03  
**Test Count**: 110 tests  
**Overall Coverage**: 67%
