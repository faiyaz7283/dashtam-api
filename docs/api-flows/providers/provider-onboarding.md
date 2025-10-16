# Provider Onboarding (HTTPS, Dev)

Create a provider instance, obtain an authorization URL, complete the OAuth flow, and verify the connection.

---

## Table of Contents

- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Steps](#steps)
  - [1) Create provider instance](#1-create-provider-instance)
  - [2) Request authorization URL](#2-request-authorization-url)
  - [3) Authorize in browser](#3-authorize-in-browser)
  - [4) Verify connection status](#4-verify-connection-status)
- [Cleanup (optional)](#cleanup-optional)
- [Troubleshooting](#troubleshooting)
- [Related Flows](#related-flows)
- [Document Information](#document-information)

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

### 1) Create provider instance

```bash
cat <<JSON >/tmp/create-provider.json
{
  "provider_key": "schwab",
  "alias": "My Schwab Account"
}
JSON

curl -sk -X POST "$BASE_URL/api/v1/providers" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  --data-binary @/tmp/create-provider.json | python3 -m json.tool
```

**Expected Response (HTTP 201 Created):**

```json
{
  "id": "a7b3c5d9-e1f2-4a6b-8c9d-0e1f2a3b4c5d",
  "provider_key": "schwab",
  "alias": "My Schwab Account",
  "status": "pending",
  "is_connected": false,
  "needs_reconnection": true,
  "connected_at": null,
  "last_sync_at": null,
  "accounts_count": 0
}
```

**Extract and export provider ID:**

```bash
# Method 1: Using jq (if installed)
export PROVIDER_ID=$(curl -sk -X POST "$BASE_URL/api/v1/providers" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  --data-binary @/tmp/create-provider.json | jq -r '.id')

# Method 2: Manual (copy from response above)
export PROVIDER_ID="a7b3c5d9-e1f2-4a6b-8c9d-0e1f2a3b4c5d"

# Verify it's set
echo "Provider ID: $PROVIDER_ID"
```

### 2) Request authorization URL

```bash
curl -sk -X POST "$BASE_URL/api/v1/providers/$PROVIDER_ID/authorization" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "auth_url": "https://api.schwabapi.com/oauth/authorize?client_id=...&redirect_uri=https://127.0.0.1:8182&state=..."
}
```

**Extract and open authorization URL:**

```bash
# Method 1: Using jq (if installed)
export AUTH_URL=$(curl -sk -X POST "$BASE_URL/api/v1/providers/$PROVIDER_ID/authorization" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq -r '.auth_url')

# Method 2: Manual (copy from response above)
export AUTH_URL="<paste_auth_url_here>"

echo "Open in browser: $AUTH_URL"
```

### 3) Authorize in browser

**Manual step:**

1. Copy the `AUTH_URL` from above
2. Paste it into your browser
3. Log in to Schwab (or the provider)
4. Review and approve the requested permissions
5. You will be redirected to: `https://127.0.0.1:8182` (callback server)

**✅ The callback server automatically handles the OAuth redirect** and exchanges the authorization code for tokens. No manual intervention needed after authorization!

**Note**: You may see a browser security warning about the self-signed SSL certificate. This is expected in development - click "Proceed" or "Accept the Risk".

### 4) Verify connection status

After authorization, wait a moment for the OAuth callback to complete, then check the provider status:

```bash
curl -sk "$BASE_URL/api/v1/providers/$PROVIDER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "id": "a7b3c5d9-e1f2-4a6b-8c9d-0e1f2a3b4c5d",
  "provider_key": "schwab",
  "alias": "My Schwab Account",
  "status": "active",
  "is_connected": true,
  "needs_reconnection": false,
  "connected_at": "2025-10-05T23:50:00Z",
  "last_sync_at": null,
  "accounts_count": 0
}
```

✅ **Provider connected successfully!**

## Cleanup (optional)

To disconnect and remove the provider:

```bash
curl -sk -X DELETE "$BASE_URL/api/v1/providers/$PROVIDER_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```

**Expected Response (HTTP 200 OK):**

```json
{
  "message": "Provider disconnected successfully"
}
```

## Troubleshooting

- **400 Bad Request - "Provider not available"**:
  - Ensure `provider_key` is valid (currently supported: "schwab")
  - Check provider is configured in environment variables
- **400 Bad Request - "Provider not configured"**:
  - Verify `SCHWAB_API_KEY` and `SCHWAB_API_SECRET` are set in `env/.env.dev`
- **401 Unauthorized**: Access token expired or invalid → refresh or re-login
- **404 Not Found**: Check that PROVIDER_ID is set correctly
- **Auth URL missing**: Ensure services are healthy (`make dev-status`)
- **Callback fails**:
  - Verify redirect URI matches exactly: `https://127.0.0.1:8182`
  - Ensure callback server is running (check `docker ps | grep callback`)
  - Check callback server logs: `docker logs dashtam-dev-callback`
- **SSL warnings in browser**: Expected for self-signed certs in dev → click "Proceed" or "Accept Risk"
- **Connection shows `needs_reconnection: true`**: OAuth may have failed → check callback server logs

## Related Flows

- **Prerequisites:** [Registration](../auth/registration.md) → [Email Verification](../auth/email-verification.md) → [Login](../auth/login.md) - Must have authenticated user
- **Alternative:** [Provider Disconnect](provider-disconnect.md) - Remove provider connection
- **Next steps:** Future account and transaction endpoints (after provider connected)
- **Complete flow:** [Complete Auth Flow](../auth/complete-auth-flow.md) - Full authentication testing
- **Architecture:** [JWT Authentication](../../development/architecture/jwt-authentication.md) - Understanding auth requirements

---

## Document Information

**Category:** API Flow  
**Created:** 2025-10-15  
**Last Updated:** 2025-10-15  
**API Version:** v1  
**Environment:** Development (HTTPS with self-signed TLS)
