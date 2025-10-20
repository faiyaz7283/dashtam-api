# Login + Token Usage (HTTPS, Dev)

Log in as a verified user, capture tokens, call a protected endpoint, refresh, and logout.

---

## Table of Contents

- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Steps](#steps)
  - [1) Login to obtain tokens](#1-login-to-obtain-tokens)
  - [2) Call a protected endpoint](#2-call-a-protected-endpoint)
  - [3) Refresh access token](#3-refresh-access-token)
  - [4) Logout (revoke refresh token)](#4-logout-revoke-refresh-token)
  - [5) Verify logout behavior](#5-verify-logout-behavior)
- [Troubleshooting](#troubleshooting)
- [Related Flows](#related-flows)
- [Document Information](#document-information)

---

## Purpose

Authenticate a user and validate token-based access to protected resources.

## Prerequisites

- Dev environment running with TLS
- An existing, verified user (see [Registration](registration.md) + [Email Verification](email-verification.md) flows)

```bash
make dev-up
BASE_URL=https://localhost:8000
# Use the email/password from registration
TEST_EMAIL='tester+1234567890@example.com'
TEST_PASSWORD='SecurePass123!'
```

## Steps

### 1) Login to obtain tokens

```bash
# Quote-safe login body via heredoc
cat <<JSON >/tmp/login.json
{
  "email": "$TEST_EMAIL",
  "password": "$TEST_PASSWORD"
}
JSON

curl -sk -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/login.json | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4NzA2...",
  "refresh_token": "-4d-3aMf5mESSaJjz7UTl81dTLFsMS0cMNBRzmfKmgc",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "87068e4d-1c72-4e14-a444-654f7162f7a4",
    "email": "tester+1234567890@example.com",
    "name": "Test User",
    "email_verified": true,
    "is_active": true,
    "created_at": "2025-10-05T23:22:06.956575Z",
    "last_login_at": "2025-10-05T23:25:50.267074Z"
  }
}
```

**Extract and export tokens:**

```bash
# Method 1: Using jq (if installed)
export ACCESS_TOKEN=$(curl -sk -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/login.json | jq -r '.access_token')
export REFRESH_TOKEN=$(curl -sk -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/login.json | jq -r '.refresh_token')

# Method 2: Manual (copy from response above)
export ACCESS_TOKEN="<paste_access_token_here>"
export REFRESH_TOKEN="<paste_refresh_token_here>"

# Verify tokens are set
echo "Access token: ${ACCESS_TOKEN:0:50}..."
echo "Refresh token: ${REFRESH_TOKEN:0:50}..."
```

### 2) Call a protected endpoint

```bash
curl -sk "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "id": "87068e4d-1c72-4e14-a444-654f7162f7a4",
  "email": "tester+1234567890@example.com",
  "name": "Test User",
  "email_verified": true,
  "is_active": true,
  "created_at": "2025-10-05T23:22:06.956575Z",
  "last_login_at": "2025-10-05T23:25:50.267074Z"
}
```

### 3) Refresh access token

```bash
cat <<JSON >/tmp/refresh.json
{
  "refresh_token": "$REFRESH_TOKEN"
}
JSON

curl -sk -X POST "$BASE_URL/api/v1/auth/refresh" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/refresh.json | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4NzA2...",
  "refresh_token": "-4d-3aMf5mESSaJjz7UTl81dTLFsMS0cMNBRzmfKmgc",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**⚠️ Note about refresh tokens**: The `refresh_token` in the response is the **same** as before. Dashtam uses **reusable refresh tokens** (not rotated). This is Pattern A (industry standard) - see [JWT Authentication Docs](../../development/architecture/jwt-authentication.md#flow-5-logout) for details.

**Update access token:**

```bash
# If you need to use the new access token
export ACCESS_TOKEN=$(curl -sk -X POST "$BASE_URL/api/v1/auth/refresh" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/refresh.json | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
```

### 4) Logout (revoke refresh token)

```bash
cat <<JSON >/tmp/logout.json
{
  "refresh_token": "$REFRESH_TOKEN"
}
JSON

curl -sk -X POST "$BASE_URL/api/v1/auth/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/logout.json | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "message": "Logged out successfully"
}
```

### 5) Verify logout behavior

**Test 1: Refresh token is revoked:**

```bash
curl -sk -X POST "$BASE_URL/api/v1/auth/refresh" \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/refresh.json | python3 -m json.tool
```

**Expected Response (HTTP 401 Unauthorized):**

```json
{
  "detail": "Invalid or revoked refresh token"
}
```

✅ **This is correct** - the refresh token has been revoked.

**Test 2: Access token STILL WORKS (expected behavior):**

```bash
curl -sk "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "id": "87068e4d-1c72-4e14-a444-654f7162f7a4",
  "email": "tester+1234567890@example.com",
  ...
}
```

⚠️ **This is CORRECT behavior**: The JWT access token remains valid until expiration (~30 minutes). Only the refresh token is immediately revoked. This is by design for stateless JWT architecture.

**Why this happens**: See [JWT Authentication - Logout Behavior](../../development/architecture/jwt-authentication.md#flow-5-logout) for detailed explanation of what gets invalidated during logout.

## Troubleshooting

- **401 Unauthorized:** access token expired/invalid → refresh or re-login
- **403 Forbidden:** missing/invalid Authorization header (Bearer prefix required)
- **SSL:** use `-k` in dev to accept self-signed certificate

## Related Flows

- **Prerequisites:** [Registration](registration.md) → [Email Verification](email-verification.md) - Required before login
- **Alternative:** [Password Reset](password-reset.md) - If password forgotten
- **Complete flow:** [Complete Auth Flow](complete-auth-flow.md) - End-to-end authentication testing
- **After login:** [Provider Onboarding](../providers/provider-onboarding.md) - Connect financial accounts
- **Architecture:** [JWT Authentication](../../development/architecture/jwt-authentication.md) - Understanding the auth system

---

## Document Information

**Template:** [api-flow-template.md](../../templates/api-flow-template.md)
**Created:** 2025-10-15
**Last Updated:** 2025-10-15
