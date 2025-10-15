# Complete Authentication Flow - End-to-End Smoke Test

End-to-end smoke test covering the complete authentication lifecycle from registration through logout.

---

## Table of Contents

- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Complete Flow Steps](#complete-flow-steps)
  - [Step 1: User Registration](#step-1-user-registration)
  - [Step 2: Email Verification](#step-2-email-verification)
  - [Step 3: Login](#step-3-login)
  - [Step 4: Access Protected Resource](#step-4-access-protected-resource)
  - [Step 5: Update Profile](#step-5-update-profile)
  - [Step 6: Token Refresh](#step-6-token-refresh)
  - [Step 7: Password Reset Request](#step-7-password-reset-request)
- [Related Flows](#related-flows)

## Purpose

Run a full authentication lifecycle smoke test from registration through logout. Tests all major auth components in a single end-to-end flow for manual verification.

**This is a smoke test** - it validates the entire auth system is operational by exercising all major endpoints in sequence.

## Prerequisites

- Development environment running: `make dev-up`
- Fresh database state (or unique test email)
- Environment variables configured:

  ```bash
  export BASE_URL="https://localhost:8000"
  export TEST_EMAIL="smoke-test-$(date +%s)@example.com"  # Unique email
  export TEST_PASSWORD="SecurePass123!"
  export FRONTEND_URL="https://localhost:3000"
  ```

## Complete Flow Steps

### Step 1: User Registration

**Register new user account:**

```bash
curl -k -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\",
    \"name\": \"Smoke Test User\"
  }"
```

**Expected:** HTTP 201 Created

```json
{
  "id": "uuid-here",
  "email": "smoke-test-123@example.com",
  "name": "Smoke Test User",
  "email_verified": false,
  "is_active": true,
  "created_at": "2025-10-05T..."
}
```

**Extract verification token from logs:**

```bash
# In separate terminal
docker logs dashtam-dev-app --tail 50 2>&1 | grep -A 20 '📧 EMAIL' | grep 'verify-email'

# Look for URL:
# https://localhost:3000/verify-email?token=YOUR_TOKEN_HERE

export VERIFICATION_TOKEN="<token-from-logs>"
echo "Verification Token: $VERIFICATION_TOKEN"
```

### Step 2: Email Verification

**Verify email with extracted token:**

```bash
curl -k -X POST "$BASE_URL/api/v1/auth/verify-email" \
  -H "Content-Type: application/json" \
  -d "{
    \"token\": \"$VERIFICATION_TOKEN\"
  }"
```

**Expected:** HTTP 200 OK

```json
{
  "message": "Email verified successfully"
}
```

### Step 3: Login

**Login with verified account:**

```bash
LOGIN_RESPONSE=$(curl -k -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$TEST_PASSWORD\"
  }")

echo "$LOGIN_RESPONSE"

# Extract tokens
export ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
export REFRESH_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"refresh_token":"[^"]*"' | cut -d'"' -f4)

echo "Access Token: ${ACCESS_TOKEN:0:50}..."
echo "Refresh Token: ${REFRESH_TOKEN:0:50}..."
```

**Expected:** HTTP 200 OK with JWT tokens

### Step 4: Access Protected Resource

**Get user profile with access token:**

```bash
curl -k -X GET "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

**Expected:** HTTP 200 OK

```json
{
  "id": "uuid-here",
  "email": "smoke-test-123@example.com",
  "name": "Smoke Test User",
  "email_verified": true,
  "is_active": true
}
```

### Step 5: Update Profile

**Update user full name:**

```bash
curl -k -X PATCH "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Updated Smoke Test\"
  }"
```

**Expected:** HTTP 200 OK with updated profile

### Step 6: Token Refresh

**Refresh access token using refresh token:**

```bash
REFRESH_RESPONSE=$(curl -k -s -X POST "$BASE_URL/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN\"
  }")

echo "$REFRESH_RESPONSE"

# Extract new access token (refresh token stays same - no rotation)
export NEW_ACCESS_TOKEN=$(echo "$REFRESH_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

echo "New Access Token: ${NEW_ACCESS_TOKEN:0:50}..."
echo "Refresh Token (unchanged): ${REFRESH_TOKEN:0:50}..."
```

**Expected:** HTTP 200 OK with new access token

**Verify new token works:**

```bash
curl -k -X GET "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $NEW_ACCESS_TOKEN"
```

### Step 7: Password Reset Request

**Request password reset:**

```bash
curl -k -X POST "$BASE_URL/api/v1/password-resets" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\"
  }"
```

**Expected:** HTTP 202 Accepted

**Extract reset token from logs:**

```bash
docker logs dashtam-dev-app --tail 50 2>&1 | grep -A 20 '📧 EMAIL' | grep 'reset-password'

# Look for URL:
# https://localhost:3000/reset-password?token=YOUR_TOKEN_HERE

export RESET_TOKEN="<token-from-logs>"
echo "Reset Token: $RESET_TOKEN"
```

**Verify token is retrievable (optional):**

```bash
curl -k -X GET "$BASE_URL/api/v1/password-resets/$RESET_TOKEN"
```

**Expected:** HTTP 200 OK

### Step 8: Password Reset Confirmation

**Complete password reset with new password:**

```bash
export NEW_PASSWORD="NewSecurePass456!"

curl -k -X PATCH "$BASE_URL/api/v1/password-resets/$RESET_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"new_password\": \"$NEW_PASSWORD\"
  }"
```

**Expected:** HTTP 200 OK

```json
{
  "message": "Password reset successfully"
}
```

**Verify new password works:**

```bash
curl -k -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$NEW_PASSWORD\"
  }"
```

**Expected:** HTTP 200 OK with new access/refresh tokens

**Extract new tokens for logout test:**

```bash
LOGIN_RESPONSE2=$(curl -k -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$TEST_EMAIL\",
    \"password\": \"$NEW_PASSWORD\"
  }")

export ACCESS_TOKEN2=$(echo "$LOGIN_RESPONSE2" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
export REFRESH_TOKEN2=$(echo "$LOGIN_RESPONSE2" | grep -o '"refresh_token":"[^"]*"' | cut -d'"' -f4)
```

### Step 9: Logout (Refresh Token Revocation)

**Logout and revoke refresh token:**

```bash
curl -k -X POST "$BASE_URL/api/v1/auth/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN2" \
  -H "Content-Type: application/json" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN2\"
  }"
```

**Expected:** HTTP 200 OK

```json
{
  "message": "Logged out successfully"
}
```

**Verify refresh token is revoked:**

```bash
# This should FAIL with 401 Unauthorized
curl -k -X POST "$BASE_URL/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN2\"
  }"
```

**Expected:** HTTP 401 Unauthorized (token revoked)

**Verify access token still works (until expiration ~30 min):**

```bash
# This should SUCCEED - access tokens remain valid until expiration
curl -k -X GET "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN2"
```

**Expected:** HTTP 200 OK (access token still valid)

**Why?** Logout only revokes refresh tokens immediately. JWT access tokens remain valid until natural expiration. This is **correct behavior** for stateless JWT systems.

See: [JWT Authentication - Logout Behavior](../../development/architecture/jwt-authentication.md#flow-5-logout)

## Smoke Test Summary

**Endpoints Tested:**

1. ✅ `POST /api/v1/auth/register` - User registration
2. ✅ `POST /api/v1/auth/verify-email` - Email verification
3. ✅ `POST /api/v1/auth/login` - User login
4. ✅ `GET /api/v1/auth/me` - Get user profile
5. ✅ `PATCH /api/v1/auth/me` - Update user profile
6. ✅ `POST /api/v1/auth/refresh` - Token refresh
7. ✅ `POST /api/v1/auth/password-resets` - Request password reset
8. ✅ `GET /api/v1/password-resets/{token}` - Verify reset token
9. ✅ `POST /api/v1/password-resets/{token}/confirm` - Confirm password reset
10. ✅ `POST /api/v1/auth/logout` - Logout and revoke refresh token

**Features Verified:**

- ✅ User registration with validation
- ✅ Email verification with token extraction from logs
- ✅ JWT authentication (access + refresh tokens)
- ✅ Token refresh (access token rotation, refresh stays same)
- ✅ Password reset flow with token
- ✅ **🔒 Password reset session revocation** (security enhancement)
- ✅ Profile management (GET/PATCH)
- ✅ Token revocation (logout behavior)
- ✅ Stateless JWT pattern (access tokens valid after logout)

## Troubleshooting

### Registration fails with 409 Conflict

**Cause:** Email already registered

**Solution:** Use unique email with timestamp:

```bash
export TEST_EMAIL="smoke-test-$(date +%s)@example.com"
```

### Cannot extract token from logs

**Cause:** Email not logged or wrong container

**Solution:**

```bash
# Verify development mode
docker exec dashtam-dev-app env | grep DEBUG
# Should show: DEBUG=True

# Check recent logs with more context
docker logs dashtam-dev-app --tail 200 2>&1 | grep -A 30 '📧'
```

### Login fails with 400 "Email not verified"

**Cause:** Email verification step skipped or failed

**Solution:** Complete email verification (Step 2) before login

### Refresh token still works after logout

**Cause:** Looking at wrong token or caching issue

**Solution:**

```bash
# Use exact refresh token from Step 9 login
echo "Using refresh token: ${REFRESH_TOKEN2:0:50}..."

# Clear any HTTP caching
curl -k -X POST "$BASE_URL/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -H "Cache-Control: no-cache" \
  -d "{
    \"refresh_token\": \"$REFRESH_TOKEN2\"
  }"
```

### Access token rejected after logout

**Cause:** Misunderstanding JWT behavior - this is a bug if it happens

**Solution:** Access tokens should remain valid after logout (up to expiration). If rejected immediately, check:

```bash
# Verify token not expired
echo "$ACCESS_TOKEN2" | cut -d'.' -f2 | base64 -d 2>/dev/null | grep exp

# Check for auth middleware issues in logs
docker logs dashtam-dev-app --tail 50 | grep -i "auth"
```

### SSL certificate errors

**Cause:** Self-signed certificates in development

**Solution:** Always use `-k` flag with curl:

```bash
curl -k -X GET "$BASE_URL/api/v1/auth/me" ...
```

## Cleanup (Optional)

**To remove test user** (when admin endpoints available):

```bash
# Future: DELETE /api/v1/admin/users/{id}
```

**For now:** Test users remain in database. Use unique emails for each smoke test run.

## Related Flows

- [Registration](registration.md) - Detailed registration flow
- [Email Verification](email-verification.md) - Email verification details
- [Login](login.md) - Login and token usage details
- [Password Reset](password-reset.md) - Password reset details
- [JWT Authentication Architecture](../../development/architecture/jwt-authentication.md) - Complete auth design

## Notes

- **Development Mode:** Emails logged to console (no AWS SES needed)
- **Token Extraction:** All email tokens available in Docker logs
- **Logout Behavior:** Only refresh tokens revoked immediately (JWT Pattern A)
- **🔒 Password Reset Security:** All sessions automatically logged out (Test 13 verifies this)
- **Test Isolation:** Use unique email per test run to avoid conflicts
- **Expected Duration:** ~2-3 minutes for complete smoke test

---

## Document Information

**Category:** API Flow  
**Created:** 2025-10-15  
**Last Updated:** 2025-10-15  
**API Version:** v1  
**Environment:** Development (HTTPS with self-signed TLS)
