# OAuth Token Rotation Guide

This guide explains how to implement OAuth token rotation correctly in Dashtam provider integrations.

## Table of Contents

- [What is Token Rotation?](#what-is-token-rotation)
- [Why Token Rotation Matters](#why-token-rotation-matters)
- [How Dashtam Handles Rotation](#how-dashtam-handles-rotation)
- [Implementation Guidelines](#implementation-guidelines)
- [Testing Token Rotation](#testing-token-rotation)
- [Common Pitfalls](#common-pitfalls)
- [Provider-Specific Behaviors](#provider-specific-behaviors)

---

## What is Token Rotation?

**Token Rotation** is a security mechanism where an OAuth provider issues a new refresh token each time you use the old one to get a new access token. The old refresh token is immediately invalidated.

### The Two Strategies

1. **No Rotation (Reusable Refresh Token)** - Most Common
   - The refresh token stays the same indefinitely
   - You use the same refresh token every time
   - The provider's response omits the `refresh_token` field
   - **Example:** Schwab (in most cases)

2. **With Rotation (One-Time Refresh Token)** - More Secure
   - Each refresh operation returns a NEW refresh token
   - The old refresh token becomes invalid immediately
   - The provider's response includes a NEW `refresh_token` field
   - **Example:** Some banking APIs, Plaid (optional)

### Visual Example

```text
NO ROTATION:
┌──────────────────────────────────────────────┐
│ Initial Authentication                       │
│ ➜ access_token: "abc123"                     │
│ ➜ refresh_token: "xyz789"                    │
└──────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────┐
│ First Refresh (30 min later)                 │
│ Send: refresh_token="xyz789"                 │
│ Get:  access_token="def456"                  │
│       (no refresh_token in response)         │
│ Keep: refresh_token="xyz789" (unchanged)     │
└──────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────┐
│ Second Refresh (30 min later)                │
│ Send: refresh_token="xyz789" (SAME)          │
│ Get:  access_token="ghi789"                  │
└──────────────────────────────────────────────┘

WITH ROTATION:
┌──────────────────────────────────────────────┐
│ Initial Authentication                       │
│ ➜ access_token: "abc123"                     │
│ ➜ refresh_token: "xyz789"                    │
└──────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────┐
│ First Refresh (30 min later)                 │
│ Send: refresh_token="xyz789"                 │
│ Get:  access_token="def456"                  │
│       refresh_token="new999" (NEW!)          │
│ Save: refresh_token="new999"                 │
│ Old:  refresh_token="xyz789" (INVALID)       │
└──────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────┐
│ Second Refresh (30 min later)                │
│ Send: refresh_token="new999" (DIFFERENT!)    │
│ Get:  access_token="ghi789"                  │
│       refresh_token="new111" (NEW!)          │
└──────────────────────────────────────────────┘
```

---

## Why Token Rotation Matters

### Security Benefits

1. **Limits Token Lifetime:** Even if a refresh token is stolen, it only works once
2. **Detects Theft:** If someone else uses the token, your next request fails
3. **Reduces Attack Window:** Stolen tokens have minimal value
4. **Prevents Replay Attacks:** Old tokens can't be reused

### Business Impact

- **No rotation:** Simpler implementation, but less secure
- **With rotation:** More secure, but requires careful handling to avoid breaking user sessions

---

## How Dashtam Handles Rotation

Dashtam uses a **universal rotation detection system** that works for ALL providers, regardless of whether they rotate tokens or not.

### Architecture

```text
┌─────────────────────────────────────────────────────┐
│  PROVIDER IMPLEMENTATION                            │
│  (Provider-specific HTTP call)                      │
│                                                     │
│  async def refresh_authentication(refresh_token):   │
│    response = await http.post(...)                  │
│    tokens = response.json()                         │
│                                                     │
│    result = {"access_token": tokens["access_token"]}│
│                                                     │
│    # KEY: Only include if provider sent it          │
│    if "refresh_token" in tokens:                    │
│        result["refresh_token"] = tokens["refresh"]  │
│                                                     │
│    return result                                    │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  TOKEN SERVICE (Universal Logic)                    │
│  (Automatic rotation detection)                     │
│                                                     │
│  if new_tokens.get("refresh_token"):                │
│    if new_tokens["refresh_token"] != old_token:     │
│      # ROTATION DETECTED                            │
│      encrypted_new = encrypt(new_refresh_token)     │
│      log("Token rotated")                           │
│    else:                                            │
│      # SAME TOKEN (edge case)                       │
│      log("Same token returned")                     │
│  else:                                              │
│    # NO ROTATION                                    │
│    log("No rotation, keeping existing token")       │
└─────────────────────────────────────────────────────┘
```

### Key Points

1. ✅ **Providers** only return what the API sends (no defaults)
2. ✅ **TokenService** automatically detects rotation
3. ✅ **Works universally** for all provider behaviors
4. ✅ **Audit logs** track rotation events
5. ✅ **No provider-specific rotation logic needed**

---

## Implementation Guidelines

### Step 1: Implement `refresh_authentication()` Method

When implementing a new provider, follow this pattern:

```python
async def refresh_authentication(self, refresh_token: str) -> Dict[str, Any]:
    """Refresh access token using refresh token.
    
    Args:
        refresh_token: Valid refresh token from provider.
        
    Returns:
        Dictionary with new tokens. Only include refresh_token if
        provider actually sends one (rotation).
    """
    async with httpx.AsyncClient(timeout=settings.get_http_timeout()) as client:
        response = await client.post(
            f"{self.base_url}/oauth/token",
            headers=self._get_auth_headers(),
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")
        
        tokens = response.json()
        
        # Build response dict - START WITH REQUIRED FIELDS
        result = {
            "access_token": tokens["access_token"],
            "expires_in": tokens.get("expires_in", 3600),
            "token_type": tokens.get("token_type", "Bearer"),
        }
        
        # ✅ CRITICAL: Only include refresh_token IF provider sent it
        if "refresh_token" in tokens:
            result["refresh_token"] = tokens["refresh_token"]
            logger.debug(f"{self.provider_name} sent new refresh token")
        else:
            logger.debug(f"{self.provider_name} did not send refresh token")
        
        return result
```

### Step 2: What NOT to Do

**❌ WRONG - Never default to old token:**

```python
# BAD - This breaks rotation detection!
return {
    "access_token": tokens["access_token"],
    "refresh_token": tokens.get("refresh_token", refresh_token),  # ❌ NO!
}
```

**Why is this wrong?**

- Makes it look like provider always returns same token
- TokenService can't detect rotation
- Breaks security if provider actually rotates

**✅ CORRECT - Only include if present:**

```python
# GOOD - Let TokenService detect rotation
result = {"access_token": tokens["access_token"]}
if "refresh_token" in tokens:
    result["refresh_token"] = tokens["refresh_token"]
return result
```

### Step 3: Optional Fields

You can include these optional fields if the provider sends them:

```python
result = {
    "access_token": tokens["access_token"],  # Required
    "expires_in": tokens.get("expires_in"),  # Optional
    "token_type": tokens.get("token_type"),  # Optional
    "id_token": tokens.get("id_token"),      # Optional (OIDC)
    "scope": tokens.get("scope"),            # Optional
}

# Only include refresh_token if provider sent it
if "refresh_token" in tokens:
    result["refresh_token"] = tokens["refresh_token"]

return result
```

---

## Testing Token Rotation

### Test Scenarios to Cover

When implementing a new provider, write tests for these scenarios:

1. **Provider rotates token** (sends new refresh_token)
2. **Provider doesn't rotate** (omits refresh_token key)
3. **Provider sends same token** (edge case)
4. **Multiple refreshes in sequence**
5. **Rotation persistence** (survives database commits)

### Example Test Structure

```python
@pytest.mark.asyncio
async def test_token_rotation_detected(db_session):
    """Test that rotation is detected when provider sends new token."""
    # Setup: Create provider with initial token
    provider = await create_test_provider(db_session)
    
    # Mock provider to return NEW refresh token
    mock_response = {
        "access_token": "new_access",
        "refresh_token": "new_refresh",  # Different from initial
        "expires_in": 3600
    }
    
    # Execute refresh
    token_service = TokenService(db_session)
    result = await token_service.refresh_token(provider.id, user.id)
    
    # Verify new refresh token was stored
    assert decrypt(result.refresh_token_encrypted) == "new_refresh"
    
    # Verify audit log shows rotation
    audit_log = await get_latest_audit_log(db_session)
    assert audit_log.details["token_rotated"] is True
    assert audit_log.details["rotation_type"] == "rotated"
```

See `tests/unit/services/test_token_rotation.py` for complete examples.

---

## Common Pitfalls

### Pitfall 1: Defaulting to Input Token

```python
# ❌ WRONG
"refresh_token": tokens.get("refresh_token", refresh_token)

# ✅ CORRECT
if "refresh_token" in tokens:
    result["refresh_token"] = tokens["refresh_token"]
```

### Pitfall 2: Not Testing All Scenarios

Make sure to test:

- ✅ Rotation happens
- ✅ No rotation (key omitted)
- ✅ Same token returned (edge case)

### Pitfall 3: Assuming Provider Behavior

Never assume:

- "Provider X always rotates" → Test both scenarios
- "Provider Y never rotates" → API may change
- "All banking providers rotate" → Each is different

### Pitfall 4: Logging Tokens in Plain Text

```python
# ❌ NEVER log actual tokens
logger.info(f"Refresh token: {refresh_token}")

# ✅ Log rotation events only
logger.info("Token rotation detected")
logger.debug("Provider sent new refresh token")
```

---

## Provider-Specific Behaviors

### Charles Schwab

**Observed Behavior:** No rotation (in most cases)

- Refresh response omits `refresh_token` field
- Same refresh token used indefinitely
- Rotation handled correctly by Dashtam's implementation

**Implementation:** `src/providers/schwab.py`

```python
# Only includes refresh_token if Schwab sends it
if "refresh_token" in tokens:
    result["refresh_token"] = tokens["refresh_token"]
```

### Future Providers (Plaid, Chase, etc.)

When adding new providers:

1. **Read the provider's documentation** for their rotation policy
2. **Implement the standard pattern** (only include if present)
3. **Test both scenarios** (with and without rotation)
4. **Document observed behavior** in provider docstring

**Example for new provider:**

```python
class ChaseProvider(BaseProvider):
    """Chase banking provider.
    
    Token Rotation: Chase DOES rotate refresh tokens on every refresh.
    Each refresh operation returns a new refresh_token that must be
    stored, and the old one becomes invalid.
    """
    
    async def refresh_authentication(self, refresh_token: str):
        # Standard implementation - works regardless of rotation
        result = {"access_token": tokens["access_token"]}
        if "refresh_token" in tokens:
            result["refresh_token"] = tokens["refresh_token"]
        return result
```

---

## Debugging Rotation Issues

### Check Audit Logs

```python
# Query audit logs for rotation events
from sqlmodel import select
from src.models.provider import ProviderAuditLog

result = await session.execute(
    select(ProviderAuditLog)
    .where(ProviderAuditLog.action == "token_refreshed")
    .order_by(ProviderAuditLog.created_at.desc())
)

for log in result.scalars():
    print(f"Rotated: {log.details['token_rotated']}")
    print(f"Type: {log.details['rotation_type']}")
```

### Check Logs

Look for these log messages:

```log
# Rotation detected
INFO: Token rotation detected for Schwab: Provider sent new refresh token

# No rotation
DEBUG: Provider Schwab did not include refresh_token in response (no rotation)

# Same token returned
DEBUG: Provider Schwab returned same refresh token (no rotation)
```

### Common Issues

1. **"Provider always shows rotation"**
   - Check if provider implementation defaults to old token
   - Should only include key if present in API response

2. **"Provider never shows rotation"**
   - Verify API actually sends refresh_token
   - Check response parsing logic

3. **"Rotation works but tokens become invalid"**
   - Ensure database commits after rotation
   - Check for race conditions in concurrent requests

---

## Summary Checklist

When implementing token rotation for a new provider:

- [ ] Read provider's OAuth documentation
- [ ] Implement `refresh_authentication()` following pattern
- [ ] Only include `refresh_token` if provider sends it
- [ ] Never default to input refresh_token
- [ ] Write tests for rotation scenarios
- [ ] Write tests for no-rotation scenarios
- [ ] Test edge case of same token returned
- [ ] Document provider's rotation behavior
- [ ] Verify audit logs capture rotation events
- [ ] Test with real API (if possible)

---

## Additional Resources

- [OAuth 2.0 RFC 6749 - Token Refresh](https://tools.ietf.org/html/rfc6749#section-6)
- [OAuth 2.0 Security Best Practices](https://tools.ietf.org/html/draft-ietf-oauth-security-topics)
- Dashtam Code:
  - `src/services/token_service.py` - Universal rotation logic
  - `src/providers/base.py` - Abstract method documentation
  - `src/providers/schwab.py` - Reference implementation
  - `tests/unit/services/test_token_rotation.py` - Comprehensive tests

---

**Questions or Issues?**

If you encounter unexpected rotation behavior:

1. Check audit logs for rotation_type
2. Review provider's API documentation
3. Test with provider's sandbox/test environment
4. Verify response format matches expectations
