# Development Documentation

Comprehensive developer documentation for the Dashtam financial data aggregation platform. This directory contains architecture guides, development workflows, testing strategies, and infrastructure documentation.

---

## 📚 Contents

This directory contains **51 documents** across **8 categories**, organized to support developers at all stages of contribution: from initial setup to advanced architecture decisions.

**Quick Navigation:**

- [Architecture](#architecture) - System design and technical decisions (6 docs)
- [Guides](#guides) - Step-by-step how-to documentation (12 docs)
- [Infrastructure](#infrastructure) - Docker, CI/CD, and deployment (4 docs)
- [Testing](#testing) - Test strategy and best practices (8 docs)
- [Troubleshooting](#troubleshooting) - Problem diagnosis and solutions (5 docs)
- [Reviews](#reviews) - Code quality audits and compliance (2 docs)
- [Implementation](#implementation) - Implementation plans (2 docs)
- [Historical](#historical) - Archived documents and history (12 docs)

---

## 🗂️ Directory Structure

```bash
docs/development/
├── architecture/           # 6 docs - System design and architecture
│   ├── async-testing-decision.md
│   ├── async-vs-sync-patterns.md
│   ├── jwt-authentication.md
│   ├── overview.md
│   ├── restful-api-design.md
│   └── schemas-design.md
├── guides/                 # 12 docs - Development how-to guides
│   ├── docstring-standards.md
│   ├── docker-refactoring-implementation.md
│   ├── documentation-implementation-guide.md
│   ├── documentation-template-migration-plan.md
│   ├── git-quick-reference.md
│   ├── git-workflow.md
│   ├── jwt-auth-quick-reference.md
│   ├── markdown-linting-guide.md
│   ├── mermaid-diagram-standards.md
│   ├── restful-api-quick-reference.md
│   ├── token-rotation.md
│   └── uv-package-management.md
├── infrastructure/         # 4 docs - Docker, CI/CD, environments
│   ├── ci-cd.md
│   ├── database-migrations.md
│   ├── docker-setup.md
│   └── environment-flows.md
├── testing/                # 6 docs - Testing strategy and guides
│   ├── DOCSTRING_AUDIT_CONTINUATION.md
│   ├── guide.md
│   ├── smoke-test-ci-debugging-journey.md
│   ├── smoke-test-design-comparison.md
│   └── strategy.md
├── troubleshooting/        # 6 docs - Problem diagnosis and solutions
│   ├── smoke-test-caplog-solution.md
│   ├── async-testing-greenlet-errors.md
│   ├── ci-test-failures-trustedhost.md
│   ├── env-directory-docker-mount-issue.md
│   ├── index.md
│   └── test-infrastructure-fixture-errors.md
├── reviews/                # 2 docs - Code quality and audits
│   ├── DOCUMENTATION_AUDIT_2025-10-05.md
│   └── REST_API_AUDIT_REPORT_2025-10-05.md
├── implementation/         # 2 docs - Implementation plans
│   ├── ssl-tls-test-ci-implementation.md
│   └── technical-debt-roadmap.md
├── historical/             # 12 docs - Archived documentation
│   └── [Various historical documents]
└── index.md                # This file
```

---

## 📄 Documents

### Architecture

System design, patterns, and technical decisions:

- [System Overview](architecture/overview.md) - High-level architecture and design philosophy
- [RESTful API Design](architecture/restful-api-design.md) - Complete REST architecture with compliance standards
- [JWT Authentication](architecture/jwt-authentication.md) - Authentication system architecture and security model
- [Schemas Design](architecture/schemas-design.md) - Pydantic schema organization and patterns
- [Async vs Sync Patterns](architecture/async-vs-sync-patterns.md) - Database access patterns and testing strategies
- [Async Testing Decision](architecture/async-testing-decision.md) - ADR for synchronous testing approach

### Guides

Step-by-step how-to documentation for developers:

**Git and Version Control:**

- [Git Workflow Guide](guides/git-workflow.md) - Complete Git Flow workflow with branching strategy
- [Git Quick Reference](guides/git-quick-reference.md) - One-page cheat sheet for common Git operations

**API Development:**

- [RESTful API Quick Reference](guides/restful-api-quick-reference.md) - Quick guide for building REST-compliant APIs
- [JWT Auth Quick Reference](guides/jwt-auth-quick-reference.md) - JWT authentication patterns and examples
- [Token Rotation](guides/token-rotation.md) - OAuth token rotation implementation guide

**Code Quality:**

- [Docstring Standards](guides/docstring-standards.md) - Google-style docstring conventions
- [Markdown Linting Guide](guides/markdown-linting-guide.md) - Markdown quality standards and fixing errors
- [Mermaid Diagram Standards](guides/mermaid-diagram-standards.md) - Diagram creation guidelines

**Project Management:**

- [UV Package Management](guides/uv-package-management.md) - Modern Python package management with UV
- [Docker Refactoring Implementation](guides/docker-refactoring-implementation.md) - Multi-environment Docker migration
- [Documentation Implementation Guide](guides/documentation-implementation-guide.md) - Creating and maintaining documentation
- [Documentation Template Migration Plan](guides/documentation-template-migration-plan.md) - Template migration project plan

### Infrastructure

Docker, environments, database, and CI/CD:

- [Docker Multi-Environment Setup](infrastructure/docker-setup.md) - Comprehensive Docker architecture guide
- [Environment Flows](infrastructure/environment-flows.md) - Development, test, and CI/CD environment workflows
- [Database Migrations](infrastructure/database-migrations.md) - Alembic migration system and best practices
- [CI/CD Pipeline](infrastructure/ci-cd.md) - GitHub Actions configuration and automation

### Testing

Testing strategy, guides, and best practices:

**Core Testing Documentation:**

- [Testing Strategy](testing/strategy.md) - Comprehensive testing strategy (unit, integration, E2E)
- [Testing Guide](testing/guide.md) - Comprehensive guide for writing tests
- [Testing Best Practices](guides/testing-best-practices.md) - Testing patterns and conventions
- [Test Docstring Standards](guides/test-docstring-standards.md) - Documenting tests properly

**Smoke Testing:**

- [Smoke Test Caplog Solution](troubleshooting/smoke-test-caplog-solution.md) - Token extraction troubleshooting and solution
- [Smoke Test CI Debugging Journey](testing/smoke-test-ci-debugging-journey.md) - Troubleshooting CI test failures
- [Smoke Test Design Comparison](testing/smoke-test-design-comparison.md) - Test implementation patterns

**Audits:**

- [Docstring Audit Continuation](testing/DOCSTRING_AUDIT_CONTINUATION.md) - Test documentation quality audit

### Troubleshooting

Problem diagnosis and solutions for common issues:

- [Async Testing Greenlet Errors](troubleshooting/async-testing-greenlet-errors.md) - Fixing async/sync testing conflicts
- [CI Test Failures TrustedHost](troubleshooting/ci-test-failures-trustedhost.md) - Resolving CI middleware issues
- [Env Directory Docker Mount Issue](troubleshooting/env-directory-docker-mount-issue.md) - Docker volume configuration problems
- [Test Infrastructure Fixture Errors](troubleshooting/test-infrastructure-fixture-errors.md) - Pytest fixture issues
- [Troubleshooting Index](troubleshooting/index.md) - Navigation for troubleshooting docs

### Reviews

Code quality audits and compliance assessments:

- [REST API Audit Report](reviews/REST_API_AUDIT_REPORT_2025-10-05.md) - Comprehensive REST API compliance audit
- [Documentation Audit](reviews/DOCUMENTATION_AUDIT_2025-10-05.md) - Documentation quality assessment

### Implementation

Implementation plans for features and improvements:

- [SSL/TLS Test CI Implementation](implementation/ssl-tls-test-ci-implementation.md) - SSL testing in CI/CD
- [Technical Debt Roadmap](implementation/technical-debt-roadmap.md) - Planned improvements and refactoring

### Historical

Archived documentation preserved for reference:

- 12 historical documents documenting past decisions, migrations, and resolved issues
- See [historical/](historical/) directory for complete list

---

## 🔗 Quick Links

**Getting Started:**

1. [System Overview](architecture/overview.md) - Understand the architecture
2. [Docker Setup](infrastructure/docker-setup.md) - Set up your environment
3. [Testing Guide](testing/guide.md) - Learn the testing approach
4. [Git Workflow](guides/git-workflow.md) - Understand version control

**Essential References:**

- [RESTful API Quick Reference](guides/restful-api-quick-reference.md) - REST API patterns
- [JWT Auth Quick Reference](guides/jwt-auth-quick-reference.md) - Authentication patterns
- [Git Quick Reference](guides/git-quick-reference.md) - Git commands cheat sheet

**Project Rules:**

- [WARP.md](../../WARP.md) - Project rules and AI agent instructions
- [README.md](../../README.md) - Project overview

**External Resources:**

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [pytest Documentation](https://docs.pytest.org/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)

---

## 🗺️ Navigation

**Parent Directory:** [Documentation Root](../index.md)

**Related Directories:**

- [API Flows](../api-flows/index.md) - Manual API testing flows
- [Research](../research/index.md) - Technical research and ADRs
- [Templates](../templates/README.md) - Documentation templates

**Other Documentation:**

- [Main README](../../README.md) - Project overview
- [Contributing Guidelines](../../CONTRIBUTING.md) - How to contribute (if exists)
- [Testing Guide](../../tests/README.md) - Test suite overview

---

## 📝 Contributing

When adding new documents to the development directory:

### 1. Choose Appropriate Template

Select from [documentation templates](../templates/README.md):

- `architecture-template.md` - For system design documents
- `guide-template.md` - For how-to guides
- `infrastructure-template.md` - For Docker, CI/CD, database docs
- `testing-template.md` - For testing documentation
- `troubleshooting-template.md` - For problem-solving guides
- `research-template.md` - For technical research
- `implementation-template.md` - For implementation plans

### 2. Follow Standards

- **Markdown Quality**: All documents must pass `make lint-md-file FILE="path/to/file.md"`
- **Diagrams**: Use [Mermaid syntax](guides/mermaid-diagram-standards.md) for all diagrams
- **Docstrings**: Follow [docstring standards](guides/docstring-standards.md)
- **Git Workflow**: Use [Git Flow](guides/git-workflow.md) for all changes

### 3. Update This Index

After creating a new document:

1. Add entry to appropriate section above
2. Include brief description (1 line)
3. Verify link works
4. Update file count in Contents section
5. Run linting: `make lint-md-file FILE="docs/development/index.md"`

### 4. Maintain Quality

- Zero markdown linting errors
- Complete metadata in all documents
- Cross-reference related documents
- Keep historical documents separate

---

## Document Information

**Category:** Index/Navigation  
**Created:** 2025-10-17  
**Last Updated:** 2025-10-17  
**Maintainer:** Development Team  
**Scope:** Development documentation for Dashtam project (51 documents across 8 categories)
