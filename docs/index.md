# Dashtam Documentation

Welcome to the Dashtam documentation! This directory contains all documentation for the project, organized by audience and purpose.

---

## 📚 Documentation Structure

### For Developers

Documentation for working on the Dashtam project:

- [Development Guide](development/) - Architecture, infrastructure, and testing
  - [Architecture Overview](development/architecture/overview.md)
  - [Improvement Guide](development/architecture/improvement-guide.md) - Design improvements and roadmap
  - [Docker Setup](development/infrastructure/docker-setup.md)
  - [Testing Strategy](development/testing/strategy.md)
  - [Testing Guide](development/testing/guide.md)
  - [Docstring Standards](development/guides/docstring-standards.md) - Comprehensive Python documentation guide
  - [Documentation Implementation](development/guides/documentation-implementation-guide.md) - MkDocs setup guide

### Research & Decisions

Historical research, architectural decisions, and migration notes:

- [Research Notes](research/) - Technical research and decision records
  - [Async Testing Research](research/async-testing.md)
  - [Infrastructure Migration](research/infrastructure-migration.md)
  - [Test Coverage Plan](research/test-coverage-plan.md)
  - [Archived Documents](research/archived/)

### For Users

Documentation for using and testing the Dashtam application:

- [Setup Guides](setup/) - Installation and configuration (planned)
- [API Documentation](api/) - API endpoints and usage (planned)
- [User Guides](guides/) - Troubleshooting and tips (planned)
- [API Flows (Manual Testing)](../docs/api-flows/) - HTTPS-first, user-centric flows for manual testing (dev TLS)

---

## 🗂️ Directory Organization

```bash
docs/
├── templates/          # Documentation templates (START HERE for new docs!)
│   ├── README.md       # Template usage guide
│   ├── general-template.md
│   ├── architecture-template.md
│   ├── guide-template.md
│   ├── infrastructure-template.md
│   ├── testing-template.md
│   ├── research-template.md
│   ├── api-flow-template.md
│   ├── index-template.md
│   ├── readme-template.md
│   └── MERMAID_GUIDELINES.md  # REQUIRED: Diagram standards
│
├── api-flows/          # Manual API flows (HTTPS-first, dev TLS)
│   ├── auth/           # Registration, login, password reset
│   └── providers/      # Provider onboarding flows
│
├── development/        # Developer documentation
│   ├── architecture/   # System architecture and design
│   ├── guides/         # How-to guides and tutorials
│   ├── implementation/ # Implementation plans
│   ├── infrastructure/ # Docker, CI/CD, environments
│   ├── research/       # Active technical research
│   ├── reviews/        # Code reviews, audits, assessments
│   └── testing/        # Testing strategy and guides
│
├── research/           # Research and decision records
│   └── archived/       # Historical/completed research
│       ├── completed-research/
│       ├── implementation-plans/
│       └── reviews/
│
├── setup/              # User setup guides (planned)
├── api/                # API reference (planned)
└── guides/             # User guides (planned)
```

---

## 📋 Documentation Templates

**IMPORTANT**: Before creating new documentation, use the appropriate template from `docs/templates/`!

### Available Templates

| Template | Use For |
|----------|----------|
| [general-template.md](templates/general-template.md) | Any documentation that doesn't fit other categories |
| [architecture-template.md](templates/architecture-template.md) | System architecture and design documents |
| [guide-template.md](templates/guide-template.md) | Step-by-step how-to guides and tutorials |
| [infrastructure-template.md](templates/infrastructure-template.md) | Infrastructure and operations documentation |
| [testing-template.md](templates/testing-template.md) | Testing strategies and guides |
| [research-template.md](templates/research-template.md) | Research documents and ADRs |
| [api-flow-template.md](templates/api-flow-template.md) | API manual testing flows |
| [index-template.md](templates/index-template.md) | Directory navigation pages (docs/index.md, docs/development/index.md) |
| [readme-template.md](templates/readme-template.md) | Feature/component READMEs (env/README.md, tests/smoke/README.md) |

**Diagram Standards:**

- 🎨 **ALL diagrams MUST use Mermaid syntax** - See [MERMAID_GUIDELINES.md](templates/MERMAID_GUIDELINES.md)
- ✅ Directory trees → Code blocks with tree structure (like `tree` command)
- ✅ Process flows → `flowchart TD`
- ✅ Database schemas → `erDiagram`
- ✅ API sequences → `sequenceDiagram`
- ❌ **NO image files** (PNG, JPG, SVG)
- ❌ **NO external tools** (draw.io, Lucidchart)

### Quick Start

```bash
# 1. Copy the appropriate template
cp docs/templates/guide-template.md docs/development/guides/my-new-guide.md

# 2. Fill out the template (replace [placeholders])

# 3. Verify quality
make lint-md
```

**Full Guide**: See [templates/README.md](templates/README.md) for complete documentation template system guide.

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

### Markdown Quality Standards

All markdown files **must pass linting** before commit:

```bash
# Lint specific file
make lint-md-file FILE="docs/path/to/file.md"

# Lint all markdown files
make lint-md

# Auto-fix issues (review changes carefully)
make lint-md-fix
```

**Workflow**: Create/edit → Lint → Fix violations → Visual inspection → Commit

See [WARP.md](../WARP.md) section "Documentation: Markdown Quality" for complete workflow and rules.

### Structure Guidelines

When adding new documentation:

1. **Choose template** → Use appropriate template from `docs/templates/`
2. **Place correctly** → Follow directory organization above
3. **Use Mermaid** → All diagrams must use Mermaid syntax (see MERMAID_GUIDELINES.md)
4. **Lint before commit** → Run `make lint-md`

**Directory Guidelines:**

- **Development docs** → `docs/development/[category]/`
  - `architecture/` - System architecture and design patterns
  - `guides/` - How-to guides and tutorials  
  - `implementation/` - Implementation plans (move to archived when complete)
  - `infrastructure/` - Docker, CI/CD, deployment
  - `research/` - Active technical research
  - `reviews/` - Code reviews, audits, assessments
  - `testing/` - Testing strategy and guides
- **User-facing docs** → `docs/setup/`, `docs/api/`, or `docs/guides/` (future)
- **Research/decisions** → `docs/research/` (active) or `docs/development/research/`
- **Historical/archived** → `docs/research/archived/`
  - `completed-research/` - Resolved research
  - `implementation-plans/` - Completed plans
  - `reviews/` - Historical reviews

**See also:**

- [templates/README.md](templates/README.md) - Template system guide
- [templates/MERMAID_GUIDELINES.md](templates/MERMAID_GUIDELINES.md) - Diagram standards
- [WARP.md](../WARP.md) - Complete documentation guidelines

---

## 🔗 Quick Links

### Essential Resources

- **[Template System](templates/README.md)** - START HERE for new documentation
- **[Mermaid Guidelines](templates/MERMAID_GUIDELINES.md)** - Diagram standards (REQUIRED)
- [Main README](../README.md) - Project overview
- [WARP.md](../WARP.md) - AI agent rules and project context

### Documentation

- [Development Docs](development/) - Full developer documentation
- [API Flows](api-flows/) - Manual API testing flows
- [Research](research/) - Technical research and decisions

### Testing

- [Testing Strategy](development/testing/strategy.md) - Overall testing approach
- [Testing Guide](development/testing/guide.md) - How to write tests
