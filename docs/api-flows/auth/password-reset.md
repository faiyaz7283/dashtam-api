# Password Reset (HTTPS, Dev)

Request a password reset, verify a token, and confirm the new password using the HTTPS-enabled development environment.

---

## Table of Contents

- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Steps](#steps)
  - [1) Request password reset](#1-request-password-reset)
  - [2) Extract reset token from logs](#2-extract-reset-token-from-logs)
  - [3) Verify reset token (optional)](#3-verify-reset-token-optional)
  - [4) Confirm password reset](#4-confirm-password-reset)
  - [5) Test login with new password](#5-test-login-with-new-password)
- [🔒 Security Note: Session Revocation](#-security-note-session-revocation)
- [Next Step](#next-step)
- [Troubleshooting](#troubleshooting)
- [Related Flows](#related-flows)

## Purpose

Allow a user to reset their password securely.

## Prerequisites

- Dev environment running with TLS
- A registered and verified user (see [Registration](registration.md) flow)

```bash
make dev-up
BASE_URL=https://localhost:8000
# Use the email from an existing verified user
TEST_EMAIL='tester+1234567890@example.com'
NEW_PASSWORD='NewSecure123!'
```

## Steps

### 1) Request password reset

```bash
cat <<JSON >/tmp/reset-request.json
{
  "email": "$TEST_EMAIL"
}
JSON

curl -sk -X POST "$BASE_URL/api/v1/password-resets" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/reset-request.json | python3 -m json.tool
```

**Expected Response (HTTP 202 Accepted):**

```json
{
  "message": "If an account exists with that email, a password reset link has been sent."
}
```

**Note**: Always returns 202 (even if email doesn't exist) to prevent email enumeration attacks.

**Optional: Inline (no heredoc):**

```bash
curl -sk -X POST "$BASE_URL/api/v1/password-resets" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$TEST_EMAIL\"}" | python3 -m json.tool
```

### 2) Extract reset token from logs

In development mode (`DEBUG=True`), password reset emails are logged to console:

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
Subject: Reset Your Dashtam Password
--------------------------------------------------------------------------------
Text Body:
Hi Test User,

We received a request to reset your password for your Dashtam account.

To reset your password, please visit:
https://localhost:3000/reset-password?token=xK9mP2vNqL8jH5tR7wY3zD6fB4cS1aE0

This link will expire in 1 hour.
================================================================================
```

**Extract and set the token:**

```bash
# Copy the token from the URL in the logs
export RESET_TOKEN="xK9mP2vNqL8jH5tR7wY3zD6fB4cS1aE0"

# Verify it's set
echo "Reset token: $RESET_TOKEN"
```

### 3) Verify reset token (optional)

You can optionally verify the token is valid before showing the password reset form:

```bash
curl -sk "$BASE_URL/api/v1/password-resets/$RESET_TOKEN" | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "valid": true,
  "email": "tester+1234567890@example.com",
  "expires_at": "2025-10-06T00:50:00Z"
}
```

**If token is invalid/expired (HTTP 200 OK):**

```json
{
  "valid": false
}
```

### 4) Confirm password reset

```bash
cat <<JSON >/tmp/reset-confirm.json
{
  "new_password": "$NEW_PASSWORD"
}
JSON

curl -sk -X PATCH "$BASE_URL/api/v1/password-resets/$RESET_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/reset-confirm.json | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "message": "Password reset successfully. You can now log in with your new password."
}
```

**Optional: Inline (no heredoc):**

```bash
curl -sk -X PATCH "$BASE_URL/api/v1/password-resets/$RESET_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"new_password\":\"$NEW_PASSWORD\"}" | python3 -m json.tool
```

### 5) Test login with new password

```bash
curl -sk -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$NEW_PASSWORD\"}" \
  | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {...}
}
```

✅ Password reset successful!

## 🔒 Security Note: Session Revocation

**Important**: When you complete a password reset, **all active sessions are automatically logged out** for security.

**What happens:**

- ✅ All refresh tokens are revoked immediately
- ⚠️ Existing access tokens remain valid for ~30 minutes (then expire)
- ✅ Cannot get new access tokens (refresh is blocked)
- ✅ Must re-login on all devices with new password

**Why this is important:**
If your password was compromised, revoking all sessions ensures that an attacker cannot continue accessing your account, even if they already have tokens.

**Testing session revocation:**
See [Complete Auth Flow](complete-auth-flow.md) for full end-to-end testing including session revocation verification (Tests 13 & 13a).

## Next Step

**Continue to:** [Login Flow](login.md) to use the new password on all devices.

## Troubleshooting

- **400 Bad Request - "Invalid or expired token"**:
  - Token may have expired (1 hour TTL)
  - Token may have already been used
  - Token may be incorrect (check for copy-paste errors)
  - Request a new token by repeating step 1
- **400 Bad Request - Password validation**: Ensure new password has:
  - At least 8 characters
  - 1 uppercase letter (A-Z)
  - 1 lowercase letter (a-z)
  - 1 digit (0-9)
  - 1 special character (!@#$%^&*)
- **422 Validation Error**: Check JSON payload format and required fields
- **Token not found in logs**:
  - Ensure password reset request was successful (check 202 response)
  - Check logs immediately after requesting reset: `docker logs dashtam-dev-app --tail 50`
  - Verify DEBUG=true in `env/.env.dev`
- **SSL certificate errors**: Use `-k` flag with curl to accept self-signed dev certificates
- **Login fails after reset**: Ensure you're using the NEW_PASSWORD, not the old one

## Related Flows

- **Prerequisites:** [Registration](registration.md) + [Email Verification](email-verification.md) - Account must exist
- **Next step:** [Login](login.md) - Authenticate with new password
- **Complete flow:** [Complete Auth Flow](complete-auth-flow.md) - End-to-end testing with password reset
- **Alternative:** [Login](login.md) - If you remember your current password
- **Architecture:** [JWT Authentication](../../development/architecture/jwt-authentication.md) - Understanding password security

---

## Document Information

**Category:** API Flow  
**Created:** 2025-10-15  
**Last Updated:** 2025-10-15  
**API Version:** v1  
**Environment:** Development (HTTPS with self-signed TLS)
