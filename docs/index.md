# Dashtam Documentation

Welcome to the Dashtam financial data aggregation platform documentation. This directory contains comprehensive guides for developers, users, and contributors working with the Dashtam project.

## Contents

All documentation is organized by audience and purpose to help you quickly find what you need.

**Main Sections:**

- [Development Documentation](#development-documentation) - Architecture, infrastructure, guides, and testing
- [Research & Decisions](#research--decisions) - Technical research and architectural decision records
- [API Flows](#api-flows) - Manual API testing workflows

## Directory Structure

```bash
docs/
├── templates/                     # Documentation templates (START HERE for new docs)
│   ├── api-flow-template.md
│   ├── architecture-template.md
│   ├── audit-template.md
│   ├── general-template.md
│   ├── guide-template.md
│   ├── implementation-template.md
│   ├── index-root-template.md
│   ├── index-section-template.md
│   ├── infrastructure-template.md
│   ├── readme-template.md
│   ├── README.md
│   ├── research-template.md
│   ├── testing-template.md
│   └── troubleshooting-template.md
├── api-flows/                     # Manual API testing workflows
│   ├── auth/
│   │   ├── complete-auth-flow.md
│   │   ├── email-verification.md
│   │   ├── index.md
│   │   ├── login.md
│   │   ├── password-reset.md
│   │   └── registration.md
│   ├── providers/
│   │   ├── index.md
│   │   ├── provider-disconnect.md
│   │   └── provider-onboarding.md
│   └── index.md
├── development/                   # Developer documentation
│   ├── architecture/
│   │   ├── async-testing-decision.md
│   │   ├── async-vs-sync-patterns.md
│   │   ├── index.md
│   │   ├── jwt-authentication.md
│   │   ├── overview.md
│   │   ├── restful-api-design.md
│   │   └── schemas-design.md
│   ├── guides/
│   │   ├── docker-refactoring-implementation.md
│   │   ├── docstring-standards.md
│   │   ├── documentation-implementation-guide.md
│   │   ├── git-quick-reference.md
│   │   ├── git-workflow.md
│   │   ├── index.md
│   │   ├── jwt-auth-quick-reference.md
│   │   ├── jwt-authentication-api-guide.md
│   │   ├── jwt-authentication-database-guide.md
│   │   ├── jwt-authentication-services-guide.md
│   │   ├── markdown-linting-guide.md
│   │   ├── mermaid-diagram-standards.md
│   │   ├── restful-api-quick-reference.md
│   │   ├── test-docstring-standards.md
│   │   ├── testing-best-practices.md
│   │   ├── testing-guide.md
│   │   ├── token-rotation.md
│   │   └── uv-package-management.md
│   ├── infrastructure/
│   │   ├── ci-cd.md
│   │   ├── database-migrations.md
│   │   ├── docker-setup.md
│   │   ├── environment-flows.md
│   │   └── index.md
│   ├── troubleshooting/
│   │   ├── async-testing-greenlet-errors.md
│   │   ├── ci-test-failures-trustedhost.md
│   │   ├── env-directory-docker-mount-issue.md
│   │   ├── index.md
│   │   ├── smoke-test-caplog-solution.md
│   │   ├── smoke-test-ci-debugging-journey.md
│   │   └── test-infrastructure-fixture-errors.md
│   ├── technical-debt-roadmap.md
│   └── index.md
├── research/                      # Research and decision records
│   ├── authentication-approaches-research.md
│   ├── documentation_guide_research.md
│   ├── index.md
│   ├── smoke-test-design-comparison.md
│   └── smoke-test-organization-research.md
├── reviews/                       # Code audits and compliance reviews
│   ├── DOCUMENTATION_AUDIT_2025-10-05.md
│   ├── index.md
│   └── REST_API_AUDIT_REPORT_2025-10-05.md
├── testing/                       # Testing strategy and guides
│   ├── index.md
│   └── strategy.md
└── index.md
```

## Documents

### Development Documentation

Comprehensive guides for developers, including system architecture, development workflows, testing strategies, and infrastructure setup.

**Architecture & Design:**

- [Architecture Index](development/architecture/index.md) - System architecture overview
- [Overview](development/architecture/overview.md) - High-level system design and components
- [JWT Authentication](development/architecture/jwt-authentication.md) - Authentication system design and implementation
- [RESTful API Design](development/architecture/restful-api-design.md) - REST API architecture and compliance
- [Schemas Design](development/architecture/schemas-design.md) - Request/response schema patterns
- [Async vs Sync Patterns](development/architecture/async-vs-sync-patterns.md) - Testing strategy decisions
- [Async Testing Decision](development/architecture/async-testing-decision.md) - Testing implementation rationale

**Infrastructure & Setup:**

- [Infrastructure Index](development/infrastructure/index.md) - Infrastructure documentation overview
- [Docker Setup](development/infrastructure/docker-setup.md) - Docker configuration and development environment
- [CI/CD Pipeline](development/infrastructure/ci-cd.md) - GitHub Actions automation and testing
- [Database Migrations](development/infrastructure/database-migrations.md) - Alembic migration management
- [Environment Flows](development/infrastructure/environment-flows.md) - Dev, test, and CI environment setup

**Developer Guides:**

- [Guides Index](development/guides/index.md) - Developer guides overview
- [Git Workflow](development/guides/git-workflow.md) - Git Flow branching strategy
- [Git Quick Reference](development/guides/git-quick-reference.md) - Common git commands
- [Testing Guide](development/guides/testing-guide.md) - Comprehensive testing tutorial
- [Testing Best Practices](development/guides/testing-best-practices.md) - Testing patterns and strategies
- [Docstring Standards](development/guides/docstring-standards.md) - Python documentation standards
- [Test Docstring Standards](development/guides/test-docstring-standards.md) - Test documentation guidelines
- [Markdown Linting Guide](development/guides/markdown-linting-guide.md) - Documentation quality standards
- [Mermaid Diagram Standards](development/guides/mermaid-diagram-standards.md) - Diagram creation guide
- [UV Package Management](development/guides/uv-package-management.md) - Modern Python package management
- [Docker Refactoring Implementation](development/guides/docker-refactoring-implementation.md) - Docker optimization guide
- [Documentation Implementation](development/guides/documentation-implementation-guide.md) - Doc creation workflow

**JWT Authentication Guides:**

- [JWT Auth Quick Reference](development/guides/jwt-auth-quick-reference.md) - Quick authentication reference
- [JWT Authentication - Services](development/guides/jwt-authentication-services-guide.md) - Service implementation
- [JWT Authentication - Database](development/guides/jwt-authentication-database-guide.md) - Database schema and models
- [JWT Authentication - API](development/guides/jwt-authentication-api-guide.md) - API endpoints and flows

**Security & Token Management:**

- [Token Rotation](development/guides/token-rotation.md) - Token refresh and rotation mechanisms
- [RESTful API Quick Reference](development/guides/restful-api-quick-reference.md) - REST pattern reference

**Troubleshooting & Issues:**

- [Troubleshooting Index](development/troubleshooting/index.md) - Troubleshooting guide overview
- [Async Testing Greenlet Errors](development/troubleshooting/async-testing-greenlet-errors.md) - Async test debugging
- [Test Infrastructure Fixture Errors](development/troubleshooting/test-infrastructure-fixture-errors.md) - Fixture issues
- [Smoke Test Caplog Solution](development/troubleshooting/smoke-test-caplog-solution.md) - Smoke test implementation
- [Smoke Test CI Debugging](development/troubleshooting/smoke-test-ci-debugging-journey.md) - CI test debugging
- [CI Test Failures TrustedHost](development/troubleshooting/ci-test-failures-trustedhost.md) - Network middleware issues
- [Env Directory Docker Mount](development/troubleshooting/env-directory-docker-mount-issue.md) - Docker mount troubleshooting

**Project Planning:**

- [Technical Debt Roadmap](development/technical-debt-roadmap.md) - Future improvements and refactoring
- [Development Index](development/index.md) - Complete development documentation index

### Testing

Testing strategy, guides, and documentation for the test infrastructure.

- [Testing Index](testing/index.md) - Testing documentation overview
- [Testing Strategy](testing/strategy.md) - Test pyramid and testing approach

### Research & Decisions

Technical research, architectural decision records, and comparative analysis of design approaches.

- [Research Index](research/index.md) - Research and decision records navigation
- [Authentication Approaches Research](research/authentication-approaches-research.md) - Comprehensive comparison of authentication methods
- [Smoke Test Design Comparison](research/smoke-test-design-comparison.md) - Smoke test implementation approaches
- [Smoke Test Organization Research](research/smoke-test-organization-research.md) - Test file organization strategies
- [Documentation Guide Research](research/documentation_guide_research.md) - Documentation structure research

### Code Reviews & Audits

Comprehensive code reviews, API audits, and compliance verification.

- [Reviews Index](reviews/index.md) - Code reviews and audits overview
- [REST API Audit Report](reviews/REST_API_AUDIT_REPORT_2025-10-05.md) - RESTful API compliance audit
- [Documentation Audit](reviews/DOCUMENTATION_AUDIT_2025-10-05.md) - Documentation quality audit

### API Flows

User-centric manual API testing workflows designed for HTTPS-first development environments.

- [API Flows Index](api-flows/index.md) - Navigation for all API testing workflows

**Authentication Flows:**

- [Authentication Index](api-flows/auth/index.md) - Authentication workflow overview
- [Registration](api-flows/auth/registration.md) - User account creation
- [Email Verification](api-flows/auth/email-verification.md) - Email verification workflow
- [Login](api-flows/auth/login.md) - User login process
- [Password Reset](api-flows/auth/password-reset.md) - Password recovery workflow
- [Complete Auth Flow](api-flows/auth/complete-auth-flow.md) - Full authentication journey

**Provider Flows:**

- [Providers Index](api-flows/providers/index.md) - Provider workflow overview
- [Provider Onboarding](api-flows/providers/provider-onboarding.md) - OAuth provider connection
- [Provider Disconnect](api-flows/providers/provider-disconnect.md) - Provider disconnection

### Documentation Templates

Reusable templates for creating new documentation that follows project standards.

- [Templates Index](templates/README.md) - Template system overview and guidelines
- [Index Root Template](templates/index-root-template.md) - Root documentation index template
- [Index Section Template](templates/index-section-template.md) - Section documentation index template
- [General Template](templates/general-template.md) - General purpose documentation template
- [Architecture Template](templates/architecture-template.md) - Architecture documentation template
- [Guide Template](templates/guide-template.md) - Developer guide template
- [Infrastructure Template](templates/infrastructure-template.md) - Infrastructure documentation template
- [Testing Template](templates/testing-template.md) - Testing documentation template
- [Troubleshooting Template](templates/troubleshooting-template.md) - Troubleshooting guide template
- [Research Template](templates/research-template.md) - Research and ADR template
- [Audit Template](templates/audit-template.md) - Code audit and review template
- [API Flow Template](templates/api-flow-template.md) - API testing workflow template
- [Implementation Template](templates/implementation-template.md) - Implementation guide template
- [README Template](templates/readme-template.md) - README documentation template

## Quick Links

**Getting Started:**

- [System Architecture](development/architecture/overview.md) - Understand the platform design
- [Docker Setup](development/infrastructure/docker-setup.md) - Set up your development environment
- [Development Index](development/index.md) - Browse all development documentation

**Essential References:**

- [Testing Strategy](testing/strategy.md) - Testing approach and best practices
- [Git Workflow](development/guides/git-workflow.md) - Version control guidelines
- [Template System](templates/README.md) - Documentation template reference

**External Resources:**

- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Web framework reference
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/) - Database ORM reference
- [Docker Documentation](https://docs.docker.com/) - Container platform reference

## Navigation

**Main Sections:**

- [Development Documentation](development/index.md) - Architecture, guides, infrastructure, testing
- [Research & Decisions](research/index.md) - Technical research and decision records
- [API Flows](api-flows/index.md) - Manual testing workflows
- [Documentation Templates](templates/README.md) - Template system and standards

**Related Repositories:**

- `src/` - Application source code
- `tests/` - Test suites and fixtures
- `compose/` - Container orchestration files

## Contributing

When adding new documentation:

1. Follow appropriate [template](templates/README.md) from the templates directory
2. Place documents in correct category directory
3. Use Directory Structure section above as reference
4. Update relevant index.md file with new links and descriptions
5. Run markdown linting: `make lint-md-file FILE="path/to/file.md"`
6. Ensure document follows markdown quality standards

---

## Document Information

**Template:** [index-root-template.md](templates/index-root-template.md)
**Created:** 2025-10-03
**Last Updated:** 2025-10-21
