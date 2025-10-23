# JWT Authentication Quick Reference

A comprehensive quick reference guide for developers using the Dashtam JWT authentication system with Pattern A (JWT Access + Opaque Refresh tokens).

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

### All API Endpoints

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

### Token Lifecycle

```mermaid
flowchart TD
    A[Registration] --> B[Email Verification]
    B -->|Token valid 24h| C[Login]
    C --> D[Access Token: 30 min<br/>Refresh Token: 30 days]
    D --> E[Use Access Token<br/>for API Requests]
    E --> F{After 30 min}
    F -->|Access Token Expires| G[Use Refresh Token]
    G --> H[Get NEW Access Token]
    H --> E
    E --> I[Logout]
    I --> J[Refresh Token Revoked]
```

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

**What This Does:** Creates a new user account and sends verification email.

### Step 2: Verify Email

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

**What This Does:** Activates the user account by verifying email ownership.

### Step 3: Login

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
```

**Important Notes:**

- ⚠️ Store both tokens securely! Access token expires in 30 minutes, refresh token in 30 days.
- ℹ️ The `access_token` is used for all API requests.
- ℹ️ The `refresh_token` is used only to get new access tokens.

### Step 4: Make Authenticated Requests

```bash
# Use the access token in Authorization header
curl http://localhost:8000/api/v1/providers \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Response: 200 OK
{
  "providers": [...]
}
```

**What This Does:** Authenticates the request using the JWT access token.

### Step 5: Refresh Access Token

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
```

**Important Notes:**

- ⚠️ Update your stored access token after refresh.
- ℹ️ The refresh token remains the same (not rotated in Pattern A).

### Step 6: Logout

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
```

**What This Does:** Revokes the refresh token in the database, preventing future token refreshes.

## Examples

### Example 1: Python Client Implementation

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

**Result:** A fully functional Python authentication client with automatic token refresh.

### Example 2: JavaScript/TypeScript Client Implementation

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

**Result:** A type-safe TypeScript authentication client with automatic token refresh.

### Example 3: React Hook Implementation

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

**Result:** A production-ready React authentication hook with state management and automatic token refresh.

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

### Check 4: Token Expiry Testing

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

**Expected Result:** Should show token expiration time and remaining validity period.

## Troubleshooting

### Issue 1: Token Validation Failed

**Symptoms:**

- API returns 401 Unauthorized
- Error message: "Token validation failed" or "Invalid token"

**Cause:** Token expired, malformed, or incorrect format.

**Solution:**

```bash
# Check token format (should be three base64 parts separated by dots)
echo "Bearer eyJhbGci..." | grep -E '^Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$'

# If token expired, refresh it
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your-refresh-token"}'
```

**Additional Checks:**

- Verify token is being sent in correct format: `Authorization: Bearer <token>`
- Ensure no extra spaces or newlines in token
- Check token hasn't expired using verification steps above

### Issue 2: Refresh Token Not Found or Revoked

**Symptoms:**

- API returns 401 Unauthorized on refresh request
- Error message: "Invalid refresh token" or "Refresh token not found"

**Cause:** Token was already used for logout, expired (30 days), or revoked.

**Solution:**

User must login again to get new token pair:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

### Issue 3: Email Not Verified

**Symptoms:**

- Login returns 403 Forbidden
- Error message: "Email not verified"

**Cause:** User registered but didn't verify email address.

**Solution:**

```bash
# Check email for verification link
# In dev mode, check application logs for verification token

# Then verify:
curl -X POST http://localhost:8000/api/v1/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"token": "verification-token-from-email"}'
```

### Issue 4: Account is Locked

**Symptoms:**

- Login returns 403 Forbidden
- Error message: "Account is locked" or "Too many failed attempts"

**Cause:** Too many failed login attempts (10+) triggered account lockout.

**Solution:**

- Wait 1 hour - Account auto-unlocks after lockout period
- Or contact administrator to manually unlock account
- Prevention: Use correct credentials, avoid brute force attempts

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

**Example Error Handling:**

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

## Best Practices

Follow these best practices for secure and reliable authentication:

### Security Best Practices

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

### Common Patterns

#### Auto-Refresh Pattern

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

#### Error Handling Pattern

```typescript
async function authenticatedRequest<T>(endpoint: string): Promise<T> {
  try {
    return await api.get<T>(endpoint);
  } catch (error) {
    if (error.status === 401) {
      // Token expired, refresh and retry
      await auth.refresh();
      return await api.get<T>(endpoint);
    }
    throw error;
  }
}
```

### Quick Reference Card

```mermaid
graph TB
    subgraph "DASHTAM AUTH QUICK REFERENCE"
        A[Pattern A: JWT Access + Opaque Refresh]
        
        B["Access Token:<br/>JWT, 30 min, stateless"]
        C["Refresh Token:<br/>Random, 30 days, hashed in DB"]
        
        D["FLOW"]
        E["1. Register → Email verification"]
        F["2. Login → Get tokens"]
        G["3. Use access token Bearer header"]
        H["4. Refresh when expired 30 min"]
        I["5. Logout → Revoke refresh token"]
        
        J["ENDPOINTS"]
        K["POST /auth/register - Register<br/>POST /auth/verify-email - Verify email<br/>POST /auth/login - Login<br/>POST /auth/refresh - Refresh token<br/>POST /auth/logout - Logout<br/>GET /auth/me - Get user profile<br/>PATCH /auth/me - Update profile"]
        
        L["SECURITY"]
        M["✅ All tokens hashed in database<br/>✅ Email verification required<br/>✅ Password complexity enforced<br/>✅ Account lockout 10 failures → 1h<br/>✅ HTTPS only in production"]
        
        A --> B
        A --> C
        D --> E
        E --> F
        F --> G
        G --> H
        H --> I
        J --> K
        L --> M
    end
    
    style A fill:#e1f5ff
    style D fill:#fff3e0
    style J fill:#f3e5f5
    style L fill:#e8f5e9
```

## Next Steps

After completing this guide, consider:

- [ ] Review [JWT Authentication Architecture](../architecture/jwt-authentication.md) for complete system design
- [ ] Explore [Token Rotation Guide](token-rotation.md) for advanced security patterns
- [ ] Implement [Error Handling Best Practices](testing-best-practices.md) in your client
- [ ] Set up automated tests for authentication flows
- [ ] Configure secure token storage in production (httpOnly cookies)
- [ ] Add monitoring and alerting for authentication failures
- [ ] Review [REST API Design](../architecture/restful-api-design.md) for API integration patterns

## References

- [JWT Authentication Architecture](../architecture/jwt-authentication.md) - Complete system architecture and design
- [API Documentation](http://localhost:8000/docs) - Interactive OpenAPI documentation
- [Token Rotation Guide](token-rotation.md) - Advanced token security patterns
- [REST API Design](../architecture/restful-api-design.md) - API design principles
- [Testing Guide](testing-guide.md) - Authentication testing strategies

---

## Document Information

**Template:** [guide-template.md](../../templates/guide-template.md)
**Created:** 2025-10-04
**Last Updated:** 2025-10-20
