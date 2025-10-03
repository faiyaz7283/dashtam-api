# Architecture Improvement Guide

**Document Purpose**: Track design flaws discovered during development and testing, with recommended best-practice solutions to improve application quality, security, and reliability.

**Status**: Living Document - Updated as issues are discovered  
**Priority**: High-priority items should be addressed before production deployment

---

## Critical Issues (Must Fix Before Production)

### 1. Timezone-Naive DateTime Storage ⚠️ CRITICAL

**Current State**: Database stores naive (timezone-unaware) Python `datetime` objects.

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

**Estimated Effort**: 1-2 days (Medium priority for pre-production)

**References**:
- [PostgreSQL Timestamp Documentation](https://www.postgresql.org/docs/current/datatype-datetime.html)
- [Python datetime best practices](https://blog.ganssle.io/articles/2019/11/utcnow.html)
- [PCI-DSS Requirement 10.4.2](https://www.pcisecuritystandards.org/) - Time synchronization

---

## High Priority Issues

### 2. Missing Database Migration Framework

**Current State**: Database schema managed manually via `init_db.py` script.

**Problem**:
- No version control for database schema changes
- Cannot rollback schema changes
- No automated migration process for production deployments
- Risk of data loss during manual schema updates
- Team members may have different database states

**Best Practice Solution**:
- Implement Alembic for database migrations
- All schema changes tracked in version-controlled migration files
- Support for upgrade/downgrade operations
- Automated migration application on deployment

**Status**: Already planned in WARP.md roadmap

---

### 3. Token Security - Missing Token Rotation on Breach

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

---

### 4. Missing Connection Timeout Handling

**Current State**: HTTP requests to provider APIs have no explicit timeout configuration.

**Problem**:
- Requests may hang indefinitely
- Can exhaust connection pools
- Poor user experience with no feedback
- Potential for resource exhaustion attacks

**Best Practice Solution**:
```python
# Add to all httpx.AsyncClient calls
async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
    response = await client.get(url)
```

**Estimated Effort**: 1 day

---

## Medium Priority Issues

### 5. Audit Log Lacks Request Context

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

### 6. Missing Rate Limiting

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

### 7. Environment-Specific Secrets in Version Control

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

### 8. Inconsistent Error Messages

**Current State**: Error messages vary in format and detail level.

**Best Practice Solution**:
- Standardize error response format
- Include error codes for client handling
- Provide user-friendly messages
- Log detailed errors server-side

---

### 9. Missing Request Validation Schemas

**Current State**: Some endpoints lack comprehensive input validation.

**Best Practice Solution**:
- Pydantic models for all request bodies
- Query parameter validation
- Consistent validation error responses

---

### 10. Hard-Coded Configuration Values

**Current State**: Some configuration values are hard-coded in source files.

**Best Practice Solution**:
- Move all configuration to settings module
- Support environment-specific overrides
- Configuration validation on startup

---

## Tracking and Implementation

### Priority Matrix

| Priority | Issue | Impact | Effort | Status |
|----------|-------|--------|--------|--------|
| P0 (Critical) | Timezone-aware datetimes | High | Medium | 🔴 Discovered |
| P0 (Critical) | Missing migrations | High | Medium | 🟡 Planned |
| P1 (High) | Token rotation | Medium | Medium | 🔴 Discovered |
| P1 (High) | Connection timeouts | Medium | Low | 🔴 Discovered |
| P2 (Medium) | Audit log context | Low | Medium | 🔴 Discovered |
| P2 (Medium) | Rate limiting | Medium | Medium | 🔴 Discovered |
| P2 (Medium) | Secret management | High | High | 🔴 Discovered |
| P3 (Low) | Error messages | Low | Low | 🔴 Discovered |
| P3 (Low) | Request validation | Low | Medium | 🔴 Discovered |
| P3 (Low) | Hard-coded config | Low | Low | 🔴 Discovered |

### Status Legend
- 🔴 Discovered - Issue identified, not started
- 🟡 Planned - Included in roadmap
- 🔵 In Progress - Actively being worked on
- ✅ Resolved - Implemented and tested

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

**Last Updated**: 2025-10-03  
**Next Review**: 2025-11-03  
**Document Owner**: Architecture Team
