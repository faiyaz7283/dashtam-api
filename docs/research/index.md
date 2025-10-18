# Research & Decision Records

Technical research, architectural decision records (ADRs), and migration documentation for the Dashtam project.

---

## 📚 Contents

This directory contains:

- **Active Research**: Ongoing technical investigations and findings
- **Architectural Decisions**: Records of significant technical decisions
- **Design Comparisons**: Analysis of implementation patterns and approaches
- **Archived Research**: Completed research preserved for historical reference

---

## 🗂️ Directory Structure

```bash
research/
├── authentication-approaches-research.md
├── documentation_guide_research.md
├── smoke-test-design-comparison.md
├── smoke-test-organization-research.md
├── archived/
│   ├── implementation-plans/
│   │   ├── jwt-auth-implementation-plan.md
│   │   ├── authentication-implementation.md
│   │   └── rest-api-compliance-implementation-plan.md
│   ├── reviews/
│   │   ├── rest-api-compliance-review.md
│   │   └── comprehensive-review-2025-10-03.md
│   ├── completed-research/
│   │   ├── async-testing.md
│   │   ├── infrastructure-migration.md
│   │   ├── test-infrastructure-fix-summary.md
│   │   ├── test-coverage-plan.md
│   │   ├── migration.md
│   │   ├── CI_DEBUGGING_ANALYSIS.md
│   │   └── MAKEFILE_IMPROVEMENTS.md
│   ├── phase-3-handoff.md
│   ├── phase-3-progress.md
│   ├── env-file-fix.md
│   ├── documentation-organization-plan.md
│   └── docs-reorganization-summary.md
└── index.md  # This file
```

---

## 📄 Documents

### Active Research

Current technical investigations and decision-making documents:

- **[Authentication Approaches Research](authentication-approaches-research.md)** - Comprehensive comparison of 6 authentication methods (1,010 lines)
  - JWT, Sessions, OAuth, Passkeys, Magic Links, Social Auth
  - Industry analysis, user preferences, compliance requirements
  - ✅ Decision: JWT + Refresh Tokens (implemented)

- **[Smoke Test Design Comparison](smoke-test-design-comparison.md)** - Monolithic vs modular smoke test design analysis
  - Design pattern comparison for CI/CD visibility
  - Test isolation and debugging experience
  - ✅ Decision: Modular design with 18 separate test functions

- **[Smoke Test Organization & SSL/TLS Research](smoke-test-organization-research.md)** - Test organization patterns and SSL/TLS in testing
  - Smoke test location best practices (85% projects use `tests/` directory)
  - SSL/TLS production parity (pytest + HTTPS everywhere)
  - CI/CD integration patterns
  - ✅ Decision: pytest-based smoke tests with SSL/TLS everywhere (implemented)

- **[Documentation Guide Research](documentation_guide_research.md)** - Documentation standards and template system research
  - Template-based documentation approach
  - Markdown quality standards
  - Mermaid diagram requirements

### Archived Research

Completed research, implementation plans, and historical documents preserved for reference.

#### Implementation Plans (✅ Completed)

- [JWT Auth Implementation Plan](archived/implementation-plans/jwt-auth-implementation-plan.md) - Complete JWT authentication implementation guide
- [Authentication Implementation Guide](archived/implementation-plans/authentication-implementation.md) - User authentication system implementation
- [REST API Compliance Implementation Plan](archived/implementation-plans/rest-api-compliance-implementation-plan.md) - RESTful API migration plan

#### Historical Reviews

- [REST API Compliance Review](archived/reviews/rest-api-compliance-review.md) - Initial REST API audit
- [Comprehensive Review 2025-10-03](archived/reviews/comprehensive-review-2025-10-03.md) - Project-wide technical review

#### Completed Research & Fixes (✅ Resolved)

- [Async Testing Research](archived/completed-research/async-testing.md) - Synchronous testing strategy decision
- [Infrastructure Migration](archived/completed-research/infrastructure-migration.md) - Docker refactoring completion
- [Test Infrastructure Fix Summary](archived/completed-research/test-infrastructure-fix-summary.md) - Test environment fixes
- [Test Coverage Plan](archived/completed-research/test-coverage-plan.md) - 76% coverage achievement plan
- [Testing Migration](archived/completed-research/migration.md) - Test suite migration notes
- [CI Debugging Analysis](archived/completed-research/CI_DEBUGGING_ANALYSIS.md) - CI/CD troubleshooting
- [Makefile Improvements](archived/completed-research/MAKEFILE_IMPROVEMENTS.md) - Build system enhancements

#### Earlier Archives

- [Phase 3 Handoff](archived/phase-3-handoff.md) - Development phase transition notes
- [Phase 3 Progress](archived/phase-3-progress.md) - Phase 3 milestone tracking
- [Environment File Fix](archived/env-file-fix.md) - Environment configuration fixes
- [Documentation Organization Plan](archived/documentation-organization-plan.md) - Documentation restructuring plan
- [Docs Reorganization Summary](archived/docs-reorganization-summary.md) - Documentation migration summary

---

## 🔗 Quick Links

**Related Documentation:**

- [Development Documentation](../development/index.md) - Active development guides and architecture
- [Testing Documentation](../development/testing/) - Testing strategy and implementation
- [Architecture Overview](../development/architecture/overview.md) - System architecture
- [Documentation Templates](../templates/README.md) - Template system for new documents

**External Resources:**

- [Architectural Decision Records (ADR) Template](https://github.com/joelparkerhenderson/architecture-decision-record) - ADR best practices
- [Research Documentation Guide](https://www.writethedocs.org/) - Documentation standards
- [Technical Writing Guidelines](https://developers.google.com/tech-writing) - Google's technical writing courses

---

## 🗺️ Navigation

**Parent Directory:** [Documentation Root](../index.md)

**Related Directories:**

- [Development Documentation](../development/index.md) - Guides, architecture, and infrastructure
- [API Flows](../api-flows/index.md) - Manual API testing flows
- [Templates](../templates/README.md) - Documentation templates

---

## 📝 Contributing

### When to Add Research Documents

Add new research documents when:

- **Technical Investigation**: Researching new technologies, patterns, or approaches
- **Architectural Decisions**: Making significant technical or design decisions
- **Design Comparisons**: Analyzing multiple implementation options
- **Migration Planning**: Planning major refactoring or system changes

### Document Creation Process

1. **Choose Template**: Use [research-template.md](../templates/research-template.md) for new research documents
2. **Follow Structure**: Include context, problem statement, options, analysis, decision, consequences
3. **Add to Index**: Update this index.md with link and brief description
4. **Run Linting**: Ensure markdown quality: `make lint-md-file FILE="docs/research/filename.md"`
5. **Update WARP.md**: If the decision impacts project rules or standards

### When to Archive

Move documents to `archived/` when:

- ✅ The research has led to implementation and is complete
- ✅ The migration is finished and validated
- ✅ The document serves only as historical reference
- ✅ The information is captured in active documentation (guides, architecture docs)

Keep documents active when:

- ⏳ Research is ongoing or decision is being implemented
- ⏳ Future reference is needed for similar work
- ⏳ The document informs current development decisions

---

## Document Information

**Category:** Index/Navigation
**Created:** 2025-09-15
**Last Updated:** 2025-10-18
**Maintainer:** Development Team
**Scope:** Research directory navigation and organization guide
