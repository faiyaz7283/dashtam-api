# Async vs Sync Design Patterns

**Document Purpose**: Define when to use async vs sync patterns in Dashtam, following industry best practices and maintaining consistency.

**Last Updated**: 2025-10-04  
**Status**: Active Standard

---

## Core Principle

> **Use `async def` for I/O-bound operations. Use `def` for CPU-bound operations.**

This ensures optimal performance, maintains FastAPI best practices, and keeps code clean and maintainable.

---

## The Rule

### Use `async def` when

- ✅ Performing database operations (SELECT, INSERT, UPDATE, DELETE)
- ✅ Making HTTP/network requests to external APIs
- ✅ Reading/writing files asynchronously
- ✅ Calling other async functions with `await`
- ✅ Using async libraries (httpx, asyncpg, etc.)

### Use `def` (synchronous) when

- ✅ Performing pure computational work (encryption, hashing, parsing)
- ✅ Using synchronous-only libraries (passlib/bcrypt, cryptography)
- ✅ Implementing utility functions with no I/O
- ✅ Working with in-memory data structures
- ✅ Mathematical calculations

---

## Dashtam Service Patterns

### Pattern 1: I/O-Bound Services (Use `async def`)

**Example - TokenService, AuthService:**

```python
class TokenService:
    """Service with I/O operations - uses async."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def store_tokens(self, provider_id: UUID, tokens: dict) -> ProviderToken:
        """Store tokens - requires database I/O."""
        # Database query - needs await
        result = await self.session.execute(
            select(Provider).where(Provider.id == provider_id)
        )
        provider = result.scalar_one_or_none()
        
        # More database operations
        self.session.add(token)
        await self.session.flush()
        
        return token
    
    async def refresh_token(self, provider_id: UUID) -> dict:
        """Refresh token - makes HTTP call."""
        # HTTP request to provider API - needs await
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
        
        return response.json()
```

**Why async?**

- Database operations with `AsyncSession`
- HTTP requests with `httpx.AsyncClient`
- Must `await` I/O operations

---

### Pattern 2: CPU-Bound Services (Use `def`)

**Example - EncryptionService, PasswordService:**

```python
class PasswordService:
    """Service with CPU operations - uses sync."""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"])
    
    def hash_password(self, password: str) -> str:
        """Hash password - CPU-intensive but synchronous."""
        # Bcrypt hashing is synchronous by design
        # Takes ~300ms but doesn't block event loop improperly
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain: str, hashed: str) -> bool:
        """Verify password - CPU-intensive computation."""
        return self.pwd_context.verify(plain, hashed)
    
    def validate_password_strength(self, password: str) -> tuple[bool, str]:
        """Validate password - pure computation, no I/O."""
        if len(password) < 8:
            return False, "Too short"
        # ... more validation logic
        return True, None
```

**Why sync?**

- Pure CPU operations (no I/O)
- Libraries are synchronous (passlib, cryptography)
- Can be called from async code without issues
- Simpler to test and reason about

---

### Pattern 3: Hybrid Services (Sync methods, async wrappers if needed)

**When CPU-bound operations need async behavior:**

```python
class PasswordService:
    """Primarily sync service with optional async wrappers."""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"])
    
    # Primary interface - synchronous
    def hash_password(self, password: str) -> str:
        """Synchronous password hashing."""
        return self.pwd_context.hash(password)
    
    # Optional async wrapper for high-concurrency scenarios
    async def hash_password_async(self, password: str) -> str:
        """Async wrapper that offloads to thread pool.
        
        Use this only in high-concurrency scenarios where
        blocking for 300ms is problematic.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Use default ThreadPoolExecutor
            self.hash_password,
            password
        )
```

**When to use async wrappers:**

- High-concurrency endpoints where 300ms+ blocking is noticeable
- Operations taking >100ms that would benefit from parallelism
- NOT needed initially - add when performance profiling shows need

---

## FastAPI Endpoint Patterns

### Async Endpoint (Recommended for most cases)

```python
@router.post("/login")
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session)
):
    """Async endpoint - can mix sync and async operations."""
    auth_service = AuthService(session)
    password_service = PasswordService()  # Sync service
    
    # Get user from database (async I/O)
    user = await auth_service.get_user_by_email(request.email)
    
    # Verify password (sync CPU operation - called directly)
    if not password_service.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate tokens (sync CPU operation)
    jwt_service = JWTService()
    access_token = jwt_service.create_access_token(user.id, user.email)
    
    # Store refresh token (async I/O)
    refresh_token = await auth_service.create_refresh_token(user.id)
    
    return {"access_token": access_token, "refresh_token": refresh_token}
```

**Key Points:**

- Endpoint is `async def`
- Can call sync functions directly (password_service.verify_password)
- Must `await` async functions (auth_service.get_user_by_email)
- FastAPI handles the sync/async bridge automatically

---

## Current Dashtam Service Classification

### Async Services (I/O-bound)

| Service | Reason | I/O Type |
|---------|--------|----------|
| `TokenService` | Database operations, HTTP calls to providers | PostgreSQL, HTTP |
| `AuthService` | Database operations, user management | PostgreSQL |
| `EmailService` | Sends emails via AWS SES | HTTP/Network |

### Sync Services (CPU-bound)

| Service | Reason | Operation Type |
|---------|--------|----------------|
| `EncryptionService` | AES encryption/decryption | CPU (cryptography) |
| `PasswordService` | Bcrypt hashing/verification | CPU (passlib) |
| `JWTService` | JWT encoding/decoding | CPU (python-jose) |

---

## Best Practices

### 1. Don't Mix Patterns Within a Service

```python
# ❌ BAD - Mixing async/sync in same service
class BadService:
    def sync_method(self):
        pass
    
    async def async_method(self):
        pass

# ✅ GOOD - Consistent pattern based on service type
class GoodService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def method1(self):
        await self.session.execute(...)
    
    async def method2(self):
        await self.session.execute(...)
```

### 2. Call Sync from Async (Not Async from Sync)

```python
# ✅ CORRECT - Calling sync from async
async def async_endpoint():
    password_service = PasswordService()  # Sync service
    hashed = password_service.hash_password("password")  # Direct call
    
    auth_service = AuthService(session)  # Async service
    user = await auth_service.get_user(user_id)  # Must await

# ❌ WRONG - Calling async from sync
def sync_function():
    auth_service = AuthService(session)
    user = auth_service.get_user(user_id)  # Missing await, will fail!
```

### 3. Use Dependency Injection for Services

```python
# ✅ CORRECT - Services injected with dependencies
@router.post("/endpoint")
async def endpoint(session: AsyncSession = Depends(get_session)):
    # Inject session into async service
    auth_service = AuthService(session)
    
    # No injection needed for stateless sync services
    password_service = PasswordService()
    jwt_service = JWTService()
```

### 4. Keep Service Initialization Lightweight

```python
# ✅ CORRECT - Lightweight init
class PasswordService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"])

# ❌ AVOID - Heavy init with I/O
class BadService:
    def __init__(self):
        self.data = self.load_from_database()  # Sync I/O in __init__!
```

---

## Testing Patterns

### Testing Async Services

```python
# Use pytest-asyncio for async tests
@pytest.mark.asyncio
async def test_auth_service(test_session: AsyncSession):
    """Test async service."""
    service = AuthService(test_session)
    
    # Must await async methods
    user = await service.register_user(
        email="test@example.com",
        password="SecurePass123!",
        name="Test User"
    )
    
    assert user.email == "test@example.com"
```

### Testing Sync Services

```python
# Regular synchronous tests
def test_password_service():
    """Test sync service."""
    service = PasswordService()
    
    # Direct calls, no await
    hashed = service.hash_password("MyPassword123!")
    
    assert service.verify_password("MyPassword123!", hashed) is True
    assert service.verify_password("WrongPassword", hashed) is False
```

---

## Performance Considerations

### When CPU-Bound Work Blocks

If bcrypt (or other CPU work) becomes a bottleneck:

**Option 1: Thread Pool (Recommended):**

```python
async def hash_password_async(password: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, hash_password, password)
```

**Option 2: Process Pool (For heavy computation):**

```python
from concurrent.futures import ProcessPoolExecutor

async def heavy_computation_async(data: str) -> str:
    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as pool:
        return await loop.run_in_executor(pool, heavy_computation, data)
```

**Option 3: Background Tasks (Fire and forget):**

```python
from fastapi import BackgroundTasks

@router.post("/endpoint")
async def endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_email, user.email)
    return {"status": "Processing"}
```

### Current Performance Profile

| Operation | Time | Acceptable? | Async Needed? |
|-----------|------|-------------|---------------|
| Bcrypt hash (12 rounds) | ~300ms | ✅ Yes | Not yet |
| JWT generation | <1ms | ✅ Yes | No |
| AES encryption | <1ms | ✅ Yes | No |
| Database query | 1-50ms | ✅ Yes | Already async |
| HTTP provider call | 100-1000ms | ✅ Yes | Already async |

**Verdict**: Current sync services are performant enough. Monitor in production.

---

## When to Revisit This Decision

Monitor these metrics in production:

1. **Request latency p95/p99** - If >500ms due to password hashing
2. **Concurrent user load** - If >100 simultaneous logins cause issues
3. **CPU usage** - If bcrypt saturates CPU during peak times
4. **User complaints** - If login feels slow (>1s response time)

**Action**: If any of the above occur, implement async wrappers using `run_in_executor`.

---

## Migration Path (If Needed)

### Step 1: Add Async Wrappers

```python
class PasswordService:
    def hash_password(self, password: str) -> str:
        """Original sync method - keep for backward compatibility."""
        return self.pwd_context.hash(password)
    
    async def hash_password_async(self, password: str) -> str:
        """New async wrapper for high-concurrency."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.hash_password, password)
```

### Step 2: Update Endpoints

```python
@router.post("/register")
async def register(request: RegisterRequest):
    password_service = PasswordService()
    
    # Use async wrapper for better concurrency
    hashed = await password_service.hash_password_async(request.password)
```

### Step 3: Deprecate Sync Methods

```python
def hash_password(self, password: str) -> str:
    """DEPRECATED: Use hash_password_async() instead."""
    warnings.warn("Use hash_password_async()", DeprecationWarning)
    return self.pwd_context.hash(password)
```

---

## Summary

| Aspect | Async (`async def`) | Sync (`def`) |
|--------|---------------------|--------------|
| **Use for** | I/O operations | CPU operations |
| **Examples** | Database, HTTP, Files | Encryption, Hashing, Parsing |
| **Services** | TokenService, AuthService, EmailService | PasswordService, JWTService, EncryptionService |
| **Can call from** | Async code only (with `await`) | Both sync and async code |
| **Testing** | `@pytest.mark.asyncio` | Regular `def test_*()` |
| **Performance** | Non-blocking I/O | Blocks during computation |
| **Complexity** | Higher (async/await) | Lower (straightforward) |

---

## References

- [FastAPI Async SQL Databases](https://fastapi.tiangolo.com/advanced/async-sql-databases/)
- [Python asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
- [When to use async in Python](https://stackoverflow.com/questions/49005651/how-does-asyncio-actually-work)
- [Bcrypt and async discussion](https://github.com/pyca/bcrypt/issues/394)

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-10-04 | Keep PasswordService synchronous | Follows EncryptionService pattern, bcrypt is sync-only, no performance issues identified |
| 2025-10-04 | Keep JWTService synchronous | Pure CPU work (<1ms), python-jose is synchronous |
| 2025-10-04 | Keep AuthService asynchronous | Performs database I/O operations |
| 2025-10-04 | Keep EmailService asynchronous | Performs HTTP/network I/O to AWS SES |

**Next Review**: When production metrics indicate performance issues with sync services.
