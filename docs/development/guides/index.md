# Development Guides

Comprehensive how-to guides, best practices, and implementation tutorials for developing features in the Dashtam project.

## Contents

This directory contains step-by-step development guides organized by topic. Each guide provides practical instructions for implementing features, following standards, and contributing to the project.

## Directory Structure

```bash
guides/
├── docker-refactoring-implementation.md
├── docstring-standards.md
├── documentation-implementation-guide.md
├── git-quick-reference.md
├── git-workflow.md
├── index.md
├── jwt-auth-quick-reference.md
├── jwt-authentication-api-guide.md
├── jwt-authentication-database-guide.md
├── jwt-authentication-services-guide.md
├── markdown-linting-guide.md
├── mermaid-diagram-standards.md
├── restful-api-quick-reference.md
├── test-docstring-standards.md
├── testing-best-practices.md
├── testing-guide.md
├── token-rotation.md
└── uv-package-management.md
```

## 📄 Documents

### Git & Version Control

- [Git Workflow Guide](git-workflow.md) - Complete Git Flow implementation with branching strategy, branch protection, and PR process
- [Git Quick Reference](git-quick-reference.md) - One-page Git commands cheat sheet for common operations

### API Development

- [RESTful API Quick Reference](restful-api-quick-reference.md) - Quick guide for building REST-compliant APIs
- [JWT Auth Quick Reference](jwt-auth-quick-reference.md) - JWT authentication patterns and code examples
- [Token Rotation](token-rotation.md) - OAuth token rotation detection and refresh implementation

### JWT Authentication Implementation

**Core Implementation Guides:**

- [JWT Authentication Database Guide](jwt-authentication-database-guide.md) - Database schema, tables, and migrations for authentication
- [JWT Authentication Services Guide](jwt-authentication-services-guide.md) - PasswordService, JWTService, EmailService, AuthService implementation details
- [JWT Authentication API Guide](jwt-authentication-api-guide.md) - API endpoints, request/response schemas, and authentication flows

### Code Quality & Documentation

- [Docstring Standards](docstring-standards.md) - Google-style docstring conventions for Python
- [Markdown Linting Guide](markdown-linting-guide.md) - Markdown quality standards and fixing linting errors
- [Test Docstring Standards](test-docstring-standards.md) - Test documentation conventions
- [Mermaid Diagram Standards](mermaid-diagram-standards.md) - Creating diagrams with Mermaid syntax

### Project Management & Procedures

- [UV Package Management](uv-package-management.md) - Modern Python package management with UV CLI
- [Docker Refactoring Implementation](docker-refactoring-implementation.md) - Multi-environment Docker migration and best practices
- [Documentation Implementation Guide](documentation-implementation-guide.md) - Creating and maintaining documentation
- [Testing Best Practices](testing-best-practices.md) - Testing patterns, fixtures, and conventions
- [Testing Guide](testing-guide.md) - Comprehensive testing tutorial with examples

## Quick Links

**Related Documentation:**

- [Architecture Overview](../architecture/overview.md) - System design and patterns
- [Testing Strategy](../../testing/strategy.md) - Testing approach and framework
- [Infrastructure Setup](../infrastructure/docker-setup.md) - Docker configuration

**External Resources:**

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Git Documentation](https://git-scm.com/doc)

## Navigation

**Parent Directory:** [../index.md](../index.md)

**Related Directories:**

- [Architecture](../architecture/index.md) - System design and decisions
- [Infrastructure](../infrastructure/index.md) - Docker, CI/CD, database
- [Testing](../../testing/index.md) - Testing documentation

## Contributing

When adding new guides to this directory:

1. Choose appropriate guide-template.md (located in docs/templates/) - Use for step-by-step how-to guides
2. Include clear prerequisites and requirements
3. Provide complete code examples with explanations
4. Use [Mermaid diagrams](mermaid-diagram-standards.md) for visual concepts
5. Document both happy path and error cases
6. Update this index with a link and brief description
7. Run markdown linting: `make lint-md-file FILE="path/to/file.md"`

---

## Document Information

**Template:** index-section-template.md
**Created:** 2025-10-03
**Last Updated:** 2025-10-21
