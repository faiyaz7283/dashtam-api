# JWT Authentication Quick Reference

A comprehensive quick reference guide for developers using the Dashtam JWT authentication system with Pattern A (JWT Access + Opaque Refresh tokens).

---

## Table of Contents

- [Overview](#overview)
  - [What You'll Learn](#what-youll-learn)
  - [When to Use This Guide](#when-to-use-this-guide)
  - [Authentication Pattern](#authentication-pattern)
- [Prerequisites](#prerequisites)
- [Step-by-Step Instructions](#step-by-step-instructions)
  - [1. Register a New User](#1-register-a-new-user)
  - [2. Verify Email](#2-verify-email)
  - [3. Login](#3-login)
  - [4. Make Authenticated Requests](#4-make-authenticated-requests)
  - [5. Refresh Access Token (When Expired)](#5-refresh-access-token-when-expired)
  - [6. Logout](#6-logout)
- [Examples](#examples)
  - [Python Client Example](#python-client-example)
  - [JavaScript/TypeScript Client Example](#javascripttypescript-client-example)
  - [React Hook Example](#react-hook-example)
- [Verification](#verification)
  - [Check 1: Registration and Email Verification](#check-1-registration-and-email-verification)
  - [Check 2: Token Validation](#check-2-token-validation)
  - [Check 3: Protected Endpoint Access](#check-3-protected-endpoint-access)
- [All API Endpoints](#all-api-endpoints)
- [Common Patterns](#common-patterns)
  - [Auto-Refresh Pattern](#auto-refresh-pattern)
  - [Token Storage (Security)](#token-storage-security)
- [Troubleshooting](#troubleshooting)
  - [Common Error Codes](#common-error-codes)
  - [Example Error Handling](#example-error-handling)
  - [Common Authentication Issues](#common-authentication-issues)
- [Token Lifecycle](#token-lifecycle)
- [Best Practices](#best-practices)
  - [Token Storage Security](#token-storage-security-1)
- [Testing](#testing)
  - [Test Account Creation](#test-account-creation)
  - [Check Token Expiry](#check-token-expiry)
- [Quick Reference Card](#quick-reference-card)
  - [Authentication Pattern A: JWT Access + Opaque Refresh](#authentication-pattern-a-jwt-access--opaque-refresh)
  - [API Endpoints Reference](#api-endpoints-reference)
  - [Security Features](#security-features)
- [References](#references)

---

## Overview

This guide provides quick reference information for integrating with Dashtam's JWT authentication system. You'll learn how to register users, authenticate, manage tokens, and handle common authentication scenarios.

### What You'll Learn

- How to register and verify user accounts
- How to login and manage JWT access tokens
- How to implement token refresh patterns
- How to build authentication clients in Python, JavaScript/TypeScript, and React
- How to handle common authentication errors

### When to Use This Guide

Use this guide when:

- Building client applications that integrate with Dashtam
- Implementing user authentication flows
- Need quick reference for API endpoints and patterns
- Troubleshooting authentication issues

### Authentication Pattern

**Pattern A:** JWT Access + Opaque Refresh

- **Access Token:** JWT, 30 minutes TTL, stateless
- **Refresh Token:** Opaque, 30 days TTL, hashed in database

## Prerequisites

Before using this guide, ensure you have:

- [ ] Dashtam API server running (localhost:8000 or production URL)
- [ ] Valid API endpoint access
- [ ] HTTP client (curl, Postman, or programmatic client)

**Required Tools:**

- curl - For command line testing
- Python 3.13+ - For Python examples (optional)
- Node.js 18+ - For JavaScript/TypeScript examples (optional)
- React 18+ - For React hook examples (optional)

**Required Knowledge:**

- Basic understanding of HTTP/REST APIs
- Familiarity with JWT tokens
- Understanding of authentication vs authorization

## Step-by-Step Instructions

### Step 1: Register a New User

### 1. Register a New User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "name": "John Doe"
  }'

# Response: 201 Created
{
  "message": "Registration successful. Please check your email to verify your account."
}
```

### 2. Verify Email

```bash
# User clicks link in email, or:
curl -X POST http://localhost:8000/api/v1/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{
    "token": "abc123def456..."
  }'

# Response: 200 OK
{
  "message": "Email verified successfully. You can now log in."
}
```

### 3. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'

# Response: 200 OK
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "a8f4e2d9c1b7f6e3d2c8b4a1e9f7d6c5...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "name": "John Doe",
    "email_verified": true,
    "is_active": true,
    "created_at": "2025-10-04T20:00:00Z",
    "last_login_at": "2025-10-04T22:00:00Z"
  }
}

# Store both tokens securely!
# - access_token: Use for API requests (expires in 30 min)
# - refresh_token: Use to get new access token (expires in 30 days)
```

### 4. Make Authenticated Requests

```bash
# Use the access token in Authorization header
curl http://localhost:8000/api/v1/providers \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Response: 200 OK
{
  "providers": [...]
}
```

### 5. Refresh Access Token (When Expired)

```bash
# After 30 minutes, access token expires
# Use refresh token to get new access token
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "a8f4e2d9c1b7f6e3d2c8b4a1e9f7d6c5..."
  }'

# Response: 200 OK
{
  "access_token": "eyJnEwMiOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",  # NEW
  "refresh_token": "a8f4e2d9c1b7f6e3d2c8b4a1e9f7d6c5...",  # SAME
  "token_type": "bearer",
  "expires_in": 1800
}

# Update your stored access token
```

### 6. Logout

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "a8f4e2d9c1b7f6e3d2c8b4a1e9f7d6c5..."
  }'

# Response: 200 OK
{
  "message": "Logged out successfully"
}

# Delete stored tokens from client
```

## Examples

### Python Client Example

```python
import httpx
from typing import Optional

class DashtamAuth:
    """Simple authentication client for Dashtam API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.client = httpx.Client()
    
    def register(self, email: str, password: str, name: str) -> dict:
        """Register a new user."""
        response = self.client.post(
            f"{self.base_url}/api/v1/auth/register",
            json={"email": email, "password": password, "name": name}
        )
        response.raise_for_status()
        return response.json()
    
    def login(self, email: str, password: str) -> dict:
        """Login and store tokens."""
        response = self.client.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        
        # Store tokens
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        
        return data
    
    def refresh(self) -> dict:
        """Refresh access token using refresh token."""
        if not self.refresh_token:
            raise ValueError("No refresh token available")
        
        response = self.client.post(
            f"{self.base_url}/api/v1/auth/refresh",
            json={"refresh_token": self.refresh_token}
        )
        response.raise_for_status()
        data = response.json()
        
        # Update access token
        self.access_token = data["access_token"]
        
        return data
    
    def get(self, endpoint: str) -> dict:
        """Make authenticated GET request."""
        if not self.access_token:
            raise ValueError("Not authenticated")
        
        response = self.client.get(
            f"{self.base_url}{endpoint}",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        
        # Auto-refresh if token expired
        if response.status_code == 401:
            self.refresh()
            response = self.client.get(
                f"{self.base_url}{endpoint}",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
        
        response.raise_for_status()
        return response.json()
    
    def logout(self):
        """Logout and clear tokens."""
        if self.refresh_token:
            self.client.post(
                f"{self.base_url}/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={"refresh_token": self.refresh_token}
            )
        
        # Clear tokens
        self.access_token = None
        self.refresh_token = None


# Usage Example
if __name__ == "__main__":
    auth = DashtamAuth()
    
    # Register
    auth.register("user@example.com", "SecurePass123!", "John Doe")
    print("✅ Registered! Check email to verify.")
    
    # Login
    result = auth.login("user@example.com", "SecurePass123!")
    print(f"✅ Logged in as {result['user']['name']}")
    
    # Make authenticated request
    providers = auth.get("/api/v1/providers")
    print(f"✅ Found {len(providers)} providers")
    
    # Logout
    auth.logout()
    print("✅ Logged out")
```

---

## JavaScript/TypeScript Client Example

```typescript
interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface User {
  id: string;
  email: string;
  name: string;
  email_verified: boolean;
  is_active: boolean;
  created_at: string;
  last_login_at: string;
}

class DashtamAuth {
  private baseUrl: string;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor(baseUrl: string = "http://localhost:8000") {
    this.baseUrl = baseUrl;
  }

  async register(email: string, password: string, name: string): Promise<{message: string}> {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    });

    if (!response.ok) throw new Error("Registration failed");
    return response.json();
  }

  async login(email: string, password: string): Promise<{ user: User }> {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) throw new Error("Login failed");
    
    const data: AuthTokens & { user: User } = await response.json();
    
    // Store tokens (in production, use httpOnly cookies or secure storage)
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    
    return { user: data.user };
  }

  async refresh(): Promise<void> {
    if (!this.refreshToken) throw new Error("No refresh token available");

    const response = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: this.refreshToken }),
    });

    if (!response.ok) throw new Error("Token refresh failed");
    
    const data: AuthTokens = await response.json();
    this.accessToken = data.access_token;
  }

  async get<T>(endpoint: string): Promise<T> {
    if (!this.accessToken) throw new Error("Not authenticated");

    let response = await fetch(`${this.baseUrl}${endpoint}`, {
      headers: { Authorization: `Bearer ${this.accessToken}` },
    });

    // Auto-refresh if token expired
    if (response.status === 401) {
      await this.refresh();
      response = await fetch(`${this.baseUrl}${endpoint}`, {
        headers: { Authorization: `Bearer ${this.accessToken}` },
      });
    }

    if (!response.ok) throw new Error("Request failed");
    return response.json();
  }

  async logout(): Promise<void> {
    if (this.refreshToken && this.accessToken) {
      await fetch(`${this.baseUrl}/api/v1/auth/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      });
    }

    // Clear tokens
    this.accessToken = null;
    this.refreshToken = null;
  }

  isAuthenticated(): boolean {
    return this.accessToken !== null;
  }
}

// Usage Example
const auth = new DashtamAuth();

// Register
await auth.register("user@example.com", "SecurePass123!", "John Doe");
console.log("✅ Registered! Check email to verify.");

// Login
const { user } = await auth.login("user@example.com", "SecurePass123!");
console.log(`✅ Logged in as ${user.name}`);

// Make authenticated request
const providers = await auth.get("/api/v1/providers");
console.log(`✅ Found ${providers.length} providers`);

// Logout
await auth.logout();
console.log("✅ Logged out");
```

---

## React Hook Example

```typescript
import { useState, useEffect, useCallback } from 'react';

interface User {
  id: string;
  email: string;
  name: string;
  email_verified: boolean;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  error: string | null;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isLoading: true,
    error: null,
  });

  // Load tokens from storage on mount
  useEffect(() => {
    const accessToken = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    const userStr = localStorage.getItem('user');
    
    if (accessToken && refreshToken && userStr) {
      setState({
        user: JSON.parse(userStr),
        accessToken,
        refreshToken,
        isLoading: false,
        error: null,
      });
    } else {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    
    try {
      const response = await fetch('http://localhost:8000/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) throw new Error('Login failed');

      const data = await response.json();
      
      // Store tokens (WARNING: localStorage is vulnerable to XSS)
      // In production, use httpOnly cookies
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      localStorage.setItem('user', JSON.stringify(data.user));

      setState({
        user: data.user,
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        isLoading: false,
        error: null,
      });
    } catch (error) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error.message,
      }));
    }
  }, []);

  const logout = useCallback(async () => {
    if (state.refreshToken && state.accessToken) {
      try {
        await fetch('http://localhost:8000/api/v1/auth/logout', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${state.accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ refresh_token: state.refreshToken }),
        });
      } catch (error) {
        console.error('Logout failed:', error);
      }
    }

    // Clear storage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');

    setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isLoading: false,
      error: null,
    });
  }, [state.accessToken, state.refreshToken]);

  const refreshAccessToken = useCallback(async () => {
    if (!state.refreshToken) return;

    try {
      const response = await fetch('http://localhost:8000/api/v1/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: state.refreshToken }),
      });

      if (!response.ok) throw new Error('Refresh failed');

      const data = await response.json();
      
      localStorage.setItem('access_token', data.access_token);

      setState(prev => ({
        ...prev,
        accessToken: data.access_token,
      }));
    } catch (error) {
      // Refresh failed, logout user
      await logout();
    }
  }, [state.refreshToken, logout]);

  return {
    user: state.user,
    isAuthenticated: !!state.user,
    isLoading: state.isLoading,
    error: state.error,
    login,
    logout,
    refreshAccessToken,
  };
}

// Usage in component
function LoginPage() {
  const { login, isLoading, error } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await login(email, password);
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Logging in...' : 'Login'}
      </button>
      {error && <div className="error">{error}</div>}
    </form>
  );
}
```

## Verification

How to verify your authentication integration is working correctly:

### Check 1: Registration and Email Verification

```bash
# Test user registration
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "name": "Test User"
  }')

echo "Registration: $REGISTER_RESPONSE"
```

**Expected Result:** Should receive `201 Created` with message about email verification.

### Check 2: Token Validation

```bash
# Verify JWT token structure (decode without validation)
python3 -c "
import jwt
import json
token = 'your-jwt-token-here'
decoded = jwt.decode(token, options={'verify_signature': False})
print(json.dumps(decoded, indent=2))
"
```

**Expected Result:** Should show JWT payload with `sub`, `exp`, `iat` fields.

### Check 3: Protected Endpoint Access

```bash
# Test authenticated request
curl -H "Authorization: Bearer your-access-token" \
  http://localhost:8000/api/v1/auth/me
```

**Expected Result:** Should return user profile information.

---

## All API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/auth/register` | POST | No | Register new user |
| `/api/v1/auth/verify-email` | POST | No | Verify email address |
| `/api/v1/auth/login` | POST | No | Login with credentials |
| `/api/v1/auth/refresh` | POST | No* | Get new access token |
| `/api/v1/auth/logout` | POST | Yes | Revoke refresh token |
| `/api/v1/auth/password-reset/request` | POST | No | Request password reset |
| `/api/v1/auth/password-reset/confirm` | POST | No | Confirm password reset |
| `/api/v1/auth/me` | GET | Yes | Get current user |
| `/api/v1/auth/me` | PATCH | Yes | Update user profile |

*Requires valid refresh token (not access token)

---

## Common Patterns

### Auto-Refresh Pattern

```python
def make_request(url: str, auth_client: DashtamAuth):
    """Make request with automatic token refresh."""
    try:
        return auth_client.get(url)
    except HTTPException as e:
        if e.status_code == 401:
            # Access token expired, refresh it
            auth_client.refresh()
            # Retry request
            return auth_client.get(url)
        raise
```

### Token Storage (Security)

**❌ DON'T** (Vulnerable to XSS):

```javascript
// Storing tokens in localStorage
localStorage.setItem('access_token', token);
```

**✅ DO** (More secure):

```javascript
// Use httpOnly cookies (backend sets it)
// Or use memory storage (lost on refresh, but safer)
const [accessToken, setAccessToken] = useState(null);
```

**🏆 BEST** (Production):

- Access token: Memory (React state)
- Refresh token: httpOnly cookie (auto-sent)
- Backend returns `Set-Cookie` header with httpOnly flag

## Troubleshooting

### Common Error Codes

| Status | Error | Solution |
|--------|-------|----------|
| 400 | `Email already registered` | Use different email |
| 400 | `Password too weak` | Use stronger password (8+ chars, mixed case, digits, symbols) |
| 401 | `Invalid email or password` | Check credentials |
| 401 | `Invalid refresh token` | Login again |
| 403 | `Email not verified` | Verify email first |
| 403 | `Account is disabled` | Contact support |
| 403 | `Account is locked` | Wait 1 hour or contact support |

### Example Error Handling

```python
try:
    auth.login(email, password)
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        print("Invalid credentials")
    elif e.response.status_code == 403:
        error = e.response.json()
        if "not verified" in error["detail"].lower():
            print("Please verify your email first")
        elif "locked" in error["detail"].lower():
            print("Account locked due to failed attempts")
    else:
        print(f"Error: {e.response.json()['detail']}")
```

---

## Token Lifecycle

```text
REGISTRATION
    ↓
EMAIL VERIFICATION (token valid 24h)
    ↓
LOGIN → Access Token (30 min) + Refresh Token (30 days)
    ↓
USE Access Token for API requests
    ↓
After 30 min → Access Token EXPIRES
    ↓
Use Refresh Token → Get NEW Access Token
    ↓
Repeat...
    ↓
LOGOUT → Refresh Token REVOKED
```

## Best Practices

Follow these best practices for secure and reliable authentication:

- ✅ **Never Log Tokens:** Treat tokens like passwords - never log or expose them
- ✅ **Always Use HTTPS:** Tokens transmitted over HTTP can be intercepted
- ✅ **Secure Token Storage:** Use httpOnly cookies for refresh tokens, memory for access tokens
- ✅ **Implement Auto-Refresh:** Handle token expiry gracefully with automatic refresh
- ✅ **Use Strong Passwords:** Enforce password complexity (8+ chars, mixed case, symbols)
- ✅ **Logout on Suspicious Activity:** Revoke tokens on multiple failed attempts
- ✅ **One Token Per Device:** Each device/session should have its own token pair

### Token Storage Security

**❌ DON'T** (Vulnerable to XSS):

```javascript
// Storing tokens in localStorage
localStorage.setItem('access_token', token);
```

**✅ DO** (More secure):

```javascript
// Use httpOnly cookies (backend sets it) or memory storage
const [accessToken, setAccessToken] = useState(null);
```

**🏆 BEST** (Production):

- Access token: Memory storage (React state)
- Refresh token: httpOnly cookie (auto-sent by browser)
- Backend returns `Set-Cookie` header with httpOnly flag

---

## Testing

### Test Account Creation

```bash
# Create test user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "name": "Test User"
  }'

# In development, check logs for verification token
# (emails are not actually sent in DEBUG mode)
```

### Check Token Expiry

```python
import jwt
from datetime import datetime

# Decode token (without verification for inspection)
token = "eyJhbGci..."
decoded = jwt.decode(token, options={"verify_signature": False})

# Check expiration
exp_timestamp = decoded['exp']
exp_time = datetime.fromtimestamp(exp_timestamp)
print(f"Token expires at: {exp_time}")
print(f"Time remaining: {exp_time - datetime.now()}")
```

### Common Authentication Issues

#### "Token validation failed"

- Check token hasn't expired
- Verify token is being sent in correct format: `Authorization: Bearer <token>`
- Ensure no extra spaces or newlines in token

#### "Refresh token not found or revoked"

- Token was already used for logout
- Token expired (30 days)
- User needs to login again

#### "Email not verified"

- User must verify email before logging in
- Check email for verification link
- In dev mode, check logs for token

#### "Account is locked"

- Too many failed login attempts (10+)
- Wait 1 hour or contact administrator
- Account auto-unlocks after lockout period

---

## Quick Reference Card

### Authentication Pattern A: JWT Access + Opaque Refresh

```mermaid
flowchart TD
    A[User Registration] --> B[Email Verification Required]
    B --> C[Login with Email/Password]
    C --> D[Receive Token Pair]
    D --> E[Access Token: JWT, 30 min]
    D --> F[Refresh Token: Opaque, 30 days]
    E --> G[Make API Requests]
    G --> H{Token Expired?}
    H -->|No| G
    H -->|Yes| I[Use Refresh Token]
    I --> J[Get New Access Token]
    J --> G
    K[Logout] --> L[Revoke Refresh Token]
    
    style E fill:#e1f5fe
    style F fill:#fff3e0
    style G fill:#e8f5e8
```

### API Endpoints Reference

| Endpoint | Method | Purpose | Auth Required |
|----------|---------|---------|---------------|
| `/auth/register` | POST | User registration | ❌ |
| `/auth/verify-email` | POST | Email verification | ❌ |
| `/auth/login` | POST | User login | ❌ |
| `/auth/refresh` | POST | Token refresh | ❌ |
| `/auth/logout` | POST | User logout | ✅ |
| `/auth/me` | GET | Get user profile | ✅ |
| `/auth/me` | PATCH | Update profile | ✅ |

### Security Features

- ✅ **Token Security**: All refresh tokens hashed in database
- ✅ **Email Verification**: Required before login access
- ✅ **Password Policy**: Complexity requirements enforced
- ✅ **Account Protection**: Lockout after 10 failed attempts (1 hour)
- ✅ **Transport Security**: HTTPS only in production
- ✅ **Token Expiry**: Short-lived access tokens (30 minutes)

## References

- [JWT Authentication Architecture](../architecture/jwt-authentication.md) - Complete system architecture and design
- [API Documentation](http://localhost:8000/docs) - Interactive OpenAPI documentation
- [Authentication Implementation Guide](authentication-implementation.md) - Detailed implementation guide
- [Token Rotation Guide](token-rotation.md) - Advanced token security patterns
- [REST API Design](../architecture/restful-api-design.md) - API design principles

---

## Document Information

**Category:** Guide
**Created:** 2025-10-04
**Last Updated:** 2025-10-15
**Difficulty Level:** Intermediate
**Estimated Time:** 30-45 minutes
