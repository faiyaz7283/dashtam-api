# Architecture Improvement Guide

**Document Purpose**: Track design flaws discovered during development and testing, with recommended best-practice solutions to improve application quality, security, and reliability.

**Status**: Living Document - Updated as issues are discovered  
**Priority**: High-priority items should be addressed before production deployment

---

## 🎉 Recent Achievements

### ✅ Completed Items (October 2025)

**P0 Critical Issues - RESOLVED**:
1. ✅ **Timezone-aware datetime storage** - Completed 2025-10-03
   - Full TIMESTAMPTZ implementation across all tables
   - Alembic migration: `bce8c437167b`
   - All 295 tests updated and passing (76% coverage)
   - PR: #5 merged to development

2. ✅ **Database migration framework** - Completed 2025-10-03
   - Alembic fully integrated with async support
   - Automatic migrations in all environments (dev/test/CI)
   - Comprehensive documentation: `docs/development/infrastructure/database-migrations.md`
   - PR: #6 merged to development

**P1 High-Priority Issues - RESOLVED**:
3. ✅ **HTTP connection timeouts** - Completed 2025-10-04
   - HTTP timeout configuration in settings (30s total, 10s connect)
   - Applied to all provider HTTP calls (Schwab)
   - Comprehensive unit tests for timeout behavior
   - PR: #7 merged to development

4. ✅ **OAuth token rotation handling** - Completed 2025-10-04
   - Fixed Schwab provider refresh token response handling
   - Enhanced TokenService with rotation detection (3 scenarios)
   - Comprehensive documentation: `docs/development/guides/token-rotation.md`
   - 8 unit tests covering all rotation scenarios
   - PR: #8 merged to development

**Impact**: All P0 and P1 items resolved. System is production-ready from architecture perspective. Focus can now shift to P2 items for enhanced security and operational excellence.

---

## Critical Issues (Must Fix Before Production)

### ~~1. Timezone-Naive DateTime Storage~~ ✅ RESOLVED

**Status**: ✅ **COMPLETED 2025-10-03** (PR #5)  
**Resolution**: Full timezone-aware implementation with TIMESTAMPTZ

**What Was Done**:

**Problem**:
- Timestamps are stored without timezone information
- Token expiration comparisons fail when comparing aware vs naive datetimes
- Financial applications MUST have precise, unambiguous timestamps
- Regulatory compliance (SOC 2, PCI-DSS) requires timezone-aware audit trails
- Cannot accurately track when events occurred across different timezones
- Risk of data corruption during DST transitions

**Impact**:
- **Regulatory**: Audit logs may not meet compliance requirements
- **Functional**: Token expiration logic breaks with timezone mismatches
- **Data Integrity**: Transaction timestamps may be ambiguous
- **User Experience**: Incorrect timestamps displayed to users in different timezones

**Affected Components**:
```
src/models/base.py          - DashtamBase.created_at, updated_at, deleted_at
src/models/provider.py      - All datetime fields (connected_at, expires_at, etc.)
src/services/token_service.py - Token expiration calculations
```

**Best Practice Solution**:

1. **Database Level**: Use PostgreSQL `TIMESTAMP WITH TIME ZONE` (timestamptz)
   ```python
   from sqlalchemy import DateTime
   from datetime import timezone
   
   # ✅ CORRECT - Timezone-aware field
   created_at: datetime = Field(
       sa_column=Column(DateTime(timezone=True)),
       default_factory=lambda: datetime.now(timezone.utc)
   )
   ```

2. **Application Level**: Always use timezone-aware datetimes
   ```python
   # ✅ CORRECT
   from datetime import datetime, timezone
   now = datetime.now(timezone.utc)
   
   # ❌ WRONG
   now = datetime.utcnow()  # Deprecated and timezone-naive
   ```

3. **ORM Configuration**: Configure SQLModel/SQLAlchemy for timezone awareness
   ```python
   from sqlalchemy import event, DateTime
   
   # Ensure all DateTime columns use timezone
   @event.listens_for(Base.metadata, "before_create")
   def set_datetime_timezone(target, connection, **kw):
       for table in target.tables.values():
           for column in table.columns:
               if isinstance(column.type, DateTime):
                   column.type.timezone = True
   ```

4. **Validation**: Add Pydantic validators to ensure timezone awareness
   ```python
   from pydantic import field_validator
   
   @field_validator('created_at', 'expires_at')
   @classmethod
   def ensure_timezone_aware(cls, v):
       if v and v.tzinfo is None:
           raise ValueError('Datetime must be timezone-aware')
       return v
   ```

**Migration Strategy**:
1. Create Alembic migration to alter columns to `TIMESTAMP WITH TIME ZONE`
2. Backfill existing data (assume UTC if no timezone)
3. Update all model field definitions
4. Add timezone validation to prevent naive datetimes
5. Update all tests to use timezone-aware datetimes
6. Add CI check to fail on `datetime.utcnow()` usage

**Implementation Details**:
- ✅ All datetime columns converted to `TIMESTAMP WITH TIME ZONE`
- ✅ All Python code uses `datetime.now(timezone.utc)`
- ✅ SQLModel field definitions updated with `sa_column=Column(timezone=True))`
- ✅ Fixed 4 integration tests for timezone-aware comparisons
- ✅ 295/295 tests passing (76% coverage)
- ✅ Alembic migration: `bce8c437167b`

**Verification**:
```sql
-- Confirmed: All datetime columns are TIMESTAMPTZ
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND data_type LIKE '%time%';
-- Result: timestamp with time zone
```

**References**:
- [PostgreSQL Timestamp Documentation](https://www.postgresql.org/docs/current/datatype-datetime.html)
- [Python datetime best practices](https://blog.ganssle.io/articles/2019/11/utcnow.html)
- [PCI-DSS Requirement 10.4.2](https://www.pcisecuritystandards.org/) - Time synchronization

---

## High Priority Issues

### ~~2. Database Migration Framework~~ ✅ RESOLVED

**Status**: ✅ **COMPLETED 2025-10-03** (PR #6)  
**Resolution**: Alembic fully integrated with automatic execution

**What Was Done**:
- ✅ Alembic configured with async SQLAlchemy support
- ✅ Initial migration created: `20251003_2149-bce8c437167b`
- ✅ Automatic migration execution in all environments:
  - Development: Runs on `make dev-up`
  - Test: Runs on `make test-up`
  - CI/CD: Runs in GitHub Actions pipeline
- ✅ Makefile commands added:
  - `make migrate-create` - Generate new migration
  - `make migrate-up/down` - Apply/rollback migrations
  - `make migrate-history` - View migration history
  - `make migrate-current` - Check current version
- ✅ Comprehensive documentation: 710-line guide
- ✅ Ruff linting hooks integrated
- ✅ Timestamped filenames with UTC timezone

**Implementation Files**:
- `alembic.ini` - Configuration
- `alembic/env.py` - Async environment setup
- `alembic/versions/` - Migration scripts
- `docs/development/infrastructure/database-migrations.md` - Full guide

**Verification**:
```bash
make migrate-current
# Output: bce8c437167b (head)

make migrate-history
# Shows: Initial database schema with timezone-aware datetimes
```

---

### ~~3. HTTP Connection Timeout Handling~~ ✅ RESOLVED

**Status**: ✅ **COMPLETED 2025-10-04** (PR #7)  
**Resolution**: HTTP timeout configuration implemented across all provider API calls

**What Was Done**:
- ✅ Added HTTP timeout settings to core configuration:
  - `HTTP_TIMEOUT_TOTAL`: 30 seconds (overall request timeout)
  - `HTTP_TIMEOUT_CONNECT`: 10 seconds (connection establishment)
  - `HTTP_TIMEOUT_READ`: 30 seconds (reading response data)
  - `HTTP_TIMEOUT_POOL`: 5 seconds (acquiring connection from pool)
- ✅ Helper method `get_http_timeout()` returns configured `httpx.Timeout` object
- ✅ Applied to all Schwab provider HTTP calls (authenticate, refresh, accounts, transactions)
- ✅ Configurable via environment variables for different environments
- ✅ 5 unit tests validating timeout configuration and behavior
- ✅ Documentation in code and docstrings

**Implementation Files**:
- `src/core/config.py` - Timeout configuration settings
- `src/providers/schwab.py` - Applied to all HTTP calls
- `tests/unit/core/test_config_timeouts.py` - Comprehensive tests

**Verification**:
```python
# All httpx.AsyncClient calls now use timeouts
async with httpx.AsyncClient(timeout=settings.get_http_timeout()) as client:
    response = await client.post(url, ...)
```

**Benefits**:
- Prevents indefinite hangs on slow/unresponsive APIs
- Protects against connection pool exhaustion
- Better user experience with predictable response times
- Prevents resource exhaustion attacks

---

### ~~4. OAuth Token Rotation Logic~~ ✅ RESOLVED

**Status**: ✅ **COMPLETED 2025-10-04** (PR #8)  
**Resolution**: Universal token rotation detection implemented with comprehensive testing

**What Was Done**:
- ✅ Fixed Schwab provider to only include `refresh_token` if provider sends it
- ✅ Enhanced TokenService with intelligent rotation detection:
  - **Scenario 1**: Provider rotates token (sends new refresh_token)
  - **Scenario 2**: No rotation (omits refresh_token key) - most common
  - **Scenario 3**: Same token returned (edge case)
- ✅ Improved logging for all rotation scenarios (INFO and DEBUG levels)
- ✅ Updated audit logs to capture rotation details (`token_rotated`, `rotation_type`)
- ✅ Comprehensive BaseProvider documentation with implementation examples
- ✅ Complete implementation guide: `docs/development/guides/token-rotation.md` (469 lines)
- ✅ 8 unit tests covering all rotation scenarios (511 lines)
- ✅ Universal logic works for ANY OAuth provider (Schwab, Plaid, Chase, etc.)

**Implementation Files**:
- `src/providers/schwab.py` - Fixed refresh token response handling
- `src/services/token_service.py` - Enhanced rotation detection and logging
- `src/providers/base.py` - Detailed refresh_authentication() documentation
- `docs/development/guides/token-rotation.md` - Complete implementation guide
- `tests/unit/services/test_token_rotation.py` - 8 comprehensive tests

**Verification**:
```python
# TokenService automatically detects rotation
if new_tokens.get("refresh_token"):
    if new_tokens["refresh_token"] != old_token:
        # Rotation detected - encrypt and store new token
        logger.info("Token rotation detected")
    else:
        # Same token returned
        logger.debug("Same refresh token returned")
else:
    # No rotation - keep existing token
    logger.debug("No refresh_token in response, keeping existing")
```

**Benefits**:
- Correctly handles both rotating and non-rotating OAuth providers
- Detailed audit trail of all token rotation events
- Future-proof: works with any new provider without changes
- Comprehensive documentation for implementing new providers
- Enhanced security through proper token lifecycle management

---

### 5. User Authentication System (JWT) 🔥 PRIORITY P1

**Current State**: Using mock authentication that creates/returns a test user. No real authentication or authorization.

**Problem**:
- **Security Gap**: No real user authentication - anyone can access test user's data
- **Architecture Lock-In**: More endpoints built = harder to retrofit auth later
- **Blocks P2 Features**: Rate limiting, token breach rotation, and audit logs all require real auth
- **Testing Limitation**: Cannot test multi-user scenarios or authorization
- **Production Blocker**: Cannot onboard real users without authentication
- **Compliance Risk**: Financial apps require provable user identity for audit trails
- **Technical Debt**: 91 failing fixture tests need updates anyway - combine with auth migration

**Affected Components**:
```
src/api/v1/auth.py         - Mock get_current_user() function
src/models/user.py         - User model lacks authentication fields
tests/*                    - All tests use mock authentication
src/api/v1/providers.py    - Basic ownership check but no real auth
```

**Best Practice Solution**:

**Implement JWT + Refresh Token Authentication (Industry Standard)**

1. **Database Schema** (4 new tables):
   - Extend `users` table: password_hash, email_verified, failed_login_attempts, locked_until
   - New `refresh_tokens` table: token rotation, device tracking, revocation
   - New `email_verification_tokens` table: one-time tokens, 24h expiry
   - New `password_reset_tokens` table: one-time tokens, 15min expiry

2. **Service Layer**:
   ```python
   # src/services/auth_service.py
   class AuthService:
       - register_user() - Create user with bcrypt password hash
       - authenticate_user() - Verify credentials, track failed attempts
       - create_access_token() - Generate JWT (30 min expiry)
       - create_refresh_token() - Generate & store refresh token (30 days)
       - verify_refresh_token() - Validate and rotate refresh tokens
       - verify_email() - One-time email verification
       - reset_password() - Secure password reset flow
   ```

3. **API Endpoints** (11 new endpoints):
   ```python
   POST /api/v1/auth/signup              # Create account + send verification
   POST /api/v1/auth/login               # Get access + refresh tokens
   POST /api/v1/auth/refresh             # Rotate tokens (refresh flow)
   POST /api/v1/auth/logout              # Revoke refresh token
   POST /api/v1/auth/verify-email        # Verify with token from email
   POST /api/v1/auth/resend-verification # Resend verification email
   POST /api/v1/auth/forgot-password     # Request reset token
   POST /api/v1/auth/reset-password      # Reset with token from email
   GET  /api/v1/auth/me                  # Get current user
   PATCH /api/v1/auth/me                 # Update profile
   POST /api/v1/auth/change-password     # Change password (authenticated)
   ```

4. **Security Features**:
   - ✅ Bcrypt password hashing (12 rounds, ~300ms)
   - ✅ Password complexity requirements (8+ chars, upper, lower, digit, special)
   - ✅ Account lockout (10 failed attempts = 1 hour lock)
   - ✅ Refresh token rotation (prevents replay attacks)
   - ✅ JWT access tokens (30 min expiry, stateless)
   - ✅ Email verification required
   - ✅ Rate limiting on auth endpoints

5. **Migration Strategy**:
   ```python
   # Update get_current_user() dependency
   # Before (mock):
   async def get_current_user() -> User:
       return test_user  # Creates/returns test@example.com
   
   # After (JWT):
   async def get_current_user(
       credentials: HTTPAuthorizationCredentials = Depends(security)
   ) -> User:
       payload = jwt.decode(credentials.credentials, SECRET_KEY)
       user = await get_user_by_id(payload["sub"])
       return user
   
   # Update all 150+ tests to use authenticated client
   # Fix 91 failing fixture tests simultaneously
   ```

**Why This is P1 (Must Do Before P2)**:
1. **Unblocks P2**: Rate limiting REQUIRES knowing which user made request
2. **Unblocks P2**: Token breach rotation REQUIRES knowing which user owns tokens
3. **Unblocks P2**: Audit log context REQUIRES real user identity
4. **Architecture**: Every day adds more endpoints assuming mock auth
5. **Testing**: Fix fixtures + add auth = ONE migration effort (not two)
6. **Product**: Cannot test with real users until auth exists
7. **Compliance**: SOC 2 / PCI-DSS require strong user authentication

**Implementation Phases**:
- Phase 1: Database Schema & Models (migrations, User, RefreshToken, etc.)
- Phase 2: Core Services (AuthService, password hashing, token management)
- Phase 3: API Endpoints (signup, login, refresh, logout, verification, reset)
- Phase 4: Testing (unit tests, integration tests, security tests)
- Phase 5: Integration (update all tests, fix failing fixtures, documentation)

**Documentation**:
- 📚 Complete research: `docs/research/authentication-approaches-research.md`
- 📚 Implementation guide: `docs/development/guides/authentication-implementation.md`
- 📚 Comparison of 6 modern auth approaches (JWT, OAuth2, Passkeys, Magic Links, etc.)

**Progressive Enhancement Path**:
- **Phase 1 (Now)**: JWT email/password → Production-ready baseline
- **Phase 2 (Q1 2026)**: Social auth (Google, Apple) → Better UX
- **Phase 3 (Q2 2026)**: Passkeys (WebAuthn) → Passwordless future
- **Phase 4 (Q3 2026)**: MFA (TOTP, SMS) → Enterprise security

**Estimated Complexity**: Fast (minimal complexity)  
**Estimated Impact**: 🔴 **CRITICAL** - Unblocks all P2 work, enables real users  
**Status**: 🟡 **READY** - Research complete, implementation guide written  
**Decision**: ✅ **APPROVED** - Prioritized as P1 (2025-10-04)

---

### 6. Token Security - Missing Token Rotation on Breach

**Current State**: Tokens are encrypted at rest but not automatically rotated on security events.

**Problem**:
- If encryption key is compromised, all existing tokens remain vulnerable
- No mechanism to force token refresh across all users
- Cannot invalidate specific tokens without database access

**Best Practice Solution**:
1. Implement token versioning with `token_version` field
2. Add global `min_token_version` configuration
3. Automatic token invalidation when version < min_version
4. Token rotation on:
   - Password change
   - Suspicious activity detection
   - Security incident response
   - Provider-initiated token revocation

**Estimated Complexity**: Moderate


## Medium Priority Issues

### 6. Audit Log Lacks Request Context

**Current State**: Audit logs capture action, user_id, and basic details, but miss critical context.

**Problem**:
- Cannot trace actions to specific API requests
- Missing correlation IDs for distributed tracing
- Cannot reconstruct full request flow for debugging
- Insufficient for security investigations

**Best Practice Solution**:
- Add request_id (UUID) to all audit logs
- Include session_id for multi-request tracking
- Capture API endpoint and HTTP method
- Add request fingerprinting (IP + User-Agent hash)
- Implement log correlation with OpenTelemetry

**Estimated Complexity**: Low-Moderate

---

### 7. Missing Rate Limiting

**Current State**: No rate limiting on API endpoints or provider calls.

**Problem**:
- Vulnerable to brute force attacks
- Can exceed provider API rate limits
- No protection against accidental DoS
- Cannot enforce fair usage policies

**Best Practice Solution**:
- Implement Redis-based rate limiting (Token Bucket algorithm)
- Per-user rate limits for sensitive endpoints
- Per-provider rate limits for external API calls
- Graceful degradation with proper HTTP 429 responses

**Estimated Complexity**: Moderate

---

### 8. Environment-Specific Secrets in Version Control

**Current State**: `.env.example` files contain example secrets, risk of actual secrets being committed.

**Problem**:
- Developers may copy real secrets into `.env.example`
- Accidental commits of sensitive data
- No secret rotation strategy
- Secrets stored as plain text in environment variables

**Best Practice Solution**:
1. Use secret management service (AWS Secrets Manager, Vault, or Doppler)
2. Implement secret rotation automation
3. Add pre-commit hooks to prevent secret commits (using detect-secrets)
4. Use different encryption keys per environment
5. Secret access auditing and versioning

**Estimated Complexity**: Moderate-High

---

## Low Priority (Quality of Life)

### 9. Inconsistent Error Messages

**Current State**: Error messages vary in format and detail level.

**Best Practice Solution**:
- Standardize error response format
- Include error codes for client handling
- Provide user-friendly messages
- Log detailed errors server-side

---

### 10. Missing Request Validation Schemas

**Current State**: Some endpoints lack comprehensive input validation.

**Best Practice Solution**:
- Pydantic models for all request bodies
- Query parameter validation
- Consistent validation error responses

---

### 11. Hard-Coded Configuration Values

**Current State**: Some configuration values are hard-coded in source files.

**Best Practice Solution**:
- Move all configuration to settings module
- Support environment-specific overrides
- Configuration validation on startup

---

## Tracking and Implementation

### Priority Matrix

| Priority | Issue | Impact | Effort | Status | Completion |
|----------|-------|--------|--------|--------|------------|
| ~~P0~~ | ~~Timezone-aware datetimes~~ | High | Medium | ✅ **RESOLVED** | 2025-10-03 |
| ~~P0~~ | ~~Missing migrations~~ | High | Medium | ✅ **RESOLVED** | 2025-10-03 |
| ~~**P1**~~ | ~~**Connection timeouts**~~ | Medium | Low | ✅ **RESOLVED** | 2025-10-04 |
| ~~**P1**~~ | ~~**Token rotation logic**~~ | Medium | Medium | ✅ **RESOLVED** | 2025-10-04 |
| **🔥 P1** | **JWT User Authentication** | **Critical** | **Medium** | **🟡 NEXT** | **Starting** |
| **P2** | **Rate limiting** | Medium | Medium | ⏸️ **BLOCKED** | After Auth |
| **P2** | **Token breach rotation** | Medium | Medium | ⏸️ **BLOCKED** | After Auth |
| P2 | Audit log context | Low | Medium | 🔴 TODO | Later |
| P2 | Secret management | High | High | 🔴 TODO | Pre-prod |
| P3 | Error messages | Low | Low | 🔴 TODO | Polish |
| P3 | Request validation | Low | Medium | 🔴 TODO | Polish |
| P3 | Hard-coded config | Low | Low | 🔴 TODO | Polish |

### Status Legend
- ✅ **RESOLVED** - Implemented, tested, and merged to development
- 🟡 **NEXT** - Next priority item, ready to start
- 🟡 **READY** - Ready to be worked on (dependencies met)
- ⏸️ **BLOCKED** - Waiting on dependencies (e.g., auth required for rate limiting)
- 🔴 **TODO** - Issue identified, waiting for dependencies or prioritization
- 🔵 **IN PROGRESS** - Actively being worked on

---

## Contributing to This Document

When you discover a design flaw or improvement opportunity:

1. **Add an entry** with:
   - Clear description of current state
   - Explanation of the problem and impact
   - Best practice solution with code examples
   - Estimated effort
   - References to industry standards

2. **Prioritize** based on:
   - Regulatory compliance requirements
   - Security impact
   - Data integrity risk
   - User experience impact

3. **Link to tracking**:
   - Create GitHub issue for P0/P1 items
   - Reference this document in issue description
   - Update status when work begins

---

## Review Schedule

- **Monthly**: Review P0/P1 items, update priorities
- **Quarterly**: Comprehensive review of all items
- **Pre-release**: Ensure all P0 items resolved
- **Post-incident**: Add lessons learned

---

## Recent Activity Log

### 2025-10-04
- ✅ **P1 RESOLVED**: Implemented HTTP connection timeouts (PR #7)
- ✅ **P1 RESOLVED**: Implemented OAuth token rotation handling (PR #8)
- 🔥 **P1 PRIORITIZED**: JWT User Authentication system (blocks P2 work)
- 📚 **Documentation**: Created comprehensive auth research + implementation guide
- 📊 **Status**: P0/P1 items complete. Auth promoted to P1 priority.
- 🎯 **Next**: Implement JWT authentication (fast, minimal complexity), then P2 items

### 2025-10-03
- ✅ **P0 RESOLVED**: Implemented timezone-aware datetimes (PR #5)
- ✅ **P0 RESOLVED**: Integrated Alembic migrations (PR #6)
- 📊 **Status**: All critical blockers removed, ready for P1 work

---

**Last Updated**: 2025-10-04  
**Next Review**: 2025-11-03  
**Document Owner**: Architecture Team  
**Current Sprint**: P2 Items (Rate Limiting + Enhanced Security)

---

## P2: Session Management Endpoints

**Status**: Planned  
**Complexity**: Medium  
**Estimated Effort**: 3-4 days  
**Added**: 2025-10-06

**Problem Statement**:
Currently, users cannot view or manage their active sessions. After password reset, all sessions are revoked, but users have no visibility into:
- How many devices are logged in
- When/where each session was created
- Which sessions to revoke individually

**Proposed Solution**:

### New Endpoints

1. **GET /api/v1/auth/sessions** - List all active sessions with device/IP info
2. **DELETE /api/v1/auth/sessions/{id}** - Revoke specific session
3. **DELETE /api/v1/auth/sessions/all** - Logout from all devices
4. **DELETE /api/v1/auth/sessions/others** - Logout from all other devices

### Implementation Highlights

- Leverage existing `refresh_tokens` table (already has device_info, IP, user_agent)
- Add IP geolocation for user-friendly location display
- Show "current session" indicator
- Rate limit session management endpoints

### User Experience

Users can:
- View all active sessions (device, location, last activity)
- Revoke suspicious sessions individually
- Logout from all devices with one click
- See which device is currently active

### Security Benefits

- Users can detect unauthorized access
- Quick response to compromise (revoke all sessions)
- Visibility into account activity
- Complements password reset session revocation

### Related Features

- Suspicious activity alerts (login from new device/location)
- Session expiration policies (configurable per device type)
- Trusted device management

### Industry Examples

- GitHub: Settings → Sessions
- Google: Security → Your devices  
- Facebook: Settings → Security → Where You're Logged In

**See**: [Full implementation details in improvement-guide.md](improvement-guide.md)

