# Dashtam Documentation

Welcome to the Dashtam documentation! This directory contains all documentation for the project, organized by audience and purpose.

---

## 📚 Documentation Structure

### For Developers
Documentation for working **on** the Dashtam project:

- **[Development Guide](development/)** - Architecture, infrastructure, and testing
  - [Architecture Overview](development/architecture/overview.md)
  - [Docker Setup](development/infrastructure/docker-setup.md)
  - [Testing Strategy](development/testing/strategy.md)
  - [Testing Guide](development/testing/guide.md)

### Research & Decisions
Historical research, architectural decisions, and migration notes:

- **[Research Notes](research/)** - Technical research and decision records
  - [Async Testing Research](research/async-testing.md)
  - [Infrastructure Migration](research/infrastructure-migration.md)
  - [Test Coverage Plan](research/test-coverage-plan.md)
  - [Archived Documents](research/archived/)

### For Users (Coming Soon)
Documentation for using the Dashtam application:

- **[Setup Guides](setup/)** - Installation and configuration (to be added)
- **[API Documentation](api/)** - API endpoints and usage (to be added)
- **[User Guides](guides/)** - OAuth flow, troubleshooting, etc. (to be added)

---

## 🗂️ Directory Organization

```
docs/
├── development/        # Developer documentation
│   ├── architecture/   # System architecture and design
│   ├── infrastructure/ # Docker, CI/CD, environments
│   ├── testing/        # Testing strategy and guides
│   └── guides/         # Development how-tos
│
├── research/           # Research and decision records
│   └── archived/       # Historical documents
│
├── setup/              # User setup guides (future)
├── api/                # API documentation (future)
└── guides/             # User guides (future)
```

---

## 📝 Contributing to Documentation

When adding new documentation, follow this structure:

- **Development docs** → `docs/development/[category]/`
- **User-facing docs** → `docs/setup/`, `docs/api/`, or `docs/guides/`
- **Research/decisions** → `docs/research/`
- **Historical/archived** → `docs/research/archived/`

See [WARP.md](../WARP.md) for complete documentation guidelines.

---

## 🔗 Quick Links

- [Main README](../README.md) - Project overview
- [WARP.md](../WARP.md) - AI agent rules and project context
- [Testing Guide](../tests/TESTING_GUIDE.md) - Quick testing reference
- [Development Docs](development/) - Full developer documentation
