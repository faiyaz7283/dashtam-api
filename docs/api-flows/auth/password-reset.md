# Password Reset (HTTPS, Dev)

Request a password reset, verify a token, and confirm the new password using the HTTPS-enabled development environment.

## Purpose
Allow a user to reset their password securely.

## Prerequisites
- Dev environment running with TLS
- A registered and verified user

```bash
make dev-up
BASE_URL=https://localhost:8000
TEST_EMAIL="<verified_user_email>"
NEW_PASSWORD="NewSecure123!"
RESET_TOKEN="<paste_reset_token_here_if_available>"
```

## Steps

### 1) Request password reset
```bash
curl -sk -X POST "$BASE_URL/api/v1/password-resets" \
  -H "Content-Type: application/json" \
  -d "{\n    \"email\": \"$TEST_EMAIL\"\n  }" | python3 -m json.tool
```
Expected:
- 202 Accepted (even if email does not exist) to prevent email enumeration

### 2) Verify reset token (optional, if token is available)
```bash
curl -sk "$BASE_URL/api/v1/password-resets/$RESET_TOKEN" | python3 -m json.tool
```
Expected (snippet):
```json
{"valid": true, "email": "<user_email>"}
```

### 3) Confirm password reset
```bash
curl -sk -X PATCH "$BASE_URL/api/v1/password-resets/$RESET_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\n    \"new_password\": \"$NEW_PASSWORD\"\n  }" | python3 -m json.tool
```

## Notes on tokens in dev
- As with email verification, token delivery may be mocked. If unavailable:
  - Use administrative tooling to simulate a valid token
  - Add temporary dev helper endpoints to surface tokens (remove in production)

## Troubleshooting
- 400: invalid/expired token
- 422: weak password or missing fields
- 202 on request step is expected regardless of user existence
