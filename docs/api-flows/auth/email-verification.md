# Email Verification (HTTPS, Dev)

Verify a user’s email using the HTTPS-enabled development environment.

## Purpose
Confirm a registered user’s email to enable login and protected actions.

## Prerequisites
- Dev environment running with TLS
- A user recently registered (see registration flow)

```bash
make dev-up
BASE_URL=https://localhost:8000
# Replace with the token issued during registration (see notes below)
VERIFICATION_TOKEN="<paste_verification_token_here>"
```

## Steps

### 1) Verify email
```bash
curl -sk -X POST "$BASE_URL/api/v1/auth/verify-email" \
  -H "Content-Type: application/json" \
  -d "{\n    \"token\": \"$VERIFICATION_TOKEN\"\n  }" | python3 -m json.tool
```
Expected (snippet):
```json
{"message": "Email verified"}
```

## Notes on obtaining the token (dev)
- In development, email delivery may be mocked.
- Depending on your setup, the verification token may be logged, stored temporarily, or available via a dev-only endpoint (future tooling). If not available, you may:
  - Simulate verification administratively for manual testing
  - Add a development helper to expose the token temporarily (remove in production)

## Troubleshooting
- 400 Invalid token: ensure `VERIFICATION_TOKEN` is correct (not expired, not malformed)
- 422 Validation error: ensure JSON body includes a `token` field
- SSL: use `-k` to accept self-signed certs in dev
