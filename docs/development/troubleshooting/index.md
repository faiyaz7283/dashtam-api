# Troubleshooting

Documentation of critical debugging sessions, issue resolutions, and problem-solving journeys within the Dashtam project. Each troubleshooting guide provides a complete narrative from symptom discovery through investigation to final resolution.

## Contents

This directory contains detailed troubleshooting guides documenting complex bugs, their investigation, root cause analysis, and final resolutions. These guides serve as a knowledge base for future developers facing similar issues, preserving critical debugging insights and solution patterns.

**What's Here:**

- Async/await and database session issues
- CI/CD pipeline debugging and fixes
- Test infrastructure problems and solutions
- Docker and environment configuration issues

## Directory Structure

```bash
troubleshooting/
├── index.md                                      # This file
├── async-testing-greenlet-errors.md              # SQLAlchemy async session issues
├── ci-test-failures-trustedhost.md               # CI security middleware blocking
├── env-directory-docker-mount-issue.md           # Docker mount configuration fix
├── test-infrastructure-fixture-errors.md         # Pytest fixture resolution
├── smoke-test-caplog-solution.md                 # Smoke test token extraction
└── smoke-test-ci-debugging-journey.md            # CI smoke test debugging
```

## Documents

### Database and Async Issues

**[Async Testing Greenlet Errors](async-testing-greenlet-errors.md)**

- **Problem**: SQLAlchemy async session issues with pytest
- **Root Cause**: Improper async/await patterns in database operations
- **Solution**: Synchronous testing strategy with FastAPI TestClient
- **Impact**: Resolved greenlet_spawn errors, established testing foundation

### CI/CD and Infrastructure Issues

**[CI Test Failures - TrustedHost Middleware](ci-test-failures-trustedhost.md)**

- **Problem**: TestClient blocked by TrustedHostMiddleware in CI
- **Root Cause**: Missing "testserver" in ALLOWED_HOSTS configuration
- **Solution**: Add "testserver" to allowed hosts for test environments
- **Impact**: All CI tests passing, proper security middleware configuration

**[Environment Directory Docker Mount Issue](env-directory-docker-mount-issue.md)**

- **Problem**: Docker mount failure when .env is a directory
- **Root Cause**: Directory created at .env path instead of file
- **Solution**: Remove directory, use proper .env file structure
- **Impact**: Proper environment variable loading in all containers

### Testing Infrastructure Issues

**[Test Infrastructure Fixture Errors](test-infrastructure-fixture-errors.md)**

- **Problem**: Missing fixtures and async test migration issues
- **Root Cause**: Incomplete migration from async to sync test patterns
- **Solution**: Proper fixture organization and synchronous patterns
- **Impact**: Stable test infrastructure, 295+ tests passing

**[Smoke Test Caplog Solution](smoke-test-caplog-solution.md)**

- **Problem**: Token extraction in smoke tests without Docker CLI
- **Root Cause**: Need environment-agnostic token capture method
- **Solution**: Use pytest's caplog fixture for log-based extraction
- **Impact**: Smoke tests work in dev, test, and CI environments

**[Smoke Test CI Debugging Journey](smoke-test-ci-debugging-journey.md)**

- **Problem**: Smoke tests failing in CI but passing locally
- **Root Cause**: Timing issues and container startup order
- **Solution**: Proper health checks and retry logic
- **Impact**: 22/23 smoke tests passing in CI (96% success rate)

## Quick Links

**Related Documentation:**

- [Testing Documentation](../../testing/index.md) - Testing strategy and guides
- [Infrastructure Documentation](../infrastructure/index.md) - Docker, CI/CD setup
- [Architecture Documentation](../architecture/index.md) - System design and patterns

**Templates:**

- Troubleshooting Template: troubleshooting-template.md (located in docs/templates/) - Use for new troubleshooting guides
- Template README: README.md (located in docs/templates/) - Documentation template system

**External Resources:**

- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest Fixtures Documentation](https://docs.pytest.org/en/stable/explanation/fixtures.html)

## Navigation

**Parent Directory:** [../index.md](../index.md)

**Related Directories:**

- [Testing](../../testing/index.md) - Test strategy and implementation
- [Guides](../guides/index.md) - How-to guides and tutorials
- [Infrastructure](../infrastructure/index.md) - Docker and CI/CD
- [Architecture](../architecture/index.md) - System design

## Contributing

When adding new troubleshooting guides to this directory:

1. **Use the template**: Start with troubleshooting-template.md (located in docs/templates/)
2. **Document the journey**: Include symptoms → investigation → root cause → solution
3. **Add context**: Explain why the issue occurred and how to prevent it
4. **Include evidence**: Screenshots, logs, code snippets showing the problem
5. **Share lessons learned**: What did this teach us about the system?
6. **Update this index**: Add your new guide to the appropriate section above
7. **Run linting**: Verify with `make lint-md FILE="path/to/file.md"`

---

## Document Information

**Template:** index-section-template.md
**Created:** 2025-01-06
**Last Updated:** 2025-10-21
