# Registration (HTTPS, Dev)

Register a new user using the HTTPS-enabled development environment.

## Purpose
Create a new user account that can later be verified and used to log in.

## Prerequisites
- Dev environment is running with TLS
- Shell variables exported

```bash
make dev-up
BASE_URL=https://localhost:8000
TEST_EMAIL="tester+$(date +%s)@example.com"
TEST_PASSWORD="SecurePass123!"
```

## Steps

### 1) Register
```bash
curl -sk -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\n    \"email\": \"$TEST_EMAIL\",\n    \"password\": \"$TEST_PASSWORD\",\n    \"name\": \"Test User\"\n  }" | python3 -m json.tool
```
Expected (snippet):
```json
{"message": "Registration successful. Please check your email to verify."}
```

### 2) Email verification (note)
- In development, email delivery may be mocked. The verification step uses:
```bash
curl -sk -X POST "$BASE_URL/api/v1/auth/verify-email" \
  -H "Content-Type: application/json" \
  -d '{"token": "<verification_token>"}' | python3 -m json.tool
```
- If token delivery is not wired up, you may need to:
  - Inspect logs/DB for the token (future tooling), or
  - Temporarily mark the user verified for manual testing (admin action)

## Cleanup (optional)
- If you created a throwaway user, you can remove it via admin tooling (not included here yet).

## Troubleshooting
- 422 errors: ensure email and password meet validation requirements
- 400 duplicate email: try a fresh TEST_EMAIL value
- For HTTPS, use `-k` to accept self-signed dev certificates
