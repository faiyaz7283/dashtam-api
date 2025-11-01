# Token Breach Rotation Architecture

Hybrid global + per-user token versioning system for responding to security incidents with granular control and comprehensive audit trails.

---

## Overview

The Token Breach Rotation architecture implements a dual-level token versioning system (Approach 3: Hybrid) that enables both targeted per-user token rotation and system-wide emergency token rotation. This architecture provides a critical security mechanism for responding to token compromise, password changes, and security incidents while maintaining detailed audit trails for compliance.

### Why This Approach?

**Industry Standard Pattern**: Auth0, Okta, and GitHub use similar hybrid token rotation strategies.

**Dual-Level Protection**:

- **Per-User Rotation**: Fast, targeted response to individual security events (password changes, suspicious activity)
- **Global Rotation**: Nuclear option for system-wide breaches (encryption key compromise, database breach)

**Compliance Ready**: Comprehensive audit trail meets SOC 2, PCI-DSS, and GDPR requirements for security incident tracking.

**Architecture Decision Record**: See [Token Breach Rotation Research](../../research/token-breach-rotation-research.md) for detailed analysis of 3 approaches and selection rationale.

## Context

**Business Need**: Financial data aggregation platform requires robust security incident response mechanism to protect user sessions during:

- Password compromise events
- Suspicious activity detection
- Encryption key rotation
- Database breach scenarios
- Regulatory compliance audits

**Technical Constraints**:

- Existing JWT authentication system (stateless access tokens + opaque refresh tokens)
- Async Python architecture (FastAPI, SQLAlchemy AsyncSession)
- PostgreSQL database with Alembic migrations
- RESTful API design principles (10/10 compliance score)
- 86% test coverage target maintained

**Regulatory Requirements**:

- **PCI-DSS**: Audit logging of security events
- **SOC 2**: Token lifecycle management and rotation
- **GDPR**: User control over active sessions

## Architecture Goals

- **G1: Granular Control**: Support both per-user and global token rotation strategies
- **G2: Audit Trail**: Log all rotation events with who, when, why, and impact metrics
- **G3: Zero Downtime**: Grace period support for distributed systems during global rotation
- **G4: SOLID Principles**: Maintainable, testable, extensible service architecture
- **G5: REST Compliance**: Clean API endpoints following project REST standards
- **G6: Test Coverage**: Maintain 86%+ coverage with comprehensive unit/integration/API tests
- **G7: Security First**: Prevent token reuse after rotation with dual-version validation

## Design Decisions

### Decision 1: Hybrid Token Versioning (Approach 3)

**Rationale**: Combines benefits of both global and per-user approaches while avoiding their individual limitations.

**Alternatives Considered**:

- **Approach 1 (Global Only)**: Too coarse-grained, forces system-wide logout for individual events
- **Approach 2 (Per-User Only)**: Cannot respond to system-wide breaches (encryption key compromise)
- **Approach 4 (JTI Blacklist)**: Performance concerns, database bloat, no natural expiration

**Trade-offs**:

- ✅ Pros:
  - Handles both targeted and system-wide breaches
  - Industry standard pattern (proven at scale)
  - Natural token expiration (versions increment, old versions invalid)
  - Audit trail included in versioning data
- ⚠️ Cons:
  - Slightly more complex (two version checks instead of one)
  - Requires dual database indexes (user version + global version)
  - Two fields per token (token_version + global_version_at_issuance)

### Decision 2: Immutable Version Capture

**Rationale**: Tokens capture both user and global versions at issuance time (immutable). Validation compares these immutable values against current minimum versions.

**Why Immutable?**:

- Tokens are snapshots of security state at creation time
- Simplifies validation logic (no need to track "which version was this token created at?")
- Natural audit trail (can reconstruct security state at any point in time)

**Trade-offs**:

- ✅ Pros:
  - Simple validation: `token.version < user.min_version` → invalid
  - Audit trail: "This token was issued when user was at version 2"
  - No race conditions (version doesn't change after token created)
- ⚠️ Cons:
  - Cannot "upgrade" old tokens to new version (must re-login)

### Decision 3: Grace Period for Global Rotation

**Rationale**: Global rotation includes configurable grace period (0-60 minutes, default 15) to prevent abrupt service disruption for in-flight requests.

**Why Grace Period?**:

- Distributed systems: Requests may be mid-flight during rotation
- User experience: Allows users to complete current transaction before forced logout
- Compliance: Demonstrates reasonable security measures (not overly disruptive)

**Trade-offs**:

- ✅ Pros:
  - Reduces user frustration (graceful degradation)
  - Prevents transaction loss (e.g., form submission in progress)
  - Audit trail shows grace period used (demonstrates judgment)
- ⚠️ Cons:
  - Compromised tokens valid for grace period (acceptable risk for most incidents)
  - Requires revoked_at timestamp management

### Decision 4: Service Layer with SOLID Principles

**Rationale**: TokenRotationService follows SOLID principles for maintainability and testability.

**SOLID Application**:

- **Single Responsibility**: Service only handles token rotation logic (no auth, no token generation)
- **Open-Closed**: Can add new rotation strategies without modifying existing code
- **Liskov Substitution**: Works with any AsyncSession implementation
- **Interface Segregation**: Clean public API (3 methods: rotate_user, rotate_global, get_config)
- **Dependency Inversion**: Depends on AsyncSession abstraction, not concrete database

**Trade-offs**:

- ✅ Pros:
  - Easy to test (mock AsyncSession)
  - Easy to extend (add new rotation strategies)
  - Clear separation of concerns
- ⚠️ Cons:
  - Slightly more code than "God object" approach

## Components

### Architecture Diagram

```mermaid
flowchart TB
    subgraph "API Layer"
        A[Token Rotation Router]
        A1["/users/{id}"]
        A2["/global"]
        A3["/security-config"]
        A --> A1
        A --> A2
        A --> A3
    end

    subgraph "Service Layer"
        B[TokenRotationService]
        B1[rotate_user_tokens]
        B2[rotate_all_tokens_global]
        B3[get_security_config]
        B --> B1
        B --> B2
        B --> B3
        
        C[AuthService]
        C1[_validate_token_versions]
        C2[_create_refresh_token]
        C --> C1
        C --> C2
    end

    subgraph "Data Layer"
        D[(SecurityConfig)]
        E[(User)]
        F[(RefreshToken)]
        
        D --> |global_min_token_version| D1[Global Version]
        E --> |min_token_version| E1[User Version]
        F --> |token_version| F1[Token Version]
        F --> |global_version_at_issuance| F2[Global at Issuance]
    end

    A1 --> B1
    A2 --> B2
    A3 --> B3
    
    B1 --> E
    B1 --> F
    B2 --> D
    B2 --> F
    B3 --> D
    
    C1 --> E
    C1 --> D
    C1 --> F
    C2 --> E
    C2 --> D
    C2 --> F
    
    style A fill:#e1f5ff
    style B fill:#fff4e1
    style D fill:#ffe1e1
    style E fill:#ffe1e1
    style F fill:#ffe1e1
```

### Component 1: SecurityConfig Model

**Purpose**: Singleton table storing global security configuration including minimum token version.

**Responsibilities**:

- Store global minimum token version (incremented during global rotation)
- Track audit trail: who, when, why global rotation occurred
- Provide single source of truth for global security state

**Interfaces**:

- **Input**: None (singleton, always exists)
- **Output**: Global security configuration data

**Database Schema**:

```mermaid
erDiagram
    SECURITY_CONFIG {
        uuid id PK
        int global_min_token_version
        timestamp updated_at
        string updated_by
        text reason
        timestamp created_at
    }
```

**Key Fields**:

- `global_min_token_version`: Minimum token version accepted globally (starts at 1)
- `updated_at`: When global version was last incremented
- `updated_by`: Who initiated global rotation (e.g., "ADMIN:security@example.com")
- `reason`: Why global rotation was performed (audit trail)

**Dependencies**: None (root configuration)

### Component 2: User Model (Extended)

**Purpose**: Tracks per-user token versioning for targeted rotation.

**Responsibilities**:

- Store user's minimum token version (incremented during user rotation)
- Enable per-user token invalidation without affecting other users

**New Field**:

- `min_token_version`: Minimum token version for this user (default 1)

**Database Schema**:

```mermaid
erDiagram
    USER {
        uuid id PK
        string email UK
        int min_token_version "Default: 1"
        timestamp created_at
        timestamp updated_at
    }
```

**Dependencies**: None (extended existing model)

### Component 3: RefreshToken Model (Extended)

**Purpose**: Captures both version numbers at token issuance time for dual-level validation.

**Responsibilities**:

- Store token's user version at issuance (immutable snapshot)
- Store token's global version at issuance (immutable snapshot)
- Enable fast version validation queries

**New Fields**:

- `token_version`: User's min_token_version at token issuance
- `global_version_at_issuance`: Global min_token_version at token issuance

**Database Schema**:

```mermaid
erDiagram
    REFRESH_TOKEN {
        uuid id PK
        uuid user_id FK
        string token_hash UK
        int token_version "Indexed"
        int global_version_at_issuance "Indexed"
        bool is_revoked
        timestamp revoked_at
        timestamp expires_at
        timestamp created_at
    }
    
    REFRESH_TOKEN }o--|| USER : "belongs to"
```

**Indexes**:

- `(user_id, token_version)` - Fast user rotation validation
- `(global_version_at_issuance)` - Fast global rotation validation

**Dependencies**: User model, SecurityConfig model

### Component 4: TokenRotationService

**Purpose**: Core business logic for token rotation operations.

**Responsibilities**:

- Increment user's minimum token version (user rotation)
- Increment global minimum token version (global rotation)
- Revoke old tokens (mark as revoked with timestamp)
- Return structured results with audit trail data
- Log all rotation events with full context

**Public Methods**:

1. `rotate_user_tokens(user_id, reason)` → TokenRotationResult
2. `rotate_all_tokens_global(reason, initiated_by, grace_period)` → TokenRotationResult
3. `get_security_config()` → SecurityConfig

**Service Architecture**:

```mermaid
classDiagram
    class TokenRotationService {
        -AsyncSession session
        +rotate_user_tokens(user_id, reason) TokenRotationResult
        +rotate_all_tokens_global(reason, initiated_by, grace_period) TokenRotationResult
        +get_security_config() SecurityConfig
    }
    
    class TokenRotationResult {
        +rotation_type: Literal["USER", "GLOBAL"]
        +user_id: Optional[UUID]
        +old_version: int
        +new_version: int
        +tokens_revoked: int
        +users_affected: Optional[int]
        +reason: str
        +initiated_by: Optional[str]
        +grace_period_minutes: Optional[int]
    }
    
    class AsyncSession {
        <<interface>>
        +execute()
        +commit()
    }
    
    TokenRotationService --> TokenRotationResult : returns
    TokenRotationService --> AsyncSession : depends on
```

**SOLID Principles**:

- **Single Responsibility**: Only token rotation logic
- **Dependency Inversion**: Depends on AsyncSession abstraction

**Dependencies**: AsyncSession, SQLModel, SQLAlchemy

### Component 5: AuthService (Extended)

**Purpose**: Validates tokens against version numbers during authentication.

**New Responsibilities**:

- Validate token's version against user's minimum version
- Validate token's global version against global minimum version
- Capture current versions when creating new tokens

**New Methods**:

1. `_validate_token_versions(token, user)` → tuple[bool, Optional[str]]

**Updated Methods**:

1. `refresh_access_token()` - Now includes version validation
2. `_create_refresh_token()` - Now captures current versions

**Dependencies**: TokenRotationService (for version queries), SecurityConfig, User, RefreshToken

### Component 6: Token Rotation Router

**Purpose**: REST API endpoints for token rotation management.

**Responsibilities**:

- Expose token rotation operations as HTTP endpoints
- Handle authorization (users can rotate own tokens)
- Validate request payloads (reason length, grace period bounds)
- Return structured JSON responses

**Endpoints**:

1. `POST /api/v1/token-rotation/users/{user_id}` - Per-user rotation
2. `POST /api/v1/token-rotation/global` - Global rotation (emergency)
3. `GET /api/v1/token-rotation/security-config` - View global config

**Authorization**:

- All endpoints require JWT authentication
- User rotation: User can only rotate own tokens (or admin)
- Global rotation: Any authenticated user (future: admin only)

**Dependencies**: TokenRotationService, get_current_user dependency, FastAPI

## Implementation Details

### Key Patterns Used

- **Service Layer Pattern**: Business logic separated from API layer
- **Dependency Injection**: Services accept AsyncSession via constructor
- **Data Transfer Objects**: TokenRotationResult, request/response schemas
- **Immutable Snapshots**: Token versions never change after creation
- **Audit Logging**: Structured logging with full context (who, what, when, why)

### Code Organization

```text
src/
├── models/
│   ├── security_config.py        # Global security configuration singleton
│   ├── user.py                    # User model (extended with min_token_version)
│   └── auth.py                    # RefreshToken model (extended with versions)
├── services/
│   ├── token_rotation_service.py  # Core rotation logic
│   └── auth_service.py            # Extended with version validation
├── schemas/
│   └── token_rotation.py          # Request/response schemas
└── api/
    └── v1/
        └── token_rotation.py      # REST API endpoints
```

### User Token Rotation Flow

```mermaid
sequenceDiagram
    participant U as User/API
    participant R as Router
    participant S as TokenRotationService
    participant DB as Database
    
    U->>R: POST /users/{id} {reason}
    R->>R: Verify JWT auth
    R->>R: Check user can rotate own tokens
    
    R->>S: rotate_user_tokens(user_id, reason)
    
    S->>DB: SELECT min_token_version FROM users
    DB-->>S: old_version=1
    
    S->>DB: SELECT MAX(token_version) FROM refresh_tokens
    DB-->>S: max_version=1
    
    S->>S: new_version = max(old, max) + 1 = 2
    
    S->>DB: UPDATE users SET min_token_version=2
    DB-->>S: OK
    
    S->>DB: UPDATE refresh_tokens SET is_revoked=true WHERE token_version < 2
    DB-->>S: revoked_count=3
    
    S->>DB: COMMIT
    DB-->>S: OK
    
    S-->>R: TokenRotationResult(old=1, new=2, revoked=3)
    R-->>U: 200 OK {rotation details}
    
    Note over DB: All tokens with version < 2 now invalid
```

### Global Token Rotation Flow

```mermaid
sequenceDiagram
    participant A as Admin/API
    participant R as Router
    participant S as TokenRotationService
    participant DB as Database
    
    A->>R: POST /global {reason, grace_period}
    R->>R: Verify JWT auth (future: verify admin role)
    R->>R: Log WARNING (global rotation initiated)
    
    R->>S: rotate_all_tokens_global(reason, initiated_by, grace_period)
    
    S->>DB: SELECT global_min_token_version FROM security_config
    DB-->>S: old_version=1
    
    S->>S: new_version = old + 1 = 2
    
    S->>DB: UPDATE security_config SET global_min_token_version=2, updated_by=..., reason=...
    DB-->>S: OK
    
    S->>DB: SELECT COUNT(*) FROM refresh_tokens WHERE global_version_at_issuance < 2
    DB-->>S: affected_tokens=1247
    
    S->>DB: SELECT COUNT(DISTINCT user_id) FROM refresh_tokens WHERE ...
    DB-->>S: affected_users=423
    
    S->>DB: UPDATE refresh_tokens SET is_revoked=true, revoked_at=NOW()+grace WHERE ...
    DB-->>S: OK
    
    S->>DB: COMMIT
    DB-->>S: OK
    
    S->>S: Log CRITICAL (global rotation complete)
    
    S-->>R: TokenRotationResult(old=1, new=2, revoked=1247, users=423)
    R-->>A: 200 OK {rotation details}
    
    Note over DB: All tokens with global_version < 2 invalid after grace period
```

### Token Validation Flow

```mermaid
flowchart TD
    A[Token Refresh Request] --> B{Token Exists?}
    B -->|No| Z1[401 Unauthorized]
    B -->|Yes| C{Token Expired?}
    
    C -->|Yes| Z2[401 Token Expired]
    C -->|No| D{Token Revoked?}
    
    D -->|Yes| Z3[401 Token Revoked]
    D -->|No| E[Get User & Security Config]
    
    E --> F{Global Version Check}
    F -->|token.global_version < config.global_min| Z4[401 Global Version Too Old]
    F -->|OK| G{User Version Check}
    
    G -->|token.token_version < user.min_version| Z5[401 User Version Too Old]
    G -->|OK| H[Generate New Access Token]
    
    H --> I[200 OK - New Access Token]
    
    style Z1 fill:#ffcccc
    style Z2 fill:#ffcccc
    style Z3 fill:#ffcccc
    style Z4 fill:#ffcccc
    style Z5 fill:#ffcccc
    style I fill:#ccffcc
```

### Configuration

**Environment Variables**:

```bash
# Database connection (existing)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db

# No new environment variables required
# (Token rotation uses existing database and auth infrastructure)
```

**Database Migration**:

```bash
# Migration: add_token_versioning_hybrid_approach
# - Creates security_config table with initial row (global_min_token_version=1)
# - Adds min_token_version to users table (default 1)
# - Adds token_version and global_version_at_issuance to refresh_tokens (default 1)
```

## Security Considerations

### Threats Addressed

- **Threat 1: Password Compromise**
  - **Mitigation**: Automatic user token rotation on password change invalidates all existing sessions
  - **Implementation**: Password reset triggers `rotate_user_tokens(reason="Password changed")`

- **Threat 2: Encryption Key Compromise**
  - **Mitigation**: Global token rotation invalidates all tokens system-wide
  - **Implementation**: Admin triggers `rotate_all_tokens_global(reason="Encryption key rotated")`

- **Threat 3: Database Breach**
  - **Mitigation**: Global rotation with zero grace period forces immediate logout
  - **Implementation**: `rotate_all_tokens_global(grace_period_minutes=0)`

- **Threat 4: Stolen Token Reuse**
  - **Mitigation**: Dual-version validation prevents reuse of old tokens
  - **Implementation**: Both user version AND global version must be current

- **Threat 5: Session Hijacking**
  - **Mitigation**: User can manually rotate tokens to logout all devices
  - **Implementation**: User triggers rotation via API endpoint

### Security Best Practices

- **Audit Logging**: All rotation events logged with CRITICAL/WARNING level
- **Reason Required**: All rotations require human-readable reason (audit trail)
- **Authorization**: Users can only rotate own tokens (admin role check pending)
- **Grace Period**: Default 15 minutes prevents abrupt service disruption
- **Immutable Versions**: Tokens capture version at creation (cannot be upgraded)
- **Indexed Queries**: Version validation queries use indexes for performance

### Security State Diagram

```mermaid
stateDiagram-v2
    [*] --> Valid: Token Issued (version=1)
    
    Valid --> Invalid_User: User Rotation (min_version→2)
    Valid --> Invalid_Global: Global Rotation (global_min→2)
    Valid --> Expired: TTL expires
    Valid --> Revoked: Manual revocation
    
    Invalid_User --> [*]
    Invalid_Global --> [*]
    Expired --> [*]
    Revoked --> [*]
    
    note right of Valid
        Token valid if:
        - token.token_version >= user.min_token_version
        - token.global_version >= config.global_min_token_version
        - !is_revoked
        - !expired
    end note
    
    note right of Invalid_User
        User-specific rotation:
        - Password change
        - Suspicious activity
        - User requests logout all
    end note
    
    note right of Invalid_Global
        System-wide rotation:
        - Encryption key breach
        - Database breach
        - Critical vulnerability
    end note
```

## Performance Considerations

### Performance Characteristics

- **Version Validation**: O(1) with indexes on (user_id, token_version) and (global_version_at_issuance)
- **User Rotation Query**: Single UPDATE with indexed WHERE clause (~2-5ms)
- **Global Rotation Query**: Single UPDATE affecting all tokens (~100-500ms for 10k tokens)
- **Token Creation Overhead**: +2 SELECT queries to fetch current versions (~1-2ms)

### Database Indexes

```sql
-- Existing indexes
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE UNIQUE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);

-- New indexes (added by migration)
CREATE INDEX idx_users_min_token_version ON users(id, min_token_version);
CREATE INDEX idx_refresh_tokens_version ON refresh_tokens(user_id, token_version);
CREATE INDEX idx_refresh_tokens_global_version ON refresh_tokens(global_version_at_issuance);
```

### Optimization Strategies

- **Strategy 1: Batch Revocation**: Global rotation uses single UPDATE instead of row-by-row revocation
- **Strategy 2: Grace Period**: Delayed revocation reduces thundering herd (users don't all re-login simultaneously)
- **Strategy 3: Indexed Validation**: Version checks use covering indexes (no table scan)
- **Strategy 4: Immutable Versions**: No need to track "which version was current when?" (avoids complex joins)

### Performance Monitoring

**Metrics to Track**:

- Token validation latency (p50, p95, p99)
- Rotation operation duration (user vs global)
- Number of tokens affected per rotation
- Database connection pool usage during global rotation

## Testing Strategy

### Unit Tests (8 Tests)

**File**: `tests/unit/services/test_token_rotation_service.py`

**Coverage**:

- Basic user token rotation (single token)
- User rotation with multiple tokens (3+ tokens)
- Global token rotation (multiple users)
- Idempotent rotation (safe to call twice)
- Grace period behavior
- SecurityConfig singleton access
- Version increment logic
- Audit trail data

### Integration Tests (5 Tests)

**File**: `tests/integration/test_token_rotation_integration.py`

**Coverage**:

- Token invalidation after user rotation
- Token invalidation after global rotation
- New tokens valid after rotation (version incremented)
- Grace period tokens remain active until revoked_at
- Multiple rotations increment versions correctly

### API Tests (12 Tests)

**File**: `tests/api/test_token_rotation_endpoints.py`

**Coverage**:

- **User Rotation Endpoint** (5 tests):
  - Success scenario with JWT auth
  - Auth requirement (401 without token)
  - Reason validation (422 for missing/short reason)
  - Authorization (403 for different user)
  - Idempotent behavior

- **Global Rotation Endpoint** (5 tests):
  - Success with multiple users
  - Auth requirement
  - Detailed reason validation (20+ chars)
  - Grace period validation (0-60 minutes)
  - Default grace period (15 minutes)

- **Security Config Endpoint** (2 tests):
  - Success scenario
  - Auth requirement

### Test Coverage Summary

- **Total Tests**: 25 tests (8 unit + 5 integration + 12 API)
- **Coverage**: 86% overall project coverage maintained
- **Test Strategy**: Synchronous testing with FastAPI TestClient pattern

## Future Enhancements

### P1: Admin Role Check (High Priority)

**Description**: Restrict global rotation to admin users only.

**Current State**: Any authenticated user can trigger global rotation (dev/testing only).

**Implementation**:

- Add `role` field to User model (e.g., "admin", "user")
- Create `get_current_admin_user` dependency
- Update global rotation endpoint to require admin role
- Add admin role tests

**Priority**: High (required for production)

**Estimated Effort**: Small (1-2 days)

### P2: Email Notifications (Medium Priority)

**Description**: Send email notifications when tokens are rotated.

**Use Cases**:

- User rotation: "Your tokens were rotated. If this wasn't you, contact support."
- Global rotation: "All users logged out due to security incident [reason]"

**Implementation**:

- Integrate with existing EmailService
- Create rotation email templates
- Add optional email notification to TokenRotationService
- Add email flag to API endpoints (default: true)

**Priority**: Medium (improves security awareness)

**Estimated Effort**: Medium (3-5 days)

### P3: Monitoring Dashboards (Medium Priority)

**Description**: Track token rotation metrics in real-time.

**Metrics**:

- Rotation frequency (user vs global)
- Users affected per rotation
- Tokens revoked per rotation
- Average grace period used
- Top rotation reasons (audit)

**Implementation**:

- Integrate with Prometheus/Grafana (or similar)
- Add metrics instrumentation to TokenRotationService
- Create pre-built dashboard JSON
- Set up alerts for global rotation (should be rare)

**Priority**: Medium (operational visibility)

**Estimated Effort**: Medium (5-7 days)

### P4: Automatic Rotation on Password Change (High Priority)

**Description**: Trigger user rotation automatically when password changes.

**Current State**: Manual rotation required.

**Implementation**:

- Update password reset endpoint to call `rotate_user_tokens()`
- Update password change endpoint to call `rotate_user_tokens()`
- Add integration tests for automatic rotation

**Priority**: High (improves security posture)

**Estimated Effort**: Small (1-2 days)

### P5: Multi-Factor Authentication Before Global Rotation (Low Priority)

**Description**: Require MFA verification before allowing global rotation.

**Rationale**: Global rotation is nuclear option, extra verification reduces accidental triggers.

**Implementation**:

- Integrate with MFA system (TOTP, SMS, etc.)
- Add MFA check before global rotation
- Add MFA bypass for emergency scenarios (with extra logging)

**Priority**: Low (nice-to-have, not critical)

**Estimated Effort**: Large (depends on MFA system availability)

### P6: Confirmation Step for Global Rotation (Medium Priority)

**Description**: Require admin to type rotation reason twice before executing.

**Rationale**: Prevents accidental global rotation (fat-finger protection).

**Implementation**:

- Add `reason_confirmation` field to RotateGlobalTokensRequest
- Validate `reason == reason_confirmation`
- Return 422 if mismatch

**Priority**: Medium (error prevention)

**Estimated Effort**: Small (1 day)

### P7: Audit Report Endpoint (Low Priority)

**Description**: API endpoint to view rotation history.

**Endpoints**:

- `GET /api/v1/token-rotation/audit` - List all rotation events
- `GET /api/v1/token-rotation/audit/{id}` - View specific event

**Implementation**:

- Query SecurityConfig for global rotations (history in updated_at/reason)
- Add user rotation history table (optional, or infer from logs)
- Paginated results
- Admin-only access

**Priority**: Low (audit visibility, can use logs for now)

**Estimated Effort**: Medium (3-5 days)

### P8: Grace Period Scheduling (Low Priority)

**Description**: Allow scheduled grace period expiration (e.g., "rotate at 2am UTC").

**Use Cases**:

- Planned maintenance windows
- Off-hours rotation to minimize user impact

**Implementation**:

- Add `scheduled_at` field to rotation requests
- Background job to execute rotation at scheduled time
- Celery or similar task queue

**Priority**: Low (operational convenience, not critical)

**Estimated Effort**: Large (requires background job infrastructure)

## References

- [Token Breach Rotation Research](../../research/token-breach-rotation-research.md) - Comprehensive analysis and decision rationale
- [Token Rotation Implementation Guide](../implementation/token-rotation-implementation.md) - Step-by-step implementation instructions
- [JWT Authentication Architecture](jwt-authentication.md) - Existing auth system overview
- [RESTful API Design](restful-api-design.md) - REST API principles followed
- [Testing Guide](../guides/testing-guide.md) - Testing strategy and patterns
- [Security Incident Runbook](../infrastructure/security-incident-runbook.md) - Operational procedures for using token rotation
- [Auth0 Token Rotation](https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation) - Industry patterns
- [OWASP Token Management](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html) - Security best practices

---

## Document Information

**Created:** 2025-10-30
**Last Updated:** 2025-10-30
