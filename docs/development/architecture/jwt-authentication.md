# JWT Authentication Architecture

Industry-standard JWT authentication system using Pattern A (JWT access tokens + opaque refresh tokens) for secure, scalable, and revocable user authentication.

## Overview

Dashtam implements **Pattern A** JWT authentication, the industry-standard approach used by Auth0, GitHub, Google, and 95% of production systems. This pattern combines:

- **JWT Access Tokens** (stateless, short-lived)
- **Opaque Refresh Tokens** (stateful, long-lived)

This architecture provides secure, scalable authentication for the Dashtam financial data aggregation platform, supporting multi-device sessions, email verification, password reset, and session management.

## Context

### Operating Environment

Dashtam is a FastAPI-based REST API platform that requires:

- **Stateless API design**: Horizontally scalable backend services
- **Multi-device support**: Users access from web, mobile, multiple browsers
- **Async operations**: All authentication flows use async/await patterns
- **Database-backed security**: PostgreSQL stores user accounts and tokens
- **Email integration**: AWS SES for verification and password reset emails

### System Constraints

- **No server-side sessions**: FastAPI runs stateless for scalability
- **JWT signature verification**: Access tokens validated without database lookup
- **Token revocation requirement**: Users must be able to logout and revoke sessions
- **Email verification mandatory**: Prevents fake account creation
- **Password security**: Strong password requirements and bcrypt hashing

### Key Requirements

1. **Security**: Protect user credentials and tokens from compromise
2. **Performance**: Minimize database lookups for API request authentication
3. **User experience**: Seamless login, remember-me functionality, easy logout
4. **Compliance**: Industry-standard security practices (OWASP, OAuth 2.0)
5. **Revocability**: Ability to revoke sessions on logout or password reset

## Architecture Goals

1. **Industry Standard Compliance** - Use proven patterns adopted by 95% of production systems (Auth0, GitHub, Google)
2. **Security First** - Implement token hashing, short-lived access tokens, revocable refresh tokens
3. **Simplicity** - Choose the simpler, safer Pattern A over more complex alternatives
4. **Performance at Scale** - Stateless access tokens enable horizontal scaling without database bottlenecks
5. **Easy Revocation** - Opaque refresh tokens are simpler to revoke than JWT-based alternatives
6. **Developer Experience** - Clear separation between stateless (access) and stateful (refresh) tokens

## Design Decisions

### Decision 1: Pattern A - JWT Access + Opaque Refresh Tokens

**Decision**: Use JWT for access tokens (stateless, 30-minute TTL) and opaque random strings for refresh tokens (stateful, 30-day TTL).

### The Two-Token System

```text
┌─────────────────────────────────────────────────────────────┐
│              PATTERN A (Industry Standard)                  │
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

### Rationale

**Benefits of Pattern A:**

- ✅ **Industry Standard** - Used by Auth0, GitHub, Google, Stripe, AWS Cognito
- ✅ **Simpler & Safer** - Easier to implement correctly
- ✅ **Better Security** - No JWT complexity for refresh tokens
- ✅ **Proven at Scale** - Battle-tested in production systems
- ✅ **Easier to Revoke** - Opaque tokens are simpler to manage

### Alternatives Considered

#### Pattern B: JWT Access + JWT Refresh (❌ Rejected)

**Pros:**

- No database lookup if not validating hash
- Can include claims in refresh token

**Cons:**

- ❌ More complex to implement securely
- ❌ Must validate JWT hash against DB (negates benefit)
- ❌ Easy to implement insecurely (security hole)
- ❌ Mixing stateless/stateful incorrectly
- ❌ JTI is redundant with DB record ID

**Why We Rejected It:** The original implementation used Pattern B but **forgot to validate the hash**, creating a security vulnerability. Pattern A is simpler and industry-standard.

### Trade-offs

**Accepted Trade-offs:**

1. **Refresh token requires database lookup** - Acceptable because refresh happens infrequently (every 30 min vs every API call)
2. **Access tokens cannot be immediately revoked** - Acceptable with 30-minute TTL; industry-standard behavior
3. **Refresh tokens stored in database** - Required for revocation capability; enables session management

**Benefits Gained:**

1. **API performance** - Access token validation is pure signature verification (no DB)
2. **Horizontal scalability** - Stateless access tokens enable load balancing
3. **Security** - Token hashing protects against database compromise
4. **Simplicity** - Opaque tokens are simpler than JWT for refresh use case

## Components

### 1. Access Token (JWT)

**Purpose:** Authenticate API requests

**Structure:**

```json
{
  "sub": "123e4567-e89b-12d3-a456-426614174000",  // user_id
  "email": "user@example.com",
  "type": "access",
  "exp": 1696453200,  // 30 minutes from issue
  "iat": 1696451400   // issued at
}
```

**Usage:**

```bash
# Every API request
curl -H "Authorization: Bearer eyJhbGci..." https://api.dashtam.com/api/v1/providers
```

**Lifecycle:**

1. Generated at login
2. Used for all API requests (30 min)
3. Expires automatically
4. Client requests new one using refresh token

### 2. Refresh Token (Opaque)

**Purpose:** Obtain new access tokens without re-login

**Structure:**

```text
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

**Usage:**

```bash
# When access token expires
curl -X POST https://api.dashtam.com/api/v1/auth/refresh \
  -d '{"refresh_token": "a8f4e2d9c1b7..."}'
```

**Lifecycle:**

1. Generated at login (hashed in DB)
2. Stored securely by client
3. Used to get new access token (once per 30 min)
4. Revoked at logout

### 3. Email Verification Token (Opaque)

**Purpose:** Verify user email address

**Structure:** Similar to refresh token (random string)

**Lifecycle:**

- Generated at registration
- Sent via email (plain text)
- Stored as hash in DB
- One-time use
- Expires in 24 hours

### 4. Password Reset Token (Opaque)

**Purpose:** Reset forgotten password

**Structure:** Similar to refresh token (random string)

**Lifecycle:**

- Generated on password reset request
- Sent via email (plain text)
- Stored as hash in DB
- One-time use
- Expires in 1 hour (security!)

**Responsibilities:**

- Enable secure password recovery
- Prevent unauthorized password changes

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

**Scenario:** Database compromise

| Token Type | Stored As | If DB Leaked |
|-----------|-----------|--------------|
| Plain text | `a8f4e2d9...` | ❌ Attacker can login as anyone |
| Hashed | `$2b$12$...` | ✅ Attacker can't use tokens |

**Cost:** ~300ms bcrypt verification (acceptable for refresh flow)

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

## Implementation Details

### Authentication Flows

#### Flow 1: Registration & Email Verification

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant DB as Database
    participant E as Email Service

    C->>S: POST /auth/register<br/>{email, password, name}
    S->>S: Hash password (bcrypt)
    S->>DB: Create user (inactive)
    S->>S: Generate verification token
    S->>S: Hash token (bcrypt)
    S->>DB: Store token hash
    S->>E: Send verification email
    S-->>C: {message: "Check email"}
    
    Note over C,E: User clicks link in email
    
    C->>S: GET /auth/verify-email?token=abc123
    S->>S: Hash incoming token
    S->>DB: Find matching hash
    S->>DB: Mark user as verified
    S->>DB: Mark token as used
    S-->>C: {message: "Email verified"}
```

#### Flow 2: Login

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant DB as Database

    C->>S: POST /auth/login<br/>{email, password}
    S->>DB: Fetch user by email
    S->>S: Verify password (bcrypt)
    S->>S: Check email verified
    S->>S: Check account active
    S->>S: Generate JWT access token
    S->>S: Generate opaque refresh token
    S->>S: Hash refresh token
    S->>DB: Store refresh token hash
    S-->>C: {access_token: "eyJhbGci...",<br/>refresh_token: "a8f4e2d9...",<br/>user: {...}}
    C->>C: Store tokens securely
```

#### Flow 3: Authenticated API Request

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server

    C->>S: GET /api/v1/providers<br/>Authorization: Bearer eyJhbGci...
    S->>S: Extract JWT from header
    S->>S: Verify JWT signature
    S->>S: Check expiration
    S->>S: Extract user_id from JWT
    Note over S: No DB lookup needed!
    S-->>C: {providers: [...]}
```

#### Flow 4: Token Refresh

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant DB as Database

    Note over C: Access token expired after 30 min
    
    C->>S: POST /auth/refresh<br/>{refresh_token: "a8f4e2d9..."}
    S->>S: Hash incoming token
    S->>DB: Find matching hash
    S->>DB: Verify not expired
    S->>DB: Verify not revoked
    S->>S: Generate new JWT access token
    S-->>C: {access_token: "eyJnEw...",<br/>refresh_token: "a8f4e2d9..." (SAME)}
```

#### Flow 5: Logout

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant DB as Database

    C->>S: POST /auth/logout<br/>{refresh_token: "a8f4e2d9..."}
    S->>S: Hash incoming token
    S->>DB: Find matching hash
    S->>DB: Mark token as revoked
    S->>DB: Set revoked_at timestamp
    S-->>C: {message: "Logged out successfully"}
    C->>C: Delete tokens from client storage
```

**⚠️ Important: Logout Behavior & Token Revocation:**

When a user logs out, **only the refresh token is revoked**. The JWT access token remains valid until its natural expiration (30 minutes). This is by design and consistent with industry-standard JWT implementations.

**What Gets Invalidated:**

| Token Type | Revoked on Logout? | Why? |
|------------|-------------------|------|
| **Refresh Token** (Opaque) | ✅ Yes (Immediate) | Stored in database, can be marked as revoked |
| **Access Token** (JWT) | ❌ No (Expires naturally) | Stateless, no database tracking |

**Why Access Tokens Can't Be Immediately Revoked:**

1. **Stateless by Design:** JWTs are validated by signature only, no database lookup
2. **Performance:** Checking a revocation list defeats JWT's scalability benefit
3. **Industry Standard:** Auth0, GitHub, Google, AWS Cognito all work this way

**Security Implications:**

```text
┌──────────────────────────────────────────────────────────────┐
│ After Logout: What Can/Cannot Be Done                        │
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

1. **Short Window:** 30 minutes is industry-standard (configurable)
2. **No Session Extension:** Can't get new tokens without refresh token
3. **Long-term Protection:** Refresh token (30 days) is properly revoked
4. **Performance vs Security:** Acceptable trade-off for stateless scalability

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

**Current Implementation: Pattern A (Recommended):**

✅ Refresh tokens: Immediately revocable (opaque, database-backed)  
⚠️ Access tokens: Valid until expiration (JWT, stateless)  
📚 Industry standard: 30-minute window is acceptable for most applications

#### Flow 6: Password Reset with Session Revocation

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Server
    participant DB as Database
    participant E as Email Service

    C->>S: POST /password-resets/<br/>{email: "user@example.com"}
    S->>DB: Find user by email
    S->>S: Generate reset token
    S->>S: Hash token (bcrypt)
    S->>DB: Store token hash
    S->>E: Send reset email
    S-->>C: {message: "If account exists, email sent"}
    
    Note over C,E: User clicks link in email
    
    C->>S: PATCH /password-resets/{token}<br/>{new_password: "NewSecurePass123!"}
    S->>DB: Verify token
    S->>DB: Check token not expired
    S->>S: Validate new password strength
    S->>S: Hash new password
    S->>DB: Update password hash
    S->>DB: Mark reset token as used
    S->>DB: REVOKE ALL refresh tokens 🔒
    S->>E: Send confirmation email
    S-->>C: {message: "Password reset successfully"}
    
    Note over C: User must login again with new password
```

**🔒 Security Enhancement: Session Revocation on Password Reset:**

When a user resets their password, **all active refresh tokens are immediately revoked**. This ensures that any potentially compromised sessions are terminated.

**Why This Is Critical:**

```text
┌──────────────────────────────────────────────────────────────┐
│ Scenario: Password Reset After Compromise                    │
└──────────────────────────────────────────────────────────────┘

1. Attacker compromises user's password
2. Attacker logs in (gets refresh token, 30-day lifetime)
3. User realizes account compromise
4. User requests password reset

❌ WITHOUT session revocation:
  → Attacker's refresh token still works for 30 days
  → Attacker can continue accessing account
  → Password change provides NO security!

✅ WITH session revocation:
  → All refresh tokens revoked (including attacker's)
  → Attacker cannot get new access tokens
  → Account secured immediately
  → User must re-login on all devices
```

**Implementation Details:**

```python
async def reset_password(self, token: str, new_password: str) -> User:
    """Reset password and revoke all sessions."""
    # ... validate token and password ...
    
    # Update password
    user.password_hash = self.password_service.hash_password(new_password)
    
    # Mark reset token as used
    reset_token.used_at = datetime.now(timezone.utc)
    
    # 🔒 SECURITY: Revoke ALL existing refresh tokens
    result = await self.session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked == False
        )
    )
    active_tokens = result.scalars().all()
    
    for token_record in active_tokens:
        token_record.revoked_at = datetime.now(timezone.utc)
        token_record.is_revoked = True
    
    logger.info(f"Password reset: Revoked {len(active_tokens)} sessions")
    
    await self.session.commit()
    return user
```

**Testing Password Reset Security:**

```bash
# 1. Login and save tokens
curl -k -X POST "$BASE_URL/api/v1/auth/login" \
  -d '{"email": "user@example.com", "password": "OldPass123!"}'
# Save: OLD_REFRESH_TOKEN, OLD_ACCESS_TOKEN

# 2. Request password reset
curl -k -X POST "$BASE_URL/api/v1/password-resets/" \
  -d '{"email": "user@example.com"}'

# 3. Extract reset token from logs (development mode)
docker logs dashtam-dev-app | grep 'reset-password?token=' 

# 4. Complete password reset
curl -k -X PATCH "$BASE_URL/api/v1/password-resets/$RESET_TOKEN" \
  -d '{"new_password": "NewSecurePass123!"}'

# 5. Verify old refresh token is revoked
curl -k -X POST "$BASE_URL/api/v1/auth/refresh" \
  -d '{"refresh_token": "'$OLD_REFRESH_TOKEN'"}'
# → 401 Unauthorized ✅ (Token revoked by password reset)

# 6. Verify old access token still works (until expiry)
curl -k -X GET "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $OLD_ACCESS_TOKEN"
# → 200 OK ⚠️ (Access token valid for ~30 min, then expires)
```

**User Experience:**

After password reset:

- ✅ All devices logged out (refresh tokens revoked)
- ⚠️ Current sessions may work for ~30 min (access tokens valid until expiry)
- ✅ Cannot extend sessions (refresh blocked)
- ✅ Must re-login with new password on all devices

**Security vs Convenience:**

| Approach | Security | User Impact |
|----------|----------|-------------|
| **Revoke refresh only** (current) | ✅ High | ⚠️ Logged out all devices |
| Revoke nothing | ❌ Low | ✅ No disruption |
| Revoke access + refresh | ✅✅ Highest | ❌❌ Complex JWT blocklist |

**Industry Standard:** Password reset → revoke all refresh tokens (Google, GitHub, Auth0)

### Database Schema

#### `users` Table

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

#### `refresh_tokens` Table

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

#### `email_verification_tokens` Table

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

#### `password_reset_tokens` Table

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

### API Endpoints

#### Authentication Endpoints

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

#### Example Requests

##### Register

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

##### Login

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

##### Protected Endpoint

```bash
GET /api/v1/providers
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

→ 200 OK
{
  "providers": [...]
}
```

##### Refresh Token

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

### Services Architecture

```bash
src/services/
├── auth_service.py       # Orchestrates auth flows
├── password_service.py   # Password hashing & validation
├── jwt_service.py        # JWT generation & validation
└── email_service.py      # Email sending (verification, reset, etc.)
```

#### AuthService

**Responsibility:** Orchestrate all authentication workflows

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

#### PasswordService

**Responsibility:** Password hashing and validation (sync)

```python
class PasswordService:
    """Handles password hashing with bcrypt."""
    
    def hash_password(plain_password: str) -> str
    def verify_password(plain_password: str, hashed: str) -> bool
    def validate_password_strength(password: str) -> Tuple[bool, str]
    def needs_rehash(hashed: str) -> bool
```

#### JWTService

**Responsibility:** JWT generation and validation (sync)

```python
class JWTService:
    """Handles JWT operations."""
    
    def create_access_token(user_id, email, additional_claims=None) -> str
    def decode_token(token) -> Dict[str, Any]
    def verify_token_type(token, expected_type) -> Dict[str, Any]
    def get_user_id_from_token(token) -> UUID
    def get_token_jti(token) -> UUID  # Deprecated for opaque tokens
```

## Security Considerations

### Token Revocation & Logout Behavior

**⚠️ IMPORTANT:** When users logout, only the **refresh token** is immediately revoked. The **JWT access token remains valid** until its natural expiration (30 minutes). This is by design for stateless JWT implementations.

**Key Points:**

- ✅ Refresh token: Immediately revoked (can't get new access tokens)
- ⚠️ Access token: Valid until expiry (can still access API for ~30 min)
- 📚 **See [Flow 5: Logout](#flow-5-logout)** for detailed explanation and testing examples

This is the industry-standard trade-off between performance and immediate revocation. For use cases requiring immediate JWT revocation, see alternative approaches in the logout flow documentation.

**Security Features:**

✅ **Token Hashing** - Database compromise protection  
✅ **Short Access Token TTL** - Limits exposure (30 min)  
✅ **Refresh Token Revocation** - Logout capability  
✅ **Token Expiration** - Automatic cleanup  
✅ **Device Tracking** - Monitor sessions  
✅ **IP Logging** - Detect suspicious activity  
✅ **Email Verification Required** - Prevent fake accounts  
✅ **Password Complexity Rules** - Enforce strong passwords  
✅ **Account Lockout** - Brute force protection  

### Token Storage (Client-Side)

| Storage Method | Access Token | Refresh Token |
|----------------|--------------|---------------|
| **Memory (React state)** | ✅ Recommended | ❌ Lost on reload |
| **httpOnly Cookie** | ⚠️ CSRF risk | ✅ Recommended |
| **localStorage** | ❌ XSS vulnerability | ❌ XSS vulnerability |
| **sessionStorage** | ⚠️ Acceptable | ❌ Lost on tab close |

**Recommendation:**

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

## Performance Considerations

### Stateless Access Tokens

**Benefit:** JWT access tokens enable horizontal scalability

- **No database lookup** for API request authentication
- **Signature verification only** - Pure cryptographic operation
- **Load balancing** - Any server can validate any JWT
- **Zero network latency** - No Redis/DB dependency for auth

**Performance Impact:**

```text
Traditional Session:
  Request → Server → Database lookup → Response
  Latency: ~5-20ms per request (DB query)

JWT Access Token:
  Request → Server → Signature verify → Response
  Latency: ~0.1-0.5ms (CPU only)
  
Speed improvement: 10-200x faster
```

### Refresh Token Database Lookups

**Cost:** Refresh token validation requires database lookup

- **Frequency:** Once per 30 minutes (vs every API call)
- **Operation:** Hash comparison (bcrypt.verify) + DB query
- **Latency:** ~300-500ms (bcrypt + DB round-trip)

**Why This Is Acceptable:**

1. **Infrequent:** 1 DB hit per 30 min vs 1000s of API calls
2. **User experience:** Refresh happens in background
3. **Security benefit:** Enables token revocation
4. **Scalability:** Still horizontal (DB handles refresh load easily)

**Example Load:**

```text
10,000 active users
- Access token validation: 10,000,000 requests/day (no DB)
- Refresh token validation: 20,000 requests/day (DB)
  
Database load: 0.2% of requests
Performance: 99.8% stateless
```

### Bcrypt Performance

**Cost:** ~300ms per bcrypt operation (rounds=12)

**Operations Using Bcrypt:**

- Password hashing (registration): 1x per user signup
- Password verification (login): 1x per login
- Token hashing (refresh token): 1x per login
- Token verification (refresh): 1x per 30 minutes

**Optimization Strategies:**

1. **Accept the cost** - Security > performance for auth operations
2. **Async execution** - FastAPI handles bcrypt in threadpool
3. **Cache nothing** - Security tokens must be verified every time
4. **Monitor load** - Use APM to track auth endpoint latency

**Why 12 Rounds?**

- **Security:** OWASP recommended minimum
- **Performance:** ~300ms is acceptable for auth endpoints
- **Future-proof:** As CPUs get faster, 12 rounds remains secure

## Testing Strategy

### Test Pyramid

**Test Distribution:**

| Test Level | Coverage | Focus |
|------------|----------|-------|
| **E2E Tests** | 10% | Full authentication flows end-to-end |
| **Integration Tests** | 20% | API endpoint testing, database operations |
| **Unit Tests** | 70% | Service methods, token validation, business logic |

**Rationale:** The pyramid structure emphasizes a solid foundation of fast unit tests, with fewer but more comprehensive integration and E2E tests at higher levels.

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

## Future Enhancements

🔲 **Token Rotation** - Rotate refresh token on every use  
🔲 **Multi-Factor Authentication** - TOTP/SMS verification  
🔲 **Social Login** - OAuth with Google, GitHub  
🔲 **Device Management** - View/revoke all sessions  
🔲 **Rate Limiting** - Prevent brute force attacks  
🔲 **Security Events** - Email notifications for suspicious activity  
🔲 **Refresh Token Families** - Detect token reuse attacks  
🔲 **IP Whitelisting** - Restrict login by IP (optional)  

## References

- [RFC 6749: OAuth 2.0](https://datatracker.ietf.org/doc/html/rfc6749)
- [RFC 7519: JSON Web Token (JWT)](https://datatracker.ietf.org/doc/html/rfc7519)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [Auth0: Token Best Practices](https://auth0.com/docs/secure/tokens/token-best-practices)
- [JWT.io](https://jwt.io/)

**Related Dashtam Documents:**

- [Registration Flow](../../api-flows/auth/registration.md) - Registration flow testing
- [Login Flow](../../api-flows/auth/login.md) - Login flow testing
- [Complete Auth Flow](../../api-flows/auth/complete-auth-flow.md) - End-to-end testing
- [JWT Auth Quick Reference](../guides/jwt-auth-quick-reference.md) - Quick reference
- [Async vs Sync Patterns](async-vs-sync-patterns.md) - Service implementation patterns
- [RESTful API Design](restful-api-design.md) - API endpoint design standards
- [Schemas Design](schemas-design.md) - Request/response schema patterns

---

## Document Information

**Template:** architecture-template.md
**Created:** 2025-10-04
**Last Updated:** 2025-10-16
