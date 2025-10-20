# Docstring Standards Guide

Comprehensive guide for writing Google-style docstrings across all Python code in Dashtam, covering modules, classes, functions, tests, and fixtures with practical examples and best practices.

---

## Table of Contents

- [Overview](#overview)
  - [What You'll Learn](#what-youll-learn)
  - [When to Use This Guide](#when-to-use-this-guide)
  - [Why Google-Style Docstrings](#why-google-style-docstrings)
- [Prerequisites](#prerequisites)
- [Step-by-Step Instructions](#step-by-step-instructions)
  - [Step 1: Write Module-Level Docstrings](#step-1-write-module-level-docstrings)
  - [Step 2: Write Class Docstrings](#step-2-write-class-docstrings)
  - [Step 3: Write Function/Method Docstrings](#step-3-write-functionmethod-docstrings)
  - [Step 4: Write FastAPI Endpoint Docstrings](#step-4-write-fastapi-endpoint-docstrings)
  - [Step 5: Write Test Docstrings](#step-5-write-test-docstrings)
  - [Step 6: Write Pytest Fixture Docstrings](#step-6-write-pytest-fixture-docstrings)
- [Examples](#examples)
  - [Example 1: Complete Service Class](#example-1-complete-service-class)
  - [Example 2: FastAPI Endpoint](#example-2-fastapi-endpoint)
  - [Example 3: Test Function](#example-3-test-function)
  - [Example 4: Pytest Fixture](#example-4-pytest-fixture)
- [Verification](#verification)
  - [Check 1: Run Linting](#check-1-run-linting)
  - [Check 2: Review Completeness](#check-2-review-completeness)
  - [Check 3: Test Documentation Coverage](#check-3-test-documentation-coverage)
- [Troubleshooting](#troubleshooting)
  - [Issue 1: Docstring Too Brief](#issue-1-docstring-too-brief)
  - [Issue 2: Missing Fixture Documentation](#issue-2-missing-fixture-documentation)
  - [Issue 3: Implementation vs Intent](#issue-3-implementation-vs-intent)
  - [Issue 4: Missing Error Documentation](#issue-4-missing-error-documentation)
- [Best Practices](#best-practices)
  - [Quick Reference Checklist](#quick-reference-checklist)
  - [Google-Style Section Order](#google-style-section-order)
  - [Common Patterns](#common-patterns)
- [Next Steps](#next-steps)
- [References](#references)
  - [Official Style Guides](#official-style-guides)
  - [Tools and Automation](#tools-and-automation)
  - [Project Documentation](#project-documentation)
- [Document Information](#document-information)

---

## Overview

This guide provides comprehensive instructions for writing Google-style docstrings across all Python code in Dashtam, covering modules, classes, functions, tests, and fixtures with practical examples and best practices.

### What You'll Learn

- How to write Google-style docstrings for all Python code types
- Module, class, function, and test documentation patterns
- FastAPI endpoint documentation requirements
- Pytest fixture documentation standards
- Common patterns and anti-patterns to avoid
- How to verify docstring quality with linting tools

### When to Use This Guide

Use this guide when:

- Writing new Python code (modules, classes, functions)
- Writing tests and pytest fixtures
- Implementing FastAPI endpoints
- Reviewing pull requests for documentation quality
- Updating existing code to meet documentation standards

### Why Google-Style Docstrings

The Dashtam project uses **Google-style docstrings** as mandated in WARP.md for the following reasons:

1. **Readability:** Clean, natural language format that's easy to scan
2. **Consistency:** Industry-standard format used by major Python projects
3. **Tooling Support:** Compatible with Sphinx, MkDocs, mkdocstrings, and IDEs
4. **Maintainability:** Clear structure makes documentation updates straightforward
5. **Onboarding:** New developers can understand code behavior without reading implementation

**Google-Style Quick Reference:**

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

**Official Resources:**

- [Google Python Style Guide - Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- WARP.md - Project-specific docstring requirements

## Prerequisites

Before starting, ensure you have:

- [ ] Python 3.13+ development environment
- [ ] Familiarity with Python type hints
- [ ] Understanding of Google-style docstring format
- [ ] Ruff linter configured in project

**Required Tools:**

- Ruff - For linting and docstring validation
- Python 3.13+ - With type hints support
- IDE with docstring preview (VSCode, PyCharm)

**Required Knowledge:**

- Familiarity with Python syntax and structure
- Understanding of classes, functions, and methods
- Basic knowledge of pytest for test documentation
- Familiarity with FastAPI for endpoint documentation

## Step-by-Step Instructions

### Step 1: Write Module-Level Docstrings

Every Python module MUST have a module-level docstring at the top of the file (after imports header comments):

```python
"""User authentication service.

Provides secure user authentication using JWT tokens with refresh token
rotation. Implements password hashing, token generation/validation, and
email verification flows.

This module coordinates between PasswordService, JWTService, and EmailService
to provide complete user authentication capabilities including:
- User registration with email verification
- Login with JWT access + refresh tokens
- Token refresh with rotation
- Password reset flow
- Account lockout on failed attempts

Security Features:
    - Bcrypt password hashing (12 rounds)
    - JWT access tokens (30 min expiry)
    - Opaque refresh tokens (30 days expiry)
    - Email verification required for login
    - Account lockout after 10 failed attempts

Note:
    All methods are async and require AsyncSession for database operations.
    Token hashing uses bcrypt for security (not reversible encryption).
"""
```

**Required Elements:**

- One-line summary
- Blank line
- Detailed description of module purpose
- List of key components/classes if applicable
- Optional sections: Security Features, Architecture, Dependencies, Note

### Step 2: Write Class Docstrings

All classes MUST have comprehensive docstrings explaining their purpose, responsibilities, and usage.

#### Service Classes

```python
class AuthService:
    """User authentication and authorization service.
    
    Orchestrates user authentication flows including registration, login,
    token management, email verification, and password resets. Coordinates
    between database operations, password hashing, JWT creation, and email
    notifications.
    
    Attributes:
        session: AsyncSession for database operations
        password_service: Service for password hashing and validation
        jwt_service: Service for JWT token creation and validation
        email_service: Service for sending verification/reset emails
    
    Security:
        - All passwords hashed with bcrypt (12 rounds)
        - Refresh tokens hashed before storage (one-way)
        - Account lockout after 10 failed login attempts
        - Email verification required before login
    
    Example:
        >>> auth_service = AuthService(session, password_svc, jwt_svc, email_svc)
        >>> user = await auth_service.register_user("user@example.com", "SecurePass123!")
        >>> tokens = await auth_service.login("user@example.com", "SecurePass123!")
    
    Note:
        This service is async and all methods require await.
        Use get_auth_service() dependency for FastAPI endpoints.
    """
```

#### Model Classes (SQLModel/Pydantic)

```python
class User(SQLModel, table=True):
    """User model representing authenticated users.
    
    Stores user account information including authentication credentials,
    profile data, and account status. Users must verify their email before
    gaining full access to the platform.
    
    Attributes:
        id: Unique user identifier (UUID, primary key)
        email: User's email address (unique, required for login)
        password_hash: Bcrypt-hashed password (never stored in plaintext)
        email_verified: Whether email has been verified (required for login)
        failed_login_attempts: Counter for account lockout (resets on success)
        locked_until: Timestamp when account lockout expires (nullable)
        created_at: Account creation timestamp (UTC, timezone-aware)
        updated_at: Last modification timestamp (UTC, auto-updated)
        deleted_at: Soft delete timestamp (nullable, for audit trail)
    
    Relationships:
        providers: List of connected financial providers (one-to-many)
        refresh_tokens: Active refresh tokens for this user (one-to-many)
    
    Security:
        - Password stored as bcrypt hash (12 rounds, ~300ms compute)
        - Email must be verified before login allowed
        - Account locks for 1 hour after 10 failed attempts
    
    Note:
        All datetime fields are timezone-aware (TIMESTAMPTZ in PostgreSQL).
        Soft deletes preserve data for audit/compliance requirements.
    """
```

### Step 3: Write Function/Method Docstrings

All public functions and methods MUST have comprehensive docstrings.

#### Standard Function Pattern

```python
async def create_user(
    self,
    email: str,
    password: str,
    session: AsyncSession
) -> User:
    """Create a new user account with email verification.
    
    Registers a new user with hashed password and sends email verification.
    User cannot login until email is verified. Validates password strength
    and checks for duplicate email addresses.
    
    Args:
        email: User's email address (must be unique)
        password: Plain text password (will be hashed with bcrypt)
        session: AsyncSession for database operations
    
    Returns:
        User: Created user instance with id and hashed password
    
    Raises:
        ValueError: If email already exists or password too weak
        HTTPException: If email service fails to send verification
    
    Note:
        Password must meet complexity requirements:
        - Minimum 8 characters
        - At least one uppercase, lowercase, digit, special character
        
        Email verification token expires in 24 hours.
    
    Example:
        >>> user = await auth_service.create_user(
        ...     "user@example.com",
        ...     "SecurePass123!",
        ...     session
        ... )
        >>> print(f"User {user.id} created, verification email sent")
    """
```

**Required Sections:**

- Summary (one line)
- Description (detailed explanation)
- Args (all parameters with types and descriptions)
- Returns (return value type and description)
- Raises (all possible exceptions)
- Optional: Note, Example, Warning

### Step 4: Write FastAPI Endpoint Docstrings

FastAPI endpoint functions require special documentation patterns:

```python
@router.post("/auth/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> LoginResponse:
    """Authenticate user and return JWT tokens.
    
    Validates user credentials and returns access + refresh tokens if successful.
    Tracks failed login attempts and enforces account lockout policy.
    
    Request Body:
        - email: User's email address
        - password: User's password (plaintext, transmitted over HTTPS)
        - device_info: Optional device information for session tracking
    
    Response:
        - access_token: JWT access token (30 min expiry)
        - refresh_token: Opaque refresh token (30 days expiry)
        - token_type: Always "bearer"
        - user: User profile data (id, email)
    
    Status Codes:
        - 200: Login successful, tokens returned
        - 400: Invalid request format
        - 401: Invalid credentials or email not verified
        - 429: Too many failed attempts, account locked
    
    Args:
        credentials: Login request with email and password
        auth_service: Injected AuthService dependency
    
    Returns:
        LoginResponse: Access token, refresh token, and user data
    
    Raises:
        HTTPException: 401 if credentials invalid or email not verified
        HTTPException: 429 if account is locked due to failed attempts
    
    Security:
        - Requires HTTPS (enforced by TrustedHostMiddleware)
        - Rate limited to 5 requests per minute per IP
        - Account locks after 10 failed attempts (1 hour)
        - Tracks device and IP for session management
    
    Example:
        >>> POST /api/v1/auth/login
        >>> {
        ...   "email": "user@example.com",
        ...   "password": "SecurePass123!"
        ... }
        >>> # Returns: { "access_token": "eyJ...", "refresh_token": "...", ... }
    """
```

**FastAPI-Specific Sections:**

- Request Body (schema description)
- Response (schema description)
- Status Codes (all possible HTTP status codes)
- Security (authentication/authorization requirements)
- Example (cURL or HTTP request example)

### Step 5: Write Test Docstrings

Tests are **documentation of expected behavior**. Comprehensive test docstrings are critical for understanding what's being tested, debugging failures quickly, and onboarding new developers.

#### Test Module Docstrings

Every test module MUST have a module-level docstring:

```python
"""Unit tests for AuthService.

Tests complete user authentication flows including:
- User registration with password hashing
- Login with credential validation
- Token refresh with rotation
- Email verification
- Password reset flow
- Account lockout on failed attempts
- Session management

Coverage:
    - All AuthService public methods
    - Error handling and edge cases
    - Security features (lockout, hashing)
    - Token rotation logic

Note:
    Uses synchronous test pattern (regular def test_*(), NOT async def)
    following FastAPI TestClient conventions. Database operations are
    mocked using unittest.mock for true unit testing.
"""
```

**Required Elements:**

- One-line summary of what module tests
- List of tested functionality
- Optional Coverage section
- Optional Note for testing patterns

#### Test Class Docstrings

Test classes group related test scenarios:

```python
class TestAuthServiceLogin:
    """Test suite for AuthService login functionality.
    
    Covers all login scenarios including success, failure, account lockout,
    and edge cases. Validates credential checking, token generation, and
    audit logging.
    
    Fixtures:
        verified_user: Pre-created user with verified email
        auth_service: AuthService instance with mocked dependencies
    
    Note:
        Uses pytest fixtures for consistent test data.
        All tests are synchronous (no async/await needed).
    """
```

#### Test Function Docstrings

**Standard Test Pattern:**

```python
def test_login_success(self, client: TestClient, verified_user: User):
    """Test successful user login with valid credentials.
    
    Verifies that:
    - Login returns 200 status code
    - Response includes both access_token and refresh_token
    - Response includes user profile data
    - Token type is "bearer"
    - User email matches the logged-in user
    - Refresh token is stored in database (hashed)
    - Failed login attempts counter is reset to 0
    
    Args:
        client: FastAPI TestClient fixture for making HTTP requests
        verified_user: Pre-created user with verified email (from fixtures/users.py)
    
    Note:
        User must have email_verified=True to successfully login.
        Uses TestClient's synchronous pattern (no await needed).
    """
```

**Test with Mocks:**

```python
def test_login_with_account_lockout(
    self,
    mock_session: AsyncSession,
    locked_user: User
):
    """Test login failure when account is locked due to failed attempts.
    
    Scenario:
        User has 10+ failed login attempts and account is locked until
        future timestamp. Login should fail even with correct password.
    
    Setup:
        - Creates user with failed_login_attempts=10
        - Sets locked_until to 1 hour in future
        - Mocks database session to return locked user
    
    Verifies that:
        - Login returns 429 status (Too Many Requests)
        - Error message indicates account is locked
        - Response includes locked_until timestamp
        - Failed attempts counter is NOT incremented
    
    Args:
        mock_session: Mocked AsyncSession for database operations
        locked_user: User fixture with locked account status
    
    Raises:
        AssertionError: If lockout not properly enforced
    
    Note:
        Account lockout is automatic after 10 failed attempts.
        Lockout duration is 1 hour (configurable in settings).
    """
```

**Parametrized Test Pattern:**

```python
@pytest.mark.parametrize("password,expected_valid", [
    ("short", False),                    # Too short (< 8 chars)
    ("NoDigits!", False),                # Missing digit
    ("noupperca5e!", False),             # Missing uppercase
    ("NOLOWERCASE5!", False),            # Missing lowercase
    ("NoSpecialChar5", False),           # Missing special char
    ("ValidPass123!", True),             # Meets all requirements
])
def test_password_strength_validation(self, password: str, expected_valid: bool):
    """Test password strength validation with various inputs.
    
    Validates password requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&*)
    
    Args:
        password: Password string to validate
        expected_valid: Expected validation result (True/False)
    
    Note:
        Uses pytest.mark.parametrize for multiple test cases.
        Tests cover all password validation rules.
    """
```

### Step 6: Write Pytest Fixture Docstrings

Fixtures MUST have comprehensive docstrings:

```python
@pytest.fixture
def verified_user(db_session: Session) -> User:
    """Create test user with verified email for login tests.
    
    This fixture creates a user with email_verified=True, which is
    required for successful login operations. Password is set to
    "TestPass123!" and hashed with bcrypt.
    
    Args:
        db_session: Database session for persisting user
    
    Returns:
        User: Test user instance with:
            - email: "testuser@example.com"
            - password: "TestPass123!" (hashed)
            - email_verified: True
            - failed_login_attempts: 0
    
    Yields:
        User instance persisted in test database
    
    Cleanup:
        User is automatically cleaned up by db_session fixture rollback.
        No manual cleanup needed.
    
    Note:
        Use this fixture when testing authenticated operations.
        For testing unverified users, use base test_user fixture.
    
    Example:
        def test_login(verified_user: User):
            response = client.post("/auth/login", json={
                "email": verified_user.email,
                "password": "TestPass123!"
            })
            assert response.status_code == 200
    """
    user = User(
        email="testuser@example.com",
        password_hash=hash_password("TestPass123!"),
        email_verified=True,
        failed_login_attempts=0
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    # Cleanup handled by db_session rollback
```

**Fixture-Specific Sections:**

- Args (fixture dependencies)
- Returns or Yields (what fixture provides)
- Cleanup (how resources are cleaned up)
- Example (how to use the fixture)

## Examples

### Example 1: Complete Service Class

Here's a complete example of a service class with proper docstrings:

```python
class AuthService:
    """User authentication and authorization service.
    
    Orchestrates user authentication flows including registration, login,
    token management, email verification, and password resets. Coordinates
    between database operations, password hashing, JWT creation, and email
    notifications.
    
    Attributes:
        session: AsyncSession for database operations
        password_service: Service for password hashing and validation
        jwt_service: Service for JWT token creation and validation
        email_service: Service for sending verification/reset emails
    
    Security:
        - All passwords hashed with bcrypt (12 rounds)
        - Refresh tokens hashed before storage (one-way)
        - Account lockout after 10 failed login attempts
        - Email verification required before login
    
    Example:
        >>> auth_service = AuthService(session, password_svc, jwt_svc, email_svc)
        >>> user = await auth_service.register_user("user@example.com", "SecurePass123!")
        >>> tokens = await auth_service.login("user@example.com", "SecurePass123!")
    
    Note:
        This service is async and all methods require await.
        Use get_auth_service() dependency for FastAPI endpoints.
    """
```

### Example 2: FastAPI Endpoint

Here's a FastAPI endpoint with comprehensive documentation:

```python
@router.post("/auth/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> LoginResponse:
    """Authenticate user and return JWT tokens.
    
    Validates user credentials and returns access + refresh tokens if successful.
    Tracks failed login attempts and enforces account lockout policy.
    
    Request Body:
        - email: User's email address
        - password: User's password (plaintext, transmitted over HTTPS)
        - device_info: Optional device information for session tracking
    
    Response:
        - access_token: JWT access token (30 min expiry)
        - refresh_token: Opaque refresh token (30 days expiry)
        - token_type: Always "bearer"
        - user: User profile data (id, email)
    
    Status Codes:
        - 200: Login successful, tokens returned
        - 400: Invalid request format
        - 401: Invalid credentials or email not verified
        - 429: Too many failed attempts, account locked
    
    Args:
        credentials: Login request with email and password
        auth_service: Injected AuthService dependency
    
    Returns:
        LoginResponse: Access token, refresh token, and user data
    
    Raises:
        HTTPException: 401 if credentials invalid or email not verified
        HTTPException: 429 if account is locked due to failed attempts
    
    Security:
        - Requires HTTPS (enforced by TrustedHostMiddleware)
        - Rate limited to 5 requests per minute per IP
        - Account locks after 10 failed attempts (1 hour)
        - Tracks device and IP for session management
    """
```

### Example 3: Test Function

Here's a test function with proper documentation:

```python
def test_login_success(self, client: TestClient, verified_user: User):
    """Test successful user login with valid credentials.
    
    Verifies that:
    - Login returns 200 status code
    - Response includes both access_token and refresh_token
    - Response includes user profile data
    - Token type is "bearer"
    - User email matches the logged-in user
    - Refresh token is stored in database (hashed)
    - Failed login attempts counter is reset to 0
    
    Args:
        client: FastAPI TestClient fixture for making HTTP requests
        verified_user: Pre-created user with verified email (from fixtures/users.py)
    
    Note:
        User must have email_verified=True to successfully login.
        Uses TestClient's synchronous pattern (no await needed).
    """
```

### Example 4: Pytest Fixture

Here's a pytest fixture with complete documentation:

```python
@pytest.fixture
def verified_user(db_session: Session) -> User:
    """Create test user with verified email for login tests.
    
    This fixture creates a user with email_verified=True, which is
    required for successful login operations. Password is set to
    "TestPass123!" and hashed with bcrypt.
    
    Args:
        db_session: Database session for persisting user
    
    Returns:
        User: Test user instance with:
            - email: "testuser@example.com"
            - password: "TestPass123!" (hashed)
            - email_verified: True
            - failed_login_attempts: 0
    
    Yields:
        User instance persisted in test database
    
    Cleanup:
        User is automatically cleaned up by db_session fixture rollback.
        No manual cleanup needed.
    
    Note:
        Use this fixture when testing authenticated operations.
        For testing unverified users, use base test_user fixture.
    
    Example:
        def test_login(verified_user: User):
            response = client.post("/auth/login", json={
                "email": verified_user.email,
                "password": "TestPass123!"
            })
            assert response.status_code == 200
    """
    user = User(
        email="testuser@example.com",
        password_hash=hash_password("TestPass123!"),
        email_verified=True,
        failed_login_attempts=0
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    yield user
    # Cleanup handled by db_session rollback
```

## Verification

### Check 1: Run Linting

Run the following commands to verify docstring quality:

```bash
# Lint code (includes docstring checks)
make lint

# Format code (auto-formats docstrings)
make format
```

**Expected Output:**

- No linting errors related to missing or malformed docstrings
- Code formatting applied successfully

**What This Checks:** Ensures all docstrings follow proper format and all required sections are present.

### Check 2: Review Completeness

Manually review your docstrings against this checklist:

```text
For every function/method:
[ ] One-line summary
[ ] Args section (all parameters)
[ ] Returns section (return value description)
[ ] Raises section (all exceptions)
[ ] Example for complex functions

For every class:
[ ] Class-level docstring
[ ] Attributes section
[ ] Example usage

For every test:
[ ] Summary of what's tested
[ ] "Verifies that:" section
[ ] Args section for all fixtures
```

**What This Checks:** Ensures completeness beyond what automated tools can verify.

### Check 3: Test Documentation Coverage

Verify test documentation quality:

```bash
# Run tests with verbose output
make test
```

**What to Look For:**

- Test names are descriptive and match docstrings
- Failed tests show clear context from docstrings
- All fixtures used have documentation

## Troubleshooting

### Issue 1: Docstring Too Brief

```python
def test_login(self, client, user):
    """Test login."""  # TOO BRIEF - doesn't explain what's validated
```

**Why This is Wrong:**

- Doesn't explain what's being tested
- No information about fixtures
- Missing verification details
- Not helpful for debugging failures

**✅ Correct Version:**

```python
def test_login_success(self, client: TestClient, verified_user: User):
    """Test successful user login with valid credentials.
    
    Verifies that login returns 200 status, includes access and refresh
    tokens, and resets failed login attempts counter.
    
    Args:
        client: FastAPI TestClient for HTTP requests
        verified_user: User with verified email (fixture)
    """
```

### Issue 2: Missing Fixture Documentation

```python
def test_token_refresh(self, client, refresh_token):
    """Test token refresh."""
    # MISSING: No Args section documenting fixtures
```

**✅ Correct Version:**

```python
def test_token_refresh(self, client: TestClient, refresh_token: str):
    """Test successful token refresh with valid refresh token.
    
    Args:
        client: FastAPI TestClient for HTTP requests
        refresh_token: Valid refresh token string (fixture)
    """
```

### Issue 3: Implementation vs Intent

```python
def test_password_reset(self, auth_service):
    """Calls auth_service.reset_password() and checks result."""
    # WRONG: Describes implementation, not test purpose/validation
```

**✅ Correct Version:**

```python
def test_password_reset_sends_email(self, auth_service, mock_email_service):
    """Test password reset sends email with reset token.
    
    Verifies that requesting password reset generates secure token,
    stores it in database with expiration, and sends email to user.
    
    Args:
        auth_service: AuthService instance with mocked email
        mock_email_service: Mocked EmailService to verify call
    """
```

### Issue 4: Missing Error Documentation

```python
async def authenticate_user(email: str, password: str) -> User:
    """Authenticate user with email and password."""
    # MISSING: No Raises section for possible exceptions
```

**✅ Correct Version:**

```python
async def authenticate_user(email: str, password: str) -> User:
    """Authenticate user with email and password.
    
    Args:
        email: User's email address
        password: Plain text password to verify
    
    Returns:
        User: Authenticated user instance
    
    Raises:
        HTTPException: 401 if credentials invalid
        HTTPException: 429 if account is locked
        ValueError: If email format invalid
    """
```

## Best Practices

### Quick Reference Checklist

**Every Module:**

- [ ] Module-level docstring at top
- [ ] One-line summary + detailed description
- [ ] Lists key components/functionality

**Every Class:**

- [ ] Class-level docstring
- [ ] Attributes section (if applicable)
- [ ] Example usage (for public APIs)
- [ ] Note section for patterns/warnings

**Every Function/Method:**

- [ ] One-line summary
- [ ] Detailed description (if needed)
- [ ] Args section (all parameters documented)
- [ ] Returns section (describes return value)
- [ ] Raises section (all possible exceptions)
- [ ] Optional: Example, Note, Warning

**Every Test Function:**

- [ ] Summary of what's tested
- [ ] "Verifies that:" section with checks
- [ ] Args section documenting all fixtures
- [ ] Optional: Scenario, Setup, Note sections

**Every Pytest Fixture:**

- [ ] Summary of fixture purpose
- [ ] Args section (dependencies)
- [ ] Returns/Yields section (what's provided)
- [ ] Cleanup section (resource cleanup)
- [ ] Example usage

### Google-Style Section Order

Standard order for sections (not all required):

1. Summary (one line)
2. Detailed description (paragraph)
3. Args
4. Returns / Yields
5. Raises
6. Note / Warning
7. Example
8. References (for complex algorithms)

### Common Patterns

Follow these patterns when writing docstrings:

- ✅ **Write docstrings first**: Define behavior before implementing (TDD for documentation)
- ✅ **Use type hints**: Always combine type annotations with docstring descriptions
- ✅ **Include examples**: Provide usage examples for complex functions and public APIs
- ✅ **Document errors**: List all possible exceptions in Raises section
- ✅ **Test docstrings**: Treat tests as first-class documentation
- ✅ **Keep current**: Update docstrings when behavior changes

**For test docstrings, use these additional sections:**

For test functions, use these additional sections:

- **Scenario:** Context/background for the test
- **Setup:** Test data preparation steps
- **Verifies that:** Specific checks performed
- **Raises:** Expected assertion failures

## Next Steps

After completing this guide, consider:

- [ ] Review existing modules and update docstrings to meet standards
- [ ] Set up automated docstring checks in CI/CD pipeline
- [ ] Create project-specific docstring templates for common patterns
- [ ] Document complex algorithms with References section
- [ ] Review [Testing Guide](testing-guide.md) for comprehensive testing documentation
- [ ] Review [Test Docstring Standards](test-docstring-standards.md) for test-specific patterns
- [ ] Verify WARP.md compliance for all new code

## References

### Official Style Guides

- [Google Python Style Guide - Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)

### Tools and Automation

- [mkdocstrings](https://mkdocstrings.github.io/) - Auto-generate docs from docstrings
- [Sphinx](https://www.sphinx-doc.org/) - Documentation builder
- [Ruff](https://docs.astral.sh/ruff/) - Fast Python linter (checks docstrings)

### Project Documentation

- WARP.md - Complete project rules and context
- [Test Docstring Standards](test-docstring-standards.md) - Test-specific patterns
- [Documentation Implementation Guide](documentation-implementation-guide.md) - MkDocs setup

---

## Document Information

**Template:** [guide-template.md](../../templates/guide-template.md)
**Created:** 2025-10-11
**Last Updated:** 2025-10-15
