# Dashtam

> A secure financial data aggregation API that provides unified access to multiple financial institutions, designed using clean architecture principles for scalability and maintainability

[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://faiyaz7283.github.io/Dashtam/) [![Test Suite](https://github.com/faiyaz7283/Dashtam/workflows/Test%20Suite/badge.svg)](https://github.com/faiyaz7283/Dashtam/actions) [![codecov](https://codecov.io/gh/faiyaz7283/Dashtam/branch/development/graph/badge.svg)](https://codecov.io/gh/faiyaz7283/Dashtam) [![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.118+-green.svg)](https://fastapi.tiangolo.com) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## What is Dashtam?

Dashtam is a **financial data aggregation API** that provides secure, unified access to accounts and transactions across multiple financial institutions. Built with hexagonal architecture and domain-driven design, Dashtam prioritizes security, maintainability, and compliance.

### Core Principles

**Architecture-First Development**:

- **Hexagonal Architecture** - Domain logic isolated from infrastructure concerns
- **CQRS Pattern** - Separate read and write operations for optimal performance
- **Domain-Driven Design** - Rich domain models with business logic where it belongs
- **Protocol-Based Design** - Structural typing with Python `Protocol` for testability

**Document-Driven Development**:

- Every architectural decision documented before implementation
- Comprehensive guides for authentication, authorization, audit trails, events
- Architecture documents reviewed and approved before coding begins

**Security & Compliance**:

- **PCI-DSS** compliant audit trails with immutable logging
- **SOC 2** controls for access management and encryption
- **GDPR** ready with data retention and audit capabilities
- **Bank-grade security** - AES-256 encryption, bcrypt hashing, JWT authentication

**Standards & Quality**:

- **100% REST Compliance** - Non-negotiable RESTful API design (no controller-style endpoints)
- **Type Safety** - Strict mypy checking, modern Python 3.13+ type hints
- **Test Coverage** - Comprehensive test suite with unit, integration, and API tests
- **CI/CD Pipeline** - Automated testing, linting, and type checking on every commit

## Documentation

📚 **[Complete Documentation](https://faiyaz7283.github.io/Dashtam/)** - Architecture guides, API reference, development workflows

**API Documentation**:

- **[Swagger UI](https://dashtam.local/docs)** - Interactive API exploration and testing
- **[ReDoc](https://dashtam.local/redoc)** - Clean, readable API documentation
- **[MkDocs](https://docs.dashtam.local/Dashtam/)** - Architecture, guides, and design decisions

**Key Documentation**:

- [Architecture Overview](https://faiyaz7283.github.io/Dashtam/architecture/directory-structure/) - Hexagonal architecture, layers, patterns
- [Authentication](https://faiyaz7283.github.io/Dashtam/architecture/authentication-architecture/) - JWT + opaque refresh tokens, multi-device sessions
- [Authorization](https://faiyaz7283.github.io/Dashtam/architecture/authorization-architecture/) - Casbin RBAC with role hierarchy
- [Audit Trail](https://faiyaz7283.github.io/Dashtam/architecture/audit-trail-architecture/) - PCI-DSS compliant immutable logging
- [Domain Events](https://faiyaz7283.github.io/Dashtam/architecture/domain-events-architecture/) - Event-driven workflows with 3-state pattern
- [Error Handling](https://faiyaz7283.github.io/Dashtam/architecture/error-handling-architecture/) - Railway-oriented programming with Result types

## Quick Start

### Prerequisites

- **Docker** and Docker Compose v2.0+
- **Make** (optional, for convenience commands)
- **Python 3** (for key generation during setup)

> **No Python packages required** - All application code runs in Docker containers.

### First-Time Setup

Complete zero-to-working Dashtam in 5 steps:

#### Step 1: Add Local Domains

Add Dashtam domains to `/etc/hosts`:

```bash
sudo sh -c 'echo "127.0.0.1 dashtam.local" >> /etc/hosts'
sudo sh -c 'echo "127.0.0.1 test.dashtam.local" >> /etc/hosts'
sudo sh -c 'echo "127.0.0.1 docs.dashtam.local" >> /etc/hosts'
```

**Verify**:

```bash
grep "dashtam.local" /etc/hosts
# Should show: 127.0.0.1 dashtam.local
#              127.0.0.1 test.dashtam.local
#              127.0.0.1 docs.dashtam.local
```

#### Step 2: Start Traefik Reverse Proxy

Dashtam requires Traefik for HTTPS routing. Use the shared Traefik setup:

```bash
# Clone Docker services setup (SSH)
git clone git@github.com:faiyazhaider/docker-services.git ~/docker-services
cd ~/docker-services

# Start Traefik
make traefik-up
```

**If you already have the docker-services repo**:

```bash
cd ~/docker-services
make traefik-up
```

**Verify Traefik is running**:

```bash
cd -  # Return to previous directory (or cd ~/Dashtam)
make check
# Should show: ✅ Traefik is running
```

> **Note**: The Traefik setup creates the `traefik-public` network required by Dashtam.

#### Step 3: Clone Repository

```bash
git clone https://github.com/faiyazhaider/Dashtam.git
cd Dashtam
```

#### Step 4: Run Setup (Idempotent)

Generates environment files and cryptographic keys:

```bash
make setup
```

This will:

- ✅ Create `env/.env.dev` from `env/.env.dev.example`
- ✅ Generate `SECRET_KEY` (64 chars for JWT signing)
- ✅ Generate `ENCRYPTION_KEY` (32 chars for AES-256-GCM)
- ✅ Verify Traefik is running

**Optional**: Add your Schwab OAuth credentials to `env/.env.dev`:

```bash
# Edit env/.env.dev and set:
SCHWAB_API_KEY=your_api_key_here
SCHWAB_API_SECRET=your_api_secret_here
```

> **Note**: Provider OAuth is optional. You can test auth endpoints without it.

#### Step 5: Start Development Environment

```bash
make dev-up
```

This starts:

- ✅ PostgreSQL 17.6 (port 5432)
- ✅ Redis 8.2.1 (port 6379)
- ✅ FastAPI app (<https://dashtam.local>)
- ✅ Alembic migrations (run automatically)

**Verify it's working**:

```bash
curl -k https://dashtam.local/health
# Should return: {"status":"healthy"}
```

### What's Next?

After successful setup:

1. **Explore API Documentation**:
   - Swagger UI: <https://dashtam.local/docs>
   - ReDoc: <https://dashtam.local/redoc>

2. **Create a Session** (test authentication):

   ```bash
   curl -X POST https://dashtam.local/api/v1/sessions \
     -H "Content-Type: application/json" \
     -d '{"email": "admin@example.com", "password": "admin"}'
   ```

3. **Review Architecture** (understand how it works):
   - Start MkDocs: `make docs-serve`
   - Browse: <https://docs.dashtam.local/Dashtam/>

4. **Run Tests** (verify everything works):

   ```bash
   make test  # All tests with coverage
   ```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| API | <https://dashtam.local> | RESTful API endpoints |
| Swagger UI | <https://dashtam.local/docs> | Interactive API documentation |
| ReDoc | <https://dashtam.local/redoc> | Alternative API reference |
| MkDocs | <https://docs.dashtam.local/Dashtam/> | Architecture documentation |
| Health Check | <https://dashtam.local/health> | Service health status |
| Traefik Dashboard | <http://localhost:8080> | Reverse proxy monitoring |

> **Note**: All API endpoints use `/api/v1/` prefix. Local HTTPS uses Traefik with mkcert certificates.

### Example API Calls

```bash
# Create session (login)
curl -X POST https://dashtam.local/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'

# List accounts (requires authentication)
curl -X GET https://dashtam.local/api/v1/accounts \
  -H "Authorization: Bearer {access_token}"

# Initiate provider OAuth connection
curl -X POST https://dashtam.local/api/v1/providers/schwab/oauth/initiate \
  -H "Authorization: Bearer {access_token}"
```

## Architecture Highlights

### Hexagonal Architecture

```text
┌─────────────────────────────────────────┐
│ Presentation Layer (FastAPI)            │  ← HTTP, REST, Schemas
└──────────────┬──────────────────────────┘
               │ depends on
               ↓
┌─────────────────────────────────────────┐
│ Application Layer (CQRS)                │  ← Commands, Queries, Handlers
└──────────────┬──────────────────────────┘
               │ depends on
               ↓
┌─────────────────────────────────────────┐
│ Domain Layer (Business Logic)           │  ← Entities, Events, Protocols
└─────────────────────────────────────────┘  ← ZERO infrastructure dependencies
               ↑ implements
               │
┌─────────────────────────────────────────┐
│ Infrastructure Layer (Adapters)         │  ← Database, Cache, Providers
└─────────────────────────────────────────┘
```

**Key Patterns**:

- Domain defines **Protocols** (ports), Infrastructure implements **Adapters**
- Application layer orchestrates with **Command/Query** handlers
- Presentation layer is thin, delegates to Application layer
- All dependencies point **inward** toward Domain

### Technology Stack

**Core**:

- **Python 3.13+** - Modern type hints, pattern matching, performance
- **FastAPI** - Async web framework with automatic OpenAPI docs
- **PostgreSQL 17.6** - Primary database with async SQLAlchemy
- **Redis 8.2.1** - Caching and rate limiting
- **UV 0.8.22** - Fast, modern Python package manager (NOT pip)

**Security**:

- **JWT** - Stateless access tokens (15 min expiry)
- **Opaque Refresh Tokens** - Bcrypt hashed, database-backed (30 day expiry)
- **AES-256-GCM** - Provider credential encryption
- **Bcrypt** - Password hashing (12 rounds)
- **Casbin** - Role-based access control (admin > user > readonly)

**Infrastructure**:

- **Docker Compose** - Multi-environment orchestration (dev, test, CI)
- **Traefik** - Reverse proxy with automatic HTTPS
- **Alembic** - Database migrations with async support
- **Structlog** - JSON structured logging for observability

## Security & Compliance

### Security Features

**Authentication & Authorization**:

- ✅ JWT access tokens (15 min expiry) + opaque refresh tokens (30 day expiry)
- ✅ Multi-device session management with metadata tracking
- ✅ Role-based access control with Casbin RBAC (admin > user > readonly)
- ✅ Email verification required before login
- ✅ Account lockout after 5 failed login attempts
- ✅ Emergency token rotation (global + per-user)

**Data Protection**:

- ✅ AES-256-GCM encryption for provider credentials
- ✅ Bcrypt password hashing (12 rounds)
- ✅ Secrets management with multi-tier strategy (local .env → AWS Secrets Manager)
- ✅ TLS/HTTPS required for all endpoints (Traefik with Let's Encrypt)

**Rate Limiting**:

- ✅ Token bucket algorithm with Redis Lua scripts (atomic, no race conditions)
- ✅ Per-endpoint rate limits (e.g., 5 login attempts/min)
- ✅ RFC 6585 compliant headers (X-RateLimit-*, Retry-After)
- ✅ Fail-open strategy (never blocks if Redis fails)

**Audit & Monitoring**:

- ✅ Immutable audit trail with 3-state pattern (ATTEMPT → SUCCEEDED/FAILED)
- ✅ Structured JSON logging with correlation IDs
- ✅ Complete audit history for all provider operations
- ✅ 7-year audit retention (PCI-DSS requirement)

### Compliance

**PCI-DSS** (Payment Card Industry Data Security Standard):

- Immutable audit logs with semantic accuracy (who, what, when, why, outcome)
- 7-year retention for all provider access attempts
- Strong cryptography (AES-256, bcrypt, TLS 1.3)

**SOC 2** (Service Organization Control):

- Role-based access control with audit trails
- Multi-factor authentication ready
- Automated security updates and patching

**GDPR** (General Data Protection Regulation):

- Complete audit trail for data access
- Data retention policies documented
- User consent tracking ready

### Error Handling

**Railway-Oriented Programming**:

- Domain functions return `Result[T, E]` (no exceptions)
- Explicit error handling at every layer
- Type-safe error propagation

**RFC 7807 Problem Details**:

- Standardized error responses for HTTP APIs
- Machine-readable error codes
- Human-readable error messages with context

## Development

### Common Commands

```bash
# Development Environment
make dev-up          # Start all services (app, postgres, redis)
make dev-down        # Stop all services
make dev-logs        # View application logs
make dev-shell       # Open shell in app container
make dev-restart     # Restart all services

# Testing
make test            # Run all tests with coverage report
make test-unit       # Unit tests only (domain, application)
make test-integration # Integration tests (database, cache, APIs)
make test-api        # API endpoint tests

# CI/CD (Local)
make ci-test-local   # Full CI suite (tests + lint + type-check)
make ci-test         # Tests only (matches GitHub Actions)
make ci-lint         # Linting only

# Code Quality
make lint            # Run ruff linter
make format          # Format code with ruff
make type-check      # Run mypy type checking

# Documentation
make docs-serve      # Start MkDocs live preview (https://docs.dashtam.local/Dashtam/)
make docs-build      # Build static documentation (strict mode)
make lint-md FILE=<file> # Lint markdown file

# Database
make migrate         # Apply database migrations
make db-shell        # Open PostgreSQL shell
```

### Local Development

**Environment Files**:

- `env/.env.dev` - Development configuration
- `env/.env.test` - Test configuration
- `env/.env.dev.example` - Template with all available settings

**Key Configuration**:

```bash
# Required for OAuth
SCHWAB_API_KEY=your_api_key_here
SCHWAB_API_SECRET=your_api_secret_here

# Generated by make setup
SECRET_KEY=<jwt-signing-key>
ENCRYPTION_KEY=<aes-256-key>
```

**Troubleshooting**:

- If services don't start: `make dev-down && make dev-up`
- If tests fail: Check test environment is running (`make test-up`)
- If SSL errors: Regenerate certificates (`make certs FORCE=1`)
- For orphan containers: Add `--remove-orphans` to docker-compose commands

## License

[MIT License](LICENSE) - See LICENSE file for details.

## Support

- 📚 [Documentation](https://faiyaz7283.github.io/Dashtam/)
- 🐛 [Issue Tracker](https://github.com/faiyazhaider/Dashtam/issues)
- 💬 [Discussions](https://github.com/faiyazhaider/Dashtam/discussions)

---

**Built by [Faiyaz Haider](https://github.com/faiyazhaider)**
