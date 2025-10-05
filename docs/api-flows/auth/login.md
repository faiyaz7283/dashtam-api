# Login + Token Usage (HTTPS, Dev)

Log in as a verified user, capture tokens, call a protected endpoint, refresh, and logout.

## Purpose
Authenticate a user and validate token-based access to protected resources.

## Prerequisites
- Dev environment running with TLS
- An existing, verified user (registration + email verification)

```bash
make dev-up
BASE_URL=https://localhost:8000
TEST_EMAIL="<verified_user_email>"
TEST_PASSWORD="<verified_user_password>"
```

## Steps

### 1) Login to obtain tokens
```bash
ACCESS_TOKEN=$(curl -sk -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\n    \"email\": \"$TEST_EMAIL\",\n    \"password\": \"$TEST_PASSWORD\"\n  }" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

REFRESH_TOKEN=$(curl -sk -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\n    \"email\": \"$TEST_EMAIL\",\n    \"password\": \"$TEST_PASSWORD\"\n  }" | python3 -c "import sys, json; print(json.load(sys.stdin)['refresh_token'])")

echo "ACCESS_TOKEN=${ACCESS_TOKEN:0:20}..."
echo "REFRESH_TOKEN=${REFRESH_TOKEN:0:12}..."
```

### 2) Call a protected endpoint
```bash
curl -sk "$BASE_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```
Expected (snippet):
```json
{"email": "<verified_user_email>", "email_verified": true}
```

### 3) Refresh access token
```bash
NEW_ACCESS=$(curl -sk -X POST "$BASE_URL/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\n    \"refresh_token\": \"$REFRESH_TOKEN\"\n  }" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
```

### 4) Logout (invalidate current session)
```bash
curl -sk -X POST "$BASE_URL/api/v1/auth/logout" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\n    \"refresh_token\": \"$REFRESH_TOKEN\"\n  }" | python3 -m json.tool
```

## Troubleshooting
- 401 Unauthorized: access token expired/invalid → refresh or re-login
- 403 Forbidden: missing/invalid Authorization header (Bearer prefix required)
- SSL: use `-k` in dev to accept self-signed certificate
