# Development

Comprehensive developer documentation for the Dashtam financial data aggregation platform. This directory contains architecture guides, development workflows, testing strategies, and infrastructure documentation.

## Contents

This directory contains 39 documents across 4 main subdirectories plus technical debt planning, organized by topic and use case. Each subdirectory has its own index for navigation and quick access.

## Directory Structure

```bash
development/
├── architecture/
│   ├── async-testing-decision.md
│   ├── async-vs-sync-patterns.md
│   ├── index.md
│   ├── jwt-authentication.md
│   ├── overview.md
│   ├── restful-api-design.md
│   └── schemas-design.md
├── guides/
│   ├── docker-refactoring-implementation.md
│   ├── docstring-standards.md
│   ├── documentation-implementation-guide.md
│   ├── git-quick-reference.md
│   ├── git-workflow.md
│   ├── index.md
│   ├── jwt-auth-quick-reference.md
│   ├── jwt-authentication-api-guide.md
│   ├── jwt-authentication-database-guide.md
│   ├── jwt-authentication-services-guide.md
│   ├── markdown-linting-guide.md
│   ├── mermaid-diagram-standards.md
│   ├── restful-api-quick-reference.md
│   ├── test-docstring-standards.md
│   ├── testing-best-practices.md
│   ├── testing-guide.md
│   ├── token-rotation.md
│   └── uv-package-management.md
├── infrastructure/
│   ├── ci-cd.md
│   ├── database-migrations.md
│   ├── docker-setup.md
│   ├── environment-flows.md
│   └── index.md
├── troubleshooting/
│   ├── async-testing-greenlet-errors.md
│   ├── ci-test-failures-trustedhost.md
│   ├── env-directory-docker-mount-issue.md
│   ├── index.md
│   ├── smoke-test-caplog-solution.md
│   ├── smoke-test-ci-debugging-journey.md
│   └── test-infrastructure-fixture-errors.md
├── technical-debt-roadmap.md
└── index.md
```

## Documents

### Architecture

System design, patterns, and technical decisions:

- [Architecture Index](architecture/index.md) - Navigation for all architecture documents
- [System Overview](architecture/overview.md) - High-level architecture and design philosophy
- [RESTful API Design](architecture/restful-api-design.md) - Complete REST architecture with compliance standards
- [JWT Authentication](architecture/jwt-authentication.md) - Authentication system architecture and security model
- [Schemas Design](architecture/schemas-design.md) - Pydantic schema organization and patterns
- [Async vs Sync Patterns](architecture/async-vs-sync-patterns.md) - Database access patterns and testing strategies
- [Async Testing Decision](architecture/async-testing-decision.md) - Architectural decision record for synchronous testing

### Guides

Step-by-step how-to documentation for developers:

- [Guides Index](guides/index.md) - Navigation for all development guides

**Git and Version Control:**

- [Git Workflow Guide](guides/git-workflow.md) - Complete Git Flow workflow with branching strategy
- [Git Quick Reference](guides/git-quick-reference.md) - One-page cheat sheet for common Git operations

**API Development:**

- [RESTful API Quick Reference](guides/restful-api-quick-reference.md) - Quick guide for building REST-compliant APIs
- [JWT Auth Quick Reference](guides/jwt-auth-quick-reference.md) - JWT authentication patterns and examples
- [Token Rotation](guides/token-rotation.md) - OAuth token rotation implementation guide

**JWT Authentication Implementation:**

- [JWT Authentication Database Guide](guides/jwt-authentication-database-guide.md) - Database schema, tables, and migrations for authentication
- [JWT Authentication Services Guide](guides/jwt-authentication-services-guide.md) - PasswordService, JWTService, EmailService, AuthService implementation
- [JWT Authentication API Guide](guides/jwt-authentication-api-guide.md) - API endpoints, schemas, and authentication flows

**Code Quality & Testing:**

- [Docstring Standards](guides/docstring-standards.md) - Google-style docstring conventions
- [Test Docstring Standards](guides/test-docstring-standards.md) - Test documentation conventions
- [Testing Best Practices](guides/testing-best-practices.md) - Testing patterns and conventions
- [Testing Guide](guides/testing-guide.md) - Comprehensive testing tutorial with examples
- [Markdown Linting Guide](guides/markdown-linting-guide.md) - Markdown quality standards and fixing errors
- [Mermaid Diagram Standards](guides/mermaid-diagram-standards.md) - Diagram creation guidelines

**Project Management:**

- [UV Package Management](guides/uv-package-management.md) - Modern Python package management with UV
- [Docker Refactoring Implementation](guides/docker-refactoring-implementation.md) - Multi-environment Docker migration
- [Documentation Implementation Guide](guides/documentation-implementation-guide.md) - Creating and maintaining documentation

### Infrastructure

Docker, environments, database, and CI/CD:

- [Infrastructure Index](infrastructure/index.md) - Navigation for all infrastructure documents
- [Docker Multi-Environment Setup](infrastructure/docker-setup.md) - Comprehensive Docker architecture guide
- [Environment Flows](infrastructure/environment-flows.md) - Development, test, and CI/CD environment workflows
- [Database Migrations](infrastructure/database-migrations.md) - Alembic migration system and best practices
- [CI/CD Pipeline](infrastructure/ci-cd.md) - GitHub Actions configuration and automation

### Troubleshooting

Problem diagnosis and solutions for common issues:

- [Troubleshooting Index](troubleshooting/index.md) - Navigation for troubleshooting docs
- [Async Testing Greenlet Errors](troubleshooting/async-testing-greenlet-errors.md) - Fixing async/sync testing conflicts
- [CI Test Failures TrustedHost](troubleshooting/ci-test-failures-trustedhost.md) - Resolving CI middleware issues
- [Env Directory Docker Mount Issue](troubleshooting/env-directory-docker-mount-issue.md) - Docker volume configuration problems
- [Test Infrastructure Fixture Errors](troubleshooting/test-infrastructure-fixture-errors.md) - Pytest fixture issues
- [Smoke Test Caplog Solution](troubleshooting/smoke-test-caplog-solution.md) - Smoke test implementation guide
- [Smoke Test CI Debugging Journey](troubleshooting/smoke-test-ci-debugging-journey.md) - CI test debugging walkthrough

### Project Planning

- [Technical Debt Roadmap](technical-debt-roadmap.md) - Technical debt tracking and development planning

## Quick Links

**Getting Started:**

- [System Overview](architecture/overview.md) - Understand the architecture
- [Docker Setup](infrastructure/docker-setup.md) - Set up your environment
- [Git Workflow](guides/git-workflow.md) - Understand version control

**Essential References:**

- [RESTful API Quick Reference](guides/restful-api-quick-reference.md) - REST API patterns
- [JWT Auth Quick Reference](guides/jwt-auth-quick-reference.md) - Authentication patterns
- [Git Quick Reference](guides/git-quick-reference.md) - Git commands cheat sheet

**External Resources:**

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [pytest Documentation](https://docs.pytest.org/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)

## Navigation

**Parent Directory:** [../index.md](../index.md)

**Related Sections:**

- [API Flows](../api-flows/index.md) - Manual API testing workflows
- [Research](../research/index.md) - Technical research and ADRs
- [Testing](../testing/index.md) - Testing strategy and documentation

**Other Documentation:**

- [Main Index](../index.md) - Documentation home
- `README.md` (project root) - Project overview

## Contributing

When adding new documents to the development directory:

1. Choose appropriate  based on document type
2. Place in correct subdirectory (architecture, guides, infrastructure, troubleshooting)
3. Follow markdown quality standards and guidelines
4. Update this index with link and brief description
5. Run markdown linting: `make lint-md FILE="path/to/file.md"`

---

## Document Information

**Template:** index-section-template.md
**Created:** 2025-10-03
**Last Updated:** 2025-10-21
