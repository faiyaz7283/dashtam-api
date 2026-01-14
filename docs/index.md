# Dashtam Documentation

Dashtam is a **secure financial data aggregation platform** built with hexagonal architecture, CQRS, and domain-driven design in Python.

## Core Architecture

Six foundational pillars:

| Pattern | Description |
|---------|-------------|
| [Hexagonal Architecture](architecture/hexagonal.md) | Domain at center, zero framework dependencies, ports & adapters |
| [Protocol-Based Design](architecture/protocols.md) | Structural typing with Python `Protocol`, no inheritance |
| [CQRS](architecture/cqrs.md) | Separate command (write) and query (read) handlers |
| [Domain-Driven Design](architecture/domain-driven-design.md) | Entities, value objects, domain events for critical workflows |
| [Registry Pattern](architecture/registry.md) | Auto-wiring with self-enforcing tests (events, routes, rate limits) |
| [Dependency Injection](architecture/dependency-injection.md) | Centralized container, protocol-first design |

## Documentation Structure

**[Architecture](architecture/index.md)** — 34 docs covering patterns, infrastructure, security, domain models

**[API Reference](api/index.md)** — 15 docs for all REST endpoints (auth, accounts, providers, transactions)

**[Guides](guides/index.md)** — 17 practical how-to guides (releases, providers, error handling)

**[Code Reference](reference/index.md)** — Auto-generated from Python docstrings

## Key Features

- **Clean Architecture** — 100% hexagonal with protocol-based ports & adapters
- **Production Security** — JWT + opaque refresh tokens, Casbin RBAC, PCI-DSS audit trails
- **Multi-Provider** — OAuth (Schwab), API Key (Alpaca), File Import (Chase)
- **Modern Python** — Python 3.14, FastAPI, Pydantic v2, Result types
- **Comprehensive Testing** — 2,273 tests, 87% coverage

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.14, UV 0.9.21 |
| Framework | FastAPI, Pydantic v2 |
| Database | PostgreSQL 17.7, async SQLAlchemy |
| Cache | Redis 8.4 |
| Infrastructure | Docker Compose, Traefik, Alembic |
| CI/CD | GitHub Actions, Codecov |

## Quick Start

```bash
# Prerequisites: Docker, Make
sudo sh -c 'echo "127.0.0.1 dashtam.local" >> /etc/hosts'

# Start Traefik (one-time)
git clone git@github.com:faiyazhaider/docker-services.git ~/docker-services
cd ~/docker-services && make traefik-up

# Clone and run
git clone https://github.com/faiyaz7283/Dashtam.git
cd Dashtam
make setup && make dev-up

# Verify
curl -k https://dashtam.local/health
```

## Essential Reading

New to Dashtam? Start here:

1. [Hexagonal Architecture](architecture/hexagonal.md) — Core pattern
2. [Protocols](architecture/protocols.md) — Why Protocol over ABC
3. [Error Handling](guides/error-handling.md) — RFC 7807, Result types
4. [Registry Pattern](architecture/registry.md) — Auto-wiring, self-enforcing tests
5. [Release Management](guides/releases.md) — Git flow, versioning

## Development

```bash
make dev-up       # Start environment
make test         # Run all tests
make verify       # Full CI suite
make docs-serve   # Live documentation
```

**Workflow**: Feature branch → Plan → Implement → Test (85%+) → PR to `development`

**Principles**: Hexagonal architecture | Protocol-based | Result types | 100% REST

---

**Created**: 2025-11-13 | **Last Updated**: 2026-01-10
