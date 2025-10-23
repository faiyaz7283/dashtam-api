# System Architecture

Comprehensive system design, architectural patterns, and technical decision records for the Dashtam financial data aggregation platform.

## Contents

This directory contains architectural documentation covering system design, technology decisions, design patterns, and API standards. All documents follow established templates and provide detailed technical context for developers.

## Directory Structure

```bash
architecture/
├── async-testing-decision.md
├── async-vs-sync-patterns.md
├── index.md
├── jwt-authentication.md
├── overview.md
├── restful-api-design.md
└── schemas-design.md
```

## Documents

### Core Architecture

- [System Overview](overview.md) - High-level architecture, component relationships, and design philosophy
  - Technology stack rationale
  - System components and interactions
  - Design principles and patterns

### Authentication & Security

- [JWT Authentication](jwt-authentication.md) - Complete authentication system architecture
  - JWT access tokens and opaque refresh tokens design
  - Token storage and encryption model
  - Complete flow diagrams and security considerations
  - Database schema for authentication

### API Design

- [RESTful API Design](restful-api-design.md) - RESTful API principles and compliance standards
  - REST architectural constraints
  - Resource-oriented design patterns
  - Consistent HTTP methods and status codes
  - API versioning and evolution strategy
  - 100% compliance audit and scoring methodology

- [Schemas Design](schemas-design.md) - Pydantic schema organization and patterns
  - Schema file structure and organization
  - Request/response schema patterns
  - Database model separation
  - Schema reusability and inheritance

### Database & Async Patterns

- [Async vs Sync Patterns](async-vs-sync-patterns.md) - Database access patterns and design tradeoffs
  - SQLAlchemy async/await patterns
  - Proper query construction with selectinload()
  - Connection pooling and session management
  - Synchronous testing strategy for async code

- [Async Testing Decision](async-testing-decision.md) - Architectural decision record for synchronous testing
  - Comparison of async/sync testing approaches
  - Decision rationale and tradeoffs
  - Benefits of synchronous testing pattern
  - Implementation guidelines

## Quick Links

**Related Documentation:**

- [Development Guides](../guides/index.md) - How-to guides and implementation details
- [Testing Strategy](../../testing/strategy.md) - Testing approach and framework
- [Infrastructure Setup](../infrastructure/docker-setup.md) - Docker and environment configuration

**Implementation Guides:**

- [JWT Authentication Implementation](../guides/jwt-authentication-services-guide.md) - Service implementation
- [REST API Quick Reference](../guides/restful-api-quick-reference.md) - API patterns cheat sheet

**External Resources:**

- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Web framework reference
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/) - ORM and schema patterns
- [Pydantic Documentation](https://docs.pydantic.dev/) - Data validation and serialization
- [REST API Design Best Practices](https://restfulapi.net/) - REST architectural standards

## Navigation

**Parent Directory:** [../index.md](../index.md)

**Related Directories:**

- [Development Guides](../guides/index.md) - Implementation guides and tutorials
- [Infrastructure](../infrastructure/index.md) - Docker, CI/CD, database
- [Testing](../../testing/index.md) - Testing strategy and best practices

**Other Documentation:**

- `README.md` (project root) - Project overview
- `WARP.md` (project root) - Project rules and standards

## Contributing

When adding new architecture documents to this directory:

1. Choose appropriate [template](../../templates/architecture-template.md) - Use for system design documents
2. Focus on **why** decisions were made, not just **what** was implemented
3. Include diagrams using [Mermaid syntax](../guides/mermaid-diagram-standards.md)
4. Reference implementation guides for details
5. Document tradeoffs and alternatives considered
6. Update this index with a link and brief description
7. Run markdown linting: `make lint-md FILE="path/to/file.md"`

### Architecture Decision Records (ADRs)

When documenting significant architectural decisions:

1. Use the [architecture-template.md](../../templates/architecture-template.md)
2. Follow the format: Context → Problem → Options → Analysis → Decision → Consequences
3. Document decision date and decision maker
4. Include links to related implementations
5. Update `WARP.md` (project root) if the decision impacts project standards

---

## Document Information

**Template:** [index-section-template.md](../../templates/index-section-template.md)
**Created:** 2025-10-03
**Last Updated:** 2025-10-21
