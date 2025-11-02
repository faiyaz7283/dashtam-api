# Session Manager Implementation Guide

Comprehensive, production-ready plan for implementing the framework-agnostic session manager package and integrating it end-to-end across the Dashtam application.

---

## Purpose

- Implement the session manager following docs/development/architecture/session-manager-package.md
- Achieve 100% application integration by addressing gaps in docs/reviews/integration-status.md
- Enforce the Feature Integration Checklist (WARP.md, Enforcement section)

---

## Scope

- Package: src/session_manager/ (abstract interfaces + concrete implementations)
- Storage: database.py (SQLAlchemy AsyncSession), cache.py (CacheClient protocol), memory.py
- Audit: database.py (app-provided model), logger.py (stdlib), noop.py, metrics.py (optional)
- Backends: JWTSessionBackend (primary), DatabaseSessionBackend (optional)
- Service: SessionManagerService (orchestrator)
- Factory: get_session_manager (dependency injection)
- Middleware: FastAPI adapter (no base.py abstraction)
- App integration: Session metadata collection across all relevant endpoints
- Tests: Unit, integration, API, smoke

Out of scope:

- Non-FastAPI adapters (Django/Flask)
- Advanced analytics
- Multi-tenancy
- Tracing

---

## Principles

- Follow architecture doc exactly (naming, abstractions, patterns)
- Package is infrastructure-agnostic: App provides DB session, models, cache client
- No ORM or database coupling inside package
- Middleware is framework-specific adapter (no base.py)
- Enforce Feature Integration Checklist before completion

---

## Directory Structure (Package)

```text
src/session_manager/
├── backends/
│   ├── base.py
│   ├── jwt_backend.py
│   └── database_backend.py
├── storage/
│   ├── base.py
│   ├── database.py
│   ├── cache.py
│   └── memory.py
├── audit/
│   ├── base.py
│   ├── database.py
│   ├── logger.py
│   ├── noop.py
│   └── metrics.py
├── enrichers/
│   ├── base.py
│   ├── geolocation.py
│   └── device_fingerprint.py
├── models/
│   ├── __init__.py
│   ├── base.py
│   ├── filters.py
│   └── config.py
├── middleware/
│   └── fastapi_middleware.py
├── service.py
├── factory.py
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

Note: middleware/ has NO base.py by design (framework adapter per architecture).

---

## Phase 1: Models and Interfaces

- models/base.py: Define SessionBase abstract interface (fields + is_active)
- models/filters.py: SessionFilters dataclass for list queries
- storage/base.py: SessionStorage abstract interface (save/get/list/revoke/delete)
- audit/base.py: SessionAuditBackend abstract interface (created/revoked/accessed/suspicious)
- backends/base.py: SessionBackend abstract interface (create/validate/revoke/list)
- enrichers/base.py: SessionEnricher abstract interface (enrich)

Acceptance:

- All base interfaces defined and imported without dependencies on ORMs or frameworks
- mypy/type hints clean locally in package scope

---

## Phase 2: Storage Implementations

- storage/database.py: DatabaseSessionStorage
  - Accepts AsyncSession (app-provided) and app Session model (implements SessionBase)
  - Uses SQLAlchemy select() patterns per architecture
  - No engine creation, no migrations, no table creation

- storage/cache.py: CacheSessionStorage
  - Define CacheClient Protocol (get/set/delete)
  - Accepts any client implementing protocol (Redis, Memcached)
  - JSON serialize/deserialize session payloads

- storage/memory.py: MemorySessionStorage
  - In-memory dict with TTL; no external deps

Acceptance:

- Works with PostgreSQL/MySQL/SQLite when app provides AsyncSession
- Works with Redis/Memcached when app provides cache client
- Unit tests cover CRUD and TTL behavior

---

## Phase 3: Audit Backends

- audit/database.py: DatabaseAuditBackend
  - Accepts AsyncSession and app audit model
  - Writes audit rows; no schema management

- audit/logger.py: LoggerAuditBackend (concrete)
  - Uses Python stdlib logging; app configures handlers

- audit/noop.py: NoOpAuditBackend

- audit/metrics.py: MetricsAuditBackend (optional)
  - Depends on app-provided metrics client

Acceptance:

- Logger backend logs structured events using `extra=`
- Database backend inserts audit rows using app model
- No external deps or schema coupling

---

## Phase 4: Backends

- backends/jwt_backend.py: JWTSessionBackend
  - Create session domain object from inputs
  - Validate/revoke per SessionBase semantics

- backends/database_backend.py: Optional alternative

Acceptance:

- Backend returns SessionBase-compatible instances
- Pluggable with SessionManagerService

---

## Phase 5: Orchestrator Service

- service.py: SessionManagerService
  - Coordinates backend, storage, audit, enrichers
  - Flow: backend.create → enrichers → storage.save → audit.log

Acceptance:

- No knowledge of specific storage/audit implementations
- Works with any combination wired via factory

---

## Phase 6: Factory (Dependency Injection)

- factory.py: get_session_manager
  - Inputs: session_model, audit_model (optional), backend_type, storage_type, audit_type, db_session, cache_client
  - storage_type: "database" | "cache" | "memory"
  - audit_type: "database" | "logger" | "noop" | "metrics"
  - Returns configured SessionManagerService

Acceptance:

- No engine/client creation inside factory
- Uses only provided instances (db_session, cache_client)

---

## Phase 7: FastAPI Integration (Adapter)

- middleware/fastapi_middleware.py
  - Adds SessionManagerService into request.state
  - Provides dependency helper `get_session_manager(request)`

Acceptance:

- Works without a base middleware class (per architecture)

---

## Phase 8: Application Integration (Dashtam)

Follow docs/reviews/integration-status.md to reach 100% integration.

### 8.1 Session Metadata Dependencies

- Add to relevant endpoints:
  - `ip_address: Optional[str] = Depends(get_client_ip)`
  - `user_agent: Optional[str] = Depends(get_user_agent)`

- Pass to services:
  - AuthService.change_password(..., ip_address=ip_address, user_agent=user_agent)
  - AuthService.reset_password(..., ip_address=ip_address, user_agent=user_agent)
  - TokenRotationService.rotate_user_tokens(..., ip_address=ip_address, user_agent=user_agent)
  - TokenRotationService.rotate_all_tokens_global(..., ip_address=ip_address, user_agent=user_agent)

- Update audit calls to include metadata context

Target endpoints to update (from Integration Status Tracker):

- Authentication & User Management
  - POST /api/v1/auth/logout
  - GET /api/v1/auth/me
  - PATCH /api/v1/auth/me
  - PATCH /api/v1/auth/me/password (P0)

- Password Reset (Critical)
  - PATCH /api/v1/password-resets/{token} (P0)

- Session Management
  - DELETE /api/v1/auth/sessions/all/revoke (consistency fix)

- Token Rotation (Critical)
  - DELETE /api/v1/users/{user_id}/tokens
  - DELETE /api/v1/tokens

- Providers (Recommended)
  - POST/DELETE under /api/v1/providers and /provider authorization

### 8.2 Authorization Enforcement

- Protect global token rotation with admin role
  - Require admin dependency for `DELETE /api/v1/tokens`

### 8.3 Rate Limiting

- Confirm configuration already applied to token rotation endpoints

Acceptance:

- 100% coverage for session metadata on all security-sensitive endpoints
- Admin enforcement on global rotation
- Endpoints consistent with dependency injection for metadata

---

## Phase 9: Migration Plan

- Introduce new package alongside existing session system
- Wire factory-produced service into FastAPI middleware
- Migrate endpoints to use new service incrementally
- Remove old session code after parity verified by tests

Acceptance:

- No breaking changes to public API paths
- All flows continue to operate under test

---

## Phase 10: Testing Strategy

- Unit tests (src/session_manager/tests/unit/)
  - Backends: creation/validation/revocation
  - Storage: database/cache/memory behaviors
  - Audit: logger/database behavior
  - Service: orchestration with fakes/mocks

- Integration tests (src/session_manager/tests/integration/)
  - DatabaseSessionStorage with AsyncSession
  - CacheSessionStorage with in-memory fake client
  - LoggerAuditBackend with test logger handler

- API tests (tests/api/)
  - Verify session metadata collected on all updated endpoints
  - Verify admin enforcement on global rotation

- Smoke tests (tests/smoke/)
  - Full auth flow + session listing + revocation + password change + rotation

Acceptance:

- All tests green under `make test`
- Coverage at or above project target for new code

---

## Phase 11: Documentation

- Update or create manual API flows under docs/api-flows/ for impacted journeys
  - Login/logout, password reset, password change, token rotation, session management
- Cross-reference architecture doc
- Keep HTTPS-first examples with environment variables and placeholders

Acceptance:

- Markdown linting clean
- MkDocs builds with zero warnings

---

## Phase 12: Feature Integration Checklist (Enforcement)

This checklist is MANDATORY for completion (see WARP.md Enforcement section).

- [ ] 1. Endpoint Coverage: List ALL endpoints and mark coverage for session metadata, auth controls, rate limits
- [ ] 2. Dependency Injection: Add `get_client_ip` and `get_user_agent` to ALL relevant endpoints
- [ ] 3. Configuration Completeness: Verify any config entries and factory parameters
- [ ] 4. Service Layer Integration: Ensure services accept and use metadata
- [ ] 5. Database & Models: App models control schema (sessions + audit) with migrations
- [ ] 6. Testing Integration: Unit + Integration + API + Smoke tests implemented
- [ ] 7. Documentation Updates: Architecture + API flows updated
- [ ] 8. Code Quality: `make lint`, `make format`, `make lint-md` all pass
- [ ] 9. Security Review: Admin enforcement on global rotation; audit trails populated
- [ ] 10. Performance Impact: No significant regressions observed

Append to PR using WARP.md checklist template.

---

## Verification Steps

- Endpoint inventory:

```bash
grep -r "@router\." src/api/v1/*.py | sort > /tmp/endpoints.txt
wc -l /tmp/endpoints.txt  # Expect 30
```

- Session metadata coverage:

```bash
grep -n "get_client_ip" -r src/api/v1 | wc -l
grep -n "get_user_agent" -r src/api/v1 | wc -l
```

- Factory wiring sanity:

```python
# Pseudocode
from src.models.session import Session
from src.models.session_audit import SessionAuditLog
from src.core.database import get_session
from src.session_manager.factory import get_session_manager

db_session = await anext(get_session())
manager = get_session_manager(
    session_model=Session,
    audit_model=SessionAuditLog,
    backend_type="jwt",
    storage_type="database",
    audit_type="logger",  # or "database"
    db_session=db_session,
)
```

- MkDocs and linting:

```bash
make lint-md FILE="docs/development/implementation/session-manager-implementation.md"
make docs-build
```

---

## Appendix A: Naming and Abstraction Guarantees

- Storage: database.py (DB-agnostic), cache.py (cache-agnostic), memory.py (concrete)
- Audit: database.py (DB-agnostic), logger.py (concrete), noop.py (concrete), metrics.py (optional)
- Middleware: no base.py (framework adapter only)
- Models: SessionBase defined by package; app provides concrete Session and audit models

---

## Appendix B: Non-Goals

- No direct imports of app models inside package
- No creation of engine/clients inside package
- No schema or migration ownership by package

---

## Document Information

- **Created**: 2025-11-01
- **Last Updated**: 2025-11-01
