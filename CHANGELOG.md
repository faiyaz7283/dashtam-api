# Changelog

All notable changes to Dashtam will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.3] - 2025-12-25

### Added

- **F6.14**: Application Handler Test Coverage Improvement
  - Added 49 new tests across 4 test files to improve application handler coverage
  - **Phase 1**: Integration tests for sync handlers (test_sync_handlers.py) - 10 tests covering account/transaction sync with provider data mapping, upsert logic, and error handling
  - **Phase 2**: Unit tests for auth flow handlers (test_auth_flow_handlers.py) - 12 tests covering logout, token refresh, email verification, and password reset error paths
  - **Phase 3**: Unit tests for core validation (test_core_validation.py) - 22 tests covering validate_not_empty, validate_email, validate_min_length, validate_max_length functions
  - **Phase 4**: Unit tests for value objects (test_value_objects_email_password.py) - 15 tests covering Email and Password validation, `__str__`, `__repr__`, and error handling
  - Increased overall project coverage from 83% to 86% (+3%)
  - Total test count increased from 1,682 to 1,731 tests (+49)
  - Coverage improvements: sync_transactions_handler.py (22% → covered), sync_accounts_handler.py (30% → covered), core/validation.py (17% → 100%)
  - Exceeded 85% coverage target with comprehensive test coverage across all application layers

### Changed

- Updated uv.lock from version 1.0.1 to 1.0.2 (missed in commit b8dc49a)
- All quality checks passing: 1,731 tests (17 skipped), 86% coverage, zero lint violations

### Fixed

- Fixed Makefile test targets to properly check if containers are running before auto-starting test environment (use `ps --status running` instead of `ps -q`)

## [1.0.2] - 2025-12-25

### Added

- **F6.11**: Cache Optimization (PR #100)
  - Implemented 4-layer cache optimization for high-traffic data paths
  - **Provider Connection Cache**: ~10x faster lookups (<5ms vs ~50ms), 5-minute TTL
  - **Schwab API Response Cache**: 70-90% reduction in external API calls, 5-minute TTL
  - **Account List Cache**: 50-70% reduction in database queries, 5-minute TTL
  - **Security Config Cache**: Reduced token refresh DB load, 1-minute TTL
  - Added CacheMetrics infrastructure for thread-safe hit/miss/error tracking
  - Added CacheKeys utility for centralized cache key pattern management
  - Created 7 new files: cache-key-patterns.md (354 lines), provider_connection_cache.py, cache_keys.py, cache_metrics.py, 3 test files
  - Added 13 integration tests (test_cache_optimization.py, test_cache_provider_connection.py, test_cache_performance.py)
  - Performance verified: >20% improvement on cache hits, fail-open behavior confirmed
  - Total test count increased from 1,659 to 1,672 tests (+13)
  - Overall coverage maintained at 83%

- **F6.13**: API Test Coverage Improvement
  - Added 62 new API tests across 7 test files (test_users_api.py, test_tokens_api.py, test_password_resets_api.py, test_email_verifications_api.py, test_providers_callback_refresh.py, test_accounts_edge_cases.py, test_transactions_edge_cases.py)
  - Improved API v1 layer coverage from 81% to 92% (exceeds 85% target)
  - Increased overall project coverage from 81% to 83% (+2%)
  - Total test count increased from 1,597 to 1,659 tests (+62)
  - Coverage improvements: users.py (46% → 100%), tokens.py (50% → 100%), password_resets.py (48% → 100%), email_verifications.py (50% → 100%), providers.py (60% → 87%), accounts.py (91% → 94%)

### Changed

- Updated cache-usage.md with F6.11 implementation details and usage patterns
- Updated WARP.md with F6.11 completion summary
- Added 6 cache TTL settings to configuration (CACHE_TTL_PROVIDER_CONNECTION, CACHE_TTL_SCHWAB_ACCOUNTS, CACHE_TTL_ACCOUNTS_LIST, CACHE_TTL_SECURITY_CONFIG)
- All quality checks passing: 1,672 tests (17 skipped), 83% coverage, zero lint violations, strict type checking

## [1.0.1] - 2025-12-24

### Fixed

- **F6.15**: Event Handler Wiring Completion
  - Wired 30 missing event handler subscriptions (100 total subscriptions now registered)
  - Added 6 new AuditAction enums for token rotation workflows
  - Fixed 10 syntax errors in logging event handler (extra quotes in type hints)
  - Added registry verification test to prevent future handler drift
  - Added 5 integration tests for new event flows (419 total integration tests)
  - Updated test expectations for deferred operational events (RateLimitCheck, Session events)

### Changed

- Updated container docstring with final event counts and workflow breakdown
- Updated WARP.md with F6.15 completion summary
- Removed temporary event-handler-inventory.md file (working document)
- All 1,597 tests passing (17 skipped), coverage maintained at 81%

## [1.0.0] - 2025-12-12

### Added

#### Phase 0: Foundation (11 features)

- Project structure with hexagonal architecture and clean separation of concerns
- Docker Compose multi-environment orchestration (development, test, CI)
- Configuration management with Pydantic Settings and environment-based loading
- PostgreSQL 17.6 database with async SQLAlchemy and Alembic migrations
- Redis 8.2.1 cache layer with async support for rate limiting and sessions
- Traefik reverse proxy with automatic HTTPS and domain-based routing
- Secrets management with multi-tier strategy (local .env files, AWS Secrets Manager ready)
- Structured logging with structlog for JSON output and correlation IDs
- PCI-DSS compliant audit trail with 3-state pattern (ATTEMPT → SUCCEEDED/FAILED)
- Domain events architecture with event bus and multiple event handlers
- RFC 7807 Problem Details error handling with railway-oriented programming (Result types)

#### Phase 1: Core Infrastructure (5 features)

- JWT authentication with short-lived access tokens (15 min) and opaque refresh tokens (30 days)
- Casbin RBAC authorization with role hierarchy (admin > user > readonly) and 15 permissions
- Token bucket rate limiting with atomic Redis Lua scripts (RFC 6585 compliant headers)
- Multi-device session management with metadata tracking (device info, location, IP address)
- Emergency token rotation with hybrid versioning (global + per-user) and configurable grace period

#### Phase 2: Domain Layer (3 features)

- ProviderConnection entity with 6-state connection lifecycle and encrypted credentials
- Account entity with Money value object for Decimal precision in financial calculations
- Transaction entity with 21 fields, immutable design, and two-level classification system

#### Phase 3: Application Layer (6 features)

- Repository implementations for Provider, Account, and Transaction with entity ↔ model mapping
- CQRS pattern with clear separation of Commands (write) and Queries (read) operations
- Command and Query handlers returning Result types for type-safe error handling
- Domain event handlers for logging, audit trail, email notifications, and session management
- Container factory functions for all handlers with dependency injection
- DTOs for query results with proper serialization (Money → amount + currency)

#### Phase 4: Provider Integration (3 features)

- Charles Schwab OAuth 2.0 Authorization Code flow with token exchange and refresh
- Schwab Accounts API client with JSON-to-domain mapper for account data synchronization
- Schwab Transactions API client with JSON-to-domain mapper for transaction history
- AES-256-GCM encryption service for provider credentials (bank-grade security)
- Clean separation: API clients → Mappers → Provider orchestration layer

#### Phase 5: API Endpoints (15 endpoints)

- **Provider endpoints** (7): list, get by ID, initiate OAuth, OAuth callback, update, disconnect, token refresh
- **Account endpoints** (4): list by user, get by ID, sync from provider, list by connection
- **Transaction endpoints** (4): get by ID, sync from provider, list by account with date range filters
- RFC 7807 error responses with `ErrorResponseBuilder` for consistent API error handling
- Request/response schemas in `src/schemas/` for all endpoints with proper validation
- RESTful design with resource-oriented URLs (100% REST compliance, no controller-style endpoints)

#### Phase 6: v1.0 Release Preparation (9/15 streams completed)

- **F6.1**: Route organization with consistent patterns and proper separation of concerns
- **F6.3**: MkDocs local preview with Traefik routing on `docs.dashtam.local`
- **F6.4**: Architecture compliance audit verifying hexagonal architecture and CQRS patterns
- **F6.5**: Security audit achieving Grade A (Excellent) with 100% vulnerability remediation
- **F6.6**: Test cleanup and coverage analysis (1,589 tests, 81% coverage, 17 skipped)
- **F6.7**: Documentation updates with comprehensive README and zero-to-working Quick Start
- **F6.9**: Migration of API tests to real app pattern (no mock app instances)
- **F6.10**: Adoption of freezegun for reliable time-dependent test execution
- **F6.12**: Admin authentication for protected endpoints with proper authorization checks

### Security

- **Encryption**: AES-256-GCM for provider credentials, bcrypt (12 rounds) for password hashing
- **Authentication**: JWT with 15-minute expiry, email verification required before login
- **Authorization**: Role-based access control with Casbin (admin/user/readonly roles)
- **Rate Limiting**: Token bucket algorithm with atomic Redis operations, fail-open strategy
- **Session Security**: Multi-device tracking, account lockout after 5 failed login attempts
- **Audit Trail**: PCI-DSS compliant immutable logging with 7-year retention requirement
- **Compliance**: SOC 2 ready access controls, GDPR ready audit capabilities
- **Token Management**: Emergency rotation (global + per-user), automatic token breach detection

### Documentation

- **MkDocs**: 18+ architecture documents and guides with Mermaid diagrams
  - Architecture: Hexagonal, CQRS, Domain Events, Error Handling, Testing, etc.
  - Guides: Import Guidelines, Audit Usage, Domain Events Usage, Database Seeding
  - API Flows: 15+ examples with curl commands for authentication, providers, accounts
- **API Documentation**: Auto-generated Swagger UI and ReDoc at `/docs` and `/redoc`
- **README**: Comprehensive Quick Start guide (5 steps from zero to working Dashtam)
- **GitHub Pages**: Deployed documentation at <https://faiyaz7283.github.io/Dashtam/>

### Testing

- **Coverage**: 81% overall (1,589 tests passing, 17 skipped)
- **Test Types**: Unit tests (domain, application), integration tests (database, Redis), API tests
- **Test Strategy**: Pyramid approach with majority unit tests, comprehensive critical path coverage
- **CI/CD**: GitHub Actions with automated testing, linting, type checking on every commit
- **Quality**: 100% type safety with mypy strict mode, zero lint violations with ruff

### Infrastructure

- **Containerization**: Docker Compose for all environments (dev, test, CI)
- **Reverse Proxy**: Traefik with automatic HTTPS using mkcert for local development
- **Databases**: PostgreSQL 17.6 for primary data, Redis 8.2.1 for cache and rate limiting
- **Package Management**: UV 0.8.22 for fast, modern Python dependency management
- **Migrations**: Alembic with async support for database schema versioning

### Development Experience

- **Local Development**: Complete Docker-based workflow with hot reload
- **Environment Isolation**: Separate dev/test environments with no port conflicts
- **Make Commands**: 40+ commands for common tasks (dev-up, test, lint, docs, etc.)
- **Type Safety**: Strict mypy checking with modern Python 3.13+ type hints
- **Code Quality**: Automated formatting (ruff), linting, and type checking in CI/CD

[Unreleased]: https://github.com/faiyaz7283/Dashtam/compare/v1.0.3...HEAD
[1.0.3]: https://github.com/faiyaz7283/Dashtam/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/faiyaz7283/Dashtam/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/faiyaz7283/Dashtam/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/faiyaz7283/Dashtam/releases/tag/v1.0.0
