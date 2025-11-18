# Dashtam Documentation

Welcome to the Dashtam documentation. Dashtam is a secure, modern
financial data aggregation platform built with clean architecture
principles from the ground up.

## Architecture Documentation

### Core Architecture

- **[Directory Structure](architecture/directory-structure.md)** -
  Hexagonal architecture organization, layer responsibilities,
  file naming conventions
- **[Dependency Injection](architecture/dependency-injection-architecture.md)** -
  Centralized container pattern for managing application and
  request-scoped dependencies
- **[Error Handling](architecture/error-handling-architecture.md)** -
  Railway-oriented programming with Result types, RFC 7807 compliance
- **[Testing Architecture](architecture/testing-architecture.md)** -
  Test pyramid, fixtures, mocking strategies for centralized DI

### Infrastructure Components

- **[Audit Trail](architecture/audit-trail-architecture.md)** -
  Immutable audit logging with ATTEMPT → OUTCOME semantics,
  PCI-DSS/SOC 2/GDPR compliance
- **[Database Architecture](architecture/database-architecture.md)** -
  PostgreSQL with async SQLAlchemy, session management, Alembic migrations
- **[Cache Architecture](architecture/cache-architecture.md)** -
  Redis implementation with connection pooling, TTL strategies,
  fail-open patterns
- **[Domain Events](architecture/domain-events-architecture.md)** -
  Event-driven architecture with in-memory event bus, fail-open behavior,
  pragmatic DDD approach (events for critical workflows only)
- **[Secrets Management](architecture/secrets-management-architecture.md)** -
  Multi-tier secrets (local .env → AWS Secrets Manager), read-only protocol
- **[Structured Logging](architecture/structured-logging-architecture.md)** -
  JSON structured logs with contextual information for observability

## Project Overview

### Core Architectural Principles

**Hexagonal Architecture**:

- **Domain at center**: Pure business logic with zero infrastructure
  dependencies
- **Infrastructure at edges**: Adapters implement domain protocols
- **Dependency inversion**: All dependencies point inward toward domain

**CQRS Pattern**:

- **Commands**: Write operations that change state
- **Queries**: Read operations that fetch data (can cache)
- **Handlers**: Separate command and query handlers from the start

**Domain-Driven Design**:

- **Entities**: Mutable objects with identity (User, Account, Transaction)
- **Value Objects**: Immutable values (Email, Money, DateRange)
- **Domain Events**: Critical workflows emit events
  (UserRegistered, TokenRefreshFailed)
- **Protocols**: Domain defines what it needs (Ports),
  infrastructure implements (Adapters)

**Protocol-Based Design**:

- Use Python `Protocol` for all interfaces (structural typing)
- No inheritance required for implementations
- Easy to test (mock protocols, not implementations)
- Framework-independent domain layer

### Technology Stack

**Backend**:

- **Language**: Python 3.13+ (modern type hints, match/case, slots)
- **Framework**: FastAPI (async, high performance)
- **Validation**: Pydantic v2 (strict mode)
- **Package Manager**: UV 0.8.22+ (fast, modern, NOT pip)

**Infrastructure**:

- **Database**: PostgreSQL 17.6 (async with asyncpg driver)
- **ORM**: SQLAlchemy 2.0+ (async, declarative)
- **Migrations**: Alembic (async mode)
- **Cache**: Redis 8.2.1 (async with redis-py)
- **Secrets**: Multi-tier (local .env → AWS Secrets Manager)

**Development Environment**:

- **Containers**: Docker Compose v2 (multi-environment)
- **Reverse Proxy**: Traefik 3.0+ (automatic SSL with mkcert)
- **Domains**: `https://dashtam.local` (dev),
  `https://test.dashtam.local` (test)

**Quality Assurance**:

- **Testing**: pytest + pytest-asyncio (85%+ coverage target)
- **Linting**: ruff (fast, all-in-one linter/formatter)
- **Type Checking**: mypy (strict mode)
- **CI/CD**: GitHub Actions with Codecov

### Design Patterns

**Dependency Injection**:

- Centralized container in `src/core/container.py`
- App-scoped singletons (cache, secrets, database)
- Request-scoped dependencies (sessions, handlers)
- Easy to mock for testing

**Error Handling**:

- Result types (Success/Failure) - no exceptions in domain
- Railway-oriented programming
- RFC 7807 Problem Details for HTTP APIs
- ErrorCode enums for machine-readable errors

**Testing Strategy**:

- Unit tests: Mock container dependencies (60%)
- Integration tests: Real infrastructure (30%)
- API tests: Complete request/response flows (10%)
- No unit tests for infrastructure adapters

## Getting Started

### Quick Start

```bash
# Clone repository
git clone https://github.com/faiyaz7283/Dashtam.git
cd Dashtam

# Start Traefik (reverse proxy)
make traefik-up

# Start development environment
make dev-up

# View logs
make dev-logs

# Run tests
make test
```

### Development Workflow

1. **Read feature requirements** from roadmap
2. **Follow development checklist** (`~/starter/development-checklist.md`)
3. **Plan implementation** with TODO list
4. **Get user approval** before coding
5. **Implement feature** following architecture patterns
6. **Test incrementally** (unit → integration → API)
7. **Document changes** (architecture docs, API flows)
8. **Commit with conventional commits** (`feat:`, `fix:`, `docs:`)

## Development Guides

- **[Audit Usage Patterns](guides/audit-usage-patterns.md)** -
  Complete guide with copy-pasteable examples for registration,
  login, provider connection, data access audit patterns
- **[Domain Events Usage](guides/domain-events-usage.md)** -
  Complete guide for using domain events - when to use, event naming,
  defining events, creating handlers, testing, anti-patterns

### Architecture Documentation Status

✅ **Complete**:

- Directory structure and layer organization
- Dependency injection container pattern
- Error handling with Result types
- Testing architecture with container mocking
- Audit trail with semantic accuracy (ATTEMPT → OUTCOME)
- Database setup with async SQLAlchemy
- Cache implementation with Redis
- Domain events with in-memory event bus
- Secrets management multi-tier strategy
- Structured logging with JSON output

🚧 **In Progress**:

- Audit semantic accuracy implementation (Phase 6/9)
- Feature implementation (F0.9 Audit Trail)
- Domain models and repositories

📋 **Planned**:

- Authentication & authorization
- Financial provider integrations
- Transaction aggregation

## Contributing

See `~/starter/development-checklist.md` for the complete feature development workflow.

**Key principles**:

- Always follow hexagonal architecture
- Use centralized dependency injection
- Return Result types (not exceptions)
- Test at the right level (unit vs integration)
- Document architecture decisions
- 100% REST compliance for API endpoints

---

**Created**: 2025-11-13  | **Last Updated**: 2025-11-17
