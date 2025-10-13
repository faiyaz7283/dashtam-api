# Research & Decision Records

This directory contains technical research, architectural decision records (ADRs), and migration documentation.

---

## 📚 Active Research Documents

### Authentication Research

- **[Authentication Approaches Research](authentication-approaches-research.md)** - Comprehensive comparison of 6 auth methods (1,010 lines)
  - JWT, Sessions, OAuth, Passkeys, Magic Links, Social Auth
  - Industry analysis, user preferences, compliance requirements
  - ✅ Decision: JWT + Refresh Tokens (implemented)

---

## 📦 Archived Documents

Completed research, implementation plans, and historical documents in **[archived/](archived/)**:

### Implementation Plans (✅ Completed)

- [JWT Auth Implementation Plan](archived/implementation-plans/jwt-auth-implementation-plan.md)
- [Authentication Implementation Guide](archived/implementation-plans/authentication-implementation.md)
- [REST API Compliance Implementation Plan](archived/implementation-plans/rest-api-compliance-implementation-plan.md)

### Historical Reviews

- [REST API Compliance Review](archived/reviews/rest-api-compliance-review.md)
- [Comprehensive Review 2025-10-03](archived/reviews/comprehensive-review-2025-10-03.md)

### Completed Research & Fixes (✅ Resolved)

- [Async Testing Research](archived/completed-research/async-testing.md)
- [Infrastructure Migration](archived/completed-research/infrastructure-migration.md)
- [Test Infrastructure Fix Summary](archived/completed-research/test-infrastructure-fix-summary.md)
- [Test Coverage Plan](archived/completed-research/test-coverage-plan.md) - 76% coverage achieved
- [Testing Migration](archived/completed-research/migration.md)
- [CI Debugging Analysis](archived/completed-research/CI_DEBUGGING_ANALYSIS.md)
- [Makefile Improvements](archived/completed-research/MAKEFILE_IMPROVEMENTS.md)

### Earlier Archives

- [Phase 3 Handoff](archived/phase-3-handoff.md)
- [Phase 3 Progress](archived/phase-3-progress.md)
- [Environment File Fix](archived/env-file-fix.md)
- [Documentation Organization Plan](archived/documentation-organization-plan.md)
- [Docs Reorganization Summary](archived/docs-reorganization-summary.md)

---

## 📝 Purpose of This Directory

### Research Documents

- **Purpose**: Document technical investigations and findings
- **Audience**: Developers making architectural decisions
- **When to add**: When researching new technologies, patterns, or approaches

### Decision Records

- **Purpose**: Record significant architectural and technical decisions
- **Format**: Problem statement, options considered, decision made, consequences
- **When to add**: After making important technical decisions

### Migration Documentation

- **Purpose**: Document completed or planned migrations
- **Includes**: Motivation, approach, steps, validation
- **When to add**: When planning or completing major refactoring/migrations

---

## 🗂️ When to Archive

Move documents to `archived/` when:

- ✅ The research has led to implementation
- ✅ The migration is complete
- ✅ The document is historical reference only
- ✅ The information is captured in active documentation

Keep documents active when:

- ⏳ Research is ongoing
- ⏳ Decision is being implemented
- ⏳ Future reference is needed for similar work

---

## 🔗 Related Documentation

- [Development Documentation](../development/) - Active development guides
- [Testing Documentation](../development/testing/) - Testing implementation
- [Architecture Overview](../development/architecture/overview.md) - Current architecture
