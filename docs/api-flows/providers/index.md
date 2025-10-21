# Provider Flows

Provider integration and management API testing workflows. These flows demonstrate financial institution onboarding, OAuth authorization, and account disconnection.

## Contents

End-to-end provider management workflows designed for manual API testing against the development HTTPS server. Each flow covers a specific provider integration journey with step-by-step curl commands and expected responses.

## Directory Structure

```bash
providers/
├── index.md
├── provider-disconnect.md
└── provider-onboarding.md
```

## Documents

### Provider Management Flows

- [Provider Onboarding](provider-onboarding.md) - Complete Charles Schwab provider registration, OAuth authorization, and token storage workflow
- [Provider Disconnect](provider-disconnect.md) - Provider disconnection workflow with token cleanup and account removal

## 🔗 Quick Links

**Related Documentation:**

- [System Architecture](../../development/architecture/overview.md) - System design and provider architecture
- [Token Rotation Guide](../../development/guides/token-rotation.md) - OAuth token rotation and refresh
- [Testing Strategy](../../development/testing/strategy.md) - Testing approaches and patterns

**Provider Documentation:**

- [Charles Schwab OAuth](https://developer.schwab.com/products/marketplace/documentation) - Schwab OAuth implementation guide
- [OAuth 2.0 RFC 6749](https://tools.ietf.org/html/rfc6749) - OAuth 2.0 authorization framework

## 🗺️ Navigation

**Parent Directory:** [API Flows](../index.md)

**Related Directories:**

- [Authentication Flows](../auth/index.md) - User authentication and account management
- [API Flows Index](../index.md) - All manual API testing flows

**Other Documentation:**

- [Development Guide](../../development/index.md) - Developer documentation
- [Infrastructure Guide](../../development/infrastructure/docker-setup.md) - Docker and environment setup

## 📝 Contributing

When adding new provider flows to this directory:

1. Follow the appropriate [API flow template](../../templates/api-flow-template.md)
2. Use HTTPS with self-signed certificates (dev TLS) - Use `curl -k` for development
3. Document all OAuth steps and token flows
4. Include prerequisites (provider credentials, environment variables)
5. Provide complete curl commands with expected responses
6. Include error scenarios and troubleshooting steps
7. Update this index with a link and brief description
8. Run markdown linting: `make lint-md-file FILE="path/to/file.md"`

---

## Document Information

**Template:** [index-section-template.md](../../templates/index-section-template.md)
**Created:** 2025-10-15
**Last Updated:** 2025-10-21
