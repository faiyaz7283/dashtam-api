# API Flows (Manual Testing)

This section provides end-to-end, HTTPS-first guides for manually testing real user flows against the development environment (TLS-enabled), mirroring production usage as closely as possible.

Goals
- Validate user-centric scenarios (not just single endpoints)
- Enable reproducible, copy-pasteable steps for reviewers and teammates
- Keep a consistent approach across flows and domains

Conventions
- HTTPS-first with curl -k (dev TLS uses self-signed certs)
- Organize by domain (auth, providers, etc.), not HTTP verb
- Each flow document includes:
  - Purpose and prerequisites
  - Step-by-step commands (curl)
  - Expected responses (focused snippets)
  - Cleanup (where applicable)
  - Troubleshooting
- Use shell variables for inputs and never inline secrets in docs
- Quote-safe commands: prefer heredocs + `--data-binary @file` for JSON payloads to avoid shell quoting issues (no dquote> prompts)

Quick start (dev, HTTPS)

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

Directory layout

```
docs/api-flows/
├── README.md                     # Overview and conventions
├── flow-template.md              # Reusable template for new flows
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

## How to add a new flow

- Copy `flow-template.md` into the appropriate subdirectory
- Follow the template structure (Purpose, Prerequisites, Steps, Troubleshooting, Related Flows)
- Keep commands minimal and idempotent where possible
- Include expected HTTP status codes for all responses
- Add token extraction guide if flow involves email tokens
- Prefer small JSON examples focusing on fields testers must validate
- Add comprehensive Troubleshooting section with specific error messages
- Cross-reference related flows (prerequisites and next steps)
