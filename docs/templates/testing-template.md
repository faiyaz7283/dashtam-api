# [Testing Topic/Strategy]

[Brief 1-2 sentence description of this testing documentation]

---

## Table of Contents

- [Overview](#overview)
- [Testing Strategy](#testing-strategy)
- [Test Types](#test-types)
- [Setup](#setup)
- [Writing Tests](#writing-tests)
- [Running Tests](#running-tests)
- [Coverage](#coverage)
- [Best Practices](#best-practices)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)
- [References](#references)

---

## Overview

[Describe the testing approach, scope, and goals]

### Testing Goals

- Goal 1: [Description]
- Goal 2: [Description]
- Goal 3: [Description]

### Scope

**Covered:**

- Area 1
- Area 2

**Not Covered:**

- Out-of-scope 1
- Out-of-scope 2

## Testing Strategy

[Describe the overall testing strategy and philosophy]

### Test Pyramid

```text
         /\
        /  \    E2E Tests (10%)
       /    \
      /------\   Integration Tests (30%)
     /        \
    /----------\  Unit Tests (60%)
```

### Testing Principles

- Principle 1: Description
- Principle 2: Description
- Principle 3: Description

## Test Types

### Unit Tests

**Purpose:** [What they test]

**Characteristics:**

- Fast execution
- Isolated from external dependencies
- Test single units of code

**When to Use:**

- Testing individual functions
- Testing class methods
- Testing business logic

### Integration Tests

**Purpose:** [What they test]

**Characteristics:**

- Test component interactions
- May use real database/services
- Slower than unit tests

**When to Use:**

- Testing database operations
- Testing API integrations
- Testing service interactions

### End-to-End Tests

**Purpose:** [What they test]

**Characteristics:**

- Test complete user flows
- Use real or realistic environment
- Slowest but most comprehensive

**When to Use:**

- Testing critical user journeys
- Testing auth flows
- Testing API workflows

## Setup

### Prerequisites

- [ ] Test environment configured
- [ ] Dependencies installed
- [ ] Test database available

### Test Environment Setup

```bash
# Setup command
make test-setup
```

### Test Data

[Document test data requirements and fixtures]

## Writing Tests

### Test Structure

```python
def test_feature_name():
    """Test description following Google style docstrings.
    
    This test verifies [specific behavior].
    """
    # Arrange - Set up test data
    test_data = setup_test_data()
    
    # Act - Execute the code under test
    result = function_under_test(test_data)
    
    # Assert - Verify the results
    assert result == expected_value
```

### Naming Conventions

- Test files: `test_<module>.py`
- Test functions: `test_<feature>_<scenario>()`
- Test classes: `Test<Component>`

**Examples:**

- ✅ `test_user_registration_with_valid_email()`
- ✅ `test_token_refresh_when_expired()`
- ❌ `test1()`, `testUserStuff()`

### Fixtures

```python
import pytest

@pytest.fixture
def sample_fixture():
    """Description of what this fixture provides."""
    # Setup
    data = create_test_data()
    yield data
    # Teardown (if needed)
    cleanup(data)
```

## Running Tests

### Run All Tests

```bash
# Full test suite
make test
```

### Run Specific Tests

```bash
# Single test file
pytest tests/test_module.py

# Single test function
pytest tests/test_module.py::test_specific_function

# Tests matching pattern
pytest -k "test_user"
```

### Run with Coverage

```bash
# With coverage report
make test-coverage
```

### Run in Docker

```bash
# Run tests in container
docker compose -f compose/docker-compose.test.yml exec app pytest
```

## Coverage

### Coverage Goals

- **Overall Target:** 85%
- **Critical Components:** 95%+
- **New Code:** 100%

### Checking Coverage

```bash
# Generate coverage report
pytest --cov=src tests/

# HTML coverage report
pytest --cov=src --cov-report=html tests/
```

### Coverage Exceptions

[Document any code intentionally excluded from coverage and why]

## Best Practices

### General Principles

- ✅ **Write tests first (TDD):** When possible
- ✅ **One assertion per test:** Keep tests focused
- ✅ **Independent tests:** Tests should not depend on each other
- ✅ **Clear test names:** Name describes what is tested
- ✅ **Fast tests:** Optimize for speed

### Testing Anti-Patterns to Avoid

- ❌ **Testing implementation details:** Test behavior, not implementation
- ❌ **Flaky tests:** Tests should be deterministic
- ❌ **Slow tests:** Keep unit tests under 100ms
- ❌ **Large test data:** Use minimal data needed
- ❌ **Shared mutable state:** Isolate test data

## Common Patterns

### Pattern 1: Testing Async Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function()
    assert result == expected
```

### Pattern 2: Mocking External Dependencies

```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test with mocked dependency."""
    with patch('module.external_call') as mock_call:
        mock_call.return_value = "mocked"
        result = function_under_test()
        assert result == expected
```

### Pattern 3: Database Testing

```python
def test_database_operation(test_db):
    """Test database operation with test database."""
    # Use test database fixture
    result = db_operation(test_db)
    assert result.count() == expected_count
```

## Troubleshooting

### Issue 1: Tests Failing Intermittently

**Cause:** Shared state or race conditions

**Solution:**

- Ensure test isolation
- Use fresh fixtures
- Avoid global state

### Issue 2: Slow Tests

**Cause:** Too many integration tests or inefficient setup

**Solution:**

```bash
# Profile slow tests
pytest --durations=10
```

### Issue 3: Coverage Not Accurate

**Cause:** Missing source files or incorrect paths

**Solution:**

Check `pytest.ini` or `.coveragerc` configuration

## References

- [Testing Guide](path/to/guide.md)
- [Test Fixtures](path/to/fixtures.md)
- [External Testing Resource](https://example.com)

---

## Document Information

**Category:** Testing
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
**Test Framework:** pytest
**Coverage Tool:** pytest-cov

[Optional: **Maintainer:** Team or Individual]
