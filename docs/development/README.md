# Development Documentation

Documentation for developers working on the Dashtam project.

---

## 📋 Contents

### Architecture
System design, database schema, and API architecture:

- **[System Overview](architecture/overview.md)** - High-level architecture and design decisions
- [Database Schema](architecture/) - Database models and relationships (to be documented)
- [API Design](architecture/) - API design patterns and conventions (to be documented)

### Infrastructure
Docker, environments, and CI/CD:

- **[Docker Setup](infrastructure/docker-setup.md)** - Docker architecture and configuration
- **[Environment Flows](infrastructure/environment-flows.md)** - Dev, test, and production environments
- **[CI/CD Pipeline](infrastructure/ci-cd.md)** - GitHub Actions and automated workflows

### Testing
Testing strategy, guides, and best practices:

- **[Testing Strategy](testing/strategy.md)** - Overall testing approach and philosophy
- **[Testing Guide](testing/guide.md)** - Comprehensive guide for writing tests
- **[Testing Migration](testing/migration.md)** - Migration from async to sync testing

### Development Guides
How-to guides for common development tasks:

- **[Git Workflow Guide](guides/git-workflow.md)** - Complete Git Flow workflow with examples
- **[Git Quick Reference](guides/git-quick-reference.md)** - One-page cheat sheet for Git operations
- [Adding Providers](guides/) - How to integrate new financial providers (to be documented)
- [Database Migrations](guides/) - Managing database schema changes (to be documented)

---

## 🚀 Quick Start for New Developers

1. **Read the [System Overview](architecture/overview.md)** to understand the architecture
2. **Set up your environment** using [Docker Setup](infrastructure/docker-setup.md)
3. **Learn the testing approach** from the [Testing Guide](testing/guide.md)
4. **Review [WARP.md](../../WARP.md)** for project rules and conventions

---

## 📦 Related Documentation

- [Research & Decisions](../research/) - Technical research and decision records
- [Testing Guide](../../tests/TESTING_GUIDE.md) - Quick testing reference
- [Main README](../../README.md) - Project overview
