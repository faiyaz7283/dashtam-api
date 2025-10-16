# Provider Disconnect (HTTPS, Dev)

Disconnect an authorized provider and optionally delete its instance.

---

## Table of Contents

- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Steps](#steps)
  - [1) Disconnect provider session](#1-disconnect-provider-session-invalidate-connection)
  - [2) Verify provider status](#2-verify-provider-status)
  - [3) (Optional) Delete provider instance](#3-optional-delete-provider-instance)
- [Troubleshooting](#troubleshooting)
- [Related Flows](#related-flows)

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

- **404**: provider not found → ensure `PROVIDER_ID` is correct and belongs to the user
- **403**: missing/invalid Authorization header → ensure `ACCESS_TOKEN` is valid
- **SSL**: use `-k` with curl in dev to accept self-signed certs

## Related Flows

- **Prerequisites:** [Provider Onboarding](provider-onboarding.md) - Must have connected provider first
- **Authentication:** [Login](../auth/login.md) - Need valid access token
- **Complete flow:** [Complete Auth Flow](../auth/complete-auth-flow.md) - Full authentication testing
- **Architecture:** [JWT Authentication](../../development/architecture/jwt-authentication.md) - Understanding auth requirements

---

## Document Information

**Category:** API Flow
**Created:** 2025-10-15
**Last Updated:** 2025-10-15
**API Version:** v1
**Environment:** Development (HTTPS with self-signed TLS)
