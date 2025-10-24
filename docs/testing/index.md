# Testing

Comprehensive testing strategy, guides, and best practices for the Dashtam project.

## Contents

This directory contains testing documentation covering strategy, implementation guides, best practices, and quality standards for unit, integration, and end-to-end tests.

## Directory Structure

```bash
testing/
├── strategy.md                      # Comprehensive testing strategy and approach
└── index.md                         # This file
```

## Documents

### Core Testing Documentation

- [Testing Strategy](strategy.md) - Comprehensive testing strategy covering all test types
  - **Current Coverage:** 76% (295 tests passing)
  - Unit tests (70% of total)
  - Integration tests (20% of total)
  - End-to-end smoke tests (10% of total)
  - Test pyramid approach and patterns
  - FastAPI TestClient synchronous testing
  - Fixtures, mocks, and test utilities
  - Troubleshooting and common issues
  - Target coverage goal: 85%

### Related Development Guides

For detailed implementation guidance, see:

- [Testing Guide](../development/guides/testing-guide.md) - Comprehensive how-to guide with examples
- [Testing Best Practices](../development/guides/testing-best-practices.md) - Testing patterns and conventions
- [Test Docstring Standards](../development/guides/test-docstring-standards.md) - Test documentation standards

### Test Infrastructure

- [Smoke Tests](../development/troubleshooting/smoke-test-caplog-solution.md) - End-to-end authentication flow tests
- [Test Infrastructure Guide](../development/guides/testing-guide.md) - Setting up test environment
- [Async Testing Decision](../development/architecture/async-testing-decision.md) - Synchronous testing ADR

## Quick Links

**Implementation Guides:**

- [Testing Guide](../development/guides/testing-guide.md) - Step-by-step testing tutorial
- [Testing Best Practices](../development/guides/testing-best-practices.md) - Patterns and conventions
- [Docstring Standards for Tests](../development/guides/test-docstring-standards.md) - Test documentation

**Architecture & Strategy:**

- [Async Testing Decision](../development/architecture/async-testing-decision.md) - Synchronous testing design decision
- [Testing Strategy](strategy.md) - Complete testing approach

**External Resources:**

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [SQLModel Testing](https://sqlmodel.tiangolo.com/tutorial/testing/)
- [Coverage.py](https://coverage.readthedocs.io/)

## Navigation

**Parent Directory:** [../index.md](../index.md)

**Related Directories:**

- [Development Guides](../development/guides/index.md) - How-to guides and tutorials
- [Architecture](../development/architecture/index.md) - System design decisions
- [Troubleshooting](../development/troubleshooting/index.md) - Problem diagnosis and solutions

**Development Documentation:**

- [Development Index](../development/index.md) - All development documentation
- `README.md` (project root) - Project overview

## Contributing

When adding new testing documentation to this directory:

1. Use  for testing documentation
2. Cover both strategy and implementation details
3. Include code examples and test patterns
4. Document test setup, execution, and verification
5. Link to related architecture decisions
6. Update this index with link and brief description
7. Run markdown linting: `make lint-md FILE="path/to/file.md"`

### Testing Documentation Guidelines

- Document new testing patterns as they're discovered
- Keep patterns consistent with testing-best-practices.md
- Include both passing and failing test examples
- Document fixtures and utilities clearly
- Link to architecture decisions that impact testing
- Include troubleshooting sections for common issues

---

## Document Information

**Template:** index-section-template.md
**Created:** 2025-10-03
**Last Updated:** 2025-10-21
