# JWT Authentication Architecture

**Last Updated**: 2025-10-04  
**Status**: ✅ Implemented (Pattern A - Industry Standard)  
**Version**: 1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Design Pattern: Pattern A](#design-pattern-pattern-a)
3. [Token Types](#token-types)
4. [Security Model](#security-model)
5. [Authentication Flows](#authentication-flows)
6. [Database Schema](#database-schema)
7. [API Endpoints](#api-endpoints)
8. [Implementation Details](#implementation-details)
9. [Security Considerations](#security-considerations)
10. [Testing Strategy](#testing-strategy)

---

## Overview

Dashtam implements **Pattern A** JWT authentication, the industry-standard approach used by Auth0, GitHub, Google, and 95% of production systems. This pattern combines:

- **JWT Access Tokens** (stateless, short-lived)
- **Opaque Refresh Tokens** (stateful, long-lived)

### Why Pattern A?

✅ **Industry Standard** - Used by Auth0, GitHub, Google, Stripe, AWS Cognito  
✅ **Simpler & Safer** - Easier to implement correctly  
✅ **Better Security** - No JWT complexity for refresh tokens  
✅ **Proven at Scale** - Battle-tested in production systems  
✅ **Easier to Revoke** - Opaque tokens are simpler to manage  

---

## Design Pattern: Pattern A

### The Two-Token System

```
┌─────────────────────────────────────────────────────────────┐
│              PATTERN A (Industry Standard)                   │
└─────────────────────────────────────────────────────────────┘

ACCESS TOKEN (JWT):
├─ Format: JSON Web Token (eyJhbGciOi...)
├─ Lifetime: 30 minutes (short-lived)
├─ Storage: Client memory (not localStorage!)
├─ Purpose: Authenticate API requests
├─ Validation: Signature verification only
├─ Database: No lookup required (stateless)
└─ Contains: user_id, email, expiration

REFRESH TOKEN (Opaque):
├─ Format: Random string (a8f4e2d9c1b7...)
├─ Lifetime: 30 days (long-lived)
├─ Storage: Client httpOnly cookie or secure storage
├─ Purpose: Obtain new access tokens
├─ Validation: Hash lookup in database
├─ Database: Required for validation (stateful)
└─ Contains: Only random bytes (no claims)
```

### Why This Works

| Aspect | Access Token (JWT) | Refresh Token (Opaque) |
|--------|-------------------|------------------------|
| **Speed** | Fast (no DB lookup) | Slower (DB lookup) |
| **Use Frequency** | Every API call | Rarely (every 30 min) |
| **Revocation** | Not revocable* | Easily revocable |
| **Security** | Signature-based | Hash-based |
| **Complexity** | Higher (JWT) | Lower (random string) |

*Access tokens can't be revoked but expire quickly (30 min)

---

## Token Types

### 1. Access Token (JWT)

**Purpose**: Authenticate API requests

**Structure**:
```json
{
  "sub": "123e4567-e89b-12d3-a456-426614174000",  // user_id
  "email": "user@example.com",
  "type": "access",
  "exp": 1696453200,  // 30 minutes from issue
  "iat": 1696451400   // issued at
}
```

**Usage**:
```bash
# Every API request
curl -H "Authorization: Bearer eyJhbGci..." https://api.dashtam.com/api/v1/providers
```

**Lifecycle**:
1. Generated at login
2. Used for all API requests (30 min)
3. Expires automatically
4. Client requests new one using refresh token

### 2. Refresh Token (Opaque)

**Purpose**: Obtain new access tokens without re-login

**Structure**:
```
a8f4e2d9c1b7f6e3d2c8b4a1e9f7d6c5e4d3c2b1a9f8e7d6c5b4a3e2d1c0b9a8
(64 character random URL-safe string)
```

**Storage** (Database):
```python
RefreshToken(
    id=UUID("..."),
    user_id=UUID("..."),
    token_hash="$2b$12$...",  # bcrypt hash of token
    expires_at=datetime(2025, 11, 04),  # 30 days
    revoked_at=None,
    is_revoked=False,
    device_info="Chrome 118.0 on macOS",
    ip_address="192.168.1.100"
)
```

**Usage**:
```bash
# When access token expires
curl -X POST https://api.dashtam.com/api/v1/auth/refresh \
  -d '{"refresh_token": "a8f4e2d9c1b7..."}'
```

**Lifecycle**:
1. Generated at login (hashed in DB)
2. Stored securely by client
3. Used to get new access token (once per 30 min)
4. Revoked at logout

### 3. Email Verification Token (Opaque)

**Purpose**: Verify user email address

**Structure**: Similar to refresh token (random string)

**Lifecycle**:
- Generated at registration
- Sent via email (plain text)
- Stored as hash in DB
- One-time use
- Expires in 24 hours

### 4. Password Reset Token (Opaque)

**Purpose**: Reset forgotten password

**Structure**: Similar to refresh token (random string)

**Lifecycle**:
- Generated on password reset request
- Sent via email (plain text)
- Stored as hash in DB
- One-time use
- Expires in 1 hour (security!)

---

## Security Model

### Token Hashing Strategy

All stateful tokens (refresh, email verification, password reset) are hashed before storage:

```python
# Generation
plain_token = secrets.token_urlsafe(32)  # 256 bits of entropy
token_hash = bcrypt.hashpw(plain_token, bcrypt.gensalt(rounds=12))

# Storage
db.store(token_hash)  # Never store plain token!

# Return to client
return plain_token  # Client needs plain token
```

### Why Hash Tokens?

**Scenario**: Database compromise

| Token Type | Stored As | If DB Leaked |
|-----------|-----------|--------------|
| Plain text | `a8f4e2d9...` | ❌ Attacker can login as anyone |
| Hashed | `$2b$12$...` | ✅ Attacker can't use tokens |

**Cost**: ~300ms bcrypt verification (acceptable for refresh flow)

### Validation Flow

```python
# Client sends plain token
incoming_token = "a8f4e2d9c1b7..."

# Server validates
all_tokens = db.query(RefreshToken).filter(revoked_at=None)
for token_record in all_tokens:
    if bcrypt.verify(incoming_token, token_record.token_hash):
        # Valid token found!
        return generate_new_access_token()

# No match found
raise AuthenticationError("Invalid token")
```

### Security Features

✅ **Token Hashing** - Database compromise protection  
✅ **Short Access Token TTL** - Limits exposure (30 min)  
✅ **Refresh Token Revocation** - Logout capability  
✅ **Token Expiration** - Automatic cleanup  
✅ **Device Tracking** - Monitor sessions  
✅ **IP Logging** - Detect suspicious activity  
✅ **Email Verification Required** - Prevent fake accounts  
✅ **Password Complexity Rules** - Enforce strong passwords  
✅ **Account Lockout** - Brute force protection  

---

## Authentication Flows

### Flow 1: Registration & Email Verification

```
┌────────┐                                           ┌────────┐
│ Client │                                           │ Server │
└────────┘                                           └────────┘
    │                                                      │
    │  POST /auth/register                                │
    │  {email, password, name}                            │
    ├────────────────────────────────────────────────────>│
    │                                                      │
    │                                              1. Hash password
    │                                              2. Create user (inactive)
    │                                              3. Generate verification token
    │                                              4. Hash & store token
    │                                              5. Send email with plain token
    │                                                      │
    │  {message: "Check email"}                           │
    │<────────────────────────────────────────────────────┤
    │                                                      │
    │                                                      │
    │  (User clicks link in email)                        │
    │  GET /auth/verify-email?token=abc123...             │
    ├────────────────────────────────────────────────────>│
    │                                                      │
    │                                              1. Hash incoming token
    │                                              2. Find matching hash in DB
    │                                              3. Mark user as verified
    │                                              4. Mark token as used
    │                                                      │
    │  {message: "Email verified"}                        │
    │<────────────────────────────────────────────────────┤
```

### Flow 2: Login

```
┌────────┐                                           ┌────────┐
│ Client │                                           │ Server │
└────────┘                                           └────────┘
    │                                                      │
    │  POST /auth/login                                   │
    │  {email, password}                                  │
    ├────────────────────────────────────────────────────>│
    │                                                      │
    │                                              1. Verify password
    │                                              2. Check email verified
    │                                              3. Check account active
    │                                              4. Generate JWT access token
    │                                              5. Generate opaque refresh token
    │                                              6. Hash & store refresh token
    │                                                      │
    │  {                                                   │
    │    access_token: "eyJhbGci...",  (JWT)              │
    │    refresh_token: "a8f4e2d9...", (Opaque)           │
    │    token_type: "bearer",                            │
    │    expires_in: 1800                                 │
    │  }                                                   │
    │<────────────────────────────────────────────────────┤
    │                                                      │
    │  Store tokens securely                              │
```

### Flow 3: Authenticated API Request

```
┌────────┐                                           ┌────────┐
│ Client │                                           │ Server │
└────────┘                                           └────────┘
    │                                                      │
    │  GET /api/v1/providers                              │
    │  Authorization: Bearer eyJhbGci...                  │
    ├────────────────────────────────────────────────────>│
    │                                                      │
    │                                              1. Extract JWT from header
    │                                              2. Verify JWT signature
    │                                              3. Check expiration
    │                                              4. Extract user_id from JWT
    │                                              5. (No DB lookup needed!)
    │                                                      │
    │  {providers: [...]}                                 │
    │<────────────────────────────────────────────────────┤
```

### Flow 4: Token Refresh

```
┌────────┐                                           ┌────────┐
│ Client │                                           │ Server │
└────────┘                                           └────────┘
    │                                                      │
    │  (Access token expired after 30 min)                │
    │                                                      │
    │  POST /auth/refresh                                 │
    │  {refresh_token: "a8f4e2d9..."}                     │
    ├────────────────────────────────────────────────────>│
    │                                                      │
    │                                              1. Hash incoming token
    │                                              2. Find matching hash in DB
    │                                              3. Verify not expired
    │                                              4. Verify not revoked
    │                                              5. Generate new JWT access token
    │                                                      │
    │  {                                                   │
    │    access_token: "eyJnEw...",  (NEW JWT)            │
    │    refresh_token: "a8f4e2d9...", (SAME)             │
    │    token_type: "bearer",                            │
    │    expires_in: 1800                                 │
    │  }                                                   │
    │<────────────────────────────────────────────────────┤
```

### Flow 5: Logout

```
┌────────┐                                           ┌────────┐
│ Client │                                           │ Server │
└────────┘                                           └────────┘
    │                                                      │
    │  POST /auth/logout                                  │
    │  {refresh_token: "a8f4e2d9..."}                     │
    ├────────────────────────────────────────────────────>│
    │                                                      │
    │                                              1. Hash incoming token
    │                                              2. Find matching hash in DB
    │                                              3. Mark token as revoked
    │                                              4. Set revoked_at timestamp
    │                                                      │
    │  {message: "Logged out successfully"}               │
    │<────────────────────────────────────────────────────┤
    │                                                      │
    │  Delete tokens from client storage                  │
```

**⚠️ Important: Logout Behavior & Token Revocation**

When a user logs out, **only the refresh token is revoked**. The JWT access token remains valid until its natural expiration (30 minutes). This is by design and consistent with industry-standard JWT implementations.

**What Gets Invalidated:**

| Token Type | Revoked on Logout? | Why? |
|------------|-------------------|------|
| **Refresh Token** (Opaque) | ✅ Yes (Immediate) | Stored in database, can be marked as revoked |
| **Access Token** (JWT) | ❌ No (Expires naturally) | Stateless, no database tracking |

**Why Access Tokens Can't Be Immediately Revoked:**

1. **Stateless by Design**: JWTs are validated by signature only, no database lookup
2. **Performance**: Checking a revocation list defeats JWT's scalability benefit
3. **Industry Standard**: Auth0, GitHub, Google, AWS Cognito all work this way

**Security Implications:**

```
┌──────────────────────────────────────────────────────────────┐
│ After Logout: What Can/Cannot Be Done                       │
└──────────────────────────────────────────────────────────────┘

✅ CAN (with old access token, for ~30 min):
  - Access protected API endpoints
  - Read user profile
  - Perform authenticated actions

❌ CANNOT (refresh token revoked):
  - Get new access tokens
  - Extend session beyond current token expiration
  - Refresh authentication after 30 minutes
```

**Why This Is Acceptable:**

1. **Short Window**: 30 minutes is industry-standard (configurable)
2. **No Session Extension**: Can't get new tokens without refresh token
3. **Long-term Protection**: Refresh token (30 days) is properly revoked
4. **Performance vs Security**: Acceptable trade-off for stateless scalability

**Testing Logout:**

```bash
# 1. Logout revokes refresh token
curl -k -X POST "$BASE_URL/api/v1/auth/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"refresh_token": "'$REFRESH_TOKEN'"}'
# → {"message": "Logged out successfully"}

# 2. Verify refresh token is revoked
curl -k -X POST "$BASE_URL/api/v1/auth/refresh" \
  -d '{"refresh_token": "'$REFRESH_TOKEN'"}'
# → 401 Unauthorized: "Invalid or revoked refresh token" ✅

# 3. Access token STILL WORKS (until expiry)
curl -k -X GET "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# → 200 OK: Returns user profile ⚠️ Expected behavior
```

**If Immediate Revocation Is Required:**

For use cases requiring immediate JWT revocation (rare):

```python
# Option 1: JWT Blocklist (adds database lookup)
# - Store revoked JTI (JWT ID) in Redis
# - Check every JWT against blocklist
# - Sacrifices stateless benefit

# Option 2: Shorter Access Token TTL
# - Reduce from 30 min to 5-10 min
# - More frequent refresh operations
# - Better security, more API calls

# Option 3: User-level revocation flag
# - Add database lookup for critical endpoints
# - Check user.is_active on sensitive operations
# - Hybrid approach: stateless + selective checks
```

**Current Implementation: Pattern A (Recommended)**

✅ Refresh tokens: Immediately revocable (opaque, database-backed)  
⚠️ Access tokens: Valid until expiration (JWT, stateless)  
📚 Industry standard: 30-minute window is acceptable for most applications

---

## Database Schema

### `users` Table

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Authentication
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    
    -- Email verification
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    email_verified_at TIMESTAMPTZ,
    
    -- Account security
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    account_locked_until TIMESTAMPTZ,
    
    -- Login tracking
    last_login_at TIMESTAMPTZ,
    last_login_ip INET
);

CREATE INDEX idx_users_email ON users(email);
```

### `refresh_tokens` Table

```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Token data
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,  -- bcrypt hash
    expires_at TIMESTAMPTZ NOT NULL,
    
    -- Revocation
    revoked_at TIMESTAMPTZ,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Device tracking
    device_info TEXT,
    ip_address INET,
    user_agent TEXT,
    last_used_at TIMESTAMPTZ
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_is_revoked ON refresh_tokens(is_revoked);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
```

### `email_verification_tokens` Table

```sql
CREATE TABLE email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ
);

CREATE INDEX idx_email_verification_tokens_user_id ON email_verification_tokens(user_id);
CREATE INDEX idx_email_verification_tokens_expires_at ON email_verification_tokens(expires_at);
```

### `password_reset_tokens` Table

```sql
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX idx_password_reset_tokens_expires_at ON password_reset_tokens(expires_at);
```

---

## API Endpoints

### Authentication Endpoints

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/v1/auth/register` | POST | Register new user | No |
| `/api/v1/auth/verify-email` | POST | Verify email address | No |
| `/api/v1/auth/login` | POST | Login with credentials | No |
| `/api/v1/auth/refresh` | POST | Get new access token | No* |
| `/api/v1/auth/logout` | POST | Revoke refresh token | Yes |
| `/api/v1/auth/password-reset/request` | POST | Request password reset | No |
| `/api/v1/auth/password-reset/confirm` | POST | Confirm password reset | No |
| `/api/v1/auth/me` | GET | Get current user profile | Yes |
| `/api/v1/auth/me` | PATCH | Update user profile | Yes |

*Requires valid refresh token, not access token

### Example Requests

#### Register
```bash
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "name": "John Doe"
}

→ 201 Created
{
  "message": "Registration successful. Please check your email to verify your account."
}
```

#### Login
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

→ 200 OK
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "a8f4e2d9c1b7f6e3d2c8b4a1e9f7d6c5...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "name": "John Doe",
    "email_verified": true,
    "is_active": true,
    "created_at": "2025-10-04T20:00:00Z",
    "last_login_at": "2025-10-04T22:00:00Z"
  }
}
```

#### Protected Endpoint
```bash
GET /api/v1/providers
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

→ 200 OK
{
  "providers": [...]
}
```

#### Refresh Token
```bash
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "a8f4e2d9c1b7f6e3d2c8b4a1e9f7d6c5..."
}

→ 200 OK
{
  "access_token": "eyJnEwMiOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "a8f4e2d9c1b7f6e3d2c8b4a1e9f7d6c5...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

---

## Implementation Details

### Services Architecture

```
src/services/
├── auth_service.py       # Orchestrates auth flows
├── password_service.py   # Password hashing & validation
├── jwt_service.py        # JWT generation & validation
└── email_service.py      # Email sending (verification, reset, etc.)
```

### AuthService

**Responsibility**: Orchestrate all authentication workflows

```python
class AuthService:
    """Main authentication service (async)."""
    
    async def register_user(email, password, name) -> User
    async def verify_email(token) -> User
    async def login(email, password) -> Tuple[str, str, User]
    async def refresh_access_token(refresh_token) -> str
    async def logout(refresh_token) -> None
    async def request_password_reset(email) -> None
    async def reset_password(token, new_password) -> User
    async def update_user_profile(user_id, name) -> User
    async def get_user_by_id(user_id) -> User
    
    # Private helpers
    async def _create_refresh_token(user_id) -> Tuple[str, RefreshToken]
    async def _create_verification_token(user_id) -> Tuple[str, EmailVerificationToken]
    async def _create_password_reset_token(user_id) -> Tuple[str, PasswordResetToken]
```

### PasswordService

**Responsibility**: Password hashing and validation (sync)

```python
class PasswordService:
    """Handles password hashing with bcrypt."""
    
    def hash_password(plain_password: str) -> str
    def verify_password(plain_password: str, hashed: str) -> bool
    def validate_password_strength(password: str) -> Tuple[bool, str]
    def needs_rehash(hashed: str) -> bool
```

### JWTService

**Responsibility**: JWT generation and validation (sync)

```python
class JWTService:
    """Handles JWT operations."""
    
    def create_access_token(user_id, email, additional_claims=None) -> str
    def decode_token(token) -> Dict[str, Any]
    def verify_token_type(token, expected_type) -> Dict[str, Any]
    def get_user_id_from_token(token) -> UUID
    def get_token_jti(token) -> UUID  # Deprecated for opaque tokens
```

---

## Security Considerations

### Token Revocation & Logout Behavior

**⚠️ IMPORTANT**: When users logout, only the **refresh token** is immediately revoked. The **JWT access token remains valid** until its natural expiration (30 minutes). This is by design for stateless JWT implementations.

**Key Points:**
- ✅ Refresh token: Immediately revoked (can't get new access tokens)
- ⚠️ Access token: Valid until expiry (can still access API for ~30 min)
- 📚 **See [Flow 5: Logout](#flow-5-logout)** for detailed explanation and testing examples

This is the industry-standard trade-off between performance and immediate revocation. For use cases requiring immediate JWT revocation, see alternative approaches in the logout flow documentation.

### Token Storage (Client-Side)

| Storage Method | Access Token | Refresh Token |
|----------------|--------------|---------------|
| **Memory (React state)** | ✅ Recommended | ❌ Lost on reload |
| **httpOnly Cookie** | ⚠️ CSRF risk | ✅ Recommended |
| **localStorage** | ❌ XSS vulnerability | ❌ XSS vulnerability |
| **sessionStorage** | ⚠️ Acceptable | ❌ Lost on tab close |

**Recommendation**:
- Access Token: React state/memory
- Refresh Token: httpOnly cookie (auto-sent)

### Password Requirements

```python
MIN_LENGTH = 8
REQUIRE_UPPERCASE = True   # At least 1: A-Z
REQUIRE_LOWERCASE = True   # At least 1: a-z
REQUIRE_DIGIT = True       # At least 1: 0-9
REQUIRE_SPECIAL = True     # At least 1: !@#$%^&*
```

### Account Lockout

```python
# After 10 failed login attempts
LOCKOUT_DURATION = 1 hour
MAX_FAILED_ATTEMPTS = 10

# Reset counter on successful login
```

### Token Expiration

| Token Type | Default TTL | Configurable |
|-----------|-------------|--------------|
| Access Token | 30 minutes | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Refresh Token | 30 days | `REFRESH_TOKEN_EXPIRE_DAYS` |
| Email Verification | 24 hours | `EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS` |
| Password Reset | 1 hour | `PASSWORD_RESET_TOKEN_EXPIRE_HOURS` |

### Rate Limiting (Future)

```python
# Planned rate limits
LOGIN_ATTEMPTS_PER_IP = 5 per 15 minutes
PASSWORD_RESET_REQUESTS = 3 per hour per email
EMAIL_VERIFICATION_RESEND = 3 per hour per email
REFRESH_TOKEN_USAGE = 10 per hour per token
```

---

## Testing Strategy

### Test Pyramid

```
              /\
             /  \      E2E (10%)
            /____\     - Full auth flows
           /      \    
          /  API   \   Integration (20%)
         /  Tests   \  - Endpoint testing
        /___________\ 
       /             \
      /     Unit      \ Unit Tests (70%)
     /     Tests       \ - Service methods
    /___________________\ - Token validation
```

### Test Coverage Requirements

| Component | Target Coverage |
|-----------|----------------|
| **AuthService** | 95%+ |
| **PasswordService** | 95%+ |
| **JWTService** | 90%+ |
| **API Endpoints** | 85%+ |
| **Overall** | 85%+ |

### Key Test Scenarios

✅ **Registration**
- Valid registration
- Duplicate email
- Weak password
- Email sending failure

✅ **Email Verification**
- Valid token
- Expired token
- Already used token
- Invalid token

✅ **Login**
- Valid credentials
- Invalid password
- Unverified email
- Inactive account
- Locked account

✅ **Token Refresh**
- Valid refresh token
- Expired refresh token
- Revoked refresh token
- Invalid refresh token

✅ **Logout**
- Valid logout
- Already revoked token
- Invalid token

✅ **Password Reset**
- Request reset
- Valid reset token
- Expired reset token
- Weak new password

---

## Comparison: Pattern A vs Pattern B

### Pattern A: JWT Access + Opaque Refresh (✅ Our Choice)

**Pros**:
- ✅ Simpler to implement correctly
- ✅ Industry standard (95% adoption)
- ✅ Easier token validation (hash lookup)
- ✅ No JWT complexity for refresh
- ✅ Consistent with other opaque tokens

**Cons**:
- ⚠️ Database lookup on refresh (acceptable - infrequent)

### Pattern B: JWT Access + JWT Refresh (❌ Rejected)

**Pros**:
- ✅ No database lookup if not validating hash
- ✅ Can include claims in refresh token

**Cons**:
- ❌ More complex to implement securely
- ❌ Must validate JWT hash against DB (negates benefit)
- ❌ Easy to implement insecurely (security hole)
- ❌ Mixing stateless/stateful incorrectly
- ❌ JTI is redundant with DB record ID

**Why We Changed**: The original implementation had Pattern B but **forgot to validate the hash**, creating a security vulnerability. Pattern A is simpler and industry-standard.

---

## Future Enhancements

### Planned Features

🔲 **Token Rotation** - Rotate refresh token on every use  
🔲 **Multi-Factor Authentication** - TOTP/SMS verification  
🔲 **Social Login** - OAuth with Google, GitHub  
🔲 **Device Management** - View/revoke all sessions  
🔲 **Rate Limiting** - Prevent brute force attacks  
🔲 **Security Events** - Email notifications for suspicious activity  
🔲 **Refresh Token Families** - Detect token reuse attacks  
🔲 **IP Whitelisting** - Restrict login by IP (optional)  

---

## References

- [RFC 6749: OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc6749)
- [RFC 7519: JSON Web Token (JWT)](https://datatracker.ietf.org/doc/html/rfc7519)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [Auth0: Token Best Practices](https://auth0.com/docs/secure/tokens/token-best-practices)
- [JWT.io](https://jwt.io/)

---

**Document Version**: 1.0  
**Last Reviewed**: 2025-10-04  
**Status**: ✅ Production Ready
