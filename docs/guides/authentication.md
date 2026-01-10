# Authentication Usage Guide

Quick reference guide for developers implementing authentication flows in Dashtam.

**Target Audience**: Developers building API endpoints and integrating authentication

**Related Documentation**:

- Architecture: `docs/architecture/authentication.md` (why/what)
- Session Management: `docs/guides/sessions.md`
- Authorization: `docs/guides/authorization.md`

---

## Quick Reference

| Operation | Endpoint | Method | Auth Required |
|-----------|----------|--------|---------------|
| Register | `/api/v1/users` | POST | No |
| Login | `/api/v1/sessions` | POST | No |
| Logout | `/api/v1/sessions/current` | DELETE | Yes |
| Refresh Token | `/api/v1/tokens` | POST | No (refresh token) |
| Verify Email | `/api/v1/email-verifications` | POST | No |
| Request Password Reset | `/api/v1/password-reset-tokens` | POST | No |
| Confirm Password Reset | `/api/v1/password-resets` | POST | No |

---

## 1. Getting the Current User

### In API Endpoints

```python
from fastapi import APIRouter, Depends
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)

router = APIRouter()

@router.get("/me")
async def get_my_profile(
    current_user: CurrentUser = Depends(get_current_user),
) -> UserResponse:
    """Get current user's profile (requires authentication)."""
    return UserResponse(
        id=current_user.user_id,
        email=current_user.email,
    )
```

### What `get_current_user` Does

1. Extracts `Authorization: Bearer {token}` header
2. Validates JWT signature and expiration
3. Extracts user info from token payload (`sub`, `email`, `roles`, `session_id`)
4. Returns `CurrentUser` dataclass or raises `HTTPException(401)`

**Note**: `CurrentUser` is a dataclass containing JWT payload data, not a database entity.

### Handling Optional Authentication

```python
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user_optional,
)

@router.get("/public-with-user-context")
async def public_endpoint(
    current_user: CurrentUser | None = Depends(get_current_user_optional),
) -> Response:
    """Public endpoint that can use user context if available."""
    if current_user:
        # Personalized response
        return {"message": f"Hello, {current_user.email}"}
    else:
        # Anonymous response
        return {"message": "Hello, guest"}
```

---

## 2. User Registration Flow

### Registration Handler Usage

```python
from src.application.commands import RegisterUser
from src.application.commands.handlers import RegisterUserHandler
from src.core.container import get_register_user_handler

@router.post("/users", status_code=201)
async def register_user(
    data: UserCreate,
    request: Request,
    handler: RegisterUserHandler = Depends(get_register_user_handler),
) -> UserResponse:
    """Register a new user."""
    command = RegisterUser(
        email=data.email,
        password=data.password,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )
    
    result = await handler.handle(command)
    
    if isinstance(result, Failure):
        # Handle specific errors
        match result.error:
            case "email_already_registered":
                raise HTTPException(409, "Email already registered")
            case "weak_password":
                raise HTTPException(400, "Password does not meet requirements")
            case _:
                raise HTTPException(500, "Registration failed")
    
    return UserResponse(id=result.value.id, email=result.value.email)
```

### Registration Events Emitted

```text
UserRegistrationAttempted → Before business logic
    ↓
UserRegistrationSucceeded → After user created
OR
UserRegistrationFailed → If validation/DB fails
```

---

## 3. Login Flow (3-Handler Pattern)

### Overview

Login uses three handlers orchestrated by the endpoint:

1. `AuthenticateUserHandler` - Verify credentials
2. `CreateSessionHandler` - Create session with metadata
3. `GenerateAuthTokensHandler` - Generate JWT + refresh token

### Login Endpoint Implementation

```python
from src.application.commands import AuthenticateUser, CreateSession, GenerateAuthTokens
from src.core.container import (
    get_authenticate_user_handler,
    get_create_session_handler,
    get_generate_auth_tokens_handler,
)

@router.post("/sessions", status_code=201)
async def login(
    data: LoginRequest,
    request: Request,
    auth_handler: AuthenticateUserHandler = Depends(get_authenticate_user_handler),
    session_handler: CreateSessionHandler = Depends(get_create_session_handler),
    token_handler: GenerateAuthTokensHandler = Depends(get_generate_auth_tokens_handler),
) -> LoginResponse:
    """Login and create session."""
    
    # Step 1: Authenticate user
    auth_result = await auth_handler.handle(AuthenticateUser(
        email=data.email,
        password=data.password,
        ip_address=request.client.host,
    ))
    
    if isinstance(auth_result, Failure):
        # Don't reveal whether email exists
        raise HTTPException(401, "Invalid credentials")
    
    authenticated_user = auth_result.value
    
    # Step 2: Create session
    session_result = await session_handler.handle(CreateSession(
        user_id=authenticated_user.id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    ))
    
    if isinstance(session_result, Failure):
        raise HTTPException(500, "Failed to create session")
    
    session = session_result.value
    
    # Step 3: Generate tokens
    token_result = await token_handler.handle(GenerateAuthTokens(
        user_id=authenticated_user.id,
        email=authenticated_user.email,
        roles=authenticated_user.roles,
        session_id=session.id,
    ))
    
    if isinstance(token_result, Failure):
        raise HTTPException(500, "Failed to generate tokens")
    
    tokens = token_result.value
    
    return LoginResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        expires_in=900,  # 15 minutes
    )
```

### Login Events Emitted

```text
UserLoginAttempted → Before credential check
    ↓
UserLoginFailed → Invalid credentials, unverified email, locked account
OR
UserLoginSucceeded → After session created
    ↓
SessionCreated → After session persisted
```

### Login Blocking Scenarios

| Scenario | Error Code | Message |
|----------|------------|---------|
| Wrong password | `invalid_credentials` | "Invalid credentials" |
| Email not verified | `email_not_verified` | "Please verify your email" |
| Account locked | `account_locked` | "Account locked. Try again in X minutes" |
| User not found | `invalid_credentials` | "Invalid credentials" (same as wrong password) |

---

## 4. Token Refresh

### Refresh Token Handler Usage

```python
from src.application.commands import RefreshAccessToken
from src.core.container import get_refresh_access_token_handler

@router.post("/tokens", status_code=201)
async def refresh_token(
    data: RefreshTokenRequest,
    request: Request,
    handler: RefreshAccessTokenHandler = Depends(get_refresh_access_token_handler),
) -> TokenResponse:
    """Refresh access token using refresh token."""
    
    result = await handler.handle(RefreshAccessToken(
        refresh_token=data.refresh_token,
        ip_address=request.client.host,
    ))
    
    if isinstance(result, Failure):
        match result.error:
            case "token_expired":
                raise HTTPException(401, "Refresh token expired")
            case "token_revoked":
                raise HTTPException(401, "Refresh token revoked")
            case "invalid_token":
                raise HTTPException(401, "Invalid refresh token")
            case _:
                raise HTTPException(401, "Token refresh failed")
    
    return TokenResponse(
        access_token=result.value.access_token,
        refresh_token=result.value.refresh_token,  # New refresh token (rotation)
        token_type="bearer",
        expires_in=900,
    )
```

### Token Rotation

On every refresh:

1. Old refresh token is invalidated
2. New refresh token is generated
3. Client must use new refresh token for next refresh

**Theft Detection**: If old refresh token is reused, ALL user sessions are revoked.

---

## 5. Logout

### Logout Handler Usage

```python
from src.application.commands import LogoutUser
from src.core.container import get_logout_user_handler

@router.delete("/sessions/current", status_code=204)
async def logout(
    current_user: User = Depends(get_current_user),
    handler: LogoutUserHandler = Depends(get_logout_user_handler),
) -> None:
    """Logout current session."""
    
    # Get session_id from JWT claims
    session_id = get_session_id_from_token()  # From auth middleware
    
    result = await handler.handle(LogoutUser(
        user_id=current_user.id,
        session_id=session_id,
    ))
    
    if isinstance(result, Failure):
        # Log but don't fail - logout is best-effort
        logger.warning("Logout failed", error=result.error)
    
    # Always return 204 (don't reveal whether session existed)
    return None
```

---

## 6. Email Verification

### Verification Token Generation

Email verification tokens are generated during registration and stored in database.

```python
# Generated automatically during registration
token = secrets.token_hex(32)  # 64-character hex string
expires_at = datetime.now(UTC) + timedelta(hours=24)
```

### Verification Handler Usage

```python
from src.application.commands import VerifyEmail
from src.core.container import get_verify_email_handler

@router.post("/email-verifications", status_code=200)
async def verify_email(
    data: VerifyEmailRequest,
    handler: VerifyEmailHandler = Depends(get_verify_email_handler),
) -> VerifyEmailResponse:
    """Verify email address using token."""
    
    result = await handler.handle(VerifyEmail(token=data.token))
    
    if isinstance(result, Failure):
        match result.error:
            case "token_expired":
                raise HTTPException(400, "Verification link expired")
            case "token_already_used":
                raise HTTPException(400, "Link already used")
            case "invalid_token":
                raise HTTPException(400, "Invalid verification link")
            case _:
                raise HTTPException(500, "Verification failed")
    
    return VerifyEmailResponse(message="Email verified successfully")
```

### Resending Verification Email

```python
from src.application.commands import ResendVerificationEmail

@router.post("/email-verifications/resend", status_code=201)
async def resend_verification(
    data: ResendVerificationRequest,
    handler: ResendVerificationEmailHandler = Depends(...),
) -> Response:
    """Resend verification email (rate limited)."""
    # Implementation details...
```

---

## 7. Password Reset

### Request Password Reset

```python
from src.application.commands import RequestPasswordReset
from src.core.container import get_request_password_reset_handler

@router.post("/password-reset-tokens", status_code=201)
async def request_password_reset(
    data: PasswordResetRequest,
    handler: RequestPasswordResetHandler = Depends(get_request_password_reset_handler),
) -> Response:
    """Request password reset email."""
    
    # Always return success (don't reveal email existence)
    await handler.handle(RequestPasswordReset(email=data.email))
    
    return {"message": "If email exists, reset link sent"}
```

### Confirm Password Reset

```python
from src.application.commands import ConfirmPasswordReset
from src.core.container import get_confirm_password_reset_handler

@router.post("/password-resets", status_code=200)
async def confirm_password_reset(
    data: ConfirmPasswordResetRequest,
    handler: ConfirmPasswordResetHandler = Depends(get_confirm_password_reset_handler),
) -> Response:
    """Reset password using token."""
    
    result = await handler.handle(ConfirmPasswordReset(
        token=data.token,
        new_password=data.new_password,
    ))
    
    if isinstance(result, Failure):
        match result.error:
            case "token_expired":
                raise HTTPException(400, "Reset link expired")
            case "weak_password":
                raise HTTPException(400, "Password does not meet requirements")
            case _:
                raise HTTPException(400, "Password reset failed")
    
    return {"message": "Password reset successfully"}
```

---

## 8. Password Requirements

### Validation Rules

```python
# src/domain/validators.py
def validate_strong_password(password: str) -> str:
    """Validate password meets security requirements."""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValueError("Password must contain special character")
    return password
```

### Using Annotated Types

```python
from src.domain.types import Password

class UserCreate(BaseModel):
    email: Email
    password: Password  # Automatically validated
```

---

## 9. Account Lockout

### Lockout Behavior

- **Threshold**: 5 failed login attempts
- **Duration**: 15 minutes (configurable)
- **Scope**: Per user (not per IP)

### Checking Lockout Status

```python
# In AuthenticateUserHandler
if user.failed_login_attempts >= 5:
    lockout_until = user.last_failed_login + timedelta(minutes=15)
    if datetime.now(UTC) < lockout_until:
        return Failure("account_locked")
```

### Resetting Lockout

Lockout resets on:

1. Successful login
2. Password reset
3. Manual admin action
4. Lockout duration expires

---

## 10. Testing Authentication

### Unit Testing Handlers

```python
import pytest
from unittest.mock import AsyncMock
from src.application.commands.handlers import AuthenticateUserHandler

@pytest.fixture
def mock_user_repo():
    repo = AsyncMock()
    repo.find_by_email.return_value = User(
        id=uuid7(),
        email="test@example.com",
        password_hash="$2b$12$...",
        is_verified=True,
    )
    return repo

async def test_authenticate_user_success(mock_user_repo, mock_password_service):
    handler = AuthenticateUserHandler(
        user_repo=mock_user_repo,
        password_service=mock_password_service,
        event_bus=AsyncMock(),
    )
    
    result = await handler.handle(AuthenticateUser(
        email="test@example.com",
        password="correct_password",
        ip_address="127.0.0.1",
    ))
    
    assert isinstance(result, Success)
    assert result.value.email == "test@example.com"
```

### API Testing with TestClient

```python
from fastapi.testclient import TestClient

def test_login_success(client: TestClient, test_user):
    response = client.post("/api/v1/sessions", json={
        "email": test_user.email,
        "password": "test_password",
    })
    
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_credentials(client: TestClient):
    response = client.post("/api/v1/sessions", json={
        "email": "wrong@example.com",
        "password": "wrong_password",
    })
    
    assert response.status_code == 401
```

---

## Common Patterns

### Pattern 1: Protected Endpoint

```python
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)

@router.get("/protected")
async def protected_endpoint(
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    # current_user is guaranteed to be authenticated
    return {"user_id": str(current_user.user_id)}
```

### Pattern 2: Admin-Only Endpoint

```python
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
    require_role,
)

@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    _: CurrentUser = Depends(require_role("admin")),
) -> None:
    # Only admins can reach here
    ...
```

### Pattern 3: Real-Time Permission Check (Casbin)

```python
from src.presentation.routers.api.middleware.authorization_dependencies import (
    require_permission,
)

@router.get("/accounts")
async def list_accounts(
    current_user: CurrentUser = Depends(get_current_user),
    _: None = Depends(require_permission("accounts", "read")),
) -> Response:
    # Casbin permission verified against database
    ...
```

---

## Troubleshooting

### "Invalid credentials" on correct password

1. Check user exists in database
2. Check `is_verified` is True
3. Check account not locked (failed_login_attempts < 5)
4. Verify password hash format (should start with `$2b$12$`)

### Token validation fails

1. Check JWT secret key matches between services
2. Check system clocks are synchronized
3. Check token hasn't expired (15 min for access, 30 days for refresh)
4. Check token version >= min_token_version (breach rotation)

### Session not found on refresh

1. Session may have been revoked (logout, password change)
2. Token version may be below minimum (emergency rotation)
3. Refresh token may have been rotated (use new one)

---

**Created**: 2025-12-05 | **Last Updated**: 2026-01-10
