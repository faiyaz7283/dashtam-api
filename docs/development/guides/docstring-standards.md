# Docstring Standards Guide

**Comprehensive guide for Python documentation across the entire Dashtam codebase:**

**Last Updated:** 2025-10-11  
**Applies To:** All Python files (src/, tests/, scripts/)  
**Format:** Google-style docstrings (WARP.md requirement)

---

## 📖 Table of Contents

- [Why Google-Style Docstrings?](#why-google-style-docstrings)
- [General Python Standards](#general-python-standards)
  - [Module-Level Docstrings](#module-level-docstrings)
  - [Class Docstrings](#class-docstrings)
  - [Function/Method Docstrings](#functionmethod-docstrings)
- [Application-Specific Patterns](#application-specific-patterns)
  - [FastAPI Endpoints](#fastapi-endpoints)
  - [Service Layer](#service-layer)
  - [SQLModel/Pydantic Models](#sqlmodelpydantic-models)
  - [Database Operations](#database-operations)
- [Test Documentation Standards](#test-documentation-standards)
  - [Test Module Docstrings](#test-module-docstrings)
  - [Test Class Docstrings](#test-class-docstrings)
  - [Test Function Docstrings](#test-function-docstrings)
  - [Pytest Fixtures](#pytest-fixtures)
- [Common Patterns](#common-patterns)
- [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
- [Development Workflow](#development-workflow)
- [Quick Reference](#quick-reference)

---

## Why Google-Style Docstrings?

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

---

## General Python Standards

### Module-Level Docstrings

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

### Class Docstrings

All classes MUST have comprehensive docstrings explaining their purpose, responsibilities, and usage:

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

### Function/Method Docstrings

All public functions and methods MUST have comprehensive docstrings:

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

---

## Application-Specific Patterns

### FastAPI Endpoints

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

### Service Layer

Service classes contain business logic and orchestration:

```python
async def refresh_access_token(
    self,
    refresh_token_str: str,
    device_info: Optional[str] = None
) -> tuple[str, str]:
    """Refresh JWT access token using refresh token with rotation.
    
    Validates refresh token, generates new access token, and rotates
    refresh token for enhanced security. Updates session tracking with
    device information and last activity timestamp.
    
    Token Rotation:
        Per security best practices, refresh tokens are rotated on each use.
        Old refresh token is invalidated and new one is issued. This prevents
        replay attacks and limits token exposure window.
    
    Args:
        refresh_token_str: Raw refresh token string from client
        device_info: Optional device/browser information for session tracking
    
    Returns:
        tuple[str, str]: New access token and new refresh token
            - access_token: JWT with 30 min expiry
            - refresh_token: New opaque token with 30 days expiry
    
    Raises:
        HTTPException: 401 if refresh token invalid, expired, or revoked
        HTTPException: 401 if user account is locked or deleted
    
    Note:
        Old refresh token is immediately revoked after validation.
        Client MUST store the new refresh token for future refreshes.
        Token rotation helps detect token theft (multiple uses = alert).
    
    Example:
        >>> new_access, new_refresh = await auth_service.refresh_access_token(
        ...     old_refresh_token,
        ...     device_info="Chrome 120 on macOS"
        ... )
        >>> # Client must replace old refresh token with new_refresh
    """
```

### SQLModel/Pydantic Models

#### Database Models

```python
class RefreshToken(SQLModel, table=True):
    """Refresh token for JWT authentication with rotation tracking.
    
    Stores hashed refresh tokens with device/session tracking. Supports
    token rotation for enhanced security. Tokens are revoked on use or
    when user logs out.
    
    Attributes:
        id: Unique token identifier (UUID, primary key)
        user_id: Owner of this token (foreign key to users.id)
        token_hash: Bcrypt hash of token string (one-way, not reversible)
        device_info: Device/browser information (e.g., "Chrome 120 macOS")
        ip_address: IP address where token was issued
        expires_at: Expiration timestamp (30 days from creation)
        revoked: Whether token has been invalidated
        revoked_at: When token was revoked (nullable)
        last_used_at: Last time token was used for refresh
        created_at: Token creation timestamp
    
    Relationships:
        user: User who owns this token (many-to-one)
    
    Security:
        - Token string hashed with bcrypt before storage (irreversible)
        - Tokens rotated on each use (old token revoked)
        - Tracks device and IP for fraud detection
        - Revoked tokens cannot be reused
    
    Note:
        Token rotation means clients MUST update stored refresh token
        after each refresh operation. Using old token after rotation
        may indicate token theft.
    """
```

#### Response Schemas

```python
class LoginResponse(BaseModel):
    """Response schema for successful login.
    
    Contains JWT tokens and user profile data. Client must store both
    tokens securely (access token for API calls, refresh token for
    obtaining new access tokens).
    
    Attributes:
        access_token: JWT access token (30 min expiry)
        refresh_token: Opaque refresh token (30 days expiry)
        token_type: Token type, always "bearer"
        expires_in: Access token lifetime in seconds (1800 = 30 min)
        user: User profile data (id, email, verified status)
    
    Example:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIs...",
            "refresh_token": "8f3d2c1b-9a7e-4f6d-8c5b-1a2d3e4f5g6h",
            "token_type": "bearer",
            "expires_in": 1800,
            "user": {
                "id": "a1b2c3d4-...",
                "email": "user@example.com",
                "email_verified": true
            }
        }
    
    Note:
        Client should store access_token in memory (not localStorage for XSS safety)
        and refresh_token in httpOnly cookie or secure storage.
    """
```

### Database Operations

Functions performing database queries need comprehensive documentation:

```python
async def get_user_by_email(
    email: str,
    session: AsyncSession
) -> Optional[User]:
    """Retrieve user by email address.
    
    Performs case-insensitive email lookup. Returns None if user not found
    or has been soft-deleted.
    
    Args:
        email: User's email address (case-insensitive)
        session: AsyncSession for database query
    
    Returns:
        Optional[User]: User instance if found, None otherwise
    
    Note:
        Uses selectinload to eagerly load relationships.
        Email comparison is case-insensitive for user convenience.
        Soft-deleted users (deleted_at != NULL) are excluded.
    
    Example:
        >>> user = await get_user_by_email("USER@example.com", session)
        >>> if user:
        ...     print(f"Found user {user.id}")
        ... else:
        ...     print("User not found")
    """
```

---

## Test Documentation Standards

Tests are **documentation of expected behavior**. Comprehensive test docstrings are critical for:

- Understanding what's being tested without reading implementation
- Debugging test failures quickly
- Onboarding new developers
- Maintaining tests during refactoring

### Test Module Docstrings

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

### Test Class Docstrings

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

### Test Function Docstrings

#### Standard Test Pattern

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

#### Test with Mocks

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

#### Parametrized Test Pattern

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

### Pytest Fixtures

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

---

## Common Patterns

### Setup/Teardown Methods

```python
def setup_method(self):
    """Set up test fixtures before each test method.
    
    Initializes:
        - JWTService instance with test configuration
        - Test user ID (UUID)
        - Test email address
        - Mock session and services
    
    Note:
        Called automatically before each test method in the class.
        Use this for per-test initialization that's too complex for fixtures.
    """
```

### Async Helper Functions

```python
async def create_test_token(
    user_id: UUID,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token for testing.
    
    Generates a valid JWT token with minimal claims for test purposes.
    Useful for testing authenticated endpoints without full auth flow.
    
    Args:
        user_id: User ID to include in token claims
        expires_delta: Optional custom expiration (default: 30 min)
    
    Returns:
        str: Signed JWT token string
    
    Note:
        Uses test secret key (not production key).
        Token is valid for 30 minutes by default.
    
    Example:
        >>> token = await create_test_token(user.id)
        >>> headers = {"Authorization": f"Bearer {token}"}
        >>> response = client.get("/auth/me", headers=headers)
    """
```

### Context Manager Classes

```python
class DatabaseTransaction:
    """Context manager for atomic database operations.
    
    Ensures database operations are committed on success or rolled back
    on exception. Useful for operations requiring multiple queries.
    
    Attributes:
        session: AsyncSession for database operations
        committed: Whether transaction was successfully committed
    
    Example:
        async with DatabaseTransaction(session) as tx:
            user = await tx.create_user(email, password)
            await tx.send_verification_email(user)
            # Auto-commits on successful exit
            # Auto-rollback on exception
    
    Note:
        Always use as async context manager (async with).
        Don't manually commit/rollback inside the context.
    """
```

---

## Anti-Patterns to Avoid

### ❌ Too Brief (Insufficient)

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

### ❌ Missing Fixture Documentation

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

### ❌ Implementation Instead of Intent

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

### ❌ Missing Error Documentation

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

### ❌ Missing Type Information

```python
def create_token(user_id, expires_in):
    """Create JWT token."""
    # MISSING: Type hints and arg descriptions
```

**✅ Correct Version:**

```python
def create_token(user_id: UUID, expires_in: int) -> str:
    """Create JWT access token for user.
    
    Args:
        user_id: Unique user identifier
        expires_in: Token lifetime in seconds
    
    Returns:
        str: Signed JWT token string
    """
```

---

## Development Workflow

### When Writing New Code

1. **Write docstring FIRST** (TDD for documentation)
   - Define what the function/class does
   - Specify inputs, outputs, and errors
   - Document security/performance considerations

2. **Implement the code** to match the docstring specification

3. **Update docstring** if implementation changes behavior

### When Reviewing Code

Check docstrings for:

- [ ] Completeness (all sections present)
- [ ] Accuracy (matches actual behavior)
- [ ] Clarity (easy to understand)
- [ ] Examples (for complex functions)
- [ ] Type hints match docstring descriptions

### Before Committing

Run these commands to verify code quality:

```bash
# Lint code (includes docstring checks)
make lint

# Format code (auto-formats docstrings)
make format

# Run tests (validates docstring examples if using doctest)
make test
```

### During PR Reviews

Docstring checklist for reviewers:

- [ ] All new functions/classes have docstrings
- [ ] Args/Returns sections match function signature
- [ ] Raises section lists all possible exceptions
- [ ] Examples provided for public APIs
- [ ] Note sections explain gotchas/limitations
- [ ] Test docstrings explain what's verified

---

## Quick Reference

### Checklist for Complete Docstrings

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

### Testing-Specific Sections

For test functions, use these additional sections:

- **Scenario:** Context/background for the test
- **Setup:** Test data preparation steps
- **Verifies that:** Specific checks performed
- **Raises:** Expected assertion failures

---

## Integration with WARP.md

This guide implements the following WARP.md requirements:

- ✅ **Google-style docstrings:** All code uses Google-style format
- ✅ **Comprehensive documentation:** Functions, classes, modules, tests
- ✅ **Type hints:** Always paired with docstring descriptions
- ✅ **Test documentation:** Tests are treated as first-class documentation
- ✅ **Code quality:** Docstrings checked by `make lint`

**See Also:**

- WARP.md - Project rules and coding standards
- [Testing Guide](../testing/guide.md) - Complete testing documentation
- [Best Practices](../testing/best-practices.md) - Testing best practices

---

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
- [Test Docstring Standards](../testing/test-docstring-standards.md) - Test-specific patterns
- [Documentation Implementation Guide](documentation-implementation-guide.md) - MkDocs setup

---

**Last Updated:** 2025-10-11  
**Maintained By:** Development Team  
**Review Schedule:** Quarterly or when adding new patterns
