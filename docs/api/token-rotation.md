# Admin Token Rotation API

## Overview

Admin-only endpoints for emergency token rotation during security incidents.

**Base URL**: `${BASE_URL}/api/v1/admin`

**Authentication**: Admin role required (`AuthLevel.ADMIN` with Casbin RBAC)

### Setup

Set your environment base URL before running commands:

```bash
# Development
export BASE_URL="https://dashtam.local"

# Test
export BASE_URL="https://test.dashtam.local"

# Production
export BASE_URL="https://api.dashtam.com"
```

---

## Endpoints Summary

| Resource | Method | Endpoint | Description |
|----------|--------|----------|-------------|
| Security Rotations | POST | `/security/rotations` | Trigger global token rotation |
| User Rotations | POST | `/users/{user_id}/rotations` | Trigger per-user token rotation |
| Security Config | GET | `/security/config` | Get current security configuration |

---

## Global Token Rotation

### POST /admin/security/rotations

Trigger global token rotation. Invalidates ALL refresh tokens with version below new minimum.

**Use Cases:**

- Database breach detected
- Security vulnerability patched
- Compliance requirement

**Request:**

```bash
curl -k -X POST "${BASE_URL}/api/v1/admin/security/rotations" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Database breach detected - rotating all tokens"
  }'
```

**Success Response (201 Created):**

```json
{
  "previous_version": 1,
  "new_version": 2,
  "grace_period_seconds": 300,
  "message": "Global token rotation triggered successfully"
}
```

**Error Responses:**

- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not authorized (admin only)
- `422 Unprocessable Entity` - Missing reason field
- `500 Internal Server Error` - Rotation failed

**Notes:**

- All existing refresh tokens with `token_version < new_version` will fail validation
- Grace period (default 300s) allows gradual transition
- Action is logged via domain events for audit trail

---

## Per-User Token Rotation

### POST /admin/users/{user_id}/rotations

Trigger token rotation for a specific user. Invalidates only that user's tokens.

**Use Cases:**

- Suspicious account activity
- User account compromise
- Administrative action

**Request:**

```bash
export USER_ID="550e8400-e29b-41d4-a716-446655440000"

curl -k -X POST "${BASE_URL}/api/v1/admin/users/${USER_ID}/rotations" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Suspicious activity detected on account"
  }'
```

**Success Response (201 Created):**

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "previous_version": 1,
  "new_version": 2,
  "message": "User token rotation triggered successfully"
}
```

**Error Responses:**

- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not authorized (admin only)
- `404 Not Found` - User not found
- `422 Unprocessable Entity` - Missing reason field
- `500 Internal Server Error` - Rotation failed

**Notes:**

- Only affects the specified user's tokens
- Other users' tokens remain valid
- User must re-authenticate after rotation

---

## Security Configuration

### GET /admin/security/config

Retrieve current security configuration including token version and grace period.

**Request:**

```bash
curl -k -X GET "${BASE_URL}/api/v1/admin/security/config" \
  -H "Content-Type: application/json"
```

**Success Response (200 OK):**

```json
{
  "global_min_token_version": 2,
  "grace_period_seconds": 300,
  "last_rotation_at": "2025-11-27T03:00:00Z",
  "last_rotation_reason": "Database breach detected"
}
```

**Error Responses:**

- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not authorized (admin only)

**Notes:**

- `last_rotation_at` and `last_rotation_reason` are null if never rotated
- Use to verify rotation was applied correctly

---

## Testing Flow

### Complete Rotation Test

```bash
# Ensure BASE_URL is set (see Setup section above)

# Step 1: Check current config
curl -k -X GET "${BASE_URL}/api/v1/admin/security/config"
# Note the global_min_token_version

# Step 2: Trigger global rotation
curl -k -X POST "${BASE_URL}/api/v1/admin/security/rotations" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Testing rotation mechanism"}'
# Response shows previous_version and new_version

# Step 3: Verify config updated
curl -k -X GET "${BASE_URL}/api/v1/admin/security/config"
# global_min_token_version should be incremented
# last_rotation_reason should match

# Step 4: Test per-user rotation
export USER_ID="<insert-user-uuid>"
curl -k -X POST "${BASE_URL}/api/v1/admin/users/${USER_ID}/rotations" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Testing per-user rotation"}'
```

### Verify Token Rejection

```bash
# After rotation, old refresh tokens should fail:

# 1. Login and get tokens (before rotation)
# 2. Trigger rotation
# 3. Wait for grace period to expire (default 300s)
# 4. Try to refresh with old token
curl -k -X POST "${BASE_URL}/api/v1/tokens" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<old-refresh-token>"}'
# Should return 401 Unauthorized
```

---

## Troubleshooting

**Issue**: Rotation returns 500 Internal Server Error

- Check database connectivity
- Verify security_config table exists
- Check application logs for specific error

**Issue**: User not found (404)

- Verify user_id is a valid UUID
- Confirm user exists in database

**Issue**: Tokens not being rejected after rotation

- Verify grace period has expired (default 300s)
- Check token_version in refresh_tokens table
- Verify global_min_token_version was incremented

---

## Rate Limiting

Admin endpoints use standard rate limiting:

| Policy | Max Requests | Refill Rate | Scope | Endpoints |
|--------|--------------|-------------|-------|----------|
| API_READ | 100 | 100/min | User | `GET /admin/security/config` |
| API_WRITE | 50 | 50/min | User | `POST /admin/security/rotations`, `POST /admin/users/{id}/rotations` |

---

## Implementation References

- **Route Registry**: All admin endpoints are defined in `src/presentation/routers/api/v1/routes/registry.py` with `AuthLevel.ADMIN` requiring admin role.
- **Handler Module**: `src/presentation/routers/api/v1/admin/token_rotation.py`
- **Domain Events**: Token rotation emits domain events for audit logging.

---

**Created**: 2025-11-27 | **Last Updated**: 2026-01-10
