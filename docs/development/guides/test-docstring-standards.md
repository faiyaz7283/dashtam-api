# Test Docstring Standards

Comprehensive guide for writing Google-style docstrings in test files, following project WARP.md requirements.

---

## Table of Contents

- [Overview](#overview)
  - [What You'll Learn](#what-youll-learn)
  - [When to Use This Guide](#when-to-use-this-guide)
- [Prerequisites](#prerequisites)
- [Step-by-Step Instructions](#step-by-step-instructions)
  - [Step 1: Module-Level Docstrings](#step-1-module-level-docstrings)
  - [Step 2: Class-Level Docstrings](#step-2-class-level-docstrings)
  - [Step 3: Test Function Docstrings (Standard)](#step-3-test-function-docstrings-standard)
  - [Step 4: Test Function Docstrings (With Fixtures)](#step-4-test-function-docstrings-with-fixtures)
  - [Step 5: Test Function Docstrings (Complex/Integration)](#step-5-test-function-docstrings-complexintegration)
  - [Step 6: Fixture Docstrings](#step-6-fixture-docstrings)
- [Examples](#examples)
  - [Example 1: Setup Method Docstring](#example-1-setup-method-docstring)
  - [Example 2: Teardown Method Docstring](#example-2-teardown-method-docstring)
  - [Example 3: Parametrized Test Docstring](#example-3-parametrized-test-docstring)
  - [Example 4: Mock-Heavy Test Docstring](#example-4-mock-heavy-test-docstring)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
  - [Issue 1: Too Brief Documentation](#issue-1-too-brief-documentation)
  - [Issue 2: Missing Fixture Documentation](#issue-2-missing-fixture-documentation)
  - [Issue 3: No Verification Details](#issue-3-no-verification-details)
  - [Issue 4: Implementation Instead of Intent](#issue-4-implementation-instead-of-intent)
- [Best Practices](#best-practices)
  - [Common Mistakes to Avoid](#common-mistakes-to-avoid)
- [Next Steps](#next-steps)
- [References](#references)
- [Document Information](#document-information)

---

## Overview

> **Note:** This document is now part of the comprehensive [Docstring Standards Guide](../guides/docstring-standards.md).
> Please refer to that guide for complete Python documentation standards covering all code types.
> This document is maintained for backward compatibility and focuses on test-specific patterns.

This guide provides standards for writing comprehensive Google-style docstrings in test files. Well-documented tests serve as living documentation, improve maintainability, and accelerate debugging.

### What You'll Learn

- How to write module-level docstrings for test files
- Standards for class-level and function-level test docstrings
- Documentation patterns for fixtures and parametrized tests
- Google-style docstring format and conventions
- How to document mocks, setup/teardown methods, and complex tests
- Anti-patterns to avoid when documenting tests

### When to Use This Guide

Use this guide when:

- Writing new test files (unit, integration, or API tests)
- Adding docstrings to existing undocumented tests
- Reviewing test code for documentation compliance
- Onboarding new developers to project testing standards

## Prerequisites

Before starting, ensure you have:

- [ ] Basic knowledge of Python and pytest
- [ ] Understanding of Google-style docstring format
- [ ] Familiarity with project's testing patterns (see [Testing Guide](testing-guide.md))

**Required Tools:**

- Python 3.13+
- pytest (project's testing framework)
- Code editor with docstring support

**Required Knowledge:**

- Familiarity with pytest fixtures and test organization
- Understanding of project WARP.md rules for documentation
- Basic knowledge of Google-style docstring sections (Args, Returns, Raises, Note)

## Step-by-Step Instructions

### Step 1: Module-Level Docstrings

Every test module MUST have a module-level docstring at the top of the file.

**Format:**

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

- One-line summary (what module tests)
- Blank line
- Detailed description of test coverage
- Optional Notes section for testing patterns or important context

**What This Does:** Provides high-level overview of test module purpose, helping developers quickly understand what functionality is being tested.

### Step 2: Class-Level Docstrings

Test classes MUST have a docstring explaining their purpose and scope.

**Format:**

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

**What This Does:** Documents the test class's responsibility and any shared fixtures or state used across test methods.

### Step 3: Test Function Docstrings (Standard)

Most test functions should follow this standard format.

**Format:**

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

**What This Does:** Clearly documents test intent and what specific behaviors are being validated, making test failures easier to diagnose.

### Step 4: Test Function Docstrings (With Fixtures)

When tests use pytest fixtures, document them in the Args section.

**Format:**

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

**What This Does:** Documents fixture dependencies, making it clear what test data is required and where fixtures are defined.

### Step 5: Test Function Docstrings (Complex/Integration)

Complex or integration tests require comprehensive documentation with multiple sections.

**Format:**

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

**What This Does:** Provides complete documentation for complex tests with extensive mocking or multi-step scenarios, ensuring maintainability.

### Step 6: Fixture Docstrings

Pytest fixtures MUST have comprehensive docstrings documenting their purpose, dependencies, and return values.

**Format:**

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

**What This Does:** Documents reusable test fixtures, explaining what they provide and how they should be used.

## Examples

### Example 1: Setup Method Docstring

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

**Result:** Clearly documents setup logic executed before each test, making test initialization transparent.

### Example 2: Teardown Method Docstring

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

**Result:** Documents cleanup logic, preventing confusion about test isolation and state management.

### Example 3: Parametrized Test Docstring

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

**Result:** Documents parametrized tests with clear explanation of validation rules and test data.

### Example 4: Mock-Heavy Test Docstring

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

**Result:** Comprehensive documentation for heavily mocked unit tests, clearly explaining isolation strategy and validation approach.

## Verification

Use this checklist to verify test docstrings are complete and compliant.

**Complete Docstring Checklist:**

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

**Verification Commands:**

```bash
# Run linting to catch docstring issues
make lint

# Format code including docstrings
make format
```

**Expected Result:** All linting passes, docstrings properly formatted, no warnings about missing or incomplete documentation.

## Troubleshooting

### Issue 1: Too Brief Documentation

**Symptoms:**

- Docstring is a single line with no details
- No explanation of what is being validated
- Example: `"""Test login."""`

**Cause:** Minimal documentation that doesn't explain test purpose or validation logic.

**Solution:**

Expand docstring with comprehensive details:

```python
# ❌ Too brief
def test_login_success(self, client, verified_user):
    """Test login."""

# ✅ Proper documentation
def test_login_success(self, client: TestClient, verified_user: User):
    """Test successful user login with valid credentials.
    
    Verifies that:
    - Login returns 200 status code
    - Response includes both access_token and refresh_token
    - Response includes user profile data
    - Token type is "bearer"
    
    Args:
        client: FastAPI TestClient fixture for making HTTP requests
        verified_user: Pre-created user with verified email
    """
```

### Issue 2: Missing Fixture Documentation

**Symptoms:**

- Test uses fixtures but doesn't document them
- No Args section in docstring
- Unclear where fixtures come from or what they provide

**Cause:** Incomplete docstring missing fixture documentation.

**Solution:**

Add Args section documenting all fixtures:

```python
# ❌ Missing fixture documentation
def test_login_success(self, client: TestClient, verified_user: User):
    """Test successful user login.
    
    Verifies that login returns tokens.
    """

# ✅ Complete fixture documentation
def test_login_success(self, client: TestClient, verified_user: User):
    """Test successful user login with valid credentials.
    
    Verifies that:
    - Login returns 200 status code
    - Response includes tokens and user profile
    
    Args:
        client: FastAPI TestClient fixture for making HTTP requests
        verified_user: Pre-created user with verified email (from fixtures/users.py)
    
    Note:
        User must have email_verified=True to successfully login.
    """
```

### Issue 3: No Verification Details

**Symptoms:**

- Docstring doesn't explain what is being validated
- Missing "Verifies that:" section
- Unclear test purpose

**Cause:** Documentation doesn't specify validation logic.

**Solution:**

Add detailed "Verifies that:" section:

```python
# ❌ No verification details
def test_token_rotation(self, mock_session):
    """Test token rotation.
    
    Args:
        mock_session: Mocked database session
    """

# ✅ Clear verification details
def test_token_rotation(self, mock_session):
    """Test OAuth token rotation detection when provider sends new refresh token.
    
    Verifies that:
        - New refresh token is encrypted before storage
        - Database token record is updated with new values
        - Audit log entry records the rotation
        - Session operations (add, flush, commit) are called
    
    Args:
        mock_session: Mocked AsyncSession for database operations
    
    Note:
        This validates the critical token rotation detection logic.
    """
```

### Issue 4: Implementation Instead of Intent

**Symptoms:**

- Docstring describes HOW test works instead of WHAT it validates
- Focus on implementation details rather than test purpose
- Example: "Calls service.method() and checks result"

**Cause:** Documentation focuses on code mechanics instead of validation intent.

**Solution:**

Focus on test purpose and what is being validated:

```python
# ❌ Implementation-focused
def test_password_reset(self, auth_service):
    """Calls auth_service.reset_password() and checks result."""

# ✅ Intent-focused
def test_password_reset(self, auth_service: AuthService):
    """Test password reset flow generates valid reset token.
    
    Verifies that:
        - Reset token is created and stored in database
        - Token has correct expiration (24 hours)
        - Token is properly hashed before storage
        - Reset email is sent to user with token link
    
    Args:
        auth_service: AuthService instance for password operations
    
    Note:
        Token must be single-use and expire after 24 hours.
    """
```

## Best Practices

Follow these best practices when documenting tests:

- ✅ **Write docstrings while writing tests:** Don't leave documentation for later - document as you code
- ✅ **Be specific in verification sections:** List exact assertions and validation logic
- ✅ **Document all fixtures:** Always include Args section for pytest fixtures
- ✅ **Use present tense:** "Test...", "Verify...", "Validate..." not past tense
- ✅ **Explain the WHY:** Document why test exists and what behavior it protects
- ✅ **Keep it readable:** Use clear language and avoid abbreviations
- ✅ **Follow Google-style format:** Consistent with project standards (WARP.md requirement)

### Common Mistakes to Avoid

- ❌ **Single-line docstrings:** Always provide details beyond just a summary
- ❌ **Missing fixture documentation:** Document ALL fixtures in Args section
- ❌ **Vague verification statements:** Be specific about what assertions validate
- ❌ **Implementation descriptions:** Focus on intent, not code mechanics
- ❌ **Inconsistent format:** Always use Google-style docstrings
- ❌ **Skipping Notes section:** Add important context about patterns or requirements

## Next Steps

After mastering test docstring standards, consider:

- [ ] Review [Docstring Standards Guide](../guides/docstring-standards.md) for application code patterns
- [ ] Study [Testing Best Practices](../guides/testing-best-practices.md) for testing patterns
- [ ] Review exemplary test files in `tests/conftest.py` and `tests/unit/services/`
- [ ] Contribute to improving undocumented tests in the codebase

## References

- [Docstring Standards Guide](docstring-standards.md) - Complete Python documentation standards
- [Testing Guide](testing-guide.md) - Comprehensive testing documentation
- [Testing Best Practices](testing-best-practices.md) - Testing patterns and conventions
- [Google Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) - Official Google Python style guide
- [PEP 257](https://peps.python.org/pep-0257/) - Docstring conventions
- WARP.md - Project rules requiring Google-style docstrings

---

## Document Information

**Template:** [guide-template.md](../../templates/guide-template.md)
**Created:** 2025-10-05
**Last Updated:** 2025-10-18
