# Authentication Architecture

## 1. Overview

### Purpose

Provide secure, production-ready authentication for Dashtam using JWT access tokens and opaque refresh tokens, with mandatory email verification and self-service password reset.

### Key Requirements

**Security First**:

- Email verification BLOCKS login (no shortcuts)
- Bcrypt password hashing (cost factor 12)
- JWT access tokens (short-lived: 15 minutes)
- Opaque refresh tokens (long-lived: 30 days, hashed in database)
- Token rotation on refresh
- Account lockout after failed login attempts

**Hexagonal Architecture**:

- Domain layer: Pure business logic, no framework dependencies
- Application layer: Commands, queries, handlers (CQRS)
- Infrastructure layer: PostgreSQL, bcrypt, JWT, email services
- Presentation layer: FastAPI endpoints

**Integration Requirements**:

- Domain events for all auth actions (registration, login, password change)
- Audit trail for all security events (PCI-DSS compliance)
- Session tracking integration (F1.3 dependency)

### Non-Goals (Phase 1)

- ❌ OAuth2/OpenID Connect (external providers: Google, GitHub)
- ❌ Multi-factor authentication (MFA)
- ❌ Passwordless authentication (magic links)
- ❌ Social login
- ❌ Account recovery questions

These features may be added in future phases.

---

## 2. Authentication Strategy

### Decision: JWT + Opaque Refresh Tokens

**Why not session cookies?**

- Dashtam is API-first (designed for future mobile apps, third-party integrations)
- Stateless authentication scales better (no server-side session store for every request)
- JWT standard, well-understood, widely supported

**Why not JWT for refresh tokens?**

- Refresh tokens are long-lived (30 days) - JWT cannot be revoked
- Opaque tokens stored in database can be immediately revoked (logout, password change, security breach)
- Reduces attack surface (refresh token theft has limited window)

**Hybrid Approach**:

```text
Access Token (JWT):
- Short-lived (15 minutes)
- Stateless validation (no database lookup)
- Includes user_id, email, roles
- Cannot be revoked (expires naturally)

Refresh Token (Opaque):
- Long-lived (30 days)
- Stored in database (hashed with bcrypt)
- Can be immediately revoked
- Used ONLY to get new access token
```

### Token Lifecycle (3-Handler Orchestration)

```text
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /api/v1/sessions
       │ email + password
       ↓
┌────────────────────────────────────────────────────┐
│  Presentation Layer (sessions.py)                  │
│  Orchestrates 3 handlers (CQRS pattern):           │
│                                                    │
│  ┌─────────────────────────────────────────────┐   │
│  │ 1. AuthenticateUserHandler                  │   │
│  │    - Verify credentials                     │   │
│  │    - Check email verified                   │   │
│  │    - Check account not locked               │   │
│  │    - Emit UserLoginAttempted event          │   │
│  │    - Emit UserLoginSucceeded/Failed event   │   │
│  │    → Returns AuthenticatedUser (user_id,    │   │
│  │      email, roles)                          │   │
│  └─────────────────────────────────────────────┘   │
│                      ↓                             │
│  ┌─────────────────────────────────────────────┐   │
│  │ 2. CreateSessionHandler                     │   │
│  │    - Enrich device info (user agent)        │   │
│  │    - Enrich location (IP address)           │   │
│  │    - Check session limit (may evict oldest) │   │
│  │    - Create session in database             │   │
│  │    - Cache session in Redis                 │   │
│  │    - Emit SessionCreatedEvent               │   │
│  │    → Returns session_id                     │   │
│  └─────────────────────────────────────────────┘   │
│                      ↓                             │
│  ┌─────────────────────────────────────────────┐   │
│  │ 3. GenerateAuthTokensHandler                │   │
│  │    - Generate JWT access token (15min)      │   │
│  │    - Generate opaque refresh token          │   │
│  │    - Hash & store refresh token in DB       │   │
│  │    → Returns access_token, refresh_token    │   │
│  └─────────────────────────────────────────────┘   │
└──────┬─────────────────────────────────────────────┘
       │ 201 Created
       │ { access_token, refresh_token }
       ↓
┌─────────────┐
│   Client    │ ← Stores tokens
│  (uses JWT) │   Uses JWT for API requests
└──────┬──────┘
       │ After 15min, JWT expires
       │ POST /api/v1/tokens
       │ { refresh_token }
       ↓
┌─────────────────────────────┐
│  Token Refresh Handler      │
│  1. Verify refresh token    │
│  2. Lookup in database      │
│  3. Validate not expired    │
│  4. Validate not revoked    │
│  5. Generate new JWT        │
│  6. Rotate refresh token    │
│  7. Emit event (success)    │
└──────┬──────────────────────┘
       │ 201 Created
       │ { access_token, refresh_token }
       ↓
┌─────────────┐
│   Client    │ ← Receives new tokens
└─────────────┘
```

**Benefits of 3-Handler Pattern**:

1. **Single Responsibility**: Each handler does ONE thing
2. **Testability**: Test each handler in isolation
3. **Reusability**: Can generate tokens without authenticating (OAuth flow)
4. **CQRS Compliance**: Presentation layer orchestrates, handlers execute single commands

---

## 3. Token Architecture

### JWT Access Token

**Header**:

```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**Payload**:

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",  // user_id (UUID)
  "email": "user@example.com",
  "roles": ["user"],                              // For F1.1b authorization
  "iat": 1700000000,                              // Issued at (Unix timestamp)
  "exp": 1700000900,                              // Expires at (15 minutes later)
  "jti": "abc123...",                             // JWT ID (unique, for revocation lists)
  "session_id": "def456..."                       // Session ID (F1.3 integration)
}
```

**Signature**:

```python
HMACSHA256(
  base64UrlEncode(header) + "." + base64UrlEncode(payload),
  JWT_SECRET_KEY  // From settings, 256-bit minimum
)
```

**Properties**:

- **Stateless**: No database lookup required to validate
- **Short-lived**: 15 minutes (balance between security and UX)
- **Cannot be revoked**: Expires naturally (acceptable for 15min window)
- **Self-contained**: Includes all data needed for authorization

### Refresh Token

**Format**: 32-byte random string (urlsafe base64 encoded)

```python
import secrets
refresh_token = secrets.token_urlsafe(32)
# Example: "dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg=="
```

**Storage** (database):

```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,  -- bcrypt hash
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,  -- 30 days from creation
    revoked_at TIMESTAMPTZ,
    revoked_reason TEXT,
    last_used_at TIMESTAMPTZ,
    rotation_count INTEGER NOT NULL DEFAULT 0,
    INDEX idx_refresh_tokens_user_id (user_id),
    INDEX idx_refresh_tokens_session_id (session_id),
    INDEX idx_refresh_tokens_expires_at (expires_at) WHERE revoked_at IS NULL
);
```

**Properties**:

- **Long-lived**: 30 days (convenient for users)
- **Revocable**: Can be immediately invalidated in database
- **One-time use**: Rotated on every refresh (token theft detection)
- **Tied to session**: Revoked when session revoked (F1.3 integration)

### Token Rotation

**Why rotate refresh tokens?**

- Detect token theft (attacker uses stolen token, user's refresh fails)
- Limit window of stolen token usefulness
- Best practice for long-lived credentials

**Rotation flow**:

1. Client sends refresh token
2. Server validates token
3. Server generates NEW refresh token
4. Server deletes OLD refresh token from database
5. Server returns new access token + new refresh token
6. Client replaces both tokens

**Theft detection**:

- If client attempts to use OLD refresh token: 401 Unauthorized + revoke ALL user sessions
- Indicates token theft (attacker used token first, or client reused old token)

---

## 4. Email Verification Flow

### Requirement

**Email verification BLOCKS login** - No shortcuts, proper security from day one.

### Flow Diagram

```text
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /auth/register
       │ { email, password }
       ↓
┌────────────────────────────────────┐
│  Registration Handler              │
│  1. Emit UserRegistrationAttempted │
│  2. Validate email format          │
│  3. Check email not already used   │
│  4. Validate password complexity   │
│  5. Hash password (bcrypt)         │
│  6. Create User (is_verified=false)│
│  7. Generate verification token    │
│  8. Store token in database        │
│  9. Emit UserRegistrationSucceeded │
└──────┬─────────────────────────────┘
       │ 201 Created
       │ { id, email, is_verified: false }
       ↓
┌─────────────┐
│   Client    │ ← Registration success
└─────────────┘

       ⬇ UserRegistrationSucceeded event published

┌────────────────────────────────────────┐
│  Email Event Handler                  │
│  1. Subscribe to                      │
│     UserRegistrationSucceeded         │
│  2. Generate verification URL         │
│  3. Send email via AWS SES            │
│  4. Log email sent                    │
└────────────────────────────────────────┘
       ⬇
┌─────────────┐
│ User's Inbox│ ← Receives email with link
└──────┬──────┘
       │ User clicks link
       │ GET /auth/verify-email?token=abc123
       ↓
┌────────────────────────────────────┐
│  Email Verification Handler        │
│  (Note: Email verification uses    │
│   simple success/failure, not full │
│   3-state pattern for MVP)         │
│  1. Validate token format          │
│  2. Lookup token in database       │
│  3. Check token not expired (24h)  │
│  4. Check token not already used   │
│  5. Update user.is_verified = true │
│  6. Mark token as used             │
│  7. Emit event (success/failure)   │
└──────┬─────────────────────────────┘
       │ 200 OK
       │ { message: "Email verified" }
       ↓
┌─────────────┐
│   Client    │ ← Email verified, can now login
└─────────────┘
```

### Email Verification Token

**Storage** (database):

```sql
CREATE TABLE email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) NOT NULL UNIQUE,  -- Random 32-byte hex
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,  -- 24 hours from creation
    used_at TIMESTAMPTZ,
    INDEX idx_email_verification_user_id (user_id),
    INDEX idx_email_verification_expires_at (expires_at) WHERE used_at IS NULL
);
```

**Token generation**:

```python
import secrets
token = secrets.token_hex(32)  # 64-character hex string
```

**Properties**:

- **One-time use**: Marked as used after verification
- **Short-lived**: 24 hours expiration
- **Unguessable**: 32 bytes of entropy (2^256 possibilities)

### Login Blocking

**Login flow check**:

```python
async def login(email: str, password: str) -> Result[LoginResponse, AuthError]:
    user = await user_repo.find_by_email(email)
    if not user:
        return Failure(AuthError.INVALID_CREDENTIALS)
    
    if not user.is_verified:
        # BLOCK LOGIN - Email not verified
        await audit.record(
            action=AuditAction.USER_LOGIN_FAILED,
            user_id=user.id,
            metadata={"reason": "email_not_verified"}
        )
        return Failure(AuthError.EMAIL_NOT_VERIFIED)
    
    # Continue with password validation...
```

---

## 5. Password Reset Flow

```text
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ POST /auth/password-reset/request
       │ { email }
       ↓
┌────────────────────────────────────┐
│  Password Reset Request Handler    │
│  (Note: Reset request uses simple  │
│   success pattern for MVP)         │
│  1. Validate email format          │
│  2. Lookup user by email           │
│  3. Generate reset token           │
│  4. Store token in database (15min)│
│  5. Emit event (if user exists)    │
│  6. Return 200 OK (always)         │  ← Security: No user enumeration
└──────┬─────────────────────────────┘
       │ 200 OK (regardless of email exists)
       ↓
┌─────────────┐
│   Client    │
└─────────────┘

       ⬇ PasswordResetRequested event

┌────────────────────────────────────┐
│  Email Event Handler               │
│  1. Subscribe to event             │
│  2. Generate reset URL             │
│  3. Send email with link           │
│  4. Audit email sent               │
└────────────────────────────────────┘
       ⬇
┌─────────────┐
│ User's Inbox│ ← Receives email with reset link
└──────┬──────┘
       │ User clicks link
       │ POST /auth/password-reset/confirm
       │ { token, new_password }
       ↓
┌────────────────────────────────────┐
│  Password Reset Confirm Handler    │
│  1. Emit PasswordChangeAttempted   │
│  2. Validate token                 │
│  3. Check not expired (15min)      │
│  4. Check not already used         │
│  5. Validate new password          │
│  6. Hash new password (bcrypt)     │
│  7. Update user password           │
│  8. Mark token as used             │
│  9. Revoke ALL user sessions       │  ← Security
│ 10. Revoke ALL refresh tokens      │  ← Security
│ 11. Emit PasswordChangeSucceeded   │
└──────┬─────────────────────────────┘
       │ 200 OK
       ↓
┌─────────────┐
│   Client    │ ← Password reset, must login again
└─────────────┘
```

### Password Reset Token

**Storage** (database):

```sql
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) NOT NULL UNIQUE,  -- Random 32-byte hex
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,  -- 15 minutes from creation
    used_at TIMESTAMPTZ,
    ip_address INET,  -- Track who requested reset
    user_agent TEXT,
    INDEX idx_password_reset_user_id (user_id),
    INDEX idx_password_reset_expires_at (expires_at) WHERE used_at IS NULL
);
```

**Properties**:

- **One-time use**: Marked as used after password change
- **Very short-lived**: 15 minutes (security vs UX tradeoff)
- **Revokes all sessions**: Force re-login after password change

### Security Considerations

**No user enumeration**:

- Always return 200 OK for password reset requests (even if email doesn't exist)
- Prevents attackers from discovering valid email addresses

**Session revocation**:

- Password change revokes ALL sessions and refresh tokens
- Assumes password reset indicates security concern

---

## 6. Domain Model

### User Entity

```python
# src/domain/entities/user.py
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass
class User:
    """User domain entity.
    
    Pure business logic, no framework dependencies.
    """
    id: UUID
    email: str  # Use Email value object
    password_hash: str  # Never store plaintext
    is_verified: bool
    is_active: bool
    failed_login_attempts: int
    locked_until: datetime | None
    created_at: datetime
    updated_at: datetime
    
    def is_locked(self) -> bool:
        """Check if account is locked due to failed login attempts."""
        if self.locked_until is None:
            return False
        return datetime.now(UTC) < self.locked_until
    
    def increment_failed_login(self) -> None:
        """Increment failed login counter, lock account after 5 attempts."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            # Lock for 15 minutes
            self.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    
    def reset_failed_login(self) -> None:
        """Reset failed login counter on successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None
```

### Value Objects

**Email** (`src/domain/value_objects/email.py`):

```python
from dataclasses import dataclass
from email_validator import validate_email, EmailNotValidError

@dataclass(frozen=True)
class Email:
    """Email value object with validation."""
    value: str
    
    def __post_init__(self):
        try:
            validate_email(self.value, check_deliverability=False)
        except EmailNotValidError as e:
            raise ValueError(f"Invalid email: {e}")
    
    def __str__(self) -> str:
        return self.value
```

**Password** (`src/domain/value_objects/password.py`):

```python
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Password:
    """Password value object with complexity validation."""
    value: str
    
    def __post_init__(self):
        self._validate()
    
    def _validate(self) -> None:
        """Validate password complexity.
        
        Requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        """
        if len(self.value) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", self.value):
            raise ValueError("Password must contain uppercase letter")
        if not re.search(r"[a-z]", self.value):
            raise ValueError("Password must contain lowercase letter")
        if not re.search(r"\d", self.value):
            raise ValueError("Password must contain digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", self.value):
            raise ValueError("Password must contain special character")
```

---

## 7. Hexagonal Architecture Integration

### Layer Responsibilities

**Domain Layer** (pure business logic):

- `User` entity with business rules
- `Email`, `Password` value objects with validation
- `UserRepository` protocol
- Domain events (`UserRegistered`, `UserLoggedIn`, `PasswordChanged`, etc.)

**Application Layer** (use cases):

- Commands: `RegisterUser`, `LoginUser`, `VerifyEmail`, `RefreshToken`, `RequestPasswordReset`, `ConfirmPasswordReset`
- Command handlers: Orchestrate domain, infrastructure, events
- No infrastructure dependencies (depend on protocols)

**Infrastructure Layer** (adapters):

- `UserRepository` implements `UserRepository` protocol
- `BcryptPasswordService` implements `PasswordHashingProtocol`
- `JWTService` implements `TokenGenerationProtocol`
- `AWSEmailService` implements `EmailProtocol`
- SQLModel database models

**Presentation Layer** (API):

- FastAPI routers
- Pydantic request/response schemas
- JWT middleware for protected endpoints
- Error handling (convert domain errors to HTTP responses)

### Dependency Flow

```text
Presentation (FastAPI)
    ↓ depends on
Application (Handlers)
    ↓ depends on
Domain (Entities, Protocols)
    ↑ implements
Infrastructure (Adapters)
```

**Key principle**: Domain knows NOTHING about infrastructure. Infrastructure knows ABOUT domain.

---

## 8. Domain Events Integration

### Authentication Events (3-State Pattern)

**Pattern**: All authentication workflows use 3 events (ATTEMPTED → SUCCEEDED/FAILED) for audit semantic accuracy and compliance.

**Reference**: See `docs/architecture/domain-events.md` for complete event-driven architecture.

#### User Registration (Workflow 1)

**UserRegistrationAttempted**:

```python
@dataclass(frozen=True, kw_only=True)
class UserRegistrationAttempted(DomainEvent):
    email: str
```

**Handlers**:

- `LoggingEventHandler`: Log attempt
- `AuditEventHandler`: Record USER_REGISTRATION_ATTEMPTED

**UserRegistrationSucceeded**:

```python
@dataclass(frozen=True, kw_only=True)
class UserRegistrationSucceeded(DomainEvent):
    user_id: UUID
    email: str
    verification_token: str  # For email handler to send verification link
```

**Handlers**:

- `LoggingEventHandler`: Log success
- `AuditEventHandler`: Record USER_REGISTERED
- `EmailEventHandler`: Send verification email

**UserRegistrationFailed**:

```python
@dataclass(frozen=True, kw_only=True)
class UserRegistrationFailed(DomainEvent):
    email: str
    reason: str
```

**Handlers**:

- `LoggingEventHandler`: Log failure
- `AuditEventHandler`: Record USER_REGISTRATION_FAILED

#### Password Change (Workflow 2)

**UserPasswordChangeAttempted**:

```python
@dataclass(frozen=True, kw_only=True)
class UserPasswordChangeAttempted(DomainEvent):
    user_id: UUID
```

**Handlers**:

- `LoggingEventHandler`: Log attempt
- `AuditEventHandler`: Record USER_PASSWORD_CHANGE_ATTEMPTED

**UserPasswordChangeSucceeded**:

```python
@dataclass(frozen=True, kw_only=True)
class UserPasswordChangeSucceeded(DomainEvent):
    user_id: UUID
    initiated_by: str  # "user" or "admin"
```

**Handlers**:

- `LoggingEventHandler`: Log success
- `AuditEventHandler`: Record USER_PASSWORD_CHANGED
- `EmailEventHandler`: Send password changed notification
- `SessionEventHandler`: Revoke all sessions (force re-login)

**UserPasswordChangeFailed**:

```python
@dataclass(frozen=True, kw_only=True)
class UserPasswordChangeFailed(DomainEvent):
    user_id: UUID
    reason: str
```

**Handlers**:

- `LoggingEventHandler`: Log failure
- `AuditEventHandler`: Record USER_PASSWORD_CHANGE_FAILED

#### Notes on Event Base Class

All events inherit from `DomainEvent` which provides:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid7)  # Auto-generated
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))  # Auto-generated
```

No need to include `event_id` or `occurred_at` in event definitions - they're inherited and auto-generated

### Event Publishing Pattern (3-State)

**Pattern**: Publish ATTEMPTED before operation, SUCCEEDED/FAILED after.

```python
# In command handler
async def handle(self, cmd: RegisterUser) -> Result[UUID, Error]:
    # Event 1: ATTEMPTED (before business logic)
    await self.event_bus.publish(UserRegistrationAttempted(
        email=cmd.email,
    ))
    # → LoggingEventHandler.on_registration_attempted()
    # → AuditEventHandler.on_registration_attempted()
    
    try:
        # Business logic
        user = User(...)
        await self.user_repo.save(user)
        
        # Event 2: SUCCEEDED (after business success)
        await self.event_bus.publish(UserRegistrationSucceeded(
            user_id=user.id,
            email=user.email,
        ))
        # → LoggingEventHandler.on_registration_succeeded()
        # → AuditEventHandler.on_registration_succeeded()
        # → EmailEventHandler.on_registration_succeeded() (send verification email)
        
        return Success(user.id)
    
    except Exception as e:
        # Event 3: FAILED (after business failure)
        await self.event_bus.publish(UserRegistrationFailed(
            email=cmd.email,
            reason=str(e),
        ))
        # → LoggingEventHandler.on_registration_failed()
        # → AuditEventHandler.on_registration_failed()
        
        return Failure(error)
```

**Benefits of 3-State Pattern**:

1. **Audit semantic accuracy**: Record ATTEMPT before operation, OUTCOME after
2. **Compliance**: PCI-DSS, SOC 2, GDPR require attempt tracking
3. **Observability**: Full state tracking for debugging
4. **Centralized side effects**: All logging, audit, email handled by event handlers

---

## 9. Audit Trail Integration

### Authentication Audit Events

**Audit all security-relevant actions** (PCI-DSS compliance):

**Registration**:

- `USER_REGISTRATION_ATTEMPTED` (before validation)
- `USER_REGISTERED` (success)
- `USER_REGISTRATION_FAILED` (validation failed, email exists)

**Email Verification**:

- `EMAIL_VERIFICATION_ATTEMPTED`
- `EMAIL_VERIFIED`
- `EMAIL_VERIFICATION_FAILED` (invalid token, expired)

**Login**:

- `USER_LOGIN_ATTEMPTED` (before credential check)
- `USER_LOGIN_SUCCESS` (credentials valid)
- `USER_LOGIN_FAILED` (invalid credentials, email not verified, account locked)

**Token Refresh**:

- `TOKEN_REFRESH_ATTEMPTED`
- `TOKEN_REFRESHED`
- `TOKEN_REFRESH_FAILED` (invalid token, expired, revoked)

**Password Reset**:

- `PASSWORD_RESET_REQUESTED`
- `PASSWORD_RESET_COMPLETED`
- `PASSWORD_RESET_FAILED` (invalid token, expired)

**Logout**:

- `USER_LOGOUT_SUCCESS`
- `USER_LOGOUT_FAILED` (invalid session)

### Audit Pattern (ATTEMPT → OUTCOME via Events)

**Pattern**: Audit trail is handled automatically by `AuditEventHandler` subscribing to domain events.

**Before (Direct Audit - OLD)**:

```python
# ❌ OLD: Handler directly calls audit (tightly coupled)
async def handle(self, cmd: LoginUser) -> Result[LoginResponse, AuthError]:
    # Direct audit call (boilerplate)
    await self.audit.record(action=AuditAction.USER_LOGIN_ATTEMPTED, ...)
    
    # Business logic
    user = await self.user_repo.find_by_email(cmd.email)
    if not user:
        # Direct audit call (boilerplate)
        await self.audit.record(action=AuditAction.USER_LOGIN_FAILED, ...)
        return Failure(AuthError.INVALID_CREDENTIALS)
    
    # Direct audit call (boilerplate)
    await self.audit.record(action=AuditAction.USER_LOGIN_SUCCESS, ...)
    return Success(LoginResponse(...))
```

**After (Event-Driven - NEW)**:

```python
# ✅ NEW: Handler publishes events, AuditEventHandler records audit
async def handle(self, cmd: RegisterUser) -> Result[UUID, Error]:
    # Publish event - AuditEventHandler automatically records audit
    await self.event_bus.publish(UserRegistrationAttempted(email=cmd.email))
    # → AuditEventHandler.on_registration_attempted() records USER_REGISTRATION_ATTEMPTED
    
    try:
        # Business logic
        user = User(...)
        await self.user_repo.save(user)
        
        # Publish event - AuditEventHandler automatically records audit
        await self.event_bus.publish(UserRegistrationSucceeded(
            user_id=user.id,
            email=user.email,
        ))
        # → AuditEventHandler.on_registration_succeeded() records USER_REGISTERED
        
        return Success(user.id)
    
    except Exception as e:
        # Publish event - AuditEventHandler automatically records audit
        await self.event_bus.publish(UserRegistrationFailed(
            email=cmd.email,
            reason=str(e),
        ))
        # → AuditEventHandler.on_registration_failed() records USER_REGISTRATION_FAILED
        
        return Failure(error)
```

**Benefits**:

1. **No audit boilerplate**: Handlers don't call audit directly
2. **Centralized audit logic**: All audit in `AuditEventHandler`
3. **Easy to extend**: Add new audit requirements without changing handlers
4. **Consistent**: All workflows follow same pattern

---

## 10. Session Management Integration

### Session Creation on Login (3-Handler Orchestration)

**Presentation layer orchestrates 3 handlers** (CQRS pattern):

```python
# src/presentation/api/v1/sessions.py
@router.post("/sessions", status_code=201)
async def create_session(
    request: Request,
    data: SessionCreateRequest,
    auth_handler: AuthenticateUserHandler = Depends(get_authenticate_user_handler),
    session_handler: CreateSessionHandler = Depends(get_create_session_handler),
    token_handler: GenerateAuthTokensHandler = Depends(get_generate_auth_tokens_handler),
) -> SessionCreateResponse:
    """Orchestrate login flow with 3 handlers."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Step 1: Authenticate user credentials
    auth_result = await auth_handler.handle(
        AuthenticateUser(email=data.email, password=data.password)
    )
    if isinstance(auth_result, Failure):
        raise appropriate_http_error(auth_result.error)

    # Step 2: Create session with device/location enrichment
    session_result = await session_handler.handle(
        CreateSession(
            user_id=auth_result.value.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )
    if isinstance(session_result, Failure):
        raise appropriate_http_error(session_result.error)

    # Step 3: Generate tokens
    token_result = await token_handler.handle(
        GenerateAuthTokens(
            user_id=auth_result.value.user_id,
            email=auth_result.value.email,
            roles=auth_result.value.roles,
            session_id=session_result.value.session_id,
        )
    )
    if isinstance(token_result, Failure):
        raise appropriate_http_error(token_result.error)

    return SessionCreateResponse(
        access_token=token_result.value.access_token,
        refresh_token=token_result.value.refresh_token,
    )
```

**Handler responsibilities**:

| Handler | Responsibility | Returns |
| ------- | -------------- | ------- |
| `AuthenticateUserHandler` | Verify credentials, check locks | `AuthenticatedUser` (user_id, email, roles) |
| `CreateSessionHandler` | Device/location enrichment, session limits | `session_id` |
| `GenerateAuthTokensHandler` | Generate JWT + refresh token | `AuthTokens` |

### Session Revocation on Password Change

**Password change revokes all sessions** (handled by `SessionEventHandler` subscribing to `UserPasswordChangeSucceeded`):

```python
async def handle(self, cmd: ConfirmPasswordReset) -> Result[None, Error]:
    # Event 1: ATTEMPTED
    await self.event_bus.publish(UserPasswordChangeAttempted(
        user_id=user.id,
    ))
    
    try:
        # ... validate token, update password ...
        
        # Event 2: SUCCEEDED
        await self.event_bus.publish(UserPasswordChangeSucceeded(
            user_id=user.id,
            initiated_by="self_service",
        ))
        # → SessionEventHandler.on_password_change_succeeded() revokes all sessions
        # → EmailEventHandler.on_password_change_succeeded() sends notification
        # → AuditEventHandler.on_password_change_succeeded() records audit
        
        return Success(None)
    
    except Exception as e:
        # Event 3: FAILED
        await self.event_bus.publish(UserPasswordChangeFailed(
            user_id=user.id,
            reason=str(e),
        ))
        return Failure(error)
```

---

## 11. Security Model

### Password Security

**Hashing Algorithm**: Bcrypt (cost factor 12)

```python
import bcrypt

def hash_password(password: str) -> str:
    """Hash password with bcrypt (cost factor 12)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hash: str) -> bool:
    """Verify password against hash."""
    return bcrypt.checkpw(password.encode(), hash.encode())
```

**Why bcrypt?**

- Adaptive (can increase cost factor as hardware improves)
- Resistant to GPU/ASIC attacks (memory-hard)
- Industry standard for password hashing
- Cost factor 12 = ~250ms per hash (balance security vs UX)

### JWT Security

**Signing Algorithm**: HMAC-SHA256 (HS256)

**Secret Key Requirements**:

- Minimum 256 bits (32 bytes)
- Stored in secrets manager (F0.7)
- NEVER committed to git
- Rotated periodically (manual process, Phase 2)

**Token Expiration**:

- Access token: 15 minutes (short window for compromise)
- Refresh token: 30 days (convenient, but revocable)

### Account Lockout

**Trigger**: 5 failed login attempts

**Lockout Duration**: 15 minutes

**Reset**: Successful login or manual unlock (admin, Phase 2)

```python
# In login handler
if user.is_locked():
    await self.audit.record(
        action=AuditAction.USER_LOGIN_FAILED,
        user_id=user.id,
        metadata={"reason": "account_locked"}
    )
    return Failure(AuthError.ACCOUNT_LOCKED)

# Check password
if not self.password_service.verify(cmd.password, user.password_hash):
    user.increment_failed_login()
    await self.user_repo.save(user)
    return Failure(AuthError.INVALID_CREDENTIALS)

# Success - reset counter
user.reset_failed_login()
await self.user_repo.save(user)
```

### Token Theft Detection

**Refresh Token Rotation**:

- Every refresh generates NEW refresh token
- OLD refresh token deleted from database
- Attempt to use OLD token = potential theft

```python
# In refresh handler
async def handle(self, cmd: RefreshToken) -> Result[RefreshResponse, Error]:
    # Hash provided token
    token_hash = bcrypt.hashpw(cmd.refresh_token.encode(), ...)
    
    # Lookup in database
    stored_token = await self.token_repo.find_by_hash(token_hash)
    if not stored_token:
        # Token not found - could be:
        # 1. Invalid token (user error)
        # 2. Already rotated (theft)
        
        # Check if recently rotated (theft indicator)
        recent_rotation = await self.token_repo.find_recent_rotation(cmd.user_id)
        if recent_rotation:
            # THEFT DETECTED - Revoke ALL sessions
            await self.session_service.revoke_all_sessions(
                user_id=cmd.user_id,
                reason="token_theft_detected",
            )
            await self.audit.record(
                action=AuditAction.TOKEN_THEFT_DETECTED,
                user_id=cmd.user_id,
            )
        
        return Failure(AuthError.INVALID_TOKEN)
    
    # Generate new tokens (rotation)
    new_access_token = self.jwt_service.generate_access_token(...)
    new_refresh_token = self.token_service.generate_refresh_token(...)
    
    # Delete old, save new
    await self.token_repo.delete(stored_token.id)
    await self.token_repo.save(new_token)
    
    return Success(RefreshResponse(...))
```

---

## 12. API Endpoints (RESTful)

**Design Principle**: 100% resource-based URLs. No verbs in URLs - HTTP methods indicate actions.

### Resource Summary

| Resource | Method | Endpoint | Description | Status |
| -------- | ------ | -------- | ----------- | ------ |
| User | POST | `/api/v1/users` | Create user (register) | 201 |
| Session | POST | `/api/v1/sessions` | Create session (login) | 201 |
| Session | DELETE | `/api/v1/sessions/current` | Delete session (logout) | 204 |
| Token | POST | `/api/v1/tokens` | Create tokens (refresh) | 201 |
| EmailVerification | POST | `/api/v1/email-verifications` | Create verification | 201 |
| PasswordResetToken | POST | `/api/v1/password-reset-tokens` | Create reset token | 201 |
| PasswordReset | POST | `/api/v1/password-resets` | Execute reset | 201 |

### User Resource

- **POST /api/v1/users** - Create user (registration)

Request:

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

Response (201 Created):

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "message": "Registration successful. Please check your email to verify your account."
}
```

### Email Verification Resource

- **POST /api/v1/email-verifications** - Create verification (verify email)

Request:

```json
{
  "token": "abc123def456..." 
}
```

Response (201 Created):

```json
{
  "message": "Email verified successfully. You can now create a session."
}
```

### Session Resource

- **POST /api/v1/sessions** - Create session (login)

Request:

```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

Response (201 Created):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg==",
  "token_type": "bearer",
  "expires_in": 900
}
```

- **DELETE /api/v1/sessions/current** - Delete current session (logout)

Request (with Authorization header):

```text
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Body:

```json
{
  "refresh_token": "dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg=="
}
```

Response: **204 No Content** (empty body)

### Token Resource

- **POST /api/v1/tokens** - Create new tokens (refresh)

Request:

```json
{
  "refresh_token": "dGhpcyBpcyBhIHJhbmRvbSB0b2tlbg=="
}
```

Response (201 Created):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "bmV3IHJhbmRvbSB0b2tlbiBhZnRlciByb3RhdGlvbg==",
  "token_type": "bearer",
  "expires_in": 900
}
```

### Password Reset Resources

- **POST /api/v1/password-reset-tokens** - Create reset token (request)

Request:

```json
{
  "email": "user@example.com"
}
```

Response (201 Created - always, prevents user enumeration):

```json
{
  "message": "If an account with that email exists, a password reset link has been sent."
}
```

- **POST /api/v1/password-resets** - Create password reset (execute)

Request:

```json
{
  "token": "xyz789...",
  "new_password": "NewSecurePass456!"
}
```

Response (201 Created):

```json
{
  "message": "Password has been reset successfully. Please create a new session."
}
```

### Error Responses

**400 Bad Request** (validation error):

```json
{
  "type": "https://api.dashtam.com/errors/validation-error",
  "title": "Validation Error",
  "status": 400,
  "detail": "Password must contain uppercase letter",
  "instance": "/api/v1/auth/register",
  "trace_id": "abc123...",
  "errors": [
    {
      "field": "password",
      "message": "Password must contain uppercase letter"
    }
  ]
}
```

**401 Unauthorized** (invalid credentials):

```json
{
  "type": "https://api.dashtam.com/errors/authentication-error",
  "title": "Authentication Error",
  "status": 401,
  "detail": "Invalid email or password",
  "instance": "/api/v1/auth/login",
  "trace_id": "def456..."
}
```

**403 Forbidden** (email not verified):

```json
{
  "type": "https://api.dashtam.com/errors/authentication-error",
  "title": "Email Not Verified",
  "status": 403,
  "detail": "Email verification required before login",
  "instance": "/api/v1/auth/login",
  "trace_id": "ghi789..."
}
```

**429 Too Many Requests** (account locked):

```json
{
  "type": "https://api.dashtam.com/errors/rate-limit-error",
  "title": "Account Locked",
  "status": 429,
  "detail": "Account locked due to failed login attempts",
  "instance": "/api/v1/auth/login",
  "trace_id": "jkl012...",
  "retry_after": 900
}
```

---

## 12. Token Breach Rotation

For emergency mass token invalidation (security incidents, database breaches), Dashtam implements version-based token rotation.

**Key Capabilities:**

- **Global rotation**: Invalidate ALL tokens system-wide
- **Per-user rotation**: Invalidate only a specific user's tokens
- **Grace period**: Gradual rollout to prevent mass logout disruption

**Token Validation Rule:**

```text
token_version >= max(global_min_token_version, user.min_token_version)
```

**Reference**: See `docs/architecture/token-rotation.md` for complete implementation details.

---

## Summary

### Key Design Decisions

1. **JWT + Opaque Refresh Tokens**: Balance stateless validation (JWT) with revocability (opaque tokens)
2. **Email Verification Blocks Login**: No shortcuts, proper security from day one
3. **Token Rotation**: Detect theft, limit stolen token usefulness
4. **Account Lockout**: 5 failed attempts = 15 minute lockout
5. **Password Reset Revokes Sessions**: Assume security concern, force re-login
6. **Hexagonal Architecture**: Domain independent of infrastructure
7. **Event-Driven**: All auth actions emit events (audit, notifications, session management)
8. **Audit Trail**: All security events logged (PCI-DSS compliance)

---

**Created**: 2025-11-19 | **Last Updated**: 2026-01-10
