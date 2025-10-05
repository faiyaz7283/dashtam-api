# Provider Disconnect (HTTPS, Dev)

Disconnect an authorized provider and optionally delete its instance.

## Purpose
Revoke a provider connection for a user and clean up resources if needed.

## Prerequisites
- Dev environment running with TLS
- Authenticated user (have `ACCESS_TOKEN` from login flow)
- An existing provider instance (have `PROVIDER_ID` from onboarding flow)

```bash
make dev-up
BASE_URL=https://localhost:8000
# From previous flows
echo $ACCESS_TOKEN >/dev/null
echo $PROVIDER_ID >/dev/null
```

## Steps

### 1) Disconnect provider session (invalidate connection)
```bash
curl -sk -X DELETE "$BASE_URL/api/v1/auth/$PROVIDER_ID/disconnect" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```
Expected (snippet):
```json
{"message": "Provider disconnected"}
```

### 2) Verify provider status
```bash
curl -sk "$BASE_URL/api/v1/providers/$PROVIDER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```
Expected (snippet):
```json
{"is_connected": false}
```

### 3) (Optional) Delete provider instance
```bash
curl -sk -X DELETE "$BASE_URL/api/v1/providers/$PROVIDER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```

## Troubleshooting
- 404: provider not found → ensure `PROVIDER_ID` is correct and belongs to the user
- 403: missing/invalid Authorization header → ensure `ACCESS_TOKEN` is valid
- SSL: use `-k` with curl in dev to accept self-signed certs
