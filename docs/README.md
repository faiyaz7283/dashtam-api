# Dashtam Documentation

Welcome to the Dashtam documentation! This directory contains all documentation for the project, organized by audience and purpose.

---

## 📚 Documentation Structure

### For Developers
Documentation for working **on** the Dashtam project:

- **[Development Guide](development/)** - Architecture, infrastructure, and testing
  - [Architecture Overview](development/architecture/overview.md)
  - [Improvement Guide](development/architecture/improvement-guide.md) - Design improvements and roadmap
  - [Docker Setup](development/infrastructure/docker-setup.md)
  - [Testing Strategy](development/testing/strategy.md)
  - [Testing Guide](development/testing/guide.md)
  - [Docstring Standards](development/guides/docstring-standards.md) - Comprehensive Python documentation guide
  - [Documentation Implementation](development/guides/documentation-implementation-guide.md) - MkDocs setup guide

### Research & Decisions
Historical research, architectural decisions, and migration notes:

- **[Research Notes](research/)** - Technical research and decision records
  - [Async Testing Research](research/async-testing.md)
  - [Infrastructure Migration](research/infrastructure-migration.md)
  - [Test Coverage Plan](research/test-coverage-plan.md)
  - [Archived Documents](research/archived/)

### For Users
Documentation for using and testing the Dashtam application:

- **[Setup Guides](setup/)** - Installation and configuration (planned)
- **[API Documentation](api/)** - API endpoints and usage (planned)
- **[User Guides](guides/)** - Troubleshooting and tips (planned)
- **[API Flows (Manual Testing)](../docs/api-flows/)** - HTTPS-first, user-centric flows for manual testing (dev TLS)

---

## 🗂️ Directory Organization

```
docs/
├── api-flows/          # Manual API flows (HTTPS-first, dev TLS)
│   ├── auth/           # Registration, login, password reset
│   └── providers/      # Provider onboarding flows
│
├── development/        # Developer documentation
│   ├── architecture/   # System architecture and design
│   ├── infrastructure/ # Docker, CI/CD, environments
│   ├── testing/        # Testing strategy and guides
│   └── guides/         # Development how-tos
│
├── research/           # Research and decision records
│   └── archived/       # Historical documents
│
├── setup/              # User setup guides (planned)
├── api/                # API reference (planned)
└── guides/             # User guides (planned)
```

---

## 📝 Naming Conventions

For API flows, use kebab-case filenames and keep each flow focused on a single user journey (not a single HTTP verb). A reusable flow template is available at `docs/api-flows/flow-template.md`.

### File Naming
- **Use kebab-case**: `my-document.md` (all lowercase with hyphens)
- **Include type suffix when helpful**:
  - `-architecture.md` - Architecture documentation
  - `-guide.md` - How-to guides and tutorials
  - `-reference.md` - Quick references
  - `-plan.md` - Implementation plans (archive when completed)
  - `-review-YYYY-MM-DD.md` - Dated reviews/audits
- **Keep names concise but descriptive**
- **Avoid special characters** except hyphens

### Examples
- ✅ Good: `jwt-authentication-architecture.md`, `git-workflow-guide.md`
- ✅ Good: `rest-api-audit-2025-10-05.md` (dated reviews)
- ❌ Avoid: `JWT_Authentication.md`, `git_workflow.md`

---

## 📝 Contributing to Documentation

When adding new documentation, follow this structure:

- **Development docs** → `docs/development/[category]/`
  - `architecture/` - System architecture and design patterns
  - `guides/` - How-to guides and tutorials
  - `infrastructure/` - Docker, CI/CD, deployment
  - `testing/` - Testing strategy and guides
  - `reviews/` - Code reviews, audits, assessments
- **User-facing docs** → `docs/setup/`, `docs/api/`, or `docs/guides/` (future)
- **Research/decisions** → `docs/research/`
- **Historical/archived** → `docs/research/archived/`
  - `implementation-plans/` - Completed implementation plans
  - `reviews/` - Historical reviews and assessments
  - `completed-research/` - Resolved research and fixes

See [WARP.md](../WARP.md) for complete documentation guidelines.

---

## 🔗 Quick Links

- [Main README](../README.md) - Project overview
- [WARP.md](../WARP.md) - AI agent rules and project context
- [Testing Guide](../tests/TESTING_GUIDE.md) - Quick testing reference
- [Development Docs](development/) - Full developer documentation
