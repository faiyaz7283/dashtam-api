# Authentication Flows

User authentication and account management API testing workflows. These flows demonstrate the complete user journey from registration through logout, including email verification, login, password reset, and profile management.

## Contents

End-to-end authentication workflows designed for manual API testing against the development HTTPS server. Each flow covers a specific user journey with step-by-step curl commands and expected responses.

## Directory Structure

```bash
auth/
├── complete-auth-flow.md
├── email-verification.md
├── index.md
├── login.md
├── password-reset.md
└── registration.md
```

## Documents

### Core Authentication Flows

- [Registration](registration.md) - Complete user registration workflow with validation and error cases
- [Email Verification](email-verification.md) - Email token verification and account activation
- [Login](login.md) - User login with JWT access and opaque refresh token generation
- [Password Reset](password-reset.md) - Password reset request and confirmation workflow

### Complete Workflows

- [Complete Auth Flow](complete-auth-flow.md) - End-to-end authentication journey from registration through logout, including token refresh, password reset, and profile updates

## 🔗 Quick Links

**Related Documentation:**

- [JWT Authentication Architecture](../../development/architecture/jwt-authentication.md) - Authentication system design
- [JWT Auth Quick Reference](../../development/guides/jwt-auth-quick-reference.md) - JWT patterns and usage
- [JWT Authentication API Guide](../../development/guides/jwt-authentication-api-guide.md) - API endpoint reference

**External Resources:**

- [OAuth 2.0 RFC 6749](https://tools.ietf.org/html/rfc6749) - OAuth 2.0 authorization framework
- [JWT RFC 7519](https://tools.ietf.org/html/rfc7519) - JSON Web Token standard
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) - FastAPI authentication patterns

## 🗺️ Navigation

**Parent Directory:** [API Flows](../index.md)

**Related Directories:**

- [Provider Flows](../providers/index.md) - Provider onboarding and management flows
- [API Flows Index](../index.md) - All manual API testing flows

**Other Documentation:**

- [Development Guide](../../development/index.md) - Developer documentation
- [Testing Strategy](../../testing/strategy.md) - Testing approach and patterns

## Contributing

When adding new authentication flows to this directory:

1. Follow the appropriate [API flow template](../../templates/api-flow-template.md)
2. Use HTTPS with self-signed certificates (dev TLS) - Use `curl -k` for development
3. Include prerequisite steps and cleanup where applicable
4. Use environment variables for sensitive data (no real secrets)
5. Provide complete curl commands with expected responses
6. Update this index with a link and brief description
7. Run markdown linting: `make lint-md-file FILE="path/to/file.md"`

---

## Document Information

**Template:** [index-section-template.md](../../templates/index-section-template.md)
**Created:** 2025-10-15
**Last Updated:** 2025-10-21
