# Provider OAuth Architecture

## Overview

**Purpose**: Document OAuth 2.0 implementation for provider authentication, focusing on the Authorization Code flow, token lifecycle, and Schwab-specific considerations.

**Scope**: This document covers OAuth-specific details. For universal provider concepts (protocol design, encryption, multi-provider support), see `provider-integration-architecture.md`.

---

## OAuth 2.0 Authorization Code Flow

### Why Authorization Code Flow

**Options Considered**:

1. **Implicit Flow**: Deprecated, tokens exposed in URL
2. **Client Credentials**: Server-to-server only, no user consent
3. **Authorization Code Flow**: ✅ Secure, user consent, refresh tokens

**Decision**: Authorization Code Flow (the only flow Schwab supports)

### Flow Diagram

```text
┌──────────┐                                           ┌──────────┐
│  User    │                                           │  Schwab  │
│ (Browser)│                                           │   API    │
└────┬─────┘                                           └────┬─────┘
     │                                                      │
     │  1. Click "Connect Schwab"                           │
     │ ─────────────────────────────────────►               │
     │                                      │               │
     │                              ┌───────▼───────┐       │
     │                              │   Dashtam     │       │
     │                              │    Backend    │       │
     │                              └───────┬───────┘       │
     │                                      │               │
     │  2. Redirect to Schwab /authorize    │               │
     │ ◄─────────────────────────────────────               │
     │                                                      │
     │  3. User logs in & grants consent                    │
     │ ─────────────────────────────────────────────────────►
     │                                                      │
     │  4. Redirect to callback with ?code=xxx              │
     │ ◄─────────────────────────────────────────────────────
     │                                                      │
     │  5. POST callback to Dashtam                         │
     │ ─────────────────────────────────────►               │
     │                              ┌───────▼───────┐       │
     │                              │   Dashtam     │       │
     │                              │    Backend    │       │
     │                              └───────┬───────┘       │
     │                                      │               │
     │                   6. Exchange code   │               │
     │                      for tokens      │               │
     │                                      │ ─────────────►│
     │                                      │               │
     │                                      │ ◄─────────────│
     │                   7. Receive tokens  │               │
     │                      (access + refresh)              │
     │                              ┌───────▼───────┐       │
     │                              │ Encrypt &     │       │
     │                              │ Store Tokens  │       │
     │                              └───────┬───────┘       │
     │                                      │               │
     │  8. Success! Connection established  │               │
     │ ◄─────────────────────────────────────               │
     │                                                      │
```

### Step-by-Step Implementation

#### Step 1-2: Generate Authorization URL

```python
# src/infrastructure/providers/schwab/schwab_oauth.py
def get_authorization_url(state: str) -> str:
    """Generate Schwab OAuth authorization URL.
    
    Args:
        state: CSRF token (stored in session, validated on callback)
        
    Returns:
        Full authorization URL for redirect.
    """
    params = {
        "response_type": "code",
        "client_id": settings.schwab_api_key,
        "redirect_uri": settings.schwab_redirect_uri,
        "scope": "api",  # Schwab uses simple "api" scope
        "state": state,
    }
    return f"https://api.schwabapi.com/v1/oauth/authorize?{urlencode(params)}"
```

#### Step 3-5: Handle OAuth Callback

```python
# src/presentation/routers/oauth_callback_router.py
@router.get("/oauth/schwab/callback")
async def schwab_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    # ... dependencies
):
    """Handle Schwab OAuth callback.
    
    Query Parameters:
        code: Authorization code (on success)
        state: CSRF token (must match session)
        error: OAuth error code (on failure)
        error_description: Human-readable error
    """
    # 1. Validate CSRF state
    if state != session_state:
        raise HTTPException(400, "Invalid state parameter")
    
    # 2. Handle OAuth errors
    if error:
        await event_bus.publish(ProviderConnectionFailed(...))
        raise HTTPException(400, f"OAuth error: {error_description}")
    
    # 3. Exchange code for tokens (returns Result)
    provider = get_provider("schwab")
    match await provider.exchange_code_for_tokens(code):
        case Failure(error):
            await event_bus.publish(ProviderConnectionFailed(...))
            raise HTTPException(400, f"Token exchange failed: {error.message}")
        case Success(tokens):
            pass  # Continue with tokens
    
    # 4. Encrypt and store (returns Result)
    match encryption_service.encrypt({
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
    }):
        case Failure(error):
            raise HTTPException(500, "Encryption failed")
        case Success(encrypted):
            pass  # Continue with encrypted blob
    
    # 5. Create connection via command
    await handler.handle(ConnectProvider(
        user_id=current_user.id,
        provider_slug="schwab",
        credentials=ProviderCredentials(
            encrypted_data=encrypted,
            credential_type=CredentialType.OAUTH2,
            expires_at=datetime.now(UTC) + timedelta(seconds=tokens.expires_in),
        ),
    ))
```

#### Step 6-7: Token Exchange

```python
# src/infrastructure/providers/schwab/schwab_provider.py
class SchwabProvider:
    async def exchange_code_for_tokens(
        self, authorization_code: str
    ) -> Result[OAuthTokens, ProviderError]:
        """Exchange authorization code for access and refresh tokens.
        
        Returns Result type (railway-oriented programming).
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.schwabapi.com/v1/oauth/token",
                headers=self._get_basic_auth_headers(),
                data={
                    "grant_type": "authorization_code",
                    "code": authorization_code,
                    "redirect_uri": settings.schwab_redirect_uri,
                },
            )
            
            if response.status_code != 200:
                return Failure(ProviderAuthenticationError(
                    code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                    message=f"Token exchange failed: {response.text}",
                ))
            
            data = response.json()
            return Success(OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_in=data.get("expires_in", 1800),
                token_type=data.get("token_type", "Bearer"),
                scope=data.get("scope"),
            ))
```

---

## Token Lifecycle

### Token Types

| Token | Lifetime | Purpose | Storage |
|-------|----------|---------|---------|
| Access Token | ~30 min | API authentication | Encrypted in DB |
| Refresh Token | ~7 days | Get new access tokens | Encrypted in DB |

### Token Expiration Handling

```python
# Check if access token needs refresh
def needs_refresh(credentials: ProviderCredentials) -> bool:
    """Check if credentials need refresh.
    
    Refresh proactively when <5 minutes remain.
    """
    if credentials.expires_at is None:
        return False
    
    buffer = timedelta(minutes=5)
    return datetime.now(UTC) + buffer >= credentials.expires_at
```

---

## Token Rotation Detection

### The 3 Scenarios

When refreshing tokens, providers may handle refresh tokens differently:

| Scenario | Provider Response | Our Action |
|----------|-------------------|------------|
| 1. No rotation | No `refresh_token` in response | Keep existing refresh token |
| 2. Same token | Same `refresh_token` returned | Update (idempotent) |
| 3. New token | New `refresh_token` returned | **Must update** (old is invalid) |

### Implementation

```python
# src/infrastructure/providers/schwab/schwab_provider.py
async def refresh_access_token(
    self, refresh_token: str
) -> Result[OAuthTokens, ProviderError]:
    """Refresh access token, detecting rotation.
    
    Returns:
        Success(OAuthTokens) with refresh_token=None if not rotated.
        Failure(ProviderError) if refresh fails.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.schwabapi.com/v1/oauth/token",
            headers=self._get_basic_auth_headers(),
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        
        if response.status_code != 200:
            return Failure(ProviderAuthenticationError(
                code=ErrorCode.PROVIDER_AUTHENTICATION_FAILED,
                message=f"Token refresh failed: {response.text}",
            ))
        
        data = response.json()
        
        # Only include refresh_token if provider sent one (rotation)
        new_refresh_token = data.get("refresh_token")
        
        return Success(OAuthTokens(
            access_token=data["access_token"],
            refresh_token=new_refresh_token,  # None if no rotation
            expires_in=data.get("expires_in", 1800),
            token_type=data.get("token_type", "Bearer"),
        ))
```

### Handling Rotation in Application Layer

```python
# src/application/commands/handlers/refresh_provider_tokens_handler.py
async def handle(self, cmd: RefreshProviderTokens) -> Result[None, ApplicationError]:
    # Get current credentials (decrypt returns Result)
    connection = await self.repo.find_by_id(cmd.connection_id)
    match encryption_service.decrypt(connection.credentials.encrypted_data):
        case Failure(error):
            return Failure(ApplicationError.from_domain(error))
        case Success(current_creds):
            pass
    
    # Refresh tokens (returns Result)
    match await provider.refresh_access_token(current_creds["refresh_token"]):
        case Failure(error):
            return Failure(ApplicationError.from_domain(error))
        case Success(new_tokens):
            pass
    
    # Build new credentials dict
    new_creds = {
        "access_token": new_tokens.access_token,
        # Keep existing refresh_token if provider didn't rotate
        "refresh_token": new_tokens.refresh_token or current_creds["refresh_token"],
    }
    
    # Encrypt and update (returns Result)
    match encryption_service.encrypt(new_creds):
        case Failure(error):
            return Failure(ApplicationError.from_domain(error))
        case Success(encrypted):
            connection.update_credentials(ProviderCredentials(
                encrypted_data=encrypted,
                credential_type=CredentialType.OAUTH2,
                expires_at=datetime.now(UTC) + timedelta(seconds=new_tokens.expires_in),
            ))
    
    return Success(None)
```

---

## Callback Server Integration

### Callback URLs (Registered in Schwab Developer Portal)

| URL | Environment | Notes |
|-----|-------------|-------|
| `https://127.0.0.1:8182/oauth/schwab/callback` | Local (standalone) | Direct HTTPS, no Traefik |
| `https://dashtam.local/oauth/schwab/callback` | Local (Traefik) | Via Traefik reverse proxy |
| Production URL TBD | Production | Real domain when available |

### Option A: Traefik Route (Recommended)

Route OAuth callback through existing Traefik infrastructure:

```yaml
# compose/docker-compose.dev.yml
services:
  app:
    labels:
      # Main app routes
      - "traefik.http.routers.dashtam-dev.rule=Host(`dashtam.local`)"
      # OAuth callback is just another route on the same host
```

```python
# src/presentation/routers/oauth_callback_router.py
router = APIRouter(prefix="/oauth", tags=["oauth"])

@router.get("/{provider_slug}/callback")
async def oauth_callback(provider_slug: str, code: str = None, ...):
    """Handle OAuth callback for any provider."""
    ...
```

**Pros**: Uses existing infrastructure, standard HTTPS port  
**Cons**: Requires hosts file entry for `dashtam.local`

### Option B: Standalone HTTPS Server (Fallback)

For `https://127.0.0.1:8182`, run secondary server:

```python
# scripts/oauth_callback_server.py (development only)
import uvicorn
from src.main import create_callback_app

if __name__ == "__main__":
    uvicorn.run(
        create_callback_app(),
        host="127.0.0.1",
        port=8182,
        ssl_keyfile="certs/localhost-key.pem",
        ssl_certfile="certs/localhost.pem",
    )
```

**Pros**: Works without Traefik/hosts file  
**Cons**: Separate process, additional SSL cert management

### Configuration

```python
# .env.dev (Traefik)
SCHWAB_REDIRECT_URI=https://dashtam.local/oauth/schwab/callback

# .env.dev (standalone)
SCHWAB_REDIRECT_URI=https://127.0.0.1:8182/oauth/schwab/callback

# .env.prod (future)
SCHWAB_REDIRECT_URI=https://api.yourdomain.com/oauth/schwab/callback
```

---

## Schwab-Specific Considerations

### API Base URLs

| API | Base URL | Purpose |
|-----|----------|---------|
| OAuth | `https://api.schwabapi.com/v1/oauth` | Authorization, token exchange |
| Trader | `https://api.schwabapi.com/trader/v1` | Accounts, transactions, orders |
| Market Data | `https://api.schwabapi.com/marketdata/v1` | Quotes, charts (Phase 6+) |

### Authentication Headers

```python
def _get_basic_auth_headers(self) -> dict[str, str]:
    """HTTP Basic Auth for token endpoints."""
    credentials = f"{settings.schwab_api_key}:{settings.schwab_api_secret}"
    b64 = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

def _get_bearer_headers(self, access_token: str) -> dict[str, str]:
    """Bearer token for API endpoints."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
```

### Schwab Token Behavior

Based on testing with old Dashtam:

- **Access token lifetime**: ~30 minutes (1800 seconds)
- **Refresh token lifetime**: ~7 days
- **Token rotation**: Schwab MAY rotate refresh tokens (handle all 3 scenarios)
- **Scope**: Simple "api" scope covers all Trader API endpoints

### Rate Limits

Schwab enforces rate limits per application:

- **Order requests**: 120/minute per account (configured in app settings)
- **Data requests**: Not documented, but be conservative

Implement exponential backoff for 429 responses:

```python
async def _make_request(self, ...) -> httpx.Response:
    """Make API request with retry logic."""
    for attempt in range(3):
        response = await client.request(...)
        
        if response.status_code == 429:
            wait = 2 ** attempt  # 1, 2, 4 seconds
            await asyncio.sleep(wait)
            continue
            
        return response
    
    raise ProviderRateLimitError("Rate limit exceeded after retries")
```

---

## Security Considerations

### CSRF Protection

Always validate `state` parameter:

```python
# Generate on authorize request
state = secrets.token_urlsafe(32)
session["oauth_state"] = state

# Validate on callback
if request.query_params.get("state") != session.get("oauth_state"):
    raise HTTPException(400, "Invalid state - possible CSRF attack")
```

### Token Storage Security

1. **Encryption at rest**: AES-256-GCM (see `provider-integration-architecture.md`)
2. **Never log tokens**: Scrub from logs
3. **Memory handling**: Use `SecretStr` for in-memory token handling where possible
4. **Database access**: Tokens only decrypted when needed for API calls

### Error Handling

Never expose internal errors to users:

```python
try:
    tokens = await provider.exchange_code_for_tokens(code)
except ProviderAuthenticationError as e:
    logger.error("OAuth token exchange failed", error=str(e))
    # Generic message to user
    raise HTTPException(400, "Failed to connect to Schwab. Please try again.")
```

---

## Error Scenarios

### OAuth Errors (from Schwab)

| Error | Meaning | User Action |
|-------|---------|-------------|
| `access_denied` | User cancelled consent | Retry connection |
| `invalid_request` | Bad request parameters | Check configuration |
| `unauthorized_client` | App not authorized | Check API credentials |
| `server_error` | Schwab internal error | Retry later |

### Token Refresh Failures

| Scenario | Cause | Action |
|----------|-------|--------|
| `invalid_grant` | Refresh token expired | User must re-authenticate |
| `invalid_client` | Credentials changed | Check app configuration |
| Network error | Schwab unavailable | Retry with backoff |

### Connection State Transitions

```text
                    ┌─────────────┐
                    │   PENDING   │ (OAuth started)
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               │               ▼
    ┌─────────────┐        │        ┌─────────────┐
    │   FAILED    │        │        │   ACTIVE    │ (tokens stored)
    └─────────────┘        │        └──────┬──────┘
                           │               │
                           │    ┌──────────┼──────────┐
                           │    │          │          │
                           │    ▼          │          ▼
                           │ ┌─────────┐   │   ┌──────────────┐
                           │ │ EXPIRED │◄──┴──►│   REVOKED    │
                           │ └────┬────┘       └──────────────┘
                           │      │
                           │      │ (user re-auths)
                           │      │
                           │      ▼
                           │ ┌─────────────┐
                           └►│   ACTIVE    │
                             └─────────────┘
```

---

## Testing Strategy

### Overview

OAuth testing is split into three layers to ensure comprehensive coverage while keeping tests fast and maintainable:

- **Unit tests**: Fast, isolated tests using `pytest-httpx` mock for HTTP calls
- **API tests**: Test endpoint behavior with mocked provider layer
- **Integration tests**: Test handler + real database persistence

### Running Tests

```bash
# Run all tests (via Docker)
make test

# Start test environment only
make test-up

# Run specific OAuth tests
docker compose -f compose/docker-compose.test.yml exec app pytest tests/unit/test_infrastructure_schwab_oauth.py -v
docker compose -f compose/docker-compose.test.yml exec app pytest tests/api/test_oauth_callbacks.py -v
docker compose -f compose/docker-compose.test.yml exec app pytest tests/integration/test_connect_provider_handler.py -v
```

### Unit Tests

**File**: `tests/unit/test_infrastructure_schwab_oauth.py` (22 tests)

Covers SchwabProvider OAuth methods using `pytest-httpx` to mock HTTP responses:

- `exchange_code_for_tokens`: Success (200), Invalid (400), Unauthorized (401), Rate limited (429), Server error (5xx)
- `refresh_access_token`: No rotation, with rotation, rotation to null
- Error handling: Invalid JSON, network failures, timeout

**File**: `tests/unit/test_infrastructure_encryption_service.py` (28 tests)

Covers EncryptionService AES-256-GCM operations:

- Key generation and validation (correct length, format errors)
- Encrypt/decrypt roundtrip for various data types
- Tamper detection (altered ciphertext, tag, nonce)
- Edge cases (empty data, large payloads, unicode)

### API Tests

**File**: `tests/api/test_oauth_callbacks.py` (13 tests)

Tests endpoint behavior with monkeypatched provider layer:

- Success flow with valid state and code
- Error paths: missing code (400), invalid state (400), provider mismatch (400)
- OAuth error responses from Schwab
- Dynamic route `/oauth/{provider_slug}/callback` coverage

### Integration Tests

**File**: `tests/integration/test_connect_provider_handler.py` (8 tests)

Tests handler with real database:

- Successful connection creates `provider_connections` row with FK to `providers`
- Credentials encrypted and stored
- Error paths don't create orphan records
- Status transitions (PENDING → ACTIVE)

### Mocking Strategy

**HTTP Mocking** (`pytest-httpx`):

```python
async def test_exchange_code_success(httpx_mock):
    httpx_mock.add_response(
        method="POST",
        url="https://api.schwabapi.com/v1/oauth/token",
        json={"access_token": "test_access", "refresh_token": "test_refresh", "expires_in": 1800},
    )
    result = await provider.exchange_code_for_tokens("auth_code")
    assert result.is_success()
```

**Provider Layer Mocking** (monkeypatch):

```python
async def test_callback_success(monkeypatch, test_client):
    async def mock_exchange(self, code):
        return Success(OAuthTokens(access_token="test", ...))
    
    monkeypatch.setattr(SchwabProvider, "exchange_code_for_tokens", mock_exchange)
    response = test_client.get("/oauth/schwab/callback?code=auth&state=valid")
    assert response.status_code == 200
```

**Database Fixtures** (`tests/conftest.py`):

- `schwab_provider`: Returns seeded Schwab provider (id, slug) for FK constraints
- `provider_factory`: Creates unique test providers dynamically
- `test_database`: Provides isolated database session per test

---

**Created**: 2025-12-03 | **Last Updated**: 2025-12-03
