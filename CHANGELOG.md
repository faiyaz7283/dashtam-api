# Changelog

All notable changes to Dashtam will be documented in this file.

## [1.9.4] - 2026-01-22

### Features

- feat(api): Account Endpoints - 4 Endpoints with Sync Support (#208)
- feat(api): Provider Endpoints - OAuth Flow & Connection Management (#207)
- feat(api): Transaction Endpoints - Date Range Queries (#209)
- feat(cache): Cache Optimization - 4 Layers, >20% Performance (#217)
- feat(domain): Balance Tracking - Point-in-Time Snapshots (#223)
- feat(domain): Holdings Support - Positions Entity & 120+ Tests (#222)
- feat(events): Event Handler Wiring Completion - 100 Subscriptions (#220)
- feat(infra): CQRS Registry Pattern - Handler Factory Auto-Wiring (23 commands, 18 queries, ~1321 lines deleted) (#239)
- feat(infra): Event Registry Pattern - Single Source of Truth (69 events, 143 subscriptions) (#225)
- feat(infra): IP Geolocation Integration - MaxMind GeoIP2 (#219)
- feat(infra): Jobs Service Monitor - Health API for dashtam-jobs (#245)
- feat(infra): Provider Integration Registry - Metadata-Driven (3 providers, 19 tests) (#228)
- feat(infra): Route Metadata Registry - Auto-Generated Routes (36 endpoints) (#231)
- feat(infra): Validation Rules Registry - 4 Rules, 18 Tests (#230)
- feat(providers): Alpaca Provider - API Key Authentication (101 tests) (#221)
- feat(providers): Chase File Import - QFX/OFX/CSV Parser (80+ tests) (#224)
- feat(providers): Schwab Transaction API - Date Range Filtering (#206)
- feat(sse): Data Sync Progress Mappings - 9 SSE Events for Real-Time Sync (#243)
- feat(sse): Data Sync Progress Streaming (#253)
- feat(sse): File Import Progress Streaming (#256)
- feat(sse): Provider Connection Health Notifications (#254)
- feat(sse): Provider Health SSE Mappings - 3 Domain-to-SSE Events (#244)
- feat(sse): SSE Foundation Infrastructure - Real-Time Event Streaming (143 tests, 25 event types) (#242)

### Documentation

- chore(deps): Comprehensive Package Upgrades - 66+ Packages, MkDocs Strict Mode Fixes (#234)
- docs: Architecture Compliance Audit - 23 Docs Reviewed (#213)
- docs: Auto-Generated API Reference - mkdocs-gen-files Plugin (#226)
- docs: Core Architecture Documentation - Hexagonal/Protocol/DDD (4,059 lines) (#227)
- docs: Documentation Audit - 63 Files Renamed, Logging & RFC 9457 Migration (#236)
- docs: Documentation Updates - README Rewrite & Quick Start (#215)
- docs: MkDocs Local Preview - HTTPS via Traefik (#212)
- docs: Rate Limit Registry Pattern Documentation (#229)
- security: Comprehensive Security Audit - Grade A (2 Fixes) (#214)

## [1.9.3] - 2026-01-22

### Features

- feat(api): Account Endpoints - 4 Endpoints with Sync Support (#208)
- feat(api): Provider Endpoints - OAuth Flow & Connection Management (#207)
- feat(api): Transaction Endpoints - Date Range Queries (#209)
- feat(cache): Cache Optimization - 4 Layers, >20% Performance (#217)
- feat(domain): Balance Tracking - Point-in-Time Snapshots (#223)
- feat(domain): Holdings Support - Positions Entity & 120+ Tests (#222)
- feat(events): Event Handler Wiring Completion - 100 Subscriptions (#220)
- feat(infra): CQRS Registry Pattern - Handler Factory Auto-Wiring (23 commands, 18 queries, ~1321 lines deleted) (#239)
- feat(infra): Event Registry Pattern - Single Source of Truth (69 events, 143 subscriptions) (#225)
- feat(infra): IP Geolocation Integration - MaxMind GeoIP2 (#219)
- feat(infra): Jobs Service Monitor - Health API for dashtam-jobs (#245)
- feat(infra): Provider Integration Registry - Metadata-Driven (3 providers, 19 tests) (#228)
- feat(infra): Route Metadata Registry - Auto-Generated Routes (36 endpoints) (#231)
- feat(infra): Validation Rules Registry - 4 Rules, 18 Tests (#230)
- feat(providers): Alpaca Provider - API Key Authentication (101 tests) (#221)
- feat(providers): Chase File Import - QFX/OFX/CSV Parser (80+ tests) (#224)
- feat(providers): Schwab Account API - Client + Mapper (#205)
- feat(providers): Schwab Transaction API - Date Range Filtering (#206)
- feat(sse): Data Sync Progress Mappings - 9 SSE Events for Real-Time Sync (#243)
- feat(sse): Data Sync Progress Streaming (#253)
- feat(sse): Provider Connection Health Notifications (#254)
- feat(sse): Provider Health SSE Mappings - 3 Domain-to-SSE Events (#244)
- feat(sse): SSE Foundation Infrastructure - Real-Time Event Streaming (143 tests, 25 event types) (#242)

### Security

- **Migrate from python-jose to PyJWT** (CVE-2024-23342 mitigation)
  - Removed `python-jose` and vulnerable `ecdsa` dependency
  - Migrated JWT service to use `PyJWT` (already present in dependencies)
  - Zero breaking changes - same HS256 algorithm, compatible token format
  - Eliminates Minerva timing attack vulnerability (CVSS 7.4)
  - All 2,648 tests pass with 89% coverage

### Documentation

- chore(deps): Comprehensive Package Upgrades - 66+ Packages, MkDocs Strict Mode Fixes (#234)
- docs: Architecture Compliance Audit - 23 Docs Reviewed (#213)
- docs: Auto-Generated API Reference - mkdocs-gen-files Plugin (#226)
- docs: Core Architecture Documentation - Hexagonal/Protocol/DDD (4,059 lines) (#227)
- docs: Documentation Audit - 63 Files Renamed, Logging & RFC 9457 Migration (#236)
- docs: Documentation Updates - README Rewrite & Quick Start (#215)
- docs: MkDocs Local Preview - HTTPS via Traefik (#212)
- docs: Rate Limit Registry Pattern Documentation (#229)
- security: Comprehensive Security Audit - Grade A (2 Fixes) (#214)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.9.2] - 2026-01-20

### Added

- **SSE Provider Health Mappings** (Closes #254)
  - 3 domain-to-SSE mappings for provider connection health notifications
  - `ProviderTokenRefreshSucceeded` → `provider.token.refreshed`
  - `ProviderTokenRefreshFailed` → `provider.token.failed`
  - `ProviderDisconnectionSucceeded` → `provider.disconnected`
  - Type-safe payload extractors for each event type

- **Jobs Service Monitor** (`src/infrastructure/jobs/monitor.py`)
  - `JobsMonitor` class for monitoring dashtam-jobs service health
  - Admin endpoint: `GET /api/v1/admin/jobs/health`
  - System endpoint: `GET /system/jobs/status`
  - Configurable via `JOBS_SERVICE_URL` environment variable

### Changed

- **README Badge URLs**: Fixed GitHub badge URLs from `Dashtam` → `dashtam-api`

### Technical Notes

- **Zero Breaking Changes**: All tests pass, 88% coverage maintained
- **New Test Files**: `test_domain_sse_provider_mappings.py`, `test_infrastructure_jobs_monitor.py`, `test_admin_jobs_api.py`
- Cross-service: Works with dashtam-jobs v0.2.0 SSE publisher

## [1.9.1] - 2026-01-18

### Added

- **SSE Data Sync Progress Mappings** (Closes #253)
  - 9 domain-to-SSE mappings for real-time sync progress streaming
  - Account sync: `AccountSyncAttempted/Succeeded/Failed` → `sync.accounts.*`
  - Transaction sync: `TransactionSyncAttempted/Succeeded/Failed` → `sync.transactions.*`
  - Holdings sync: `HoldingsSyncAttempted/Succeeded/Failed` → `sync.holdings.*`
  - Type-safe payload extractors with `cast()` for each event type
  - Common `_extract_user_id()` helper for user routing

- **GitHub Issue Templates** (`.github/ISSUE_TEMPLATE/`)
  - `feature_request.yml` - YAML-based feature request form
  - `bug_report.yml` - YAML-based bug report form
  - `config.yml` - Template chooser configuration

### Changed

- **Release Checklist**: Added GitHub Issues workflow integration
  - Milestone verification before release
  - Milestone closure after release
  - Issue references in CHANGELOG entries

- **Container Wiring Test**: Updated subscription count to include SSE handler subscriptions

### Technical Notes

- **Zero Breaking Changes**: All 2,598 tests pass, 88% coverage maintained
- **New Test File**: `tests/unit/test_domain_sse_data_sync_mappings.py` (24 tests)
- Files changed: 10 files

## [1.9.0] - 2026-01-18

### Added

- **SSE Foundation Infrastructure** - Real-time server-to-client event streaming
  - **Domain Layer**
    - `SSEEvent` dataclass with wire format serialization (`to_sse_format()`, `to_dict()`, `from_dict()`)
    - `SSEEventType` enum (25 event types across 6 categories)
    - `SSEEventCategory` enum (data_sync, provider, ai, import, portfolio, security)
    - `SSEEventMetadata` and `SSE_EVENT_REGISTRY` (registry pattern, 25 entries)
    - `SSEPublisherProtocol` and `SSESubscriberProtocol` (hexagonal ports)
  - **Infrastructure Layer**
    - `RedisSSEPublisher` - Publishes events via Redis pub/sub, optional Streams retention
    - `RedisSSESubscriber` - Async generator subscription with category filtering
    - `SSEChannelKeys` - Centralized channel/stream key generation
    - `SSEEventHandler` - Subscribes to domain events, transforms to SSE events
  - **Presentation Layer**
    - `GET /api/v1/events` endpoint with StreamingResponse
    - Route registry entry with `RateLimitPolicy.SSE_STREAM`
    - Authentication via existing Bearer token
  - **Container Wiring**
    - `get_sse_publisher()` - App-scoped singleton
    - `get_sse_subscriber()` - Request-scoped factory
  - **Configuration**
    - 6 constants in `src/core/constants.py` (heartbeat, retry, channel prefix, retention)
    - `sse_enable_retention` setting in `config.py`

- **SSE Registry Documentation** (`docs/architecture/sse-registry.md`)
  - Follows existing registry pattern (like route-registry, validation-registry)
  - Covers architecture, usage, compliance tests, and adding new events

### Changed

- **Rate Limit Policy**: Added `RateLimitPolicy.SSE_STREAM` for SSE endpoints
- **Route Registry Test**: Updated `test_response_models_are_defined` to exempt SSE streaming endpoints

### Technical Notes

- **Zero Breaking Changes**: All 2,550 tests pass, 88% coverage maintained
- **New Test Files**: 4 (`test_domain_sse_event.py`, `test_domain_sse_registry_compliance.py`, `test_events_endpoints.py`, `test_sse_redis_pubsub.py`)
- **New Tests**: 106 unit tests, 25 integration tests, 12 API tests (143 total)
- **Documentation**: `docs/architecture/sse-architecture.md` (1400+ lines), `docs/architecture/sse-registry.md` (300+ lines)
- Files changed: 25+ files

## [1.8.2] - 2026-01-17

### Added

- **OwnershipVerifier Service** (`src/application/services/ownership_verifier.py`)
  - DRY pattern for ownership chain verification (Entity → Account → Connection → User)
  - 5 methods: `verify_connection_ownership`, `verify_account_ownership`, `verify_account_ownership_only`, `verify_holding_ownership`, `verify_transaction_ownership`
  - Session-scoped via `SESSION_SERVICE_TYPES` in `handler_factory.py`
  - 20 unit tests in `test_application_ownership_verifier.py`

- **BaseProviderAPIClient** (`src/infrastructure/providers/base_api_client.py`)
  - Shared HTTP client base class for all provider API clients
  - Centralized HTTP status → `ProviderError` mapping
  - Consistent timeout and error handling
  - All 4 provider API clients (Schwab/Alpaca accounts/transactions) now extend this base

- **Centralized Constants** (`src/core/constants.py`)
  - Single source of truth for timeouts, HTTP status mappings, magic numbers
  - `DEFAULT_HTTP_TIMEOUT`, `PROVIDER_API_TIMEOUT`, `HTTP_STATUS_ERROR_MAP`
  - 15 unit tests in `test_core_constants.py`

### Changed

- **Query Handler Refactoring**
  - `GetAccountHandler`, `GetHoldingHandler`, `GetTransactionHandler` now use `OwnershipVerifier`
  - Eliminates duplicated ownership verification logic across handlers
  - Handler tests updated to mock `OwnershipVerifier` instead of individual repos

- **RFC 9457 Migration**: Updated all RFC 7807 references to RFC 9457 (current standard)
  - RFC 9457 (July 2023) obsoletes RFC 7807 with backward-compatible enhancements
  - No code changes required - JSON schema and behavior identical
  - Updated 222 references across source, docs, and tests

- **Documentation Updates**
  - `docs/architecture/dependency-injection.md`: Added OwnershipVerifier, SESSION_SERVICE_TYPES
  - `docs/architecture/cqrs.md`: Updated query handler patterns with OwnershipVerifier
  - `docs/architecture/provider-integration.md`: Added BaseProviderAPIClient section
  - `docs/guides/adding-providers.md`: Updated to show extending BaseProviderAPIClient
  - `WARP.md`: Added sections 6b (OwnershipVerifier) and 6c (Centralized Constants)

- **Configuration**
  - Added `alpaca_api_base_url` to `config.py` and all `.env.*.example` files
  - Added `_rule()` factory helper in `derivations.py` for rate limit rule creation

### Technical Notes

- **Zero Breaking Changes**: All 2,444 tests pass, 88% coverage maintained
- **New Test Files**: 3 (`test_core_constants.py`, `test_application_ownership_verifier.py`, `test_infrastructure_base_api_client.py`)
- **DRY Improvements**: Eliminated ~200 lines of duplicated ownership verification code
- Files changed: 30+ files

## [1.8.1] - 2026-01-16

### Security

- **CVE-2026-23490**: Updated `pyasn1` 0.6.1 → 0.6.2 (OID decoder vulnerability)
- **CVE-2026-21441**: Updated `urllib3` 2.6.2 → 2.6.3 (decompression bomb bypass, 8.9 High)
- **GHSA-87hc-h4r5-73f7**: Updated `werkzeug` 3.1.4 → 3.1.5 (Windows device name vulnerability)

### Changed

- **FastAPI Upgrade**: 0.118.0 → 0.128.0
  - Fixes v1.6.8 release oversight where FastAPI was not actually upgraded
  - Simplified `Path()` parameters (removed Ellipsis, FastAPI 0.128 style)
- **Python 3.14 Modernization**
  - Removed `from __future__ import annotations` from 13 files (PEP 649 native)
  - Added `ReadOnly` to `CacheEntry` TypedDict
  - Updated version references in 9 documentation files
- **Documentation**
  - Updated deprecated `@app.on_event` examples to modern `lifespan` pattern
  - Fixed GitHub repo URL in `mkdocs.yml`

### Technical Notes

- **Zero Breaking Changes**: All 2,385 tests pass, 88% coverage maintained
- **Audit Reports**: See `~/references/audit/` for Python 3.14 and FastAPI audits
- Files changed: 29+ files

## [1.8.0] - 2026-01-14

### Added

- **CQRS Registry Pattern** (`src/application/cqrs/`)
  - Single source of truth for all 23 commands and 18 queries
  - `metadata.py`: `CommandMetadata`, `QueryMetadata`, `CQRSCategory`, `CachePolicy`
  - `registry.py`: `COMMAND_REGISTRY`, `QUERY_REGISTRY` with full metadata
  - `computed_views.py`: Helper functions for introspection (`get_all_commands`, `get_statistics`, etc.)
  - Self-enforcing compliance tests (40 tests) that fail on drift

- **Handler Factory Auto-Wiring** (`src/core/container/handler_factory.py`)
  - Automatic dependency injection for all 38 CQRS handlers
  - `handler_factory()`: FastAPI dependency generator with caching
  - `create_handler()`: Introspects `__init__` type hints, resolves repositories and singletons
  - Supports 11 repository types and 25+ singleton service types
  - **Deleted ~1321 lines** of manual factory functions:
    - `auth_handlers.py` (~557 lines)
    - `data_handlers.py` (~570 lines)
    - `provider_handlers.py` (~194 lines)

- **Comprehensive Test Coverage**
  - `tests/unit/test_core_handler_factory.py` (40 tests, 94% coverage)
  - Extended `tests/unit/test_cqrs_registry_compliance.py` (55 new tests)
  - Total: 95 new tests for CQRS registry and handler factory

- **Documentation**
  - `docs/architecture/cqrs-registry.md`: Detailed CQRS Registry documentation
  - `docs/architecture/registry.md`: Added CQRS Registry to "Implemented Applications"
  - `WARP.md`: Added Section 6a (CQRS Registry Pattern)
  - `docs/guides/dependency-injection.md`: Updated with handler_factory patterns

### Changed

- **Router Migration**
  - All 17+ API routers migrated to `handler_factory(HandlerClass)` pattern
  - Test dependency overrides updated: `app.dependency_overrides[handler_factory(Handler)]`
  - OAuth callbacks updated to use handler_factory

### Technical Notes

- **Zero Breaking Changes**: All 2,385 tests pass, 88% coverage maintained
- **Coverage Improvement**:
  - `handler_factory.py`: 0% → 94%
  - `computed_views.py`: 69% → 94%
  - `metadata.py`: 77% → 94%
- **Architecture**: Registry Pattern applied to CQRS (parallel to Event Registry and Route Registry)
- **Benefits**: Zero manual factory functions, self-enforcing tests, automatic handler wiring
- Files changed: 50+ files

## [1.7.0] - 2026-01-14

### Added

- **DTO (Data Transfer Objects) Module** (`src/application/dtos/`)
  - Created dedicated directory for application-layer DTOs
  - Relocated 8 DTOs from scattered command/handler files:
    - `auth_dtos.py`: `AuthenticatedUser`, `AuthTokens`, `GlobalRotationResult`, `UserRotationResult`
    - `sync_dtos.py`: `SyncAccountsResult`, `SyncTransactionsResult`, `SyncHoldingsResult`
    - `import_dtos.py`: `ImportResult`
  - Centralized exports via `__init__.py`
  - Backward-compatible: DTOs re-exported from `src.application.commands`

- **DTO Tests** (`tests/unit/test_application_dtos.py`)
  - 17 unit tests covering all 8 DTOs
  - Tests for immutability, keyword-only args, module exports

### Changed

- **Documentation Updates**
  - `docs/architecture/cqrs.md`: Added "DTOs (Data Transfer Objects)" section explaining:
    - Purpose and benefits of DTOs
    - Layer-specific data types (DTOs vs Protocol types vs Pydantic schemas)
    - DTO structure and patterns
    - Usage examples and import guidelines
  - `docs/architecture/directory-structure.md`: Updated application layer structure to include `dtos/` directory

### Technical Notes

- **Zero Breaking Changes**: All 2,290 tests pass, 87% coverage maintained
- **Import Pattern**: `from src.application.dtos import AuthenticatedUser, AuthTokens`
- **Backward Compatible**: Original command module imports still work via re-exports
- **Files Changed**: 17 files (4 new, 13 modified)
- **Preparation for**: F-CQRS-Registry feature (DTOs needed for registry result types)

## [1.6.9] - 2026-01-14

### Changed

- **CQRS Architecture Compliance (82% → 100%)**
  - **Domain Protocols**: Created 3 new protocols in `src/domain/protocols/`
    - `EncryptionProtocol`: Defines encryption/decryption interface for sensitive data
    - `CacheKeysProtocol`: Defines cache key generation patterns
    - `CacheMetricsProtocol`: Defines cache metrics tracking interface
  - **Session Revocation Events**: Added 4 new 3-state events to `session_events.py`
    - `SessionRevocationAttempted`, `SessionRevocationSucceeded`, `SessionRevocationFailed`
    - `AllSessionsRevocationFailed` (completes 3-state pattern)
  - **Command Handlers**: Updated 5 handlers to emit 3-state domain events
    - `revoke_session_handler.py`: Full ATTEMPT → OUTCOME pattern
    - `revoke_all_sessions_handler.py`: Full ATTEMPT → OUTCOME pattern
    - `sync_accounts_handler.py`: Data sync 3-state events
    - `sync_transactions_handler.py`: Data sync 3-state events
    - `sync_holdings_handler.py`: Data sync 3-state events
  - **Event Registry**: Added all 4 new events to `EVENT_REGISTRY` with metadata
  - **Event Handlers**: Added 8 handler methods (4 logging + 4 audit)
  - **Audit Actions**: Added 4 new `AuditAction` enums for session revocation

### Fixed

- **Import Compliance**: Removed infrastructure imports from application layer handlers
  - `refresh_access_token_handler.py`: Now imports `EncryptionProtocol` from domain
  - `list_accounts_handler.py`: Now imports `CacheKeysProtocol` from domain

### Technical Notes

- **Zero Breaking Changes**: All 2,273 tests pass, 87% coverage maintained
- **Event-Driven Pattern**: All critical workflows now follow ATTEMPT → OUTCOME pattern
- **Hexagonal Compliance**: Application layer depends only on domain protocols
- **Self-Enforcing**: Event registry tests validate handler method coverage
- Files changed: 19 files

## [1.6.8] - 2026-01-10

### Changed

- **Documentation Audit (63 Files)**
  - Renamed 61 files to remove redundant suffixes (e.g., `-guide.md`, `-architecture.md`)
  - Merged duplicate error-handling guides into single comprehensive guide
  - Updated logging and audit docs with event registry integration
  - Updated all 15 API docs with rate limits, implementation refs, and schema fixes
  - Updated all 17 guides with correct import paths and types
  - Comprehensive audit of all 34 architecture docs

- **Code Migration Audit (Logging & RFC 7807)**
  - Fixed 12 f-string logging violations in 4 provider API files (Schwab/Alpaca accounts/transactions)
  - Added `http_exception_handler` and `validation_exception_handler` to `exception_handlers.py`
  - All HTTPException and RequestValidationError responses now RFC 7807 compliant
  - Updated 23 API tests to verify new RFC 7807 response format

### Documentation

- **Audit Reference**: `~/references/audit/dashtam-docs-audit-2026-01-08.md`

### Technical Notes

- **Zero Breaking Changes**: All 2,273 tests pass, coverage maintained
- **Documentation Quality**: `make lint-md` and `make docs-build` pass with zero warnings
- **Logging Pattern**: Changed from f-string interpolation to lazy `%s` formatting per structlog best practices
- **Exception Handler Signatures**: Use `Exception` type with runtime assertions for mypy compatibility
- Files changed: 73+ files (63 docs, 4 provider APIs, 1 exception handler, 5 test files)

## [1.6.7] - 2026-01-08

### Added

- **Test Type Safety (Pragmatic Approach)**
  - Enabled `check_untyped_defs = true` in mypy configuration for test files
  - Type-checking now includes `tests/` directory alongside `src/`
  - Fixed 436 mypy errors across 132 test files (unit, integration, API tests)
  - Makefile updated: `make typecheck` and `make verify` now type-check both `src` and `tests`

### Documentation

- **Testing Architecture**: Added "Type Safety in Tests" section to `docs/architecture/testing-architecture.md`
  - Common type patterns: `cast(UUID, uuid7())`, `isinstance(result, Success)`, `assert obj is not None`
  - Guidelines for `# type: ignore[error-code]` usage
  - Protocol-compliant test stub patterns
- **WARP.md**: Updated Section 12 (Testing Strategy) with type safety patterns and reference

### Technical Notes

- **Zero Breaking Changes**: All 2,273 tests pass, 87% coverage maintained
- **Pragmatic Typing**: Tests use relaxed mypy settings (`disallow_untyped_defs = false`) but still catch type mismatches in test bodies
- **Source File Change**: Widened `base_adapter.py` return type from `dict[str, str]` to `dict[str, Any]` for `get_secret_json()`
- **Key Patterns Applied**:
  - `cast(UUID, uuid7())` for uuid_utils compatibility
  - `isinstance(result, Success)` before accessing `.value` on Result types
  - `Success[object] | Failure[str]` for mock handler return types
  - Protocol-compliant signatures in StubEventBus (matching `EventBusProtocol`)
- Files changed: 135+ files (132 test files, pyproject.toml, Makefile, docs)

## [1.6.6] - 2026-01-05

### Changed

- **Python 3.14 Upgrade (Zero Application Code Changes)**
  - **Python Version**: 3.13.x → 3.14.2
  - **UV Package Manager**: 0.8.22 → 0.9.21
  - **Docker Images**:
    - Base stage: `ghcr.io/astral-sh/uv:0.9.21-python3.14-trixie` (Debian 13)
    - Production stage: `python:3.14-slim` (Debian 13)
  - **GitHub Actions**: CI/CD workflows updated to Python 3.14
  - **Breaking Changes Audit**: Zero occurrences (AST removals, argparse, asyncio child watchers, importlib.abc)
  - **Deprecation Warnings Audit**: Zero warnings from application code

### Fixed

- **Test Configuration (Python 3.14 Deprecations)**
  - Fixed `asyncio.iscoroutinefunction()` deprecation → use `inspect.iscoroutinefunction()`
  - Fixed `asyncio.get_event_loop_policy()` deprecation → use `asyncio.new_event_loop()` directly
  - Files fixed: `tests/conftest.py` (3 changes)
  - Result: Zero asyncio deprecation warnings from Dashtam code

### Technical Notes

- **Zero Application Code Changes**: All Python 3.14 breaking changes target old patterns - Dashtam uses modern patterns throughout
- **Zero Breaking Changes**: All 2,273 tests pass, 87% coverage maintained
- **Warning Analysis**: ~35 warnings from third-party `ofxparse` library (BeautifulSoup), zero from Dashtam code
- **Architecture Verification**: Hexagonal, Protocol-Based, CQRS, Domain Events - all patterns intact
- **Docker Image Strategy**: Using Debian 13 Trixie everywhere for consistency (Python 3.14 slim variant not available yet)
- **Python 3.14 Features**: Automatic benefits from PEP 649 (deferred annotations) and REPL improvements
- **Confidence Level**: HIGH - comprehensive audit, full test coverage, modern codebase
- Files changed: 5 files (+15 insertions, -10 deletions)
- **Audit Document**: `~/references/audit/python-3.14-upgrade-findings.md`

## [1.6.5] - 2026-01-04

### Changed

- **Comprehensive Package Upgrades (66+ packages)**
  - **Major Version Upgrades**:
    - `pytest`: 8.4.2 → 9.0.2 (MAJOR)
    - `mkdocstrings`: 0.30.1 → 1.0.0 (MAJOR)
    - `mkdocstrings-python`: 1.18.2 → 2.0.1 (MAJOR)
    - `maxminddb`: 2.8.2 → 3.0.0 (MAJOR)
  - **Minor/Patch Upgrades**:
    - `ruff`: 0.13.3 → 0.14.10
    - `alembic`: 1.16.5 → 1.17.2
    - `psycopg`: 3.2.10 → 3.3.2
    - `pydantic`: 2.11.9 → 2.12.5
    - `uvicorn`: 0.37.0 → 0.40.0
    - `boto3`: 1.40.45 → 1.42.21
    - `asyncpg`: 0.30.0 → 0.31.0
    - `redis`: 7.0.0 → 7.1.0
    - `sqlalchemy`: 2.0.43 → 2.0.45
    - `sqlmodel`: 0.0.25 → 0.0.31
    - `mypy`: 1.18.2 → 1.19.1
    - [51+ more packages upgraded]
  - **Dependency Changes**:
    - Added: `librt v0.7.7` (new transitive dependency)
    - Removed: `sniffio v1.3.1` (no longer required)

### Fixed

- **Documentation Generation (MkDocs Strict Mode)**
  - **27 griffe v1.15.0 warnings fixed** → **Zero warnings**
  - **Type 1 (20 files)**: Removed duplicate "Returns:" sections from class docstrings (methods already had proper Returns sections)
  - **Type 2 (7 files)**: Added explicit type hints to early `Failure()` returns using `cast()` for griffe type inference
  - **Type 3 (2 files)**: Removed "Raises:" sections that said "No exceptions raised" (griffe expects `ExceptionType: description` format)
  - **Type 4 (3 files)**: Escaped string literals in docstrings with backticks to prevent cross-reference warnings
  - Files fixed: 7 command handlers, 12 query handlers, 1 config file, 1 protocol file, 2 infrastructure files

- **Type Safety (Mypy Compliance)**
  - **14 SQLAlchemy Result.rowcount errors fixed** → **Zero errors**
  - Added `cast(Any, result).rowcount` to handle SQLAlchemy 2.0+ type stubs (Result[Any] doesn't expose rowcount attribute)
  - Files fixed: `session_repository.py` (6 locations), `holding_repository.py` (1 location)
  - Maintained **100% mypy compliance** on 311 source files

### Technical Notes

- **Zero Breaking Changes**: All 2,273 tests pass, 88% coverage maintained
- **Documentation Quality**: `mkdocs build --strict` passes with zero warnings (was failing with 27 warnings)
- **Type Safety**: 100% mypy compliance maintained (was failing with 14 errors)
- **Package Strategy**: Aggressive upgrade strategy (all 66+ packages upgraded at once)
- **Pattern**: Used `typing.cast()` for documentation metadata (zero runtime cost, griffe AST inference aid)
- **Root Cause**: griffe v1.15.0 stricter type inference couldn't infer `Failure()` as `Result[T, E]` from early returns
- **Design Validation**: Result type design is textbook-perfect Railway-Oriented Programming (verified with mypy)
- Files changed: 21 files (+87 insertions, -87 deletions)

## [1.6.4] - 2026-01-04

### Changed

- **Infrastructure Upgrades**
  - **UV**: Upgraded from 0.8.22 to 0.9.21 (Python package manager)
  - **PostgreSQL**: Upgraded from 17.6 to 17.7 (database)
  - **Redis**: Upgraded from 8.2.1 to 8.4 (cache)
  - **FastAPI**: Upgraded from 0.118.0 to 0.128.0 (web framework)
- **Type Safety Improvements**
  - Fixed all mypy type errors from FastAPI 0.128.0 upgrade (1,122 → 0 errors)
  - Updated deprecated `HTTP_422_UNPROCESSABLE_ENTITY` to `HTTP_422_UNPROCESSABLE_CONTENT`
  - Added proper type annotations to production code
  - Fixed alembic migration constraint names
  - Updated mkdocs gen script for third-party library compatibility
- **Docker Configuration**
  - Updated `docker/Dockerfile` with UV 0.9.21
  - Updated `docker-compose.dev.yml`, `docker-compose.test.yml`, `docker-compose.ci.yml` with PostgreSQL 17.7 and Redis 8.4

### Technical Notes

- **100% Mypy Compliance**: All 335 production source files pass type checking with zero errors
- **Zero Breaking Changes**: All 2,291 tests pass, 88% coverage maintained
- **Maintenance Release**: Infrastructure updates only, no functional changes
- Files changed: 9 files (+57 insertions, -19 deletions)

## [1.6.3] - 2025-12-31

### Added

- **F8.2: Route Metadata Registry (5th Registry Pattern Implementation)**
  - **Registry Infrastructure**: Created `src/presentation/routers/api/v1/routes/` module with 4 files
    - `metadata.py` (219 lines): RouteMetadata dataclass, HTTPMethod/AuthPolicy/RateLimitPolicy/IdempotencyLevel enums, ErrorSpec type
    - `registry.py` (810 lines): ROUTE_REGISTRY with 36 endpoint metadata entries (single source of truth)
    - `generator.py` (143 lines): `register_routes_from_registry()` auto-generates FastAPI routes from registry
    - `derivations.py` (252 lines): Two-tier rate limit pattern - policy assignment (Tier 1) and policy rules (Tier 2)
  - **Auto-Generated Routes**: All 36 endpoints now generated from registry (zero manual decorators)
  - **Auto-Generated Rate Limits**: Created `src/infrastructure/rate_limit/from_registry.py` (94 lines) - rate limit rules generated from registry
  - **Router Refactoring**: Converted 12 router files to pure handler functions (removed all @router decorators)
    - Sessions (6 handlers), Tokens (1), Users (1), Email Verifications (1), Password Resets (2)
    - Providers (6), Accounts (4), Transactions (3), Holdings (3), Balance Snapshots (3), Imports (2), Admin (3)
  - **Self-Enforcing Tests**: Created `tests/api/test_route_metadata_registry_compliance.py` with 18 tests
    - Registry Completeness (6 tests): All routes registered, operation IDs unique, no missing/extra routes
    - Auth Policy Enforcement (3 tests): PUBLIC/AUTHENTICATED/ADMIN/MANUAL_AUTH verified
    - Rate Limit Coverage (4 tests): All endpoints have policies, rules cover all, no unknown rules
    - Metadata Consistency (4 tests): FastAPI metadata matches registry, manual auth documented
    - Statistics Reporting (1 test): Breakdown by auth/rate limit/idempotency policies
  - **Zero Drift**: Tests fail if routes missing from registry, handlers missing, or metadata inconsistent
  - **Benefits**: Single source of truth, self-documenting API, auto-wired dependencies, future-proof (can't drift silently)
  - Total test count increased from 2,253 to 2,271 tests (+18)
  - Overall coverage maintained at 88%

### Changed

- **RFC 7807 Full Compliance (Breaking Change)**
  - **Removed**: `AuthErrorResponse` schema from `src/schemas/auth_schemas.py` (BREAKING CHANGE)
  - **Standardized**: All API errors now use RFC 7807 `ProblemDetails` format via `ErrorResponseBuilder`
  - **Updated**: 21 API tests to expect new error format with ApplicationErrorCode URLs
  - **Migration Impact**: Clients must parse `error.type` field (ApplicationErrorCode URLs) instead of `error.error` strings
- **Rate Limit Configuration Refactored**
  - `src/infrastructure/rate_limit/config.py` became thin proxy (imports from `from_registry.py`)
  - Hand-written rate limit rules replaced with auto-generated rules from Route Registry
  - Two-tier pattern: Tier 1 (policy assignment in registry) + Tier 2 (policy rules in derivations)
- **Router Architecture Modernized**
  - All routers converted from decorator-based to declarative registry-driven generation
  - Handlers are pure functions (no decorators, no router imports)
  - `src/presentation/routers/api/v1/__init__.py` uses `register_routes_from_registry()`

### Documentation

- **Error Handling Guide**: Created `docs/guides/error-handling-guide.md` (726 lines)
  - RFC 7807 Problem Details standard overview
  - ProblemDetails schema fields (type, title, status, detail, instance, errors, trace_id)
  - ErrorResponseBuilder usage patterns and ApplicationErrorCode reference
  - Client error handling examples (TypeScript/Python)
  - Migration guide from AuthErrorResponse to RFC 7807
- **Route Registry Architecture**: Created `docs/architecture/route-registry-architecture.md` (772 lines)
  - Complete registry structure and metadata documentation
  - Route generation process (declarative → FastAPI routes)
  - Two-tier rate limit pattern explanation
  - Self-enforcing compliance tests
  - Step-by-step guide for adding new endpoints
  - Benefits, design decisions, and future enhancements
- **Architecture Updates**
  - Updated `docs/architecture/registry-pattern-architecture.md` - Added Route Registry as 5th implementation
  - Updated `docs/index.md` - Redesigned landing page (247→121 lines, 50% reduction), strategic minimalistic design
  - Updated `WARP.md` - Added Section 9 (RFC 7807) and Section 9a (Route Registry pattern), updated date
  - Updated `mkdocs.yml` - Added error-handling-guide.md and route-registry-architecture.md to navigation

### Breaking Changes

- **AuthErrorResponse Removed**: All authentication/authorization errors now return RFC 7807 `ProblemDetails`
- **Error Response Format Changed**:
  - **Before** (v1.6.2 and earlier):

    ```json
    {
      "error": "invalid_credentials",
      "message": "Invalid email or password"
    }
    ```

  - **After** (v1.6.3+):
  
    ```json
    {
      "type": "https://api.dashtam.com/errors/unauthorized",
      "title": "Authentication Required",
      "status": 401,
      "detail": "Invalid email or password",
      "instance": "/api/v1/sessions",
      "trace_id": "550e8400-..."
    }
    ```

- **Client Migration Required**:
  - Match on `error.type` (ApplicationErrorCode URLs), NOT `status` code
  - Parse `detail` for human-readable message
  - Use `trace_id` for debugging/support tickets
  - See `docs/guides/error-handling-guide.md` for complete examples

### Technical Notes

- Registry Pattern now has 5 implementations: Domain Events, Provider Integration, Rate Limit Rules, Validation Rules, Route Metadata
- All 5 registries follow same pattern: metadata-driven catalog, self-enforcing tests, helper functions, zero drift
- Route generation eliminates decorator sprawl, prevents manual/automated code drift
- All markdown linting passed (68 files, zero violations)
- MkDocs builds successfully (zero warnings)
- Files changed: 38 files, +4,443 insertions, -1,443 deletions

## [1.6.2] - 2025-12-31

### Documentation

- **F8.4: Validation Rules Registry (4th Registry Pattern Implementation)**
  - Created `src/domain/validators/registry.py` (206 lines) as single source of truth for all validation rules
  - **ValidationRuleMetadata Dataclass**: Catalog with rule_name, validator_function, field_constraints, description, examples, and category
  - **ValidationCategory Enum**: 4 categories (AUTHENTICATION, API_PARAMETERS, PROVIDER_DATA, DOMAIN_VALUES)
  - **VALIDATION_RULES_REGISTRY**: 4 validation rules cataloged (email, password, verification_token, refresh_token)
  - **Helper Functions**: 4 registry helpers (`get_validation_rule`, `get_all_validation_rules`, `get_rules_by_category`, `get_statistics`)
  - **Self-Enforcing Tests**: 18 compliance tests in `test_validation_registry_compliance.py` across 4 test classes
    - Registry Completeness (8 tests): validator functions, field constraints, descriptions, examples, categories, uniqueness, naming convention
    - Validator Functions (4 tests): callable validators, error handling, return types, edge cases
    - Type Consistency (3 tests): domain types integration, no duplicates, examples validation
    - Statistics (3 tests): minimum rules, category distribution, helper functions
  - **Zero Drift**: Tests fail if validators lack metadata, examples don't validate, or constraints invalid
  - **Registry Module Coverage**: 100% achieved
  - Total test count increased from 2,231 to 2,253 tests (+18)
- **Comprehensive Architecture Documentation**
  - Created `docs/architecture/validation-registry-architecture.md` (1,097 lines)
    - Complete registry structure and metadata documentation
    - All 4 current validation rules documented with examples
    - Step-by-step guide for adding new validation rules
    - Integration examples (documentation generation, API schemas, testing, monitoring)
    - Design decisions explained (metadata-driven, dict vs list, separate functions, enum categories)
    - Pattern consistency comparison with Domain Events, Provider, and Rate Limit registries
    - Future enhancements roadmap (API parameters, provider data, domain values)
  - Updated `docs/architecture/registry-pattern-architecture.md` - Added Validation Rules Registry as 4th "Implemented Applications" example with complete results
  - Updated `docs/index.md` - Added Validation Registry reference under Domain Models, updated Event Registry Pattern description to mention 4 implementations
  - Updated `mkdocs.yml` - Added validation-registry-architecture.md to navigation
- **Timeless Architecture Standards**
  - Removed roadmap references (F7.7, F8.1, F8.3, F8.4) from multiple architecture documents
  - Updated documents to use pattern names instead of feature codes ("Domain Events Registry" not "F7.7")
  - Architecture docs now timeless and don't reference implementation timeline
  - Affected files: validation-registry-architecture.md, registry-pattern-architecture.md, provider-registry-architecture.md

### Technical Notes

- Documentation-only release (PATCH version bump)
- Registry Pattern now has 4 implementations: Domain Events, Provider Integration, Rate Limit Rules, Validation Rules
- All 4 registries follow same pattern: metadata-driven catalog, self-enforcing tests, helper functions, 100% coverage target
- All markdown linting passed (zero violations)
- MkDocs builds successfully (zero warnings)
- Overall coverage maintained at 88%

## [1.6.1] - 2025-12-31

### Documentation

- **Rate Limit Registry Pattern Documentation**
  - Added Section 5: Registry Pattern to `docs/architecture/rate-limit-architecture.md` (107 lines)
  - Documents `RATE_LIMIT_RULES` as Registry Pattern implementation following F7.7 and F8.1
  - Explains F8.3 self-enforcing compliance tests (23 tests across 5 test classes)
  - Shows Before/After F8.3 comparison (Configuration Only → Registry Pattern + Compliance Tests)
  - Documents pattern consistency: metadata-driven catalog, self-enforcing tests, zero drift
  - Updated metadata: Last Updated to 2025-12-31
- **Registry Pattern Architecture Updates**
  - Added "Implemented Applications" section to `docs/architecture/registry-pattern-architecture.md`
  - Moved Rate Limit Rules Registry from "Future Applications" to "Implemented" (3rd implementation)
  - Added complete results: 25 endpoint rules, 23 self-enforcing tests, 100% coverage, 5 test classes
  - Added F8.4 Validation Registry to "Future Applications" with implementation plan ready status
  - Updated cross-references between F7.7 (Domain Events), F8.1 (Providers), and F8.3 (Rate Limits)

### Technical Notes

- Documentation-only release (PATCH version bump)
- Completes F8.3 documentation gap identified post-merge
- All markdown linting passed (zero violations)
- MkDocs builds successfully (zero errors)

## [1.6.0] - 2025-12-31

### Added

- **F8.1**: Provider Integration Registry (Registry Pattern for Providers)
  - **Compliance Tests**: Created `tests/unit/test_rate_limit_registry_compliance.py` with 23 self-enforcing tests
  - **5 Test Classes**: Registry Completeness (8 tests), Rule Consistency (4 tests), Pattern Matching (4 tests), Registry Statistics (4 tests), Future-Proofing (3 tests)
  - **Validation Coverage**: All 25 endpoint rules verified for completeness (positive max_tokens/refill_rate/cost, valid scopes, boolean enabled, METHOD /path format, no duplicates, RateLimitRule instances)
  - **Consistency Checks**: Auth endpoints use IP/USER scope, API endpoints use USER scope, critical endpoints have explicit rules
  - **Pattern Matching Tests**: Exact match, path parameter matching, non-existent endpoints, method mismatch validation
  - **Future-Proofing**: No wildcards, lowercase paths, no trailing slashes
  - **Zero Drift**: Tests fail if rules missing required config or have malformed patterns
  - **100% Coverage**: Rate limit config module achieves 100% test coverage (exceeds 95%+ target)
  - Total test count increased from 2,208 to 2,231 tests (+23)
  - All 11 rule constants validated: AUTH_LOGIN_RULE, AUTH_REGISTER_RULE, AUTH_PASSWORD_RESET_RULE, AUTH_TOKEN_REFRESH_RULE, PROVIDER_CONNECT_RULE, PROVIDER_SYNC_RULE, API_READ_RULE, API_WRITE_RULE, EXPORT_RULE, REPORT_RULE, GLOBAL_API_RULE

### Documentation

- Rate limit registry already documented in existing `docs/architecture/rate-limiting-architecture.md`
- Self-enforcing compliance tests now prevent future drift in rate limit rules

### Technical Notes

- Registry pattern follows same self-enforcing strategy as F8.1 Provider Registry and F7.7 Domain Events Registry
- Existing registry in `src/infrastructure/rate_limit/config.py` now has comprehensive validation
- Tests validate 25 endpoint patterns across 5 scopes (IP, USER, USER_PROVIDER, GLOBAL, plus composite rules)

## [1.6.0] - 2025-12-31

### Added

- **F8.1**: Provider Integration Registry (Registry Pattern for Providers)
  - **Registry Structure**: Created `src/domain/providers/registry.py` as single source of truth for all 3 providers (Schwab, Alpaca, Chase)
  - **ProviderMetadata Dataclass**: Catalog with slug, display_name, category, auth_type, capabilities, and required_settings
  - **Registry Enums**: `ProviderCategory` (6 types: BROKERAGE, BANK, CRYPTO, RETIREMENT, INVESTMENT, OTHER) and `ProviderAuthType` (5 types: OAUTH, API_KEY, FILE_IMPORT, LINK_TOKEN, CERTIFICATE)
  - **Helper Functions**: 5 registry helpers (`get_provider_metadata`, `get_all_provider_slugs`, `get_oauth_providers`, `get_providers_by_category`, `get_statistics`)
  - **Container Integration**: Registry-driven validation and OAuth filtering (removed manual `OAUTH_PROVIDERS` set)
  - **Self-Enforcing Tests**: 19 compliance tests in `test_provider_registry_compliance.py` verify registry completeness
  - **Zero Drift**: Registry prevents drift (discovered Alpaca missing from manual `OAUTH_PROVIDERS` set during implementation)
  - **Benefits**: Single entry point for providers, centralized settings validation, auto-wiring for OAuth callbacks, 30% code reduction in container
  - Total test count increased from 2,190 to 2,208 tests (+18)
  - Registry module coverage: 100%

### Changed

- **Container Refactored**: `src/core/container/providers.py` now uses registry for:
  - Provider lookup validation (`get_provider_metadata()` before instantiation)
  - Settings validation (uses `metadata.required_settings`)
  - OAuth filtering (`get_oauth_providers()` replaces manual set)
  - Error messages (automatically list all supported providers)
- Overall coverage maintained at 88%

### Documentation

- Created `docs/architecture/provider-registry-architecture.md` (761 lines) - Provider Registry pattern architecture with 7 sections: Overview, Registry Structure, Current Providers, Adding New Providers, Helper Functions, Testing, Future Enhancements
- Updated `docs/guides/adding-new-providers.md` - Added Phase 0: Provider Registry (prerequisites before implementation)
- Updated `docs/architecture/provider-integration-architecture.md` - Added registry integration references and updated container examples
- Updated `docs/architecture/provider-domain-model.md` - Updated metadata timestamp
- Updated `docs/index.md` - Added Provider Registry reference under Domain Models section
- Updated `mkdocs.yml` - Added provider-registry-architecture.md to navigation

### Technical Notes

- Registry pattern follows same metadata-driven auto-wiring strategy as F7.7 Domain Events Registry
- No strict mode needed: Provider lookup is synchronous and fails fast (ValueError) unlike events which are fire-and-forget
- Adding new provider now requires: (1) Add to registry, (2) Tests verify completeness, (3) Add container factory case

## [1.5.2] - 2025-12-30

### Documentation

- **Core Architecture Documentation Completion**
  - Created `docs/architecture/hexagonal-architecture.md` (1,451 lines) - Complete hexagonal architecture theory including dependency rule, layer boundaries, ports & adapters pattern, benefits vs monolithic architecture, testing strategies, and integration with CQRS/DDD/Protocol patterns
  - Created `docs/architecture/protocol-based-architecture.md` (1,340 lines) - Comprehensive Protocol pattern guide covering structural vs nominal typing, why Protocol over ABC, Protocol implementations across Dashtam (repositories, services, providers), testing with Protocols, mypy type checking, common pitfalls and solutions
  - Created `docs/architecture/domain-driven-design-architecture.md` (1,268 lines) - Pragmatic DDD philosophy including what "pragmatic" means for Dashtam, DDD patterns used (entities, value objects, domain events, repositories), DDD patterns NOT used and why, integration with hexagonal/CQRS/Protocol/Event Registry, when to emit domain events, entity vs value object decision tree, domain vs application services boundary
  - Updated `docs/architecture/directory-structure.md` - Synchronized with v1.5.1 state including modularized container structure, complete event registry (69 events), and updated schemas section (3 new schema files)
  - Updated `docs/index.md` - Reorganized "Core Architecture" section to highlight 5 core architectures: Hexagonal, Protocol-Based, Domain-Driven Design, CQRS, Event Registry (updated last modified: 2025-12-30)
  - Updated `mkdocs.yml` - Added 3 new architecture docs to navigation in alphabetical order
  - Updated `WARP.md` Section 21 (Key Technical Decisions) - Added cross-references to new architecture docs with explanations (updated last modified: 2025-12-30)

### Changed

- Total architecture documentation now covers 5 core architectural patterns with comprehensive standalone docs for each
- All new architecture docs follow Dashtam documentation patterns: Overview with Purpose/Problem/Solution, horizontal rules between sections, Mermaid diagrams, real code examples, references to related docs, metadata at bottom

## [1.5.1] - 2025-12-28

### Added

- **Auto-Generated API Reference Documentation**
  - Implemented `mkdocs-gen-files` plugin for automatic module discovery
  - Implemented `mkdocs-literate-nav` plugin for auto-generated navigation
  - Created `docs/gen_ref_pages.py` script that auto-discovers all Python modules in `src/`
  - Auto-generates complete API reference from Google-style docstrings (zero maintenance)
  - Build time: ~15 seconds for complete API documentation
  - Added "Code Reference" navigation section in MkDocs
- **Release Management Guide**
  - Created comprehensive `docs/guides/release-management.md` (686 lines)
  - Git Flow workflow with mermaid visualization
  - Semantic versioning decision tree (MAJOR/MINOR/PATCH)
  - Complete 10-step release checklist
  - Tagging strategy and GitHub Releases relationship
  - CHANGELOG management guidelines
  - Sync strategy to prevent version drift
  - Troubleshooting section with common issues
  - Real examples from Dashtam history
- **Smart CI/CD Warning Filtering**
  - GitHub Actions: Intelligent filtering of griffe/autorefs warnings
  - Makefile `verify`: Smart filtering in Step 7 (docs build)
  - New `make ci-docs` command matching GitHub Actions behavior
  - Fail CI only on actual issues (broken links, missing pages)
  - Ignore documented false positives (griffe type inference, autorefs strings)

### Fixed

- Added 8 missing `__init__.py` files for proper Python package structure:
  - `src/application/commands/handlers/__init__.py`
  - `src/application/queries/handlers/__init__.py`
  - `src/application/services/__init__.py`
  - `src/infrastructure/external/__init__.py`
  - `src/infrastructure/logging/__init__.py`
  - `src/infrastructure/providers/__init__.py`
  - `src/infrastructure/rate_limit/lua_scripts/__init__.py`
  - `src/presentation/routers/api/middleware/__init__.py`

### Documentation

- Created `.griffe.yml` with comprehensive explanation of griffe warnings (62 lines)
  - Documents why "No type or annotation" warnings are false positives
  - All functions have proper return types (mypy strict mode enforces)
  - Griffe can't infer types from bare Result/Failure returns
- Updated `docs/index.md` with Release Management section
- Updated Makefile with detailed documentation build comments
- Added auto-generated reference to `mkdocs.yml` navigation

### Changed

- Documentation now includes both manual docs and auto-generated API reference
- CI/CD workflows consistently handle griffe warnings across all environments
- Local `make verify` and GitHub Actions CI behavior now matches

## [1.5.0] - 2025-12-28

### Added

- **F7.7**: Domain Events Compliance Audit & Event Registry Pattern
  - **Event Registry Pattern**: Created `src/domain/events/registry.py` as single source of truth for all 69 domain events
  - **EventMetadata Dataclass**: Catalog with event_class, category, workflow, phase, and handler requirements
  - **Automated Container Wiring**: Registry-driven subscription replaced 500+ lines of manual wiring (~71% code reduction)
  - **Self-Enforcing Tests**: Validation tests (`test_domain_events_registry_compliance.py`) fail if handlers or AuditAction enums missing
  - **Data Sync Events**: Added 12 new events (AccountSync, TransactionSync, HoldingsSync, FileImport) with 3-state ATTEMPT → OUTCOME pattern
  - **Handler Methods**: Added 24 handler methods (12 events × 2 handlers: LoggingEventHandler + AuditEventHandler)
  - **AuditAction Enums**: Added 12 new audit actions for data sync workflows
  - **Container Auto-Wiring**: Registry automatically wires all 143 subscriptions (69 events × 2-3 handlers each)
  - **Gap Detection**: Registry-driven tests prevent future drift (can't merge if handlers missing)
  - **Process Enforcement**: Adding new events requires: (1) Define event, (2) Add to registry, (3) Tests tell you what's missing, (4) Add handlers, (5) Tests pass
  - Added 6 new test files with comprehensive registry compliance validation
  - Total test count increased from 2,100 to 2,190 tests (+90)
  - Updated WARP.md: Streamlined from 1,789 lines to 1,355 lines (removed ~430 lines of bloated roadmap history)

### Changed

- **Event System Strict Mode**: Changed `events_strict_mode` default from `False` to `True` for production safety
  - Dev environment: `EVENTS_STRICT_MODE=false` (flexibility for WIP)
  - Test environment: `EVENTS_STRICT_MODE=true` (catch missing handlers early)
  - CI environment: `EVENTS_STRICT_MODE=true` (enforce before merge)
  - Strict mode fails fast at startup if required event handlers are missing
- **Dynamic Test Validation**: Replaced hardcoded event count (84) with dynamic registry-based verification
  - `test_enum_has_sufficient_coverage()` now validates AuditAction has ≥ events requiring audit
  - Self-maintaining (no manual updates when adding events)
- Overall coverage increased from 87% to 88%
- Total events: 69 (28 auth, 6 authz, 9 provider, 12 data sync, 8 session, 3 rate limit, 3 operational)
- Total subscriptions: 143 (all automatically wired via registry)
- Total workflows: 23 (17 critical with 3-state pattern, 6 operational single-state)

### Documentation

- Created `docs/architecture/registry-pattern-architecture.md` (813 lines) - Event Registry pattern architecture
- Updated `docs/architecture/domain-events-architecture.md` with registry pattern and final counts
- Streamlined `WARP.md` from 1,789 lines to 1,355 lines:
  - Removed detailed phase completion history (now in CHANGELOG)
  - Added Section 6: Event Registry Pattern (Single Source of Truth)
  - Added "Why Event Registry Pattern?" to Key Technical Decisions

### Fixed

- Fixed session event handler attribute names (revoked_by → revoked_by_user, count → session_count, etc.)
- Fixed registry type annotation (`dict` → `dict[str, int | dict[str, int]]`)
- Removed interactive prompt from `make verify` for CI compatibility

## [1.4.0] - 2025-12-27

### Added

- **F7.2**: Chase File Import Provider (First File Import provider)
  - Implemented `ChaseFileProvider` adapter with auth-agnostic `ProviderProtocol`
  - **File Parsers**: QFX/OFX parser (ofxparse library), CSV parser (checking + credit card formats)
  - **ImportFromFile Command**: New command handler for file-based transaction imports
  - **Features**: Auto account creation from file data, duplicate detection by FITID, balance snapshots
  - **Credential Type**: FILE_IMPORT (credentials passed as file content, not stored)
  - **Supported Formats**: QFX/OFX (preferred), CSV (checking/credit card)
  - **API Endpoint**: `POST /api/v1/imports` with multipart form data
  - Added 80+ tests covering parsers, provider, handler, API endpoints
  - Added database seed for Chase provider with `credential_type: file_import`
  - Added container factory registration for Chase provider

### Documentation

- Created `docs/guides/chase-file-import.md` - User guide for Chase file imports
- Updated `docs/guides/adding-new-providers.md` with Phase 3c: File Import Provider section
- Updated `docs/architecture/provider-integration-architecture.md` with all three provider types:
  - Provider Categories table (OAuth, API Key, File Import)
  - FILE_IMPORT credential type documentation
  - Updated file structure showing all 3 provider types
  - Complete comparison of authentication patterns

### Changed

- Total test count increased from 2,079 to 2,100+ tests (+80)
- Overall coverage maintained at 87%

### Technical Notes

- Domain events for file import operations (FileImportAttempted/Succeeded/Failed) deferred to F7.7
- Infrastructure layer logging via structlog follows existing provider patterns

## [1.3.0] - 2025-12-26

### Added

- **F7.1**: Alpaca Provider Integration
  - Implemented `AlpacaProvider` adapter with auth-agnostic `ProviderProtocol` (first API Key provider)
  - Added `AlpacaAccountsAPI` client for account and positions endpoints
  - Added `AlpacaTransactionsAPI` client for activities endpoint
  - Added mappers: `AlpacaAccountMapper`, `AlpacaHoldingMapper`, `AlpacaTransactionMapper`
  - **Authentication**: API Key headers (`APCA-API-KEY-ID`, `APCA-API-SECRET-KEY`) - no OAuth flow
  - **Environment Support**: Paper (`paper-api.alpaca.markets`) and Live (`api.alpaca.markets`)
  - **Features**: Account sync, holdings/positions sync, transaction/activities sync
  - **Credential Structure**: `{"api_key": "...", "api_secret": "..."}`
  - Added 101 tests with 100% coverage on all Alpaca provider code
  - Added database seed for Alpaca provider with `credential_type: api_key`
  - Added container factory registration for Alpaca provider

### Documentation

- Added "Phase 3b: API-Key Provider Implementation" section to `adding-new-providers.md`
  - Key differences table comparing OAuth vs API-Key providers
  - Complete Alpaca provider example with code snippets
  - API client authentication pattern with custom headers
  - Container registration pattern for API-Key providers
  - Database seed configuration for non-OAuth credential types

### Changed

- Total test count increased from 1,978 to 2,079 tests (+101)
- Overall coverage maintained at 87%+

## [1.2.1] - 2025-12-26

### Changed

- **Auth-Agnostic Provider Protocol Refactor** (Hotfix)
  - Refactored `ProviderProtocol` to be auth-agnostic: `fetch_*` methods now accept `credentials: dict[str, Any]` instead of `access_token: str`
  - Added `OAuthProviderProtocol` extending base protocol with OAuth-specific methods (`exchange_code_for_tokens`, `refresh_access_token`)
  - Added `is_oauth_provider()` TypeGuard function for runtime capability checking with type narrowing
  - Updated `SchwabProvider` to extract `access_token` internally from credentials dict
  - Updated sync handlers (`SyncAccountsHandler`, `SyncTransactionsHandler`, `SyncHoldingsHandler`) to pass full credentials dict
  - Updated OAuth callbacks and token refresh endpoints to use `get_provider()` + `is_oauth_provider()` pattern
  - Replaced `get_oauth_provider()` export with `is_oauth_provider()` in container
  - This change enables future providers with different auth mechanisms (API Key, Certificate, etc.) to use the same interface

### Documentation

- Updated `docs/architecture/provider-integration-architecture.md` with auth-agnostic design:
  - New Decision 1: Auth-Agnostic Provider Protocol (base + OAuth extension)
  - New Decision 2: Factory with Capability Checking (TypeGuard pattern)
  - Updated code examples showing credentials dict pattern
  - Added usage patterns for sync handlers vs OAuth callbacks

## [1.2.0] - 2025-12-26

### Added

- **F7.4**: Provider-Specific Entities - Holdings Support
  - Added `Holding` domain entity with cost basis, market value, unrealized gain/loss tracking
  - Added `AssetType` enum (STOCK, ETF, MUTUAL_FUND, BOND, OPTION, CRYPTO, CASH, OTHER)
  - Added `HoldingRepository` protocol and PostgreSQL implementation
  - Added `ProviderHoldingData` for provider-agnostic holding mapping
  - Added Schwab holdings API client (`SchwabHoldingsAPI`) and mapper (`SchwabHoldingMapper`)
  - Added `fetch_holdings()` method to `ProviderProtocol`
  - Added CQRS handlers: `SyncHoldingsHandler`, `GetHoldingHandler`, `ListHoldingsHandler`, `ListHoldingsByAccountHandler`
  - Added Holdings API endpoints: `GET /holdings`, `GET /accounts/{id}/holdings`, `POST /accounts/{id}/holdings/syncs`
  - Added 120+ tests for holdings functionality (domain, repository, handlers, API)

- **F7.5**: Balance Tracking
  - Added `BalanceSnapshot` domain entity (frozen/immutable) for point-in-time balance history
  - Added `SnapshotSource` enum (ACCOUNT_SYNC, HOLDINGS_SYNC, MANUAL_ENTRY, SCHEDULED_SYNC)
  - Added `BalanceSnapshotRepository` protocol and PostgreSQL implementation
  - Added automatic balance capture during account and holdings sync operations
  - Added CQRS handlers: `GetLatestBalanceSnapshotHandler`, `ListBalanceSnapshotsHandler`, `GetBalanceHistoryHandler`
  - Added Balance Snapshots API endpoints: `GET /balance-snapshots`, `GET /accounts/{id}/balance-history`, `GET /accounts/{id}/balance-snapshots`
  - Added 80+ tests for balance tracking functionality

- **Provider Capabilities System**
  - Added capability flags to `ProviderType` enum: `HAS_HOLDINGS`, `HAS_BALANCE_HISTORY`
  - Updated Schwab provider with `HAS_HOLDINGS=True`, `HAS_BALANCE_HISTORY=True`
  - Provider capabilities checked before sync operations

### Changed

- Updated `ProviderProtocol` with `fetch_holdings()` method signature
- Updated Account entity with optional `holdings_value` and `cash_value` fields
- Updated sync handlers to capture balance snapshots automatically
- Total test count increased from 1,746 to 1,978 tests (+232)
- Overall coverage increased from 86% to 87%

### Documentation

- Created `docs/architecture/holding-domain-model.md` - Holding entity architecture (339 lines)
- Created `docs/architecture/balance-tracking-architecture.md` - Balance snapshot architecture (429 lines)
- Created `docs/api/holdings-api.md` - Holdings API reference (263 lines)
- Created `docs/api/balance-snapshots-api.md` - Balance Snapshots API reference (277 lines)
- Updated `docs/guides/adding-new-providers.md` with Phase 9 (Holdings) and Phase 10 (Balance Tracking)
- Updated `docs/architecture/provider-integration-architecture.md` with holdings support
- Updated `docs/index.md` with new domain models and guides
- Updated `mkdocs.yml` with all new documentation files
- Added comprehensive Provider Integration Guide (`docs/guides/adding-new-providers.md`)
  - 10-phase step-by-step process for adding new financial providers
  - Complete code templates for provider adapters, API clients, and mappers
  - Testing requirements with coverage targets (90%+ provider, 95%+ mappers)
  - Files checklist: 15 must-create, 9 must-modify
  - Container registration and database seeding patterns
  - Quality verification steps and troubleshooting guidance
- Replaced Plaid references with Chase throughout documentation and code comments (27 files)
  - Updated docstrings, comments, and examples in source files
  - Updated environment template variable names (`PLAID_*` → `CHASE_*`)
  - Updated architecture docs and API guides to reference Chase/Fidelity as future providers

## [1.1.0] - 2025-12-25

### Added

- **F6.15**: IP Geolocation Integration with MaxMind GeoIP2
  - Integrated MaxMind GeoLite2-City database for IP-to-location resolution
  - Added `IPLocationEnricher` infrastructure adapter with lazy-loaded database reader
  - Session metadata now includes geographic information (city, country, coordinates) for public IPs
  - **Features**: City-level geolocation, fail-open behavior, private IP detection, lazy loading
  - **Performance**: ~10-20ms database lookups (in-memory file), first lookup loads database
  - **Configuration**: `GEOIP_DB_PATH` setting for database file path (can be disabled by setting to None)
  - **Database**: GeoLite2-City.mmdb (~60MB, mounted via Docker volume at `/app/data/geoip/`)
  - Added 15 comprehensive integration tests (test_location_enricher.py) covering:
    - Private IP detection (no lookup for RFC 1918 addresses)
    - Public IP lookup with real database (skips if database not available)
    - Location string formatting ("City, CC" or "CC" only)
    - Fail-open error handling (missing database, invalid IPs, database errors)
    - Lazy loading behavior and database initialization
    - Protocol compliance (LocationEnrichmentResult structure)
  - Updated both enrichers (device + location) to use LoggerProtocol dependency injection for architecture consistency
  - Added container wiring with logger injection for enrichers in `get_create_session_handler`
  - Updated session management documentation with GeoIP2 setup guide (9 new sections, 135 lines)
  - **Documentation**: Setup instructions, database download process, configuration options, troubleshooting guide
  - Total test count increased from 1,731 to 1,746 tests (+15)
  - Overall coverage maintained at 86%
  - All quality checks passing: 1,744 tests (19 skipped), 86% coverage, zero lint violations

### Changed

- Refactored `device_enricher.py` and `location_enricher.py` to use `LoggerProtocol` injection instead of raw Python logger
- Updated `auth_handlers.py` container to inject logger into both enrichers
- Added latitude and longitude extraction to location enricher (populated from GeoIP2 response)
- Updated `session-management-usage.md` with section renumbering (added section 9 for GeoIP2, shifted others)
- Updated documentation "Last Updated" date to 2025-12-25

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
- All tests passing, coverage maintained

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
- **F6.6**: Test cleanup and coverage analysis
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

[Unreleased]: https://github.com/faiyaz7283/Dashtam/compare/v1.5.1...HEAD
[1.5.1]: https://github.com/faiyaz7283/Dashtam/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/faiyaz7283/Dashtam/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/faiyaz7283/Dashtam/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/faiyaz7283/Dashtam/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/faiyaz7283/Dashtam/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/faiyaz7283/Dashtam/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/faiyaz7283/Dashtam/compare/v1.0.3...v1.1.0
[1.0.3]: https://github.com/faiyaz7283/Dashtam/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/faiyaz7283/Dashtam/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/faiyaz7283/Dashtam/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/faiyaz7283/Dashtam/releases/tag/v1.0.0
