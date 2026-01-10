# Dashtam Documentation

Dashtam is a **secure, modern financial data aggregation platform** built from the ground up with clean architecture principles. It demonstrates production-grade hexagonal architecture, protocol-based design, and pragmatic domain-driven design in Python.

## Core Architecture

Dashtam is built on six foundational architectural pillars:

**[Hexagonal Architecture](architecture/hexagonal.md)**
: Domain at center with zero framework dependencies. Infrastructure adapts to domain through protocols (ports & adapters).

**[Protocol-Based Design](architecture/protocols.md)**
: Structural typing with Python `Protocol`. No inheritance required. Framework-independent interfaces.

**[CQRS Pattern](architecture/cqrs.md)**
: Separate command handlers (write) from query handlers (read). Clear separation of concerns.

**[Domain-Driven Design](architecture/domain-driven-design.md)**
: Pragmatic DDD with entities, value objects, and domain events for critical workflows only.

**[Registry Pattern](architecture/registry.md)**
: Metadata-driven auto-wiring eliminates manual drift. Single source of truth with self-enforcing tests. **5 implementations**: Domain Events, Provider Integration, Rate Limits, Validation Rules, Route Metadata.

**[Dependency Injection](architecture/dependency-injection.md)**
: Centralized container with app-scoped singletons and request-scoped dependencies. Protocol-first design.

## Documentation Structure

**Architecture** (31 docs)
: Deep dives into architectural patterns, design decisions, and system components. Covers infrastructure (database, cache, audit), security (auth, authorization, rate limiting), and domain models (accounts, transactions, holdings).

**API Reference** (7 docs)
: REST API documentation for authentication, account operations, provider connections, transactions, holdings, balance snapshots, and admin endpoints.

**Guides** (16 docs)
: Practical how-to guides for common tasks. Includes release management, adding providers, error handling, domain events, and component usage patterns.

**Code Reference**
: Auto-generated API documentation from Python docstrings (Google style).

## Key Features

**Clean Architecture**
: 100% hexagonal with protocol-based ports & adapters. Domain layer has zero framework dependencies.

**Production-Ready Security**
: JWT + opaque refresh tokens, Casbin RBAC, token bucket rate limiting, audit trail (PCI-DSS compliant).

**Multi-Provider Integration**
: OAuth (Schwab), API Key (Alpaca), File Import (Chase). Extensible provider registry pattern.

**Modern Python**
: Python 3.13+, FastAPI, Pydantic v2, async/await, Result types, Protocol-based design.

**Comprehensive Testing**
: **2,253 tests** with **88% coverage**. Unit tests for domain/application, integration tests for infrastructure, API tests for endpoints.

## Technology Stack

**Backend**: Python 3.13 | FastAPI | Pydantic v2 | UV package manager

**Data**: PostgreSQL 17.6 (async) | SQLAlchemy 2.0 | Alembic | Redis 8.2.1

**Development**: Docker Compose | Traefik (HTTPS) | pytest | ruff | mypy

**CI/CD**: GitHub Actions | Codecov | Self-hosted runners

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

1. **Create feature branch** from `development`
2. **Research architecture** - Identify layers, patterns, dependencies
3. **Plan implementation** - Create TODO list, get approval
4. **Implement feature** - Follow hexagonal architecture, CQRS, protocols
5. **Test incrementally** - Unit → integration → API (85%+ coverage target)
6. **Verify quality** - `make lint && make format && make type-check`
7. **Document changes** - Update architecture docs, add usage guides
8. **Commit with conventional commits** - `feat:`, `fix:`, `docs:`
9. **Create pull request** to `development` branch

## Essential Reading

New to Dashtam? Start with these key documents:

1. **[Hexagonal Architecture](architecture/hexagonal.md)** - Understand the core architectural pattern
2. **[Protocol-Based Architecture](architecture/protocols.md)** - Learn why we use Protocol over ABC
3. **[Error Handling Guide](guides/error-handling.md)** - RFC 7807 API errors and Result types
4. **[Registry Pattern](architecture/registry.md)** - How we eliminate manual drift
5. **[Release Management](guides/releases.md)** - Complete development workflow

## Development Workflow

1. Create feature branch from `development`
2. Research & plan (identify layers, create TODO list)
3. Implement with tests (85%+ coverage target)
4. Verify quality: `make verify` (tests, lint, format, type-check)
5. Create PR to `development` branch

**Core principles**: Hexagonal architecture | Protocol-based design | Result types (no exceptions) | 100% REST compliance

---

**Created**: 2025-11-13 | **Last Updated**: 2025-12-31
