# Email Verification (HTTPS, Dev)

Verify a user's email using the HTTPS-enabled development environment.

## Purpose

Confirm a registered user’s email to enable login and protected actions.

## Prerequisites

- Dev environment running with TLS
- A user recently registered (see [Registration Flow](registration.md))
- Verification token extracted from logs (see below)

```bash
make dev-up
BASE_URL=https://localhost:8000
```

## Steps

### 1) Extract verification token from logs

After registration, the verification email is logged to console in development mode:

```bash
# View recent email logs
docker logs dashtam-dev-app --tail 100 2>&1 | grep -A 20 '📧 EMAIL'
```

**Example log output:**

```log
📧 EMAIL (Development Mode - Not Sent)
================================================================================
From: Dashtam <noreply@dashtam.com>
To: tester+1234567890@example.com
Subject: Verify Your Dashtam Account
--------------------------------------------------------------------------------
Text Body:
Hi Test User,

Thank you for signing up for Dashtam, your secure financial data aggregation platform.

To complete your registration and verify your email address, please visit:
https://localhost:3000/verify-email?token=vYaGSkz80Qoi86hR78lPyKt6zIp8LDoj13TiheZzjLk

This link will expire in 24 hours.
================================================================================
```

**Extract and set the token:**

```bash
# Copy the token from the URL in the logs
export VERIFICATION_TOKEN="vYaGSkz80Qoi86hR78lPyKt6zIp8LDoj13TiheZzjLk"

# Verify it's set
echo "Verification token: $VERIFICATION_TOKEN"
```

### 2) Verify email

```bash
cat <<JSON >/tmp/verify-email.json
{
  "token": "$VERIFICATION_TOKEN"
}
JSON

curl -sk -X POST "$BASE_URL/api/v1/auth/verify-email" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/verify-email.json | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "message": "Email verified successfully. You can now log in."
}
```

**Optional: Inline (no heredoc):**

```bash
curl -sk -X POST "$BASE_URL/api/v1/auth/verify-email" \
  -H 'Content-Type: application/json' \
  -d "{\"token\":\"$VERIFICATION_TOKEN\"}" | python3 -m json.tool
```

## Troubleshooting

- **400 Bad Request - "Invalid or already used verification token"**:
  - Token may have expired (24 hour TTL)
  - Token may have already been used
  - Token may be incorrect (check for copy-paste errors)
  - Generate a new token by re-registering with a different email
- **400 Bad Request - "Invalid token"**: Ensure the token is copied exactly from logs (no extra spaces/newlines)
- **422 Validation Error**: Ensure JSON body includes a `token` field
- **Token not found in logs**:
  - Ensure registration was successful (check registration response)
  - Check logs immediately after registration: `docker logs dashtam-dev-app --tail 50`
  - Verify DEBUG=true in `env/.env.dev`
- **SSL certificate errors**: Use `-k` flag with curl to accept self-signed dev certificates

## Related Flows

- **Previous step:** [Registration](registration.md) - Register user account and obtain verification token
- **Next step:** [Login](login.md) - Authenticate with verified account
- **Complete flow:** [Complete Auth Flow](complete-auth-flow.md) - End-to-end authentication testing
- **Architecture:** [JWT Authentication](../../development/architecture/jwt-authentication.md) - Understanding the auth system

---

## Document Information

**Template:** [api-flow-template.md](../../templates/api-flow-template.md)
**Created:** 2025-10-15
**Last Updated:** 2025-10-15
