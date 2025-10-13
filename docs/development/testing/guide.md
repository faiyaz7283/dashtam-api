# Dashtam Testing Guide

Quick reference for writing tests following the synchronous testing pattern.

---

## Quick Start

```bash
# Start test environment
make test-up

# Run all tests
make test

# Run specific test category
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-smoke         # Smoke tests (end-to-end auth flows)

# Run specific test file
docker compose -f docker-compose.test.yml exec app uv run pytest tests/unit/services/test_encryption_service.py -v

# Run tests with coverage
docker compose -f docker-compose.test.yml exec app uv run pytest tests/ --cov=src --cov-report=term-missing
```

---

## Test Categories

### Unit Tests (`tests/unit/`)

- **Purpose:** Test business logic in isolation
- **Dependencies:** None (or mocked)
- **Speed:** Very fast (< 0.01s per test)
- **Database:** No database access

**Example:**

```python
def test_encrypt_decrypt_string():
    """Test basic encryption/decryption."""
    service = EncryptionService()
    plaintext = "my_secret_token"
    
    encrypted = service.encrypt(plaintext)
    assert encrypted != plaintext
    
    decrypted = service.decrypt(encrypted)
    assert decrypted == plaintext
```

### Integration Tests (`tests/integration/`)

- **Purpose:** Test database operations and relationships
- **Dependencies:** Real PostgreSQL database
- **Speed:** Fast (< 0.1s per test)
- **Database:** Uses test database with cleanup

**Example:**

```python
def test_create_provider(db_session: Session, test_user: User):
    """Test creating a provider instance."""
    provider = Provider(
        user_id=test_user.id,
        provider_key="schwab",
        alias="My Account"
    )
    db_session.add(provider)
    db_session.commit()
    db_session.refresh(provider)
    
    assert provider.id is not None
    assert provider.user_id == test_user.id
```

### API Tests (`tests/api/`)

- **Purpose:** Test HTTP endpoints end-to-end
- **Dependencies:** Full application stack
- **Speed:** Medium (< 0.2s per test)
- **Database:** Uses test database via TestClient

**Example:**

```python
def test_create_provider_instance(client: TestClient, test_user: User):
    """Test POST /api/v1/providers/create endpoint."""
    payload = {
        "provider_key": "schwab",
        "alias": "My Schwab Account"
    }
    
    response = client.post("/api/v1/providers/create", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["provider_key"] == "schwab"
    assert data["alias"] == "My Schwab Account"
```

### Smoke Tests (`tests/smoke/`)

- **Purpose:** Validate critical user journeys are operational
- **Dependencies:** Full application stack
- **Speed:** Medium (complete auth flow < 5s)
- **Database:** Uses test database via TestClient
- **When to run:** Before deployment, after major changes

**Example:**

```python
def test_complete_registration_flow(client: TestClient, caplog):
    """Smoke: User can register, verify email, and login."""
    # Register
    with caplog.at_level(logging.INFO):
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "full_name": "Test User"
        })
    assert response.status_code == 201
    
    # Extract verification token from logs
    token = extract_token_from_caplog(caplog, "verify-email?token=")
    
    # Verify email
    response = client.post(f"/api/v1/auth/verify-email/{token}")
    assert response.status_code == 200
    
    # Login
    response = client.post("/api/v1/auth/login", json={
        "username": "test@example.com",
        "password": "SecurePass123!"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```

**Note:** See `tests/smoke/README.md` for complete documentation on smoke tests.

---

## Available Fixtures

### Database Fixtures

```python
db_session: Session
    # Function-scoped database session
    # Automatically cleans up after each test
    # Use for integration tests

test_user: User
    # Pre-created test user
    # email: test@example.com
    # Cleaned up automatically

test_user_2: User
    # Second test user for multi-user scenarios
    # email: test2@example.com

test_provider: Provider
    # Pre-created provider for test_user
    # provider_key: schwab
    # alias: Test Schwab Account

test_provider_with_connection: Provider
    # Provider with active connection
    # Includes ProviderConnection with ACTIVE status
```

### API Testing Fixtures

```python
client: TestClient
    # FastAPI TestClient for making HTTP requests
    # Module-scoped for efficiency
    # Automatically handles app lifecycle

superuser_token_headers: dict[str, str]
    # Mock authentication headers for superuser
    # Returns: {"Authorization": "Bearer mock_superuser_token"}

normal_user_token_headers: dict[str, str]
    # Mock authentication headers for normal user
    # Returns: {"Authorization": "Bearer mock_user_token"}
```

---

## Test Template: Unit Test

```python
"""Unit tests for [module_name].

Description of what is being tested.
"""

import pytest

from src.[module_path] import [ClassOrFunction]


class Test[ClassName]:
    """Test suite for [ClassName]."""

    def test_basic_functionality(self):
        """Test basic functionality."""
        # Arrange
        instance = [ClassOrFunction]()
        
        # Act
        result = instance.some_method()
        
        # Assert
        assert result == expected_value

    def test_edge_case(self):
        """Test edge case handling."""
        instance = [ClassOrFunction]()
        
        with pytest.raises(ValueError, match="error message"):
            instance.some_method(invalid_input)
```

---

## Test Template: Integration Test

```python
"""Integration tests for [feature_name].

Tests database operations and relationships.
"""

import pytest
from sqlmodel import Session, select

from src.models.[model] import [Model]
from src.models.user import User


class Test[FeatureName]:
    """Test suite for [feature_name] database operations."""

    def test_create_and_read(self, db_session: Session, test_user: User):
        """Test creating and reading a record."""
        # Create
        record = [Model](
            user_id=test_user.id,
            field1="value1",
            field2="value2"
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)
        
        # Read
        result = db_session.execute(
            select([Model]).where([Model].id == record.id)
        )
        fetched = result.scalar_one()
        
        # Assert
        assert fetched.field1 == "value1"
        assert fetched.field2 == "value2"

    def test_relationship(self, db_session: Session, test_user: User):
        """Test relationship loading."""
        from sqlalchemy.orm import selectinload
        
        result = db_session.execute(
            select([Model])
            .options(selectinload([Model].related))
            .where([Model].user_id == test_user.id)
        )
        record = result.scalar_one()
        
        assert record.related is not None
```

---

## Test Template: API Test

```python
"""API tests for [endpoint_group].

Tests HTTP endpoints using TestClient.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.user import User


class Test[EndpointGroup]:
    """Test suite for [endpoint_group] endpoints."""

    def test_create_endpoint(self, client: TestClient, test_user: User):
        """Test POST /api/v1/[resource] endpoint."""
        payload = {
            "field1": "value1",
            "field2": "value2"
        }
        
        response = client.post("/api/v1/[resource]", json=payload)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert data["field1"] == "value1"

    def test_get_endpoint(self, client: TestClient, test_user: User, db_session):
        """Test GET /api/v1/[resource]/{id} endpoint."""
        # Setup: Create test data
        from src.models.[model] import [Model]
        record = [Model](user_id=test_user.id, field1="value1")
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)
        
        # Test
        response = client.get(f"/api/v1/[resource]/{record.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(record.id)

    def test_validation_error(self, client: TestClient):
        """Test validation error handling."""
        # Missing required field
        payload = {"field1": "value1"}
        
        response = client.post("/api/v1/[resource]", json=payload)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_not_found(self, client: TestClient):
        """Test 404 error handling."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        
        response = client.get(f"/api/v1/[resource]/{fake_id}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
```

---

## Best Practices

### 1. Test Naming

```python
# ✅ Good - Descriptive, action-oriented
def test_create_provider_with_valid_data():
def test_encryption_handles_unicode_characters():
def test_api_returns_404_for_missing_resource():

# ❌ Bad - Vague, unclear purpose
def test_provider():
def test_encryption():
def test_api():
```

### 2. Test Structure (AAA Pattern)

```python
def test_example():
    # Arrange - Set up test data
    user = User(email="test@example.com")
    
    # Act - Execute the code being tested
    result = user.get_display_name()
    
    # Assert - Verify the results
    assert result == "test@example.com"
```

### 3. Test Isolation

```python
# ✅ Good - Each test is independent
def test_create_provider(db_session, test_user):
    provider = Provider(user_id=test_user.id, ...)
    db_session.add(provider)
    db_session.commit()
    # Test uses only its own data

# ❌ Bad - Test depends on previous test
providers = []  # Module-level shared state
def test_create_provider():
    provider = Provider(...)
    providers.append(provider)  # Don't do this!
```

### 4. Assertions

```python
# ✅ Good - Clear, specific assertions
assert provider.id is not None
assert provider.user_id == test_user.id
assert provider.status == ProviderStatus.ACTIVE

# ❌ Bad - Vague or missing assertions
assert provider  # What are we checking?
# No assertions at all
```

### 5. Error Testing

```python
# ✅ Good - Test specific error conditions
def test_invalid_provider_key_raises_error():
    with pytest.raises(ValueError, match="Invalid provider key"):
        provider = Provider(provider_key="invalid", ...)

# ✅ Good - Test API error responses
def test_create_provider_with_invalid_key(client):
    response = client.post("/api/v1/providers/create", 
                          json={"provider_key": "invalid"})
    assert response.status_code == 400
    assert "error" in response.json()
```

---

## Common Patterns

### Testing with Database Relationships

```python
def test_provider_with_connection(db_session, test_user):
    # Create parent
    provider = Provider(user_id=test_user.id, ...)
    db_session.add(provider)
    db_session.flush()  # Get provider.id without committing
    
    # Create child
    connection = ProviderConnection(provider_id=provider.id)
    db_session.add(connection)
    db_session.commit()
    db_session.refresh(provider)
    
    # Test relationship
    assert provider.connection is not None
    assert provider.connection.provider_id == provider.id
```

### Testing API with Authentication

```python
def test_protected_endpoint(client, normal_user_token_headers):
    headers = normal_user_token_headers
    
    response = client.get("/api/v1/protected", headers=headers)
    
    assert response.status_code == 200
```

### Testing Pagination

```python
def test_list_with_pagination(client, db_session, test_user):
    # Create test data
    for i in range(25):
        provider = Provider(user_id=test_user.id, alias=f"Provider {i}")
        db_session.add(provider)
    db_session.commit()
    
    # Test pagination
    response = client.get("/api/v1/providers?page=1&size=10")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total"] == 25
```

### Testing Error Scenarios

```python
def test_concurrent_updates_handled_correctly(db_session, test_user):
    # Create initial record
    provider = Provider(user_id=test_user.id, alias="Original")
    db_session.add(provider)
    db_session.commit()
    
    # Simulate concurrent update
    # Session 1 gets the record
    provider1 = db_session.get(Provider, provider.id)
    
    # Session 2 updates it (in real world, different session)
    provider.alias = "Updated by Session 2"
    db_session.commit()
    
    # Session 1 tries to update
    provider1.alias = "Updated by Session 1"
    db_session.commit()
    
    # Verify final state
    db_session.refresh(provider)
    assert provider.alias == "Updated by Session 1"
```

---

## Debugging Tests

### Run Single Test

```bash
pytest tests/unit/services/test_encryption_service.py::TestEncryptionService::test_encrypt_decrypt_string -v
```

### Run with Print Statements

```bash
pytest tests/unit/services/test_encryption_service.py -v -s
```

### Run with Debugger

```python
def test_example():
    import pdb; pdb.set_trace()  # Breakpoint
    result = some_function()
    assert result == expected
```

### View Full Traceback

```bash
pytest tests/unit/services/test_encryption_service.py -v --tb=long
```

### Run Failed Tests Only

```bash
pytest --lf  # Last failed
pytest --ff  # Failed first
```

---

## Useful Test Utilities

### Available in `tests/utils/utils.py`

```python
from tests.utils.utils import (
    random_lower_string,
    random_email,
    random_provider_key,
    get_superuser_token_headers,
    get_normal_user_token_headers,
)

# Generate random test data
email = random_email()  # "abc123@example.com"
name = random_lower_string(10)  # "xjfkwpqmnt"
key = random_provider_key()  # "provider_xyz"

# Get auth headers (for API tests)
headers = get_superuser_token_headers(client)
```

---

## Test Markers

Mark tests for selective execution:

```python
@pytest.mark.unit
def test_business_logic():
    """Unit test - fast, no dependencies."""
    pass

@pytest.mark.integration  
def test_database_operation():
    """Integration test - uses database."""
    pass

@pytest.mark.api
def test_endpoint():
    """API test - full HTTP cycle."""
    pass

@pytest.mark.slow
def test_performance():
    """Slow test - only run when needed."""
    pass
```

Run by marker:

```bash
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only
pytest -m "not slow"     # Skip slow tests
```

---

## Coverage

### Generate Coverage Report

```bash
# Terminal report
pytest tests/ --cov=src --cov-report=term-missing

# HTML report
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

### Target Coverage

- **Overall:** 85%+
- **Critical modules** (encryption, auth): 95%+
- **API endpoints:** 90%+
- **Models:** 80%+

---

## CI/CD Integration

Tests run automatically in CI/CD:

```yaml
# .github/workflows/test.yml
- name: Run tests
  run: |
    make test-up
    make test
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

---

## Getting Help

1. **Check existing tests:** Look at `tests/unit/services/test_encryption_service.py`, `tests/integration/test_provider_operations.py`, or `tests/api/test_provider_endpoints.py` for examples

2. **Read documentation:**
   - `TESTING_STRATEGY.md` - Testing approach
   - `TESTING_MIGRATION_SUMMARY.md` - Migration details

3. **FastAPI testing docs:** https://fastapi.tiangolo.com/tutorial/testing/

4. **pytest docs:** https://docs.pytest.org/

---

## Summary

✅ **Write synchronous tests** using `def test_*()` (not `async def`)  
✅ **Use appropriate fixtures** (`db_session`, `client`, `test_user`)  
✅ **Follow AAA pattern** (Arrange, Act, Assert)  
✅ **Test one thing** per test function  
✅ **Use descriptive names** that explain what is being tested  
✅ **Clean up automatically** via fixtures (no manual cleanup needed)  
✅ **Run tests often** during development

Happy testing! 🧪
