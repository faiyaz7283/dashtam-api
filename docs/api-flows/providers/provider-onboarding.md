# Provider Onboarding (HTTPS, Dev)

Create a provider instance, obtain an authorization URL, complete the OAuth flow, and verify the connection.

## Purpose
Manually test the end-to-end OAuth onboarding flow for a provider (e.g., Schwab).

## Prerequisites
- Dev environment running with TLS
- An authenticated, verified user (have ACCESS_TOKEN from login flow)

```bash
make dev-up
BASE_URL=https://localhost:8000
CALLBACK_URL=https://127.0.0.1:8182

# From login flow
echo $ACCESS_TOKEN | sed 's/./&/g' >/dev/null  # placeholder to show it exists
```

## Steps

### 1) Create provider instance (record provider_id)
```bash
PROVIDER_ID=$(curl -sk -X POST "$BASE_URL/api/v1/providers/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"provider_key":"schwab","alias":"My Schwab Account"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

echo "PROVIDER_ID=$PROVIDER_ID"
```
Expected (snippet):
```json
{"id": "<uuid>", "provider_key": "schwab", "status": "pending"}
```

### 2) Request authorization URL
```bash
AUTH_URL=$(curl -sk -X POST "$BASE_URL/api/v1/providers/$PROVIDER_ID/authorization" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['auth_url'])")

echo "Open in browser: $AUTH_URL"
```

### 3) Authorize in browser
- Paste `AUTH_URL` into your browser
- Log in to the provider and approve requested scopes
- You will be redirected to: `$CALLBACK_URL`

### 4) Verify connection status
```bash
curl -sk "$BASE_URL/api/v1/providers/$PROVIDER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```
Expected (snippet):
```json
{"is_connected": true, "status": "connected"}
```

## Cleanup (optional)
```bash
curl -sk -X DELETE "$BASE_URL/api/v1/providers/$PROVIDER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```

## Troubleshooting
- If `AUTH_URL` is missing, ensure provider_key is valid and services are healthy
- If callback fails, confirm the redirect URI exactly matches `$CALLBACK_URL`
- SSL warnings in browser are expected for self-signed certs in dev (proceed to site)
