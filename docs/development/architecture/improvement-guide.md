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
   - All 122 tests updated and passing
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
- ✅ SQLModel field definitions updated with `sa_column=Column(DateTime(timezone=True))`
- ✅ Fixed 4 integration tests for timezone-aware comparisons
- ✅ 122/122 tests passing
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

### 5. Token Security - Missing Token Rotation on Breach ⚠️ NEXT PRIORITY

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

**Estimated Effort**: 3-4 days


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

**Estimated Effort**: 2-3 days

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

**Estimated Effort**: 3-4 days

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

**Estimated Effort**: 4-5 days

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
| **P2** | **Token breach rotation** | Medium | Medium | 🟡 **READY** | Next |
| **P2** | **Rate limiting** | Medium | Medium | 🟡 **READY** | Next |
| P2 | Audit log context | Low | Medium | 🔴 TODO | Later |
| P2 | Secret management | High | High | 🔴 TODO | Pre-prod |
| P3 | Error messages | Low | Low | 🔴 TODO | Polish |
| P3 | Request validation | Low | Medium | 🔴 TODO | Polish |
| P3 | Hard-coded config | Low | Low | 🔴 TODO | Polish |

### Status Legend
- ✅ **RESOLVED** - Implemented, tested, and merged to development
- 🟡 **READY** - Ready to be worked on (dependencies met)
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
- 📊 **Status**: All P0 and P1 items complete! 135 tests passing, 69% coverage
- 🎯 **Next**: Rate limiting (P2) or Token breach rotation (P2)

### 2025-10-03
- ✅ **P0 RESOLVED**: Implemented timezone-aware datetimes (PR #5)
- ✅ **P0 RESOLVED**: Integrated Alembic migrations (PR #6)
- 📊 **Status**: All critical blockers removed, ready for P1 work

---

**Last Updated**: 2025-10-04  
**Next Review**: 2025-11-03  
**Document Owner**: Architecture Team  
**Current Sprint**: P2 Items (Rate Limiting + Enhanced Security)
