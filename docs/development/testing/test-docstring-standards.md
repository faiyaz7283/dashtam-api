# Test Docstring Standards

> **Note:** This document is now part of the comprehensive [Docstring Standards Guide](../guides/docstring-standards.md).
> Please refer to that guide for complete Python documentation standards covering all code types.
> This document is maintained for backward compatibility and focuses on test-specific patterns.

This document provides the standard for writing comprehensive Google-style docstrings in test files, following the project's WARP.md requirements.

## Why Comprehensive Docstrings in Tests?

1. **Code as Documentation:** Tests document expected behavior and usage patterns
2. **Onboarding:** New developers understand test purpose without reading implementation
3. **Maintenance:** Clear test intent makes refactoring safer
4. **Debugging:** Well-documented tests make failure diagnosis faster
5. **Compliance:** Follows project WARP.md rule for Google-style docstrings

## Standard Format

### Module-Level Docstring

Every test module MUST have a module-level docstring at the top:

```python
"""Unit tests for JWTService.

Tests JWT token creation, validation, and decoding functionality. Covers:
- Access token generation with user claims
- Refresh token generation with JTI
- Token validation and type checking
- Token expiration handling
- JWT payload extraction

Note:
    Uses synchronous test pattern (regular def test_*(), NOT async def)
    following FastAPI TestClient conventions.
"""
```

**Required Elements:**

- One-line summary
- Blank line
- Detailed description of what the module tests
- Optional Notes section for testing patterns or important context

### Class-Level Docstring

Test classes MUST have a docstring explaining their purpose:

```python
class TestJWTService:
    """Test suite for JWTService token operations.
    
    Covers all JWT creation, validation, and decoding scenarios including
    error handling and edge cases.
    
    Attributes:
        service: JWTService instance created in setup_method
        test_user_id: UUID for test user
        test_email: Email address for test user
    """
```

**Required Elements:**

- One-line summary of test suite purpose
- Blank line  
- Detailed description of coverage
- Optional Attributes section for shared test data

### Test Function Docstring (Standard)

Most test functions should follow this format:

```python
def test_create_access_token(self):
    """Test access token creation with user claims.
    
    Verifies that:
    - Token is generated as a valid JWT string
    - Token contains correct user_id and email claims
    - Token has standard JWT structure (3 parts separated by dots)
    - Token includes expiration and issued-at timestamps
    
    Note:
        Access tokens use shorter TTL (30 min) vs refresh tokens (30 days)
    """
```

**Required Elements:**

- One-line summary (verb + what is tested)
- Blank line
- "Verifies that:" or "Validates that:" section with specific checks
- Optional Note section for important test context

### Test Function Docstring (With Fixtures)

When test uses pytest fixtures, document them in Args section:

```python
def test_login_success(self, client: TestClient, verified_user: User):
    """Test successful user login with valid credentials.
    
    Verifies that:
    - Login returns 200 status code
    - Response includes both access_token and refresh_token
    - Response includes user profile data
    - Token type is "bearer"
    - User email matches the logged-in user
    
    Args:
        client: FastAPI TestClient fixture for making HTTP requests
        verified_user: Pre-created user with verified email (from fixtures/users.py)
    
    Note:
        User must have email_verified=True to successfully login.
        Uses TestClient's synchronous pattern (no await needed).
    """
```

**Required Elements:**

- Standard docstring sections (summary + verifies)
- Args section documenting ALL fixtures
- Each arg includes fixture name, type, and brief description
- Optional Note section for test requirements or patterns

### Test Function Docstring (Complex/Integration)

For complex or integration tests with extensive setup:

```python
async def test_token_rotation_with_new_refresh_token(
    self, mock_session, mock_encryption, mock_provider_registry
):
    """Test OAuth token rotation detection when provider sends new refresh token.
    
    Scenario:
        Provider rotates the refresh token during token refresh operation,
        returning a new refresh token in the response. This is Scenario 1
        of the Universal Token Rotation design.
    
    Setup:
        - Creates provider with existing expired token
        - Mocks OAuth provider to return NEW refresh token
        - Mocks database session and encryption service
    
    Verifies that:
        - New refresh token is encrypted before storage
        - Database token record is updated with new values
        - Audit log entry records the rotation
        - Session operations (add, flush, commit) are called
    
    Args:
        mock_session: Mocked AsyncSession for database operations
        mock_encryption: Mocked EncryptionService for token encryption
        mock_provider_registry: Mocked provider registry returning mock provider
    
    Raises:
        AssertionError: If rotation detection fails or encryption not called
    
    Note:
        Uses asyncio.run() to execute async service method in synchronous test.
        This test validates the critical token rotation detection logic.
    """
```

**Required Elements:**

- Comprehensive summary
- Scenario section explaining test context
- Setup section describing test data preparation
- Verifies section with specific validation points
- Args section for all fixtures/mocks
- Raises section for assertion failures
- Note section for patterns and importance

### Fixture Docstring

Pytest fixtures MUST also have comprehensive docstrings:

```python
@pytest.fixture
def verified_user(db_session: Session, test_user: User) -> User:
    """Create a test user with verified email for login tests.
    
    This fixture extends test_user by setting email_verified=True,
    which is required for successful login operations.
    
    Args:
        db_session: Database session for persisting user changes
        test_user: Base test user fixture from conftest.py
    
    Returns:
        User: Test user instance with email_verified=True
    
    Note:
        Modifications persist in database for the test function scope.
        User is cleaned up automatically by db_session cleanup.
    """
    test_user.email_verified = True
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)
    return test_user
```

**Required Elements:**

- Summary of fixture purpose
- Description of what fixture provides
- Args section for any dependencies
- Returns section with type and description
- Optional Note section for lifecycle/cleanup info

## Common Patterns

### Pattern 1: Setup Method Docstring

```python
def setup_method(self):
    """Set up test fixtures before each test method.
    
    Initializes:
        - JWTService instance
        - Test user ID (UUID)
        - Test email address
    
    Note:
        Called automatically before each test method in the class.
    """
```

### Pattern 2: Teardown Method Docstring

```python
def teardown_method(self):
    """Clean up test resources after each test method.
    
    Resets:
        - Global database engine to None
        - Global session maker to None
    
    Note:
        Ensures clean state for next test to avoid cross-test pollution.
    """
```

### Pattern 3: Parametrized Test Docstring

```python
@pytest.mark.parametrize("password,expected_valid", [
    ("short", False),
    ("NoDigits!", False),
    ("noupperca5e!", False),
    ("NOLOWERCASE5!", False),
    ("NoSpecialChar5", False),
    ("ValidPass123!", True),
])
def test_password_strength_validation(self, password, expected_valid):
    """Test password strength validation with various inputs.
    
    Validates password requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    
    Args:
        password: Password string to validate
        expected_valid: Expected validation result (True/False)
    
    Note:
        Uses pytest.mark.parametrize for multiple test cases.
    """
```

### Pattern 4: Mock-Heavy Test Docstring

```python
def test_auth_service_with_mocked_dependencies(
    self, mock_session, mock_password_service, mock_email_service
):
    """Test AuthService password reset with all dependencies mocked.
    
    Isolation Strategy:
        Uses unittest.mock to isolate AuthService from:
        - Database (AsyncSession)
        - Password hashing (PasswordService)
        - Email sending (EmailService)
    
    Mocks:
        - mock_session: AsyncSession for database operations
        - mock_password_service: Password hashing and validation
        - mock_email_service: Email notification sending
    
    Verifies that:
        - AuthService coordinates all dependencies correctly
        - Password is hashed before storage
        - Email notification is sent after password change
        - All service methods are called with correct parameters
    
    Args:
        mock_session: Mocked database session fixture
        mock_password_service: Mocked password service fixture
        mock_email_service: Mocked email service fixture
    
    Note:
        This is a true unit test - no real database or external services.
        Validates service orchestration logic only.
    """
```

## Anti-Patterns to Avoid

### ❌ Too Brief (Insufficient)

```python
def test_login_success(self, client, verified_user):
    """Test login."""  # TOO BRIEF - doesn't explain what's validated
```

### ❌ Missing Fixture Documentation

```python
def test_login_success(self, client: TestClient, verified_user: User):
    """Test successful user login.
    
    Verifies that login returns tokens.
    """
    # MISSING: No Args section documenting fixtures
```

### ❌ No Verification Details

```python
def test_token_rotation(self, mock_session):
    """Test token rotation.
    
    Args:
        mock_session: Mocked database session
    """
    # MISSING: No explanation of WHAT is verified or WHY
```

### ❌ Implementation Instead of Intent

```python
def test_password_reset(self, auth_service):
    """Calls auth_service.reset_password() and checks result."""
    # WRONG: Describes implementation, not test purpose/validation
```

## Checklist for Complete Docstrings

Before considering a test file complete, verify:

- [ ] Module-level docstring at top of file
- [ ] Class-level docstring for each test class
- [ ] Function docstring for EVERY test function
- [ ] Args section for ALL fixtures used
- [ ] "Verifies that:" section listing specific checks
- [ ] Note section for important patterns or context
- [ ] Fixture docstrings include Returns section
- [ ] Setup/teardown methods documented
- [ ] Consistent verb tense (present tense: "Test...", "Verify...")
- [ ] No abbreviations or unclear terminology
- [ ] Google-style format (not NumPy or reStructuredText)

## Google-Style Quick Reference

```python
"""One-line summary ending with period.

Longer description paragraph providing more context. Can span
multiple lines and include multiple paragraphs.

Args:
    param1: Description of param1 (type optional if annotated)
    param2: Description of param2

Returns:
    Description of return value and type

Raises:
    ErrorType: Description of when this error is raised

Note:
    Any additional notes or warnings about usage

Example:
    Optional example usage
"""
```

## Integration with Development Workflow

When updating test docstrings:

1. **During Development:** Write docstring WHILE writing test
2. **Code Review:** Check docstring completeness
3. **Linting:** Run `make lint` to catch issues
4. **Formatting:** Run `make format` to auto-format
5. **Before Commit:** Verify all tests have proper docstrings

## Resources

- **WARP.md:** Project rules requiring Google-style docstrings
- **Google Style Guide:** https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings
- **PEP 257:** Docstring conventions (https://peps.python.org/pep-0257/)
- **Example:** See `tests/conftest.py` for excellent docstring examples

---

**Remember:** Good test docstrings are documentation. They should be clear enough that someone can understand what's being tested without reading the test implementation.
