# API Flows

Manual API testing workflows for the Dashtam platform, organized by domain and user journey. All flows use HTTPS with self-signed certificates in development environments, mirroring production usage.

## Contents

End-to-end testing flows for authentication, token management, and provider integration. Each flow provides step-by-step curl commands for manual testing against a running development environment.

## Directory Structure

```bash
api-flows/
├── auth/
│   ├── complete-auth-flow.md
│   ├── email-verification.md
│   ├── index.md
│   ├── login.md
│   ├── password-reset.md
│   └── registration.md
├── providers/
│   ├── index.md
│   ├── provider-disconnect.md
│   └── provider-onboarding.md
└── index.md
```

## Documents

### Authentication Flows

Complete authentication workflows for user management:

- [User Registration](auth/registration.md) - Register new user with email verification
- [Email Verification](auth/email-verification.md) - Verify email address with token
- [User Login](auth/login.md) - Login, token management, and logout
- [Password Reset](auth/password-reset.md) - Forgot password workflow
- [Complete Auth Flow](auth/complete-auth-flow.md) - End-to-end authentication testing

### Provider Flows

Financial provider integration workflows:

- [Provider Onboarding](providers/provider-onboarding.md) - OAuth setup and connection
- [Provider Disconnect](providers/provider-disconnect.md) - Provider disconnection

## Quick Links

**Related Documentation:**

 - Template for creating new API flows
 - Complete template documentation
- [Development Guide](../development/index.md) - Developer documentation
- [Testing Strategy](../testing/strategy.md) - Overall testing approach

**External Resources:**

- [curl Documentation](https://curl.se/docs/) - HTTP client reference
- [HTTP Status Codes](https://httpstatuses.com/) - Status code reference
- [JWT.io](https://jwt.io/) - JWT token decoder

## Navigation

**Parent Directory:** [../index.md](../index.md)

**Related Directories:**

- [Development Documentation](../development/index.md)
- [Testing](../testing/index.md)

## Contributing

When adding new API flow documents:

1. Copy the
2. Place in appropriate subdirectory (auth/ or providers/)
3. Follow established conventions and structure
4. Update this index with link and description
5. Run markdown linting: `make lint-md-file FILE="path/to/file.md"`

### Flow Creation Guidelines

- Organize by domain (auth, providers) not HTTP verb
- Each flow represents a complete user journey
- Include Purpose, Prerequisites, Steps, and Troubleshooting
- Use HTTPS-first approach with `curl -k` for dev TLS
- Include expected HTTP status codes for all responses
- Add token extraction guides for email-based flows
- Cross-reference related flows and prerequisites

---

## Document Information

**Template:** index-section-template.md
**Created:** 2025-10-15
**Last Updated:** 2025-10-21
