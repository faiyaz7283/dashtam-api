# Research

Technical research, architectural decision records (ADRs), and design comparison documents for the Dashtam project.

## Contents

Ongoing technical investigations, architectural decision records, and design comparisons documenting important decisions about the Dashtam project.

## Directory Structure

```bash
research/
├── authentication-approaches-research.md
├── documentation_guide_research.md
├── index.md
├── smoke-test-design-comparison.md
└── smoke-test-organization-research.md
```

## Documents

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

## Quick Links

**Related Documentation:**

- [Development Documentation](../development/index.md) - Active development guides and architecture
- [Architecture Overview](../development/architecture/overview.md) - System architecture
- Template system for new documents

**External Resources:**

- [Architectural Decision Records (ADR) Template](https://github.com/joelparkerhenderson/architecture-decision-record) - ADR best practices
- [Technical Writing Guidelines](https://developers.google.com/tech-writing) - Google's technical writing courses

## Navigation

**Parent Directory:** [../index.md](../index.md)

**Related Directories:**

- [Development Documentation](../development/index.md) - Guides, architecture, and infrastructure
- [API Flows](../api-flows/index.md) - Manual API testing flows
- Documentation templates

## Contributing

When adding new research documents to this directory:

1. Choose appropriate template for research documents
2. Follow the structure: Context → Problem → Options → Analysis → Decision → Consequences
3. Include links to related implementations or decisions
4. Update this index with link and brief description
5. Run markdown linting: `make lint-md-file FILE="path/to/file.md"`

## Document Information

**Template:** index-section-template.md
**Created:** 2025-10-03
**Last Updated:** 2025-10-21
