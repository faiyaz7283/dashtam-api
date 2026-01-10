# Audit Usage Patterns

Quick reference guide for developers implementing audit logging in Dashtam.

**Target Audience**: Developers writing API endpoints and business logic

**Related Documentation**:

- Architecture: `architecture/audit.md` (why/what)
- API Reference: `src/domain/protocols/audit_protocol.py`
- Enum Reference: `src/domain/enums/audit_action.py`

---

## Quick Reference

| Pattern | When to Use | Enum Pattern |
| ------- | ----------- | ------------ |
| **ATTEMPTED → FAILED/SUCCESS** | State changes | `*_ATTEMPTED`, `*_FAILED` |
| **ACCESS_ATTEMPTED → DENIED/GRANTED** | Permissions | `ACCESS_ATTEMPTED` |
| **Completed Event Only** | Always succeeds | Single event |

---

## Core Principle: Audit the Timeline

**Remember**: Audit logs tell a story. The story has a beginning
(ATTEMPT), middle (business logic), and end (FAILED or SUCCESS).

```text
Time: T0  - User initiates action → Record ATTEMPTED
Time: T1  - Business logic executes
Time: T2  - Outcome determined → Record FAILED or SUCCESS
```

**Golden Rule**: Never record the ending before the story finishes!

---

## Pattern 1: User Registration

### 1a. Correct Implementation

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.container import get_db_session, get_audit
from src.domain.protocols import AuditProtocol
from src.domain.enums import AuditAction

router = APIRouter()


@router.post("/users", status_code=201)
async def register_user(
    data: UserCreate,
    session: AsyncSession = Depends(get_db_session),
    audit: AuditProtocol = Depends(get_audit),
    request: Request = None,
) -> UserResponse:
    """Register new user with complete audit trail."""
    
    # Step 1: ALWAYS record attempt first
    await audit.record(
        action=AuditAction.USER_REGISTRATION_ATTEMPTED,
        user_id=None,  # Don't have user_id yet
        resource_type="user",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        context={"email": data.email},
    )
    # ✅ Audit committed: Attempt is permanent record
    
    # Step 2: Validation (early failures)
    if await email_exists(data.email, session):
        # Record FAILURE before raising exception
        await audit.record(
            action=AuditAction.USER_REGISTRATION_FAILED,
            user_id=None,
            resource_type="user",
            ip_address=request.client.host,
            context={
                "email": data.email,
                "reason": "duplicate_email",
            },
        )
        # ✅ Audit committed: Failure is permanent record
        
        raise HTTPException(400, "Email already registered")
    
    if not is_strong_password(data.password):
        # Record FAILURE with different reason
        await audit.record(
            action=AuditAction.USER_REGISTRATION_FAILED,
            user_id=None,
            resource_type="user",
            ip_address=request.client.host,
            context={
                "email": data.email,
                "reason": "weak_password",
            },
        )
        raise HTTPException(400, "Password too weak")
    
    # Step 3: Business logic - create user
    try:
        user_id = uuid7()
        user = User(
            id=user_id,
            email=data.email,
            password_hash=hash_password(data.password),
            created_at=datetime.now(UTC),
        )
        session.add(user)
        await session.commit()  # ✅ User NOW exists in database
        
    except Exception as e:
        await session.rollback()
        
        # Record unexpected system error
        await audit.record(
            action=AuditAction.USER_REGISTRATION_FAILED,
            user_id=None,
            resource_type="user",
            ip_address=request.client.host,
            context={
                "email": data.email,
                "reason": "system_error",
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(500, "Registration failed")
    
    # Step 4: Record SUCCESS (only after business commit succeeds)
    await audit.record(
        action=AuditAction.USER_REGISTERED,
        user_id=user_id,  # NOW we have the ID
        resource_type="user",
        ip_address=request.client.host,
        context={"email": user.email},
    )
    # ✅ Audit committed: Success is permanent record
    
    return UserResponse(id=user_id, email=user.email)
```

### ❌ Common Mistakes

```python
# MISTAKE 1: Recording success BEFORE business commit
await audit.record(action=AuditAction.USER_REGISTERED, user_id=user_id, ...)
session.add(user)
await session.commit()  # ❌ If this fails, audit lies!

# MISTAKE 2: No ATTEMPT record
if email_exists:
    raise HTTPException(400)  # ❌ No audit of failed attempt!

# MISTAKE 3: Only recording success (no attempt)
user = User(...)
await session.commit()
await audit.record(action=AuditAction.USER_REGISTERED, ...)  # ❌ Missing ATTEMPTED

# MISTAKE 4: Not recording early validation failures
if not is_valid_email(data.email):
    raise HTTPException(400)  # ❌ No audit of invalid attempt!
```

### Audit Timeline (Success)

```text
10:00:00.001 - USER_REGISTRATION_ATTEMPTED (email: john@example.com)
10:00:00.150 - USER_REGISTERED (user_id: 123e4567-..., email: john@example.com)

Result: ✅ Clear story of successful registration
        ✅ Database consistent (user exists)
```

### Audit Timeline (Failure)

```text
10:05:00.001 - USER_REGISTRATION_ATTEMPTED (email: john@example.com)
10:05:00.050 - USER_REGISTRATION_FAILED (reason: duplicate_email)

Result: ✅ Clear story of failed attempt
        ✅ Database consistent (user doesn't exist)
        ✅ Compliance met (failed attempts logged)
```

---

## Pattern 2: User Login

### 2a. Correct Implementation

```python
@router.post("/auth/login")
async def login(
    data: LoginRequest,
    audit: AuditProtocol = Depends(get_audit),
    request: Request = None,
) -> TokenResponse:
    """Authenticate user with complete audit trail."""
    
    # Step 1: Record attempt
    await audit.record(
        action=AuditAction.USER_LOGIN_ATTEMPTED,
        user_id=None,  # Don't know yet
        resource_type="session",
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        context={"email": data.email},
    )
    
    # Step 2: Authenticate
    user = await find_user_by_email(data.email)
    
    if not user:
        # User not found
        await audit.record(
            action=AuditAction.USER_LOGIN_FAILED,
            user_id=None,
            resource_type="session",
            ip_address=request.client.host,
            context={
                "email": data.email,
                "reason": "user_not_found",
            },
        )
        raise HTTPException(401, "Invalid credentials")
    
    if not verify_password(data.password, user.password_hash):
        # Wrong password
        await audit.record(
            action=AuditAction.USER_LOGIN_FAILED,
            user_id=user.id,  # We know the user
            resource_type="session",
            ip_address=request.client.host,
            context={
                "email": data.email,
                "reason": "invalid_password",
                "attempts": await get_failed_attempts(user.id),
            },
        )
        raise HTTPException(401, "Invalid credentials")
    
    # Step 3: Create session (business logic)
    session_id = await create_session(user.id)
    
    # Step 4: Record SUCCESS
    await audit.record(
        action=AuditAction.USER_LOGIN_SUCCESS,
        user_id=user.id,
        resource_type="session",
        resource_id=session_id,
        ip_address=request.client.host,
        context={
            "method": "password",
            "mfa": False,
        },
    )
    
    return TokenResponse(
        access_token=create_token(user),
        token_type="bearer",
    )
```

### Security Investigation Example

```python
# Find brute force attacks
async def investigate_suspicious_login_attempts(ip_address: str):
    """Investigate failed login attempts from an IP."""
    
    result = await audit.query(
        action=AuditAction.USER_LOGIN_FAILED,
        start_date=datetime.now(UTC) - timedelta(hours=24),
        limit=1000,
    )
    
    failed_attempts = [
        log for log in result.value
        if log["ip_address"] == ip_address
    ]
    
    if len(failed_attempts) > 100:
        # Clear evidence of brute force attack
        await block_ip(ip_address)
        logger.warn(
            "Brute force attack detected",
            ip=ip_address,
            attempts=len(failed_attempts),
        )
```

---

## Pattern 3: Provider Connection (OAuth)

### 3a. Correct Implementation

```python
@router.post("/providers/{provider_name}/connect")
async def connect_provider(
    provider_name: str,
    data: OAuth2Request,
    session: AsyncSession = Depends(get_db_session),
    audit: AuditProtocol = Depends(get_audit),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> ProviderResponse:
    """Connect financial provider with complete audit trail."""
    
    # Step 1: Record attempt
    await audit.record(
        action=AuditAction.PROVIDER_CONNECTION_ATTEMPTED,
        user_id=current_user.id,
        resource_type="provider",
        ip_address=request.client.host,
        context={"provider": provider_name},
    )
    
    # Step 2: OAuth flow (may fail)
    try:
        tokens = await oauth_client.exchange_code(
            code=data.code,
            provider=provider_name,
        )
    except OAuthError as e:
        # OAuth failed
        await audit.record(
            action=AuditAction.PROVIDER_CONNECTION_FAILED,
            user_id=current_user.id,
            resource_type="provider",
            ip_address=request.client.host,
            context={
                "provider": provider_name,
                "reason": "oauth_failed",
                "error_code": e.code,
            },
        )
        raise HTTPException(400, "Provider connection failed")
    
    # Step 3: Save provider (business logic)
    try:
        provider = Provider(
            user_id=current_user.id,
            name=provider_name,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=tokens.expires_at,
        )
        session.add(provider)
        await session.commit()  # ✅ Provider NOW exists
        
    except IntegrityError:
        await session.rollback()
        
        # Already connected
        await audit.record(
            action=AuditAction.PROVIDER_CONNECTION_FAILED,
            user_id=current_user.id,
            resource_type="provider",
            context={
                "provider": provider_name,
                "reason": "already_connected",
            },
        )
        raise HTTPException(409, "Provider already connected")
    
    # Step 4: Record SUCCESS (after business commit)
    await audit.record(
        action=AuditAction.PROVIDER_CONNECTED,
        user_id=current_user.id,
        resource_type="provider",
        resource_id=provider.id,
        ip_address=request.client.host,
        context={
            "provider": provider_name,
            "connection_method": "oauth",
        },
    )
    
    return ProviderResponse(
        id=provider.id,
        name=provider_name,
        status="connected",
    )
```

---

## Pattern 4: Data Access (Permission Check)

### 4a. Correct Implementation

```python
@router.get("/accounts/{account_id}")
async def get_account(
    account_id: UUID,
    audit: AuditProtocol = Depends(get_audit),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> AccountResponse:
    """Get account data with permission check and audit."""
    
    # Step 1: Record access attempt
    await audit.record(
        action=AuditAction.ACCESS_ATTEMPTED,
        user_id=current_user.id,
        resource_type="account",
        resource_id=account_id,
        ip_address=request.client.host,
        context={"action": "read"},
    )
    
    # Step 2: Permission check
    account = await get_account_by_id(account_id)
    
    if not account:
        # Record access denied (not found)
        await audit.record(
            action=AuditAction.ACCESS_DENIED,
            user_id=current_user.id,
            resource_type="account",
            resource_id=account_id,
            ip_address=request.client.host,
            context={
                "action": "read",
                "reason": "not_found",
            },
        )
        raise HTTPException(404, "Account not found")
    
    if account.user_id != current_user.id:
        # Record access denied (no permission)
        await audit.record(
            action=AuditAction.ACCESS_DENIED,
            user_id=current_user.id,
            resource_type="account",
            resource_id=account_id,
            ip_address=request.client.host,
            context={
                "action": "read",
                "reason": "no_permission",
                "owner_id": str(account.user_id),
            },
        )
        raise HTTPException(403, "Access denied")
    
    # Step 3: Permission granted - record access
    await audit.record(
        action=AuditAction.ACCESS_GRANTED,
        user_id=current_user.id,
        resource_type="account",
        resource_id=account_id,
        ip_address=request.client.host,
        context={
            "action": "read",
            "permission_level": "owner",
        },
    )
    
    # Step 4: Also record data viewed (PCI-DSS requirement)
    await audit.record(
        action=AuditAction.DATA_VIEWED,
        user_id=current_user.id,
        resource_type="account",
        resource_id=account_id,
        ip_address=request.client.host,
        context={
            "data_type": "financial",
            "fields_accessed": ["balance", "account_number"],
        },
    )
    
    return AccountResponse.from_orm(account)
```

---

## Pattern 5: Completed Events (No ATTEMPT Needed)

### 5a. Correct Implementation

```python
@router.post("/auth/logout")
async def logout(
    audit: AuditProtocol = Depends(get_audit),
    current_user: User = Depends(get_current_user),
    current_session: Session = Depends(get_current_session),
    request: Request = None,
):
    """Logout user (always succeeds)."""
    
    # Revoke session
    await revoke_session(current_session.id)
    
    # Record logout (completed event - no ATTEMPT needed)
    await audit.record(
        action=AuditAction.USER_LOGOUT,
        user_id=current_user.id,
        resource_type="session",
        resource_id=current_session.id,
        ip_address=request.client.host,
    )
    
    return {"message": "Logged out successfully"}
```

**Why no ATTEMPT?**: Logout always succeeds. There's no failure case
to track. The action is already complete when we record it.

---

## Decision Tree: Which Pattern to Use?

```text
Is this a user-initiated action?
├─ YES → Does it change state (create/update/delete)?
│        ├─ YES → Use ATTEMPTED → FAILED/SUCCESS pattern
│        │        Examples: Registration, Login, Provider Connection
│        │
│        └─ NO  → Is this a permission check?
│                 ├─ YES → Use ACCESS_ATTEMPTED → DENIED/GRANTED
│                 │        Examples: View account, Export data
│                 │
│                 └─ NO  → Can this action fail?
│                          ├─ YES → Use ATTEMPTED → FAILED/SUCCESS
│                          └─ NO  → Use completed event only
│                                   Examples: Logout, Token rotation
│
└─ NO  → Is this a system event?
         └─ Use completed event only (BACKUP_CREATED, SYNC_COMPLETED)
```

---

## Anti-Patterns Checklist

Before committing code that uses audit logging, verify you haven't
made these mistakes:

- [ ] ❌ **Recording SUCCESS before business commit**

  ```python
  await audit.record(action=AuditAction.USER_REGISTERED, ...)
  await session.commit()  # Commit might fail!
  ```

- [ ] ❌ **Skipping ATTEMPT record**

  ```python
  if validation_fails:
      raise HTTPException(400)  # No audit trail!
  ```

- [ ] ❌ **Using single event for both attempt and outcome**

  ```python
  await audit.record(action=AuditAction.USER_LOGIN, ...)  # Ambiguous!
  ```

- [ ] ❌ **Recording predictions**

  ```python
  await audit.record(action="user_will_register", ...)  # Future tense!
  ```

- [ ] ❌ **Not recording early validation failures**

  ```python
  if not is_valid_email(email):
      raise HTTPException(400)  # Should record FAILED!
  ```

- [ ] ❌ **Missing context in FAILED events**

  ```python
  await audit.record(
      action=AuditAction.USER_REGISTRATION_FAILED,
      # ❌ Missing context: {"reason": "duplicate_email"}
  )
  ```

---

## Testing Your Audit Implementation

### Test Pattern: Verify Timeline

```python
# tests/integration/test_audit_registration.py

async def test_registration_audit_timeline_success(client, test_database):
    """Verify successful registration creates correct audit timeline."""
    
    # Attempt registration
    response = client.post("/users", json={
        "email": "new@example.com",
        "password": "SecurePass123!",
    })
    
    assert response.status_code == 201
    user_id = response.json()["id"]
    
    # Query audit logs
    async with test_database.get_session() as session:
        adapter = PostgresAuditAdapter(session=session)
        result = await adapter.query(limit=100)
        logs = result.value
    
    # Verify timeline: ATTEMPTED → SUCCESS
    assert len(logs) >= 2
    assert logs[-2]["action"] == "user_registration_attempted"
    assert logs[-2]["user_id"] is None
    assert logs[-2]["context"]["email"] == "new@example.com"
    
    assert logs[-1]["action"] == "user_registered"
    assert logs[-1]["user_id"] == user_id
    assert logs[-1]["context"]["email"] == "new@example.com"
    
    # Verify database consistency
    user = await get_user_by_id(user_id)
    assert user is not None
    assert user.email == "new@example.com"


async def test_registration_audit_timeline_failure(client, test_database):
    """Verify failed registration creates correct audit timeline."""
    
    # Create existing user
    await create_user("duplicate@example.com", "password123")
    
    # Attempt registration with duplicate email
    response = client.post("/users", json={
        "email": "duplicate@example.com",
        "password": "SecurePass123!",
    })
    
    assert response.status_code == 400
    
    # Query audit logs
    async with test_database.get_session() as session:
        adapter = PostgresAuditAdapter(session=session)
        result = await adapter.query(limit=100)
        logs = result.value
    
    # Verify timeline: ATTEMPTED → FAILED
    assert len(logs) >= 2
    assert logs[-2]["action"] == "user_registration_attempted"
    assert logs[-2]["context"]["email"] == "duplicate@example.com"
    
    assert logs[-1]["action"] == "user_registration_failed"
    assert logs[-1]["context"]["reason"] == "duplicate_email"
    
    # Verify database consistency (no new user created)
    users = await get_users_by_email("duplicate@example.com")
    assert len(users) == 1  # Only the original user
```

---

## Quick Tips

### 1. Use Context Field Effectively

```python
# ✅ Good: Detailed context
await audit.record(
    action=AuditAction.USER_LOGIN_FAILED,
    context={
        "reason": "invalid_password",
        "email": email,
        "attempts": 3,
        "account_locked": False,
    },
)

# ❌ Bad: Missing context
await audit.record(
    action=AuditAction.USER_LOGIN_FAILED,
    # No context - hard to investigate later
)
```

### 2. Always Include IP Address for Auth Events

```python
# ✅ Required for PCI-DSS compliance
await audit.record(
    action=AuditAction.USER_LOGIN_ATTEMPTED,
    ip_address=request.client.host,  # REQUIRED
    user_agent=request.headers.get("user-agent"),  # Recommended
)
```

### 3. Use Meaningful Resource Types

```python
# ✅ Good: Specific resource types
resource_type="user"
resource_type="session"
resource_type="provider"
resource_type="account"

# ❌ Bad: Generic or unclear
resource_type="data"
resource_type="object"
resource_type="thing"
```

### 4. Handle Result Types Properly

```python
# ✅ Good: Handle audit failures
result = await audit.record(...)
match result:
    case Failure(error):
        # Log but don't fail the request
        logger.error("Audit failed", error=error.message)

# ❌ Bad: Ignore result
await audit.record(...)  # What if it fails?
```

---

## Getting Help

**Questions?**

1. Check architecture doc: `architecture/audit.md`
2. Review enum definitions: `src/domain/enums/audit_action.py`
3. Look at existing examples in codebase
4. Ask in team chat

**Common Questions**:

**Q**: Do I need to audit read operations?

**A**: Yes, for sensitive data (accounts, transactions).
Use `ACCESS_ATTEMPTED` → `DENIED`/`GRANTED` + `DATA_VIEWED`.

**Q**: What if my operation has multiple failure modes?

**A**: Record `*_ATTEMPTED` once, then `*_FAILED` with different
`reason` in context.

**Q**: Should I audit internal system operations?

**A**: Only if they're security-relevant or compliance-required.
Most internal operations don't need audit.

**Q**: What if audit.record() fails?

**A**: Log the error but don't fail the business operation.
Audit failures are logged separately.

---

**Created**: 2025-11-17 | **Last Updated**: 2025-11-17
