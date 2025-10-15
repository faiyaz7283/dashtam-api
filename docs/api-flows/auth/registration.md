# Registration (HTTPS, Dev)

Register a new user using the HTTPS-enabled development environment.

---

## Table of Contents

- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Steps](#steps)
  - [1) Register](#1-register)
  - [2) Extract verification token from logs](#2-extract-verification-token-from-logs)
- [Next Step](#next-step)
- [Cleanup](#cleanup-optional)
- [Troubleshooting](#troubleshooting)
- [Related Flows](#related-flows)

## Purpose

Create a new user account that can later be verified and used to log in.

## Prerequisites

- Dev environment is running with TLS
- Shell variables exported

```bash
make dev-up
BASE_URL=https://localhost:8000
TEST_EMAIL='tester+'$(date +%s)'@example.com'
TEST_PASSWORD='SecurePass123!'
```

## Steps

### 1) Register

```bash
# Quote-safe JSON via heredoc
cat <<JSON >/tmp/register.json
{
  "email": "$TEST_EMAIL",
  "password": "$TEST_PASSWORD",
  "name": "Test User"
}
JSON

curl -sk -X POST "$BASE_URL/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/register.json | python3 -m json.tool
```

**Expected Response (HTTP 201 Created):**

```json
{
  "message": "Registration successful. Please check your email to verify your account."
}
```

**Optional: Inline (no heredoc):**

```bash
curl -sk -X POST "$BASE_URL/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"name\":\"Test User\"}" \
  | python3 -m json.tool
```

### 2) Extract verification token from logs

In development mode (`DEBUG=True`), emails are logged to console instead of being sent via AWS SES. Extract the verification token:

```bash
# View recent email logs
docker logs dashtam-dev-app --tail 100 2>&1 | grep -A 20 '📧 EMAIL'
```

**You'll see output like:**

```log
📧 EMAIL (Development Mode - Not Sent)
================================================================================
From: Dashtam <noreply@dashtam.com>
To: tester+1234567890@example.com
Subject: Verify Your Dashtam Account
--------------------------------------------------------------------------------
Text Body:
Hi Test User,

Thank you for signing up for Dashtam...

To complete your registration, please visit:
https://localhost:3000/verify-email?token=vYaGSkz80Qoi86hR78lPyKt6zIp8LDoj13TiheZzjLk
================================================================================
```

**Extract the token:**

```bash
# Copy the token from the URL in the logs
export VERIFICATION_TOKEN="vYaGSkz80Qoi86hR78lPyKt6zIp8LDoj13TiheZzjLk"

# Verify it's set
echo "Verification token: $VERIFICATION_TOKEN"
```

**Why this works**: The `EmailService` automatically operates in development mode when `DEBUG=True`, logging all emails with full content including verification tokens.

## Next Step

✅ **Continue to:** [Email Verification Flow](email-verification.md) to verify your email and activate the account.

## Cleanup (optional)

```bash
# Users cannot be deleted via API yet (future admin endpoint)
# For now, test users remain in the database
```

## Troubleshooting

- **400 Bad Request - "Email already registered":**
  - Use a fresh email address with timestamp: `TEST_EMAIL='tester+'$(date +%s)'@example.com'`
- **400 Bad Request - Password validation:** Ensure password has:
  - At least 8 characters
  - 1 uppercase letter (A-Z)
  - 1 lowercase letter (a-z)
  - 1 digit (0-9)
  - 1 special character (!@#$%^&*)
- **422 Validation Error:** Check JSON payload format and required fields (email, password, name)
- **SSL certificate errors:** Use `-k` flag with curl to accept self-signed dev certificates
- **Token not appearing in logs:**
  - Ensure dev environment is running: `make dev-status`
  - Check logs are streaming: `make dev-logs`
  - Verify DEBUG=true in `env/.env.dev`

## Related Flows

- **Next step:** [Email Verification](email-verification.md) - Verify the email address with extracted token
- **Complete flow:** [Complete Auth Flow](complete-auth-flow.md) - End-to-end authentication testing
- **After verification:** [Login](login.md) - Authenticate with verified credentials
- **Architecture:** [JWT Authentication](../../development/architecture/jwt-authentication.md) - Understanding the auth system

---

## Document Information

**Category:** API Flow  
**Created:** 2025-10-15  
**Last Updated:** 2025-10-15  
**API Version:** v1  
**Environment:** Development (HTTPS with self-signed TLS)
