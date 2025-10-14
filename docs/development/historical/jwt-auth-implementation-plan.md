# JWT Authentication Implementation Plan

**Status**: In Progress  
**Priority**: P1 (Blocks P2 features)  
**Started**: 2025-10-04  
**Estimated Completion**: When complete  

---

## Executive Summary

This document provides a detailed, phase-by-phase execution plan for implementing JWT-based user authentication in Dashtam. This replaces the current mock authentication system with production-ready user management.

**Key Decisions:**
- ✅ Full JWT + Refresh Token implementation (all 11 endpoints)
- ✅ AWS SES for email verification and password reset
- ✅ Build all features first, then update all tests together
- ✅ Phase-based execution (not timeline-based per project rules)

**Expected Outcomes:**
- Production-ready user authentication system
- Email verification and password reset flows
- Account security features (lockout, rate limiting)
- 150+ tests updated and passing
- Test coverage increased from 68% to 75%+
- Unblocks all P2 priority work

---

## Implementation Phases

### Phase 1: Database Schema & Models ⏳

**Objective**: Create the database foundation for JWT authentication.

**Tasks:**

#### 1.1 Install Dependencies
```bash
# Add AWS SES support
docker-compose exec dashtam-dev-app uv add boto3

# Verify all auth dependencies installed (should already exist)
# - pyjwt
# - python-jose[cryptography]
# - passlib[bcrypt]
```

#### 1.2 Update User Model
**File**: `src/models/user.py`

Add authentication fields:
- `password_hash: Optional[str]` - Bcrypt hash of password
- `email_verified: bool = False` - Email verification status
- `email_verified_at: Optional[datetime]` - Verification timestamp
- `failed_login_attempts: int = 0` - Failed login counter
- `account_locked_until: Optional[datetime]` - Lockout expiry
- `last_login_at: Optional[datetime]` - Last successful login
- `last_login_ip: Optional[str]` - IP of last login
- `is_active: bool = True` - Account status

Add helper methods:
- `is_locked() -> bool` - Check if account is locked
- `can_login() -> bool` - Check if user can authenticate
- `reset_failed_login_attempts()` - Clear login failures
- `increment_failed_login_attempts()` - Track failed login

**Important**: 
- All datetime fields use `DateTime(timezone=True)` for TIMESTAMPTZ
- Include field validators for timezone awareness
- Follow existing User model patterns

#### 1.3 Create Auth Models
**File**: `src/models/auth.py`

Create three new models:

**RefreshToken Model:**
- `user_id: UUID` - FK to users table
- `token_hash: str` - Bcrypt hash of refresh token (never store plain)
- `expires_at: datetime` - Token expiration (30 days)
- `is_revoked: bool = False` - Revocation status
- `revoked_at: Optional[datetime]` - When revoked
- `device_info: Optional[str]` - Device/browser info
- `ip_address: Optional[str]` - IP where issued
- `user_agent: Optional[str]` - User agent string
- `last_used_at: Optional[datetime]` - Last refresh timestamp

**EmailVerificationToken Model:**
- `user_id: UUID` - FK to users table
- `token_hash: str` - Bcrypt hash of verification token
- `expires_at: datetime` - Token expiration (24 hours)
- `used_at: Optional[datetime]` - When token was used

**PasswordResetToken Model:**
- `user_id: UUID` - FK to users table
- `token_hash: str` - Bcrypt hash of reset token
- `expires_at: datetime` - Token expiration (15 minutes)
- `used_at: Optional[datetime]` - When token was used
- `ip_address: Optional[str]` - IP of reset request
- `user_agent: Optional[str]` - User agent of request

**Important**:
- All models extend `DashtamBase` for UUID, timestamps, soft delete
- All datetime fields timezone-aware
- Add `is_expired`, `is_valid` properties
- Add `mark_as_used()` methods

#### 1.4 Create Database Migrations
**Commands:**
```bash
# Enter dev container
make dev-shell

# Create migration for user auth fields
alembic revision --autogenerate -m "add_auth_fields_to_users"

# Create migration for refresh tokens table
alembic revision --autogenerate -m "create_refresh_tokens_table"

# Create migration for verification/reset tokens
alembic revision --autogenerate -m "create_email_and_password_reset_tokens"

# Review migrations (ensure proper indexes)
cat alembic/versions/*.py

# Apply migrations
alembic upgrade head

# Verify in database
psql $DATABASE_URL -c "\d users"
psql $DATABASE_URL -c "\d refresh_tokens"
psql $DATABASE_URL -c "\d email_verification_tokens"
psql $DATABASE_URL -c "\d password_reset_tokens"
```

**Migration Checklist:**
- ✅ All datetime columns use `TIMESTAMP WITH TIME ZONE`
- ✅ Proper indexes on foreign keys
- ✅ Index on `refresh_tokens.token_hash` for lookups
- ✅ Composite index on `(user_id, is_revoked, expires_at)` for active token queries
- ✅ Index on token expiration fields for cleanup queries
- ✅ CASCADE delete on user deletion
- ✅ NOT NULL constraints on required fields

**Deliverables:**
- ✅ Updated `src/models/user.py` with auth fields
- ✅ New `src/models/auth.py` with 3 token models
- ✅ 3 Alembic migrations created and applied
- ✅ Database schema verified

---

### Phase 2: Core Services Implementation 🔄

**Objective**: Build the business logic layer for authentication.

**Tasks:**

#### 2.1 Password Service
**File**: `src/services/password_service.py`

**Implementation Requirements:**
```python
class PasswordService:
    """Service for password hashing and validation."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt (12 rounds)."""
        # Use passlib.context.CryptContext
        # bcrypt__rounds=12 (~300ms verification)
        
    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Verify password against hash."""
        
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, Optional[str]]:
        """Validate password meets complexity requirements.
        
        Returns:
            (is_valid, error_message)
        
        Requirements:
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
        """
```

**Key Features:**
- Use `passlib.context.CryptContext` with bcrypt
- Configure 12 rounds for security/performance balance
- Detailed error messages for password validation
- Google-style docstrings with type hints

#### 2.2 JWT Service
**File**: `src/services/jwt_service.py`

**Implementation Requirements:**
```python
class JWTService:
    """Service for JWT token generation and validation."""
    
    @staticmethod
    def create_access_token(user_id: UUID, email: str) -> str:
        """Create JWT access token (30 min TTL).
        
        Payload:
        - sub: user_id (subject)
        - email: user email
        - iat: issued at timestamp
        - exp: expiration timestamp
        """
        
    @staticmethod
    def create_refresh_token() -> str:
        """Create secure random refresh token (256 bits entropy)."""
        # Use secrets.token_urlsafe(32)
        
    @staticmethod
    def decode_access_token(token: str) -> Dict[str, Any]:
        """Decode and validate JWT access token.
        
        Raises:
            JWTError: If token invalid, expired, or tampered
        """
        
    @staticmethod
    def get_user_id_from_token(token: str) -> UUID:
        """Extract user_id from JWT token."""
```

**Key Features:**
- Use `python-jose` for JWT operations
- HS256 algorithm with `settings.SECRET_KEY`
- 30-minute expiry for access tokens
- Proper exception handling for expired/invalid tokens
- Timezone-aware timestamps

#### 2.3 Email Service
**File**: `src/services/email_service.py`

**Implementation Requirements:**
```python
class EmailService:
    """Service for sending emails via AWS SES."""
    
    def __init__(self):
        """Initialize AWS SES client."""
        # Use boto3 SES client
        # Check settings for AWS credentials
        # Fallback to console logging if not configured
        
    async def send_verification_email(
        self, 
        email: str, 
        name: str, 
        token: str
    ) -> bool:
        """Send email verification link."""
        # Construct verification URL
        # Send HTML email with template
        # Log to console in development
        
    async def send_password_reset_email(
        self,
        email: str,
        name: str,
        token: str
    ) -> bool:
        """Send password reset link."""
        # Construct reset URL
        # Send HTML email with template
        # Token expires in 15 minutes
```

**Key Features:**
- AWS SES integration with boto3
- HTML email templates (verification, reset)
- Console logging fallback for development
- Async operations
- Error handling and logging
- Rate limiting awareness

**AWS SES Configuration:**
Add to `src/core/config.py`:
```python
# AWS SES Configuration
AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None)
AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None)
AWS_SES_REGION: str = Field(default="us-east-1")
AWS_SES_SENDER_EMAIL: str = Field(default="noreply@dashtam.com")
AWS_SES_ENABLED: bool = Field(default=False)
```

#### 2.4 Auth Service
**File**: `src/services/auth_service.py`

**Implementation Requirements:**
```python
class AuthService:
    """Service for user authentication and token management."""
    
    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session
        self.password_service = PasswordService()
        self.jwt_service = JWTService()
        self.email_service = EmailService()
    
    async def register_user(
        self, 
        email: str, 
        password: str, 
        name: str
    ) -> tuple[User, str]:
        """Register new user and send verification email.
        
        Returns:
            (user, verification_token)
        
        Raises:
            ValueError: If email exists or password invalid
        """
        
    async def authenticate_user(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> Optional[User]:
        """Authenticate user with email/password.
        
        Handles:
        - Account lockout after 10 failed attempts
        - Password verification
        - Login tracking
        
        Returns:
            User if successful, None if failed
        """
        
    async def create_auth_tokens(
        self,
        user: User,
        device_info: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create access and refresh tokens for user.
        
        Returns:
            {
                "access_token": jwt_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": 1800
            }
        """
        
    async def refresh_access_token(
        self,
        refresh_token: str
    ) -> Dict[str, Any]:
        """Refresh access token with token rotation.
        
        - Validates refresh token
        - Generates new access + refresh tokens
        - Revokes old refresh token
        - Returns new token pair
        """
        
    async def logout(
        self,
        refresh_token: str
    ) -> None:
        """Logout user by revoking refresh token."""
        
    async def verify_email(
        self,
        token: str
    ) -> Optional[User]:
        """Verify user email with token."""
        
    async def request_password_reset(
        self,
        email: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """Send password reset email."""
        
    async def reset_password(
        self,
        token: str,
        new_password: str
    ) -> bool:
        """Reset password with token."""
```

**Key Features:**
- All async operations
- Comprehensive error handling
- Audit logging for security events
- Account lockout (10 attempts = 1 hour)
- Token rotation on refresh
- Email verification and password reset
- Transaction management (commit/rollback)

**Deliverables:**
- ✅ `src/services/password_service.py` - Password hashing/validation
- ✅ `src/services/jwt_service.py` - JWT token operations
- ✅ `src/services/email_service.py` - AWS SES email sending
- ✅ `src/services/auth_service.py` - Complete auth logic
- ✅ Updated `src/core/config.py` with AWS SES settings
- ✅ All services with Google-style docstrings

---

### Phase 3: API Endpoints Implementation 🔄

**Objective**: Create the API layer for user authentication.

**Tasks:**

#### 3.1 Create Request/Response Models
**File**: `src/api/v1/schemas/auth_schemas.py`

**Required Schemas:**
```python
# Request Models
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class VerifyEmailRequest(BaseModel):
    token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None

# Response Models
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    email_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
class MessageResponse(BaseModel):
    message: str
```

#### 3.2 Create Auth Router
**File**: `src/api/v1/user_auth.py`

**Implement 11 Endpoints:**

1. **POST `/api/v1/auth/signup`** - User Registration
   - Validate email format and password strength
   - Check email doesn't exist
   - Create user with hashed password
   - Generate verification token
   - Send verification email
   - Return success message

2. **POST `/api/v1/auth/login`** - User Login
   - Validate credentials
   - Check account not locked
   - Check email verified (or allow with warning)
   - Generate JWT access + refresh tokens
   - Update last_login timestamp
   - Return tokens

3. **POST `/api/v1/auth/refresh`** - Refresh Access Token
   - Validate refresh token
   - Check not expired or revoked
   - Generate new access token
   - Rotate refresh token (generate new, revoke old)
   - Return new token pair

4. **POST `/api/v1/auth/logout`** - Logout User
   - Validate refresh token
   - Revoke token in database
   - Return success message

5. **POST `/api/v1/auth/verify-email`** - Verify Email
   - Validate verification token
   - Check not expired or used
   - Mark email as verified
   - Mark token as used
   - Return success message

6. **POST `/api/v1/auth/resend-verification`** - Resend Verification Email
   - Check user exists
   - Check email not already verified
   - Generate new token
   - Send verification email
   - Return success message

7. **POST `/api/v1/auth/forgot-password`** - Request Password Reset
   - Check user exists
   - Generate reset token (15 min expiry)
   - Send reset email
   - Return success message (even if email doesn't exist - security)

8. **POST `/api/v1/auth/reset-password`** - Reset Password
   - Validate reset token
   - Check not expired or used
   - Validate new password strength
   - Update password
   - Mark token as used
   - Revoke all refresh tokens (force re-login)
   - Return success message

9. **GET `/api/v1/auth/profile`** - Get Current User Profile
   - Requires JWT authentication
   - Extract user from token
   - Return user profile

10. **PUT `/api/v1/auth/profile`** - Update User Profile
    - Requires JWT authentication
    - Validate changes
    - Update user record
    - Return updated profile

11. **PUT `/api/v1/auth/change-password`** - Change Password
    - Requires JWT authentication
    - Verify current password
    - Validate new password
    - Update password
    - Revoke all refresh tokens (force re-login on all devices)
    - Return success message

#### 3.3 Update Authentication Dependency
**File**: `src/api/v1/auth.py` (existing OAuth endpoints file)

**Rename to**: `src/api/v1/oauth.py` (for clarity)

**Update `get_current_user()` dependency:**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.database import get_session
from src.models.user import User
from src.services.jwt_service import JWTService

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """Get current authenticated user from JWT token.
    
    Validates JWT access token and returns user object.
    
    Args:
        credentials: HTTP Authorization header with Bearer token
        session: Database session
        
    Returns:
        User object if token valid
        
    Raises:
        HTTPException: 401 if token invalid, expired, or user not found
    """
    try:
        # Decode JWT token
        user_id = JWTService.get_user_id_from_token(credentials.credentials)
        
        # Get user from database
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account inactive"
            )
        
        return user
        
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

#### 3.4 Update Main Application
**File**: `src/main.py`

**Register new router:**
```python
from src.api.v1 import user_auth, oauth, providers

app.include_router(
    user_auth.router,
    prefix=settings.API_V1_PREFIX + "/auth",
    tags=["Authentication"]
)

app.include_router(
    oauth.router,  # Renamed from auth.router
    prefix=settings.API_V1_PREFIX + "/oauth",  # Changed from /auth
    tags=["OAuth Providers"]
)
```

**Deliverables:**
- ✅ `src/api/v1/schemas/auth_schemas.py` - Request/response models
- ✅ `src/api/v1/user_auth.py` - 11 auth endpoints
- ✅ Updated `get_current_user()` dependency with JWT validation
- ✅ Renamed `src/api/v1/auth.py` → `src/api/v1/oauth.py`
- ✅ Updated `src/main.py` router registration
- ✅ OpenAPI docs updated automatically

---

### Phase 4: Comprehensive Testing 🔄

**Objective**: Add complete test coverage for authentication system.

**Tasks:**

#### 4.1 Unit Tests - Password Service
**File**: `tests/unit/services/test_password_service.py`

**Test Cases (8+ tests):**
- `test_hash_password_returns_different_hash` - Same password hashes differently
- `test_verify_password_correct` - Valid password verification
- `test_verify_password_incorrect` - Invalid password rejection
- `test_validate_password_strength_valid` - Valid password passes
- `test_validate_password_strength_too_short` - < 8 chars rejected
- `test_validate_password_strength_no_uppercase` - Missing uppercase rejected
- `test_validate_password_strength_no_lowercase` - Missing lowercase rejected
- `test_validate_password_strength_no_digit` - Missing digit rejected
- `test_validate_password_strength_no_special` - Missing special char rejected

#### 4.2 Unit Tests - JWT Service
**File**: `tests/unit/services/test_jwt_service.py`

**Test Cases (10+ tests):**
- `test_create_access_token` - Token generation
- `test_decode_access_token_valid` - Valid token decode
- `test_decode_access_token_expired` - Expired token rejection
- `test_decode_access_token_invalid_signature` - Tampered token rejection
- `test_decode_access_token_malformed` - Invalid format rejection
- `test_create_refresh_token_unique` - Tokens are unique
- `test_create_refresh_token_entropy` - Sufficient randomness
- `test_get_user_id_from_token` - User ID extraction
- `test_token_contains_expected_claims` - Payload validation
- `test_token_expiration_timestamp` - Expiry calculation

#### 4.3 Unit Tests - Auth Service
**File**: `tests/unit/services/test_auth_service.py`

**Test Cases (20+ tests):**
- `test_register_user_success` - Successful registration
- `test_register_user_duplicate_email` - Duplicate email rejection
- `test_register_user_weak_password` - Weak password rejection
- `test_authenticate_user_success` - Successful login
- `test_authenticate_user_wrong_password` - Wrong password rejection
- `test_authenticate_user_nonexistent_email` - Non-existent user
- `test_authenticate_user_account_locked` - Locked account rejection
- `test_authenticate_user_increments_failed_attempts` - Failed attempt tracking
- `test_authenticate_user_locks_after_10_attempts` - Account lockout
- `test_authenticate_user_resets_failed_attempts_on_success` - Counter reset
- `test_create_auth_tokens` - Token creation
- `test_refresh_access_token_success` - Token refresh
- `test_refresh_access_token_expired` - Expired token rejection
- `test_refresh_access_token_revoked` - Revoked token rejection
- `test_refresh_access_token_rotation` - Old token revoked
- `test_logout_revokes_token` - Logout functionality
- `test_verify_email_success` - Email verification
- `test_verify_email_expired_token` - Expired token rejection
- `test_verify_email_already_used` - Used token rejection
- `test_request_password_reset` - Reset request
- `test_reset_password_success` - Password reset
- `test_reset_password_expired_token` - Expired token rejection

#### 4.4 Integration Tests - Auth Flow
**File**: `tests/integration/test_auth_flow.py`

**Test Cases (15+ tests):**
- `test_complete_signup_login_flow` - End-to-end happy path
- `test_signup_verify_login` - With email verification
- `test_login_refresh_logout` - Token lifecycle
- `test_password_reset_flow` - Complete reset flow
- `test_account_lockout_flow` - Lockout and unlock
- `test_token_expiration_handling` - Expired token behavior
- `test_multiple_device_sessions` - Multiple refresh tokens
- `test_logout_all_devices` - Revoke all tokens
- `test_change_password_revokes_tokens` - Security on password change
- `test_profile_update` - Profile management
- `test_resend_verification` - Resend verification email
- `test_concurrent_login_attempts` - Race conditions
- `test_token_reuse_prevention` - Replay attack prevention
- `test_invalid_token_format` - Malformed token handling
- `test_sql_injection_prevention` - Security testing

#### 4.5 API Endpoint Tests
**File**: `tests/api/v1/test_user_auth.py`

**Test Cases (11+ endpoint tests):**
- `test_signup_endpoint` - POST /auth/signup
- `test_login_endpoint` - POST /auth/login
- `test_refresh_endpoint` - POST /auth/refresh
- `test_logout_endpoint` - POST /auth/logout
- `test_verify_email_endpoint` - POST /auth/verify-email
- `test_resend_verification_endpoint` - POST /auth/resend-verification
- `test_forgot_password_endpoint` - POST /auth/forgot-password
- `test_reset_password_endpoint` - POST /auth/reset-password
- `test_get_profile_endpoint` - GET /auth/profile
- `test_update_profile_endpoint` - PUT /auth/profile
- `test_change_password_endpoint` - PUT /auth/change-password

Plus error case tests:
- `test_login_without_verification` - Unverified email handling
- `test_endpoints_require_authentication` - 401 without token
- `test_invalid_token_format` - 401 for bad tokens
- `test_rate_limiting` - Rate limit enforcement

**Test Infrastructure:**
Create helper fixtures in `tests/conftest.py`:
```python
@pytest.fixture
async def auth_service(test_session):
    """Auth service fixture."""
    return AuthService(test_session)

@pytest.fixture
async def test_user(test_session):
    """Create test user with verified email."""
    user = User(
        email="test@example.com",
        name="Test User",
        password_hash=PasswordService.hash_password("TestPass123!"),
        email_verified=True,
        is_active=True
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user

@pytest.fixture
async def auth_tokens(test_user):
    """Generate auth tokens for test user."""
    access_token = JWTService.create_access_token(
        user_id=test_user.id,
        email=test_user.email
    )
    refresh_token = JWTService.create_refresh_token()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }

@pytest.fixture
async def authenticated_client(client, auth_tokens):
    """Test client with authentication headers."""
    client.headers = {
        "Authorization": f"Bearer {auth_tokens['access_token']}"
    }
    return client
```

**Deliverables:**
- ✅ `tests/unit/services/test_password_service.py` - 8+ tests
- ✅ `tests/unit/services/test_jwt_service.py` - 10+ tests
- ✅ `tests/unit/services/test_auth_service.py` - 20+ tests
- ✅ `tests/integration/test_auth_flow.py` - 15+ tests
- ✅ `tests/api/v1/test_user_auth.py` - 11+ tests
- ✅ Updated `tests/conftest.py` with auth fixtures
- ✅ All new tests passing (60+ new tests)

---

### Phase 5: Migration & Integration 🔄

**Objective**: Update existing codebase to use JWT authentication.

**Tasks:**

#### 5.1 Update Test Infrastructure
**File**: `tests/conftest.py`

**Add JWT fixtures:**
```python
@pytest.fixture
async def create_authenticated_user(test_session):
    """Factory to create authenticated users."""
    async def _create_user(
        email: str = "test@example.com",
        password: str = "TestPass123!",
        verified: bool = True
    ):
        user = User(
            email=email,
            name="Test User",
            password_hash=PasswordService.hash_password(password),
            email_verified=verified,
            is_active=True
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)
        
        # Generate tokens
        access_token = JWTService.create_access_token(user.id, user.email)
        refresh_token = JWTService.create_refresh_token()
        
        # Store refresh token
        rt = RefreshToken(
            user_id=user.id,
            token_hash=PasswordService.hash_password(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        test_session.add(rt)
        await test_session.commit()
        
        return user, access_token, refresh_token
    
    return _create_user

@pytest.fixture
async def auth_headers(create_authenticated_user):
    """Create authentication headers for API requests."""
    user, access_token, _ = await create_authenticated_user()
    return {
        "Authorization": f"Bearer {access_token}"
    }
```

#### 5.2 Update All Existing Tests (122+ tests)

**Strategy:**
1. Identify all tests that use `get_current_user` dependency
2. Update to include authentication headers
3. Replace mock user creation with authenticated user fixtures
4. Ensure tests still pass

**Files to Update:**
```bash
# Find all test files that use authentication
grep -r "get_current_user" tests/

# Expected files:
# - tests/integration/test_provider_operations.py
# - tests/api/v1/test_providers.py
# - tests/api/v1/test_oauth.py (renamed from test_auth.py)
# - Any other files using current_user
```

**Example Update:**
```python
# Before (mock auth)
async def test_create_provider(client):
    response = await client.post("/api/v1/providers/create", json={...})
    assert response.status_code == 200

# After (JWT auth)
async def test_create_provider(client, auth_headers):
    response = await client.post(
        "/api/v1/providers/create",
        json={...},
        headers=auth_headers
    )
    assert response.status_code == 200
```

**Batch Update Script:**
Create `tests/scripts/update_tests_for_auth.py`:
```python
"""Script to help update tests for JWT authentication."""
import os
import re
from pathlib import Path

def update_test_file(filepath):
    """Update test file to use JWT auth."""
    # Read file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add auth_headers fixture to test functions
    # Update client calls to include headers
    # ... automated updates ...
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)

# Run on all test files
test_dir = Path("tests")
for test_file in test_dir.rglob("test_*.py"):
    update_test_file(test_file)
```

#### 5.3 Remove Mock Authentication

**Update**: `src/api/v1/oauth.py` (renamed from auth.py)

**Remove old `get_current_user()` implementation:**
```python
# DELETE THIS:
async def get_current_user(session: AsyncSession = Depends(get_session)) -> User:
    """Mock authentication - returns test user."""
    result = await session.execute(
        select(User).where(User.email == "test@example.com")
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(email="test@example.com", name="Test User", is_verified=True)
        session.add(user)
        await session.commit()
    return user
```

**Import from shared location:**
```python
from src.api.v1.dependencies import get_current_user
```

**Create**: `src/api/v1/dependencies.py`
```python
"""Shared API dependencies."""
# Move JWT-based get_current_user here
# Used by both oauth.py and user_auth.py
```

#### 5.4 Update Environment Configuration

**Update**: `.env.example`
```bash
# Add AWS SES configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_SES_REGION=us-east-1
AWS_SES_SENDER_EMAIL=noreply@dashtam.com
AWS_SES_ENABLED=true

# JWT Configuration (already exists)
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
```

**Update**: `README.md`
```markdown
## AWS SES Setup

To enable email verification and password reset:

1. Create AWS account and verify SES domain
2. Set environment variables:
   - AWS_ACCESS_KEY_ID
   - AWS_SECRET_ACCESS_KEY
   - AWS_SES_REGION
   - AWS_SES_SENDER_EMAIL

For development, emails will log to console if AWS_SES_ENABLED=false
```

**Deliverables:**
- ✅ Updated `tests/conftest.py` with JWT fixtures
- ✅ All 122+ existing tests updated to use JWT auth
- ✅ Removed mock authentication from `src/api/v1/oauth.py`
- ✅ Created `src/api/v1/dependencies.py` for shared dependencies
- ✅ Updated `.env.example` with AWS SES config
- ✅ Updated README.md with setup instructions
- ✅ All 180+ tests passing (122 existing + 60 new)

---

### Phase 6: Documentation & Verification ✅

**Objective**: Complete documentation and verify production-readiness.

**Tasks:**

#### 6.1 Update API Documentation

**OpenAPI/Swagger** (Auto-generated by FastAPI):
- Verify all 11 endpoints visible in `/docs`
- Add detailed descriptions and examples
- Document all error responses
- Add authentication flow diagram

**Update endpoint docstrings:**
```python
@router.post("/signup", response_model=MessageResponse)
async def signup(
    request: SignupRequest,
    session: AsyncSession = Depends(get_session)
):
    """Register a new user account.
    
    Creates a new user with hashed password and sends email verification link.
    User must verify email before accessing protected resources.
    
    **Request Body:**
    - email: Valid email address (unique)
    - password: Minimum 8 characters, must include uppercase, lowercase, digit, special char
    - name: User's full name
    
    **Success Response:**
    - 201 Created
    - Returns: Success message
    
    **Error Responses:**
    - 400 Bad Request: Email already exists or password too weak
    - 500 Internal Server Error: Database or email service error
    
    **Example:**
    ```json
    {
        "email": "user@example.com",
        "password": "SecurePass123!",
        "name": "John Doe"
    }
    ```
    """
```

#### 6.2 Update Project Documentation

**Create**: `docs/development/guides/authentication.md`
```markdown
# User Authentication Guide

Complete guide to JWT authentication in Dashtam.

## Overview
- JWT + Refresh Token architecture
- Email verification required
- Password reset via AWS SES
- Account lockout protection

## Authentication Flow
[Diagram of complete flow]

## API Endpoints
[Detailed documentation of all 11 endpoints]

## Security Features
[Account lockout, token rotation, password requirements]

## Development Setup
[AWS SES configuration, testing]

## Production Deployment
[Security checklist, monitoring]
```

**Update**: `WARP.md`
```markdown
### User Authentication Status ✅ COMPLETE (2025-10-04)

**Implementation:**
- ✅ JWT + Refresh Token authentication
- ✅ 11 auth endpoints (signup, login, refresh, logout, etc.)
- ✅ Email verification via AWS SES
- ✅ Password reset flow
- ✅ Account security (lockout, rate limiting)
- ✅ 180+ tests passing (68% → 75% coverage)

**Details:**
- JWT access tokens: 30 min TTL
- Refresh tokens: 30 day TTL with rotation
- Password: bcrypt hashing (12 rounds)
- Email: AWS SES integration
- Security: Account lockout after 10 failed attempts

**Documentation:**
- Implementation guide: `docs/development/guides/authentication.md`
- API reference: `https://localhost:8000/docs`
```

**Update**: `docs/development/architecture/improvement-guide.md`
```markdown
### ~~5. User Authentication System (JWT)~~ ✅ RESOLVED

**Status**: ✅ **COMPLETED 2025-10-04**  
**Resolution**: Full JWT + Refresh Token authentication implemented

**What Was Done**:
- ✅ Database schema (4 tables: users extended, refresh_tokens, email_verification_tokens, password_reset_tokens)
- ✅ Service layer (PasswordService, JWTService, EmailService, AuthService)
- ✅ API layer (11 endpoints for complete auth flow)
- ✅ Security features (account lockout, token rotation, password complexity)
- ✅ AWS SES email integration
- ✅ 60+ new tests added
- ✅ 122+ existing tests migrated to JWT auth
- ✅ Test coverage increased from 68% to 75%+

**Impact**:
- ✅ Production-ready user authentication
- ✅ Unblocked all P2 work (rate limiting, token breach rotation)
- ✅ Can onboard real users
- ✅ SOC 2 / PCI-DSS compliant baseline
```

#### 6.3 Final Verification

**Run Complete Test Suite:**
```bash
# In Docker container
make test

# Expected results:
# - 180+ tests passing
# - 75%+ code coverage
# - 0 failures
# - All auth tests green
```

**Manual Testing Checklist:**
```bash
# 1. Signup flow
curl -X POST https://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!","name":"Test User"}'

# 2. Check email (console or AWS SES)
# Click verification link or use token

# 3. Verify email
curl -X POST https://localhost:8000/api/v1/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"token":"verification_token_here"}'

# 4. Login
curl -X POST https://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!"}'

# 5. Use access token
curl -X GET https://localhost:8000/api/v1/auth/profile \
  -H "Authorization: Bearer <access_token>"

# 6. Refresh token
curl -X POST https://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"refresh_token_here"}'

# 7. Logout
curl -X POST https://localhost:8000/api/v1/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"refresh_token_here"}'
```

**Performance Testing:**
```bash
# Login should complete < 500ms
time curl -X POST https://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!"}'

# Token verification should be < 100ms
time curl -X GET https://localhost:8000/api/v1/auth/profile \
  -H "Authorization: Bearer <token>"
```

#### 6.4 Security Verification Checklist

**Password Security:**
- ✅ Passwords hashed with bcrypt (12 rounds)
- ✅ Plain passwords never logged
- ✅ Password complexity enforced
- ✅ Password history not implemented (future P2)

**Token Security:**
- ✅ Access tokens expire in 30 minutes
- ✅ Refresh tokens expire in 30 days
- ✅ Refresh token rotation on use
- ✅ Tokens properly signed with SECRET_KEY
- ✅ Old refresh tokens revoked on rotation

**Account Security:**
- ✅ Account lockout after 10 failed attempts
- ✅ 1-hour lockout duration
- ✅ Failed attempts reset on successful login
- ✅ Account lockout status visible

**Email Security:**
- ✅ Verification tokens expire in 24 hours
- ✅ Reset tokens expire in 15 minutes
- ✅ Tokens are one-time use
- ✅ Tokens properly hashed in database

**API Security:**
- ✅ All protected endpoints require JWT
- ✅ Expired tokens rejected
- ✅ Invalid tokens rejected
- ✅ SQL injection prevention verified
- ✅ Rate limiting implemented (future P2)

**Deliverables:**
- ✅ Updated OpenAPI documentation
- ✅ Created `docs/development/guides/authentication.md`
- ✅ Updated `WARP.md` with auth status
- ✅ Updated `docs/development/architecture/improvement-guide.md`
- ✅ All 180+ tests passing
- ✅ Manual testing verified
- ✅ Performance benchmarks met
- ✅ Security checklist complete

---

## Success Criteria

**Phase Completion:**
- ✅ Phase 1: Database schema and models created
- ✅ Phase 2: All 4 services implemented
- ✅ Phase 3: All 11 API endpoints working
- ✅ Phase 4: 60+ new tests passing
- ✅ Phase 5: 122+ existing tests migrated
- ✅ Phase 6: Documentation complete

**Quantitative Metrics:**
- ✅ 180+ total tests passing
- ✅ 75%+ code coverage
- ✅ 0 test failures
- ✅ Login performance < 500ms
- ✅ Token validation < 100ms

**Qualitative Metrics:**
- ✅ Production-ready authentication system
- ✅ Can onboard real users
- ✅ Unblocks P2 priorities
- ✅ SOC 2 / PCI-DSS compliant baseline
- ✅ Clear documentation for future developers

---

## Next Steps After Completion

**Immediate (P2 Priorities - Unblocked):**
1. Rate limiting (requires real user auth) ✅ Unblocked
2. Token breach rotation (requires real user auth) ✅ Unblocked
3. Enhanced audit logging with user context ✅ Unblocked

**Near-term Enhancements (Q1 2026):**
1. Social authentication (Google, Apple)
2. MFA/2FA support (TOTP)
3. Session management dashboard
4. Email notification preferences

**Long-term (Q2-Q3 2026):**
1. Passkeys/WebAuthn support
2. Advanced security features (device fingerprinting)
3. Enterprise SSO (SAML, OIDC)

---

## Rollback Plan

If critical issues discovered after deployment:

**Database Rollback:**
```bash
# Revert migrations
alembic downgrade -1  # One step back
alembic downgrade <previous_revision>  # Specific revision
```

**Code Rollback:**
```bash
# Revert to previous commit
git revert <commit_hash>
git push origin development
```

**Quick Fixes:**
- Disable email verification requirement (allow login without verification)
- Extend token expiration if causing UX issues
- Disable account lockout if too aggressive
- Fall back to console email logging if AWS SES issues

---

## Contact & Resources

**Primary Documentation:**
- Implementation guide: `docs/development/guides/authentication-implementation.md`
- API reference: `https://localhost:8000/docs`
- Quick reference: `docs/development/guides/auth-quick-reference.md`

**Dependencies Documentation:**
- FastAPI Security: https://fastapi.tiangolo.com/tutorial/security/
- PyJWT: https://pyjwt.readthedocs.io/
- Passlib: https://passlib.readthedocs.io/
- AWS SES: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ses.html

**Support:**
- GitHub Issues: Project issues tracker
- Development team: Internal communication channels

---

**Document Version**: 1.0  
**Last Updated**: 2025-10-04  
**Status**: Ready for Execution  
**Estimated Total Effort**: Implementation complete when all phases done
