# Flow Template

Use this template when adding a new manual API flow. Keep it focused on the user journey and include only the essential commands and validation tips.

## Purpose
- What is the user trying to accomplish?
- Why this flow exists and when to use it.

## Prerequisites
- Dev environment running with TLS
- Required environment variables set

```bash
# Dev environment (TLS)
make dev-up
BASE_URL=https://localhost:8000
CALLBACK_URL=https://127.0.0.1:8182
# Per-flow variables (example)
TEST_EMAIL="tester+$(date +%s)@example.com"
TEST_PASSWORD="SecurePass123!"
```

## Steps

### 1) Step title
- Brief explanation
```bash
curl -sk -X {METHOD} "$BASE_URL{/path}" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "key": "value"
  }' | python3 -m json.tool
```
Expected (snippet):
```json
{"key": "value"}
```

### 2) Step title
- Brief explanation
```bash
# command here
```

## Cleanup (optional)
- Commands to revert or remove test data

## Troubleshooting
- SSL issues (use -k for self-signed TLS in dev)
- Missing tokens or 401/403 responses
- Endpoint returns 4xx/5xx: double-check environment variables and payloads
