# API Flows (Manual Testing)

This section provides end-to-end, HTTPS-first guides for manually testing real user flows against the development environment (TLS-enabled), mirroring production usage as closely as possible.

## 📚 Contents

Comprehensive manual testing flows for the Dashtam API, organized by domain and user journey. All flows use HTTPS with self-signed certificates for development environment testing.

## 🗂️ Directory Structure

```bash
api-flows/
├── auth/
│   ├── registration.md           # User registration flow
│   ├── email-verification.md     # Email verification process
│   ├── login.md                  # Login and token management
│   ├── password-reset.md         # Password reset flow
│   └── complete-auth-flow.md     # End-to-end authentication
├── providers/
│   ├── provider-onboarding.md    # Provider OAuth setup
│   └── provider-refresh.md       # Token refresh flow
└── index.md                      # This file
```

**Quick start (dev, HTTPS):**

```bash
# From repo root
make dev-up

# Environment variables for curl (dev TLS)
BASE_URL=https://localhost:8000
CALLBACK_URL=https://127.0.0.1:8182

# Example test credentials (adjust per flow)
TEST_EMAIL='tester+'$(date +%s)'@example.com'
TEST_PASSWORD='SecurePass123!'
```

**Directory layout:**

```bash
docs/api-flows/
├── README.md                     # Overview and conventions
├── auth/
│   ├── registration.md           # Register a new user (HTTPS)
│   ├── email-verification.md     # Verify email address
│   ├── login.md                  # Login + use tokens + logout (HTTPS)
│   ├── password-reset.md         # Reset forgotten password
│   └── complete-auth-flow.md     # End-to-end smoke test (all auth steps)
└── providers/
    ├── provider-onboarding.md    # Create provider → OAuth → verify connection
    └── provider-disconnect.md    # Disconnect and remove provider
```

## Development: Email Token Extraction

**Important for dev/test/CI environments:**

In development mode (`DEBUG=True`), the `EmailService` automatically operates in "development mode" - emails are **logged to console** instead of being sent via AWS SES.

**How to extract tokens from logs:**

```bash
# View recent email logs
docker logs dashtam-dev-app --tail 100 2>&1 | grep -A 20 '📧 EMAIL'

# Look for verification/reset tokens in URLs like:
# https://localhost:3000/verify-email?token=YOUR_TOKEN_HERE

# Extract and use the token
export VERIFICATION_TOKEN="<token-from-logs>"
```

**Why this works**: No AWS credentials needed in dev! The system automatically detects `DEBUG=True` and logs emails with full content including tokens.

**Applies to**:

- Email verification tokens (registration flow)
- Password reset tokens (password reset flow)

See individual flows for detailed examples.

## Expected HTTP Status Codes

All flows document expected HTTP status codes in responses:

- **200 OK**: Successful GET/PATCH/DELETE
- **201 Created**: Successful POST (resource created)
- **202 Accepted**: Async operation accepted (e.g., password reset email)
- **400 Bad Request**: Invalid input or business logic error
- **401 Unauthorized**: Missing/invalid/expired authentication
- **403 Forbidden**: Valid auth but insufficient permissions
- **404 Not Found**: Resource doesn't exist
- **409 Conflict**: Duplicate resource (e.g., email already registered)
- **422 Validation Error**: Request payload validation failed

## Important: Logout Behavior

When users logout, **only the refresh token is immediately revoked**. JWT access tokens remain valid until expiration (~30 minutes).

This is **correct behavior** for stateless JWT architecture (Pattern A - industry standard).

**See**: [JWT Authentication - Logout Behavior](../development/architecture/jwt-authentication.md#flow-5-logout) for detailed explanation.

## 📝 Documents

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
- [Provider Token Refresh](providers/provider-refresh.md) - Token refresh and rotation


## 🔗 Quick Links

**Related Documentation:**

- [API Flow Template](../templates/api-flow-template.md) - Template for creating new API flows
- [Template System Guide](../templates/README.md) - Complete template documentation
- [Development Guide](../development/) - Developer documentation
- [Testing Strategy](../testing/strategy.md) - Overall testing approach

**External Resources:**

- [curl Documentation](https://curl.se/docs/) - HTTP client reference
- [HTTP Status Codes](https://httpstatuses.com/) - Status code reference
- [JWT.io](https://jwt.io/) - JWT token decoder


## 🗺️ Navigation

**Parent Directory:** [../index.md](../index.md)

**Related Directories:**

- [Development Documentation](../development/index.md)
- [Templates](../templates/README.md)
- [Testing](../testing/)


## 📝 Contributing

When adding new API flow documents:

1. Copy the [API Flow Template](../templates/api-flow-template.md)
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

**Template:** [index-template.md](../templates/index-template.md)
**Created:** 2025-10-15
**Last Updated:** 2025-10-15
