# Authentication API

## Overview

This document describes the authentication API endpoints for Dashtam.
All authentication endpoints follow RESTful conventions with resource-based URLs.

**Base URL**: `https://dashtam.local/api/v1`

---

## Endpoints Summary

| Resource | Method | Endpoint | Description |
|----------|--------|----------|-------------|
| Users | POST | `/users` | Register new user |
| Sessions | POST | `/sessions` | Login (create session) |
| Sessions | DELETE | `/sessions/current` | Logout (end session) |
| Tokens | POST | `/tokens` | Refresh access token |
| Email Verifications | POST | `/email-verifications` | Verify email |
| Password Reset Tokens | POST | `/password-reset-tokens` | Request password reset |
| Password Resets | POST | `/password-resets` | Confirm password reset |

---

## User Registration

### POST /users

Register a new user account.

**Request:**

```bash
curl -k -X POST "https://dashtam.local/api/v1/users" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

**Success Response (201 Created):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "is_verified": false,
  "created_at": "2025-11-25T19:00:00Z"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid email format or weak password
- `409 Conflict` - Email already registered

**Notes:**

- Password must be 8+ characters with uppercase, lowercase, number, and special character
- Verification email is sent automatically
- User cannot login until email is verified

---

## Login (Create Session)

### POST /sessions

Authenticate user and create a session.

**Request:**

```bash
curl -k -X POST "https://dashtam.local/api/v1/sessions" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

**Success Response (201 Created):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Error Responses:**

- `401 Unauthorized` - Invalid credentials
- `403 Forbidden` - Email not verified / Account locked / Account inactive

**Notes:**

- Access token expires in 15 minutes (900 seconds)
- Refresh token is used to obtain new access tokens
- Store tokens securely (httpOnly cookies recommended)

---

## Logout (End Session)

### DELETE /sessions/current

End the current user session and revoke tokens.

**Request:**

```bash
curl -k -X DELETE "https://dashtam.local/api/v1/sessions/current" \
  -H "Authorization: Bearer <access_token>"
```

**Success Response (204 No Content):**

No body returned.

**Error Responses:**

- `401 Unauthorized` - Invalid or expired token

**Notes:**

- Refresh token is revoked server-side
- Client should discard stored tokens

---

## Refresh Token

### POST /tokens

Obtain a new access token using a refresh token.

**Request:**

```bash
curl -k -X POST "https://dashtam.local/api/v1/tokens" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "dGhpcyBpcyBhIHJlZnJlc2ggdG9rZW4..."
  }'
```

**Success Response (201 Created):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "bmV3IHJlZnJlc2ggdG9rZW4...",
  "token_type": "bearer",
  "expires_in": 900
}
```

**Error Responses:**

- `401 Unauthorized` - Invalid or expired refresh token

**Notes:**

- Old refresh token is revoked (rotation)
- New refresh token is issued with each refresh

---

## Email Verification

### POST /email-verifications

Verify user email with token from verification email.

**Request:**

```bash
curl -k -X POST "https://dashtam.local/api/v1/email-verifications" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "abc123def456..."
  }'
```

**Success Response (201 Created):**

```json
{
  "message": "Email verified successfully",
  "verified_at": "2025-11-25T19:05:00Z"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid or expired token
- `409 Conflict` - Email already verified

**Notes:**

- Token is single-use and expires after 24 hours
- After verification, user can login

---

## Request Password Reset

### POST /password-reset-tokens

Request a password reset email.

**Request:**

```bash
curl -k -X POST "https://dashtam.local/api/v1/password-reset-tokens" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com"
  }'
```

**Success Response (201 Created):**

```json
{
  "message": "If the email exists, a reset link has been sent"
}
```

**Notes:**

- Always returns success (prevents user enumeration)
- Reset email sent if account exists
- Token expires after 1 hour
- Rate limited to prevent abuse

---

## Confirm Password Reset

### POST /password-resets

Reset password with token from reset email.

**Request:**

```bash
curl -k -X POST "https://dashtam.local/api/v1/password-resets" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "xyz789...",
    "new_password": "NewSecurePassword456!"
  }'
```

**Success Response (201 Created):**

```json
{
  "message": "Password reset successfully"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid/expired token or weak password

**Notes:**

- Token is single-use
- All existing sessions are revoked after reset
- New password must meet strength requirements

---

## Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB

    Note over Client,DB: Registration Flow
    Client->>API: POST /users
    API->>DB: Create user (unverified)
    API->>Client: 201 + user data
    API-->>Client: Email with verification token

    Note over Client,DB: Email Verification
    Client->>API: POST /email-verifications
    API->>DB: Mark email verified
    API->>Client: 201 + verified

    Note over Client,DB: Login Flow
    Client->>API: POST /sessions
    API->>DB: Verify credentials
    API->>DB: Create refresh token
    API->>Client: 201 + tokens

    Note over Client,DB: Token Refresh
    Client->>API: POST /tokens
    API->>DB: Validate refresh token
    API->>DB: Rotate refresh token
    API->>Client: 201 + new tokens

    Note over Client,DB: Logout
    Client->>API: DELETE /sessions/current
    API->>DB: Revoke refresh token
    API->>Client: 204 No Content
```

---

## Error Response Format (RFC 7807)

All errors follow RFC 7807 Problem Details format:

```json
{
  "type": "https://api.dashtam.com/errors/unauthorized",
  "title": "Authentication Required",
  "status": 401,
  "detail": "Invalid credentials provided",
  "instance": "/api/v1/sessions",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Security Considerations

1. **HTTPS Only** - All endpoints require HTTPS
2. **Password Hashing** - Passwords hashed with bcrypt (cost factor 12)
3. **Token Security** - JWTs signed with HS256, refresh tokens are opaque
4. **Rate Limiting** - Login and password reset endpoints are rate limited
5. **Account Lockout** - Accounts locked after 5 failed login attempts

---

**Created**: 2025-11-25 | **Last Updated**: 2025-11-25
