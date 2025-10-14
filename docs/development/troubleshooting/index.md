# Troubleshooting

Documentation of critical debugging sessions, issue resolutions, and problem-solving journeys within the Dashtam project.

---

## 📚 Contents

This directory contains detailed troubleshooting guides documenting complex bugs, their investigation, root cause analysis, and final resolutions. Each document provides a complete narrative of the debugging process to help future developers facing similar issues.

---

## 🗂️ Directory Structure

```bash
troubleshooting/
├── index.md
└── [troubleshooting-guides.md]
```

---

## 📄 Documents

### Current Troubleshooting Guides

- [Async Testing Greenlet Errors](async-testing-greenlet-errors.md) - SQLAlchemy async session issues with pytest
- [CI Test Failures - TrustedHost Middleware](ci-test-failures-trustedhost.md) - TestClient blocked by security middleware
- [Test Infrastructure Fixture Errors](test-infrastructure-fixture-errors.md) - Missing fixtures and async test migration issues
- [Environment Directory Docker Mount Issue](env-directory-docker-mount-issue.md) - Docker mount failure when .env is a directory

---

## 🔗 Quick Links

**Related Documentation:**

- [Testing Documentation](../testing/index.md)
- [Infrastructure Documentation](../infrastructure/index.md)
- [Architecture Documentation](../architecture/index.md)

**Template:**

- [Troubleshooting Template](../../templates/troubleshooting-template.md) - Use this template for new troubleshooting guides

---

## 🗺️ Navigation

**Parent Directory:** [Development Documentation](../index.md)

**Related Directories:**

- [Testing](../testing/index.md)
- [Guides](../guides/index.md)
- [Infrastructure](../infrastructure/index.md)

---

## 📝 Contributing

When adding new troubleshooting guides to this directory:

1. Use the [troubleshooting template](../../templates/troubleshooting-template.md)
2. Document the complete debugging journey (symptoms → investigation → solution)
3. Include root cause analysis and lessons learned
4. Update this README with a link and description
5. Run markdown linting: `make lint-md FILE="path/to/file.md"`

---

## Document Information

**Category:** Index/Navigation
**Created:** 2025-01-06
**Last Updated:** 2025-01-06
**Maintainer:** Dashtam Development Team
**Scope:** Troubleshooting and debugging documentation
