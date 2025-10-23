# Infrastructure

Docker, containerization, CI/CD pipelines, database migrations, and environment configuration for the Dashtam project.

## Contents

This directory contains infrastructure and DevOps documentation covering Docker setup, environments, database migrations, and continuous integration/deployment workflows.

## Directory Structure

```bash
infrastructure/
├── docker-setup.md                  # Multi-environment Docker configuration
├── environment-flows.md             # Development, test, and CI/CD workflows
├── database-migrations.md           # Alembic migration system and best practices
├── ci-cd.md                         # GitHub Actions CI/CD pipeline
└── index.md                         # This file
```

## Documents

### Container & Environment Setup

- [Docker Multi-Environment Setup](docker-setup.md) - Comprehensive Docker architecture with dev, test, and CI configurations
  - Multi-stage Dockerfile
  - Docker Compose configurations
  - Network and service configuration
  - Volume management and security

- [Environment Flows](environment-flows.md) - Development, test, and CI/CD environment workflows
  - Environment-specific configurations
  - Service initialization and health checks
  - Local development process flow
  - Testing environment setup
  - CI/CD environment configuration

### Database Management

- [Database Migrations](database-migrations.md) - Alembic migration system and best practices
  - Migration creation and management
  - Async SQLAlchemy support
  - Safe schema evolution
  - Production deployment strategies
  - Testing migrations in isolation

### CI/CD Pipeline

- [CI/CD Pipeline](ci-cd.md) - GitHub Actions workflow and automation
  - Workflow configuration and triggers
  - Test execution in Docker
  - Coverage reporting and Codecov integration
  - Branch protection requirements
  - Automated deployment processes

## Quick Links

**Related Documentation:**

- [Docker Refactoring Guide](../guides/docker-refactoring-implementation.md) - Docker migration implementation details
- [Architecture Overview](../architecture/overview.md) - System design
- [Testing Strategy](../../testing/strategy.md) - Testing approach

**Development Workflows:**

- [Git Workflow Guide](../guides/git-workflow.md) - Version control and branching
- [UV Package Management](../guides/uv-package-management.md) - Dependency management

**External Resources:**

- [Docker Documentation](https://docs.docker.com/) - Official Docker reference
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## Navigation

**Parent Directory:** [../index.md](../index.md)

**Related Directories:**

- [Architecture](../architecture/index.md) - System design and decisions
- [Development Guides](../guides/index.md) - How-to guides and tutorials
- [Testing](../../testing/index.md) - Testing documentation

## Contributing

When adding new infrastructure documentation to this directory:

1. Choose appropriate [template](../../templates/infrastructure-template.md) - Use for infrastructure and operations docs
2. Document both local development and production setups
3. Include configuration examples and troubleshooting steps
4. Use [Mermaid diagrams](../guides/mermaid-diagram-standards.md) for environment flows
5. Document health checks and monitoring requirements
6. Update this index with a link and brief description
7. Run markdown linting: `make lint-md-file FILE="path/to/file.md"`

---

## Document Information

**Template:** [index-section-template.md](../../templates/index-section-template.md)
**Created:** 2025-10-03
**Last Updated:** 2025-10-21
