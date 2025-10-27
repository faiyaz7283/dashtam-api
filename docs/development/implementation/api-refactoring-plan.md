# API Refactoring Implementation Plan

## Overview

This plan implements recommendations from the Architectural Audit Report (2025-10-27) to improve service dependency injection, code organization, and test coverage. Since the application is in development with no external dependencies, we can make breaking changes freely as long as tests are updated accordingly.

## Objectives

- Standardize service dependency injection across all routers
- Improve testability with service factory functions
- Normalize import patterns (module-level, not local)
- Add missing test coverage for edge cases
- Prepare architecture for Session Management feature

## Scope

### In Scope

- Service DI providers for AuthService and TokenService
- Router import normalization
- Service extraction from AuthService (optional but recommended)
- Additional API test coverage
- Update all affected tests

### Out of Scope

- URL structure changes (already RESTful)
- Schema changes (already separated)
- Database models or migrations
- Provider implementations

## Phase 1: Service DI Providers

### 1.1 Create Service Factory Functions

**File**: `src/api/dependencies.py`

Add service factory dependencies alongside existing auth dependencies:

```python
"""FastAPI dependencies for authentication, database, and services."""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.database import get_session
from src.models.user import User
from src.services.auth_service import AuthService
from src.services.jwt_service import JWTService, JWTError
from src.services.token_service import TokenService

logger = logging.getLogger(__name__)

security = HTTPBearer()

# ==================== Existing Dependencies ====================
# get_current_user, get_current_verified_user, get_optional_current_user
# get_client_ip, get_user_agent
# (keep all existing code)

# ==================== NEW: Service Factory Dependencies ====================

def get_auth_service(
    session: AsyncSession = Depends(get_session),
) -> AuthService:
    """Get AuthService instance with injected session.
    
    This provides a consistent dependency injection point for AuthService
    across all routers, improving testability and maintainability.
    
    Args:
        session: Database session from dependency.
        
    Returns:
        AuthService instance.
        
    Example:
        @router.post("/register")
        async def register(
            request: RegisterRequest,
            auth_service: AuthService = Depends(get_auth_service),
        ):
            user = await auth_service.register_user(...)
    """
    return AuthService(session)


def get_token_service(
    session: AsyncSession = Depends(get_session),
) -> TokenService:
    """Get TokenService instance with injected session.
    
    This provides a consistent dependency injection point for TokenService
    across all routers, improving testability and maintainability.
    
    Args:
        session: Database session from dependency.
        
    Returns:
        TokenService instance.
        
    Example:
        @router.get("/{provider_id}/authorization")
        async def get_authorization_status(
            provider_id: UUID,
            token_service: TokenService = Depends(get_token_service),
        ):
            token_info = await token_service.get_token_info(provider_id)
    """
    return TokenService(session)
```

**Why This Helps**:

- Uniform injection pattern across all routers
- Easy to override in tests (dependency_overrides)
- Single source of truth for service instantiation
- Enables future enhancements (logging, metrics, context injection)

### 1.2 Update Routers to Use DI Providers

**Files to Update**:

1. `src/api/v1/auth_jwt.py` - Replace `AuthService(session)` with `Depends(get_auth_service)`
2. `src/api/v1/provider_authorization.py` - Replace `TokenService(session)` with `Depends(get_token_service)`

**Example Change** (auth_jwt.py):

Before:

```python
@router.post("/register", response_model=MessageResponse)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    auth_service = AuthService(session)
    user = await auth_service.register_user(...)
```

After:

```python
@router.post("/register", response_model=MessageResponse)
async def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    user = await auth_service.register_user(...)
```

**Benefits**:

- Remove `session` parameter from endpoints that only need services
- Cleaner function signatures
- Services become mockable at router level in tests

### 1.3 Update Tests

**Files to Update**:

- `tests/api/routes/test_auth.py`
- `tests/api/routes/test_providers.py`
- Any integration tests using AuthService/TokenService

**Approach**:

```python
# In conftest.py or test file
from src.api.dependencies import get_auth_service

@pytest.fixture
def mock_auth_service():
    """Mock AuthService for testing."""
    service = MagicMock(spec=AuthService)
    # Configure mock behavior
    return service

def test_register(client, mock_auth_service):
    """Test registration endpoint."""
    # Override dependency
    app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
    
    response = client.post("/api/v1/auth/register", json={...})
    
    # Verify mock was called
    mock_auth_service.register_user.assert_called_once()
    
    # Cleanup
    app.dependency_overrides.clear()
```

## Phase 2: Import Normalization

### 2.1 Move Local Imports to Module Level

**Files to Update**:

- `src/api/v1/providers.py` (lines 146, 237, 301, 396)
- `src/api/v1/provider_authorization.py` (if any local imports exist)

**Pattern to Fix**:

Before:

```python
async def list_user_providers(...):
    from sqlalchemy.orm import selectinload  # ❌ Local import
    
    query = select(Provider).options(selectinload(Provider.connection))
```

After:

```python
# At module top
from sqlalchemy.orm import selectinload

async def list_user_providers(...):
    query = select(Provider).options(selectinload(Provider.connection))
```

**Why**:

- Standard Python convention
- Clearer dependencies at module level
- Slight performance improvement (import once, not per-call)

## Phase 3: AuthService Refactoring (Optional)

### 3.1 Extract Sub-Services

AuthService currently handles:

- User registration
- Email verification
- Login/logout
- Token refresh
- Password reset request
- Password reset confirmation
- Profile updates
- Password changes

**Recommendation**: Extract verification and password reset into dedicated services:

**New Services**:

1. `src/services/verification_service.py`

```python
class VerificationService:
    """Service for email verification workflows."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.password_service = PasswordService()
        self.email_service = EmailService(...)
    
    async def create_verification_token(self, user_id: UUID) -> str:
        """Create and send verification token."""
        ...
    
    async def verify_email(self, token: str) -> User:
        """Verify email using token."""
        ...
```

1. `src/services/password_reset_service.py`

```python
class PasswordResetService:
    """Service for password reset workflows."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.password_service = PasswordService()
        self.email_service = EmailService(...)
    
    async def request_reset(self, email: str) -> None:
        """Send password reset email."""
        ...
    
    async def reset_password(self, token: str, new_password: str) -> User:
        """Reset password using token."""
        ...
```

**Updated AuthService** (becomes orchestrator):

```python
class AuthService:
    """Core authentication service (orchestrator)."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.password_service = PasswordService()
        self.jwt_service = JWTService()
        self.verification_service = VerificationService(session)
        self.password_reset_service = PasswordResetService(session)
    
    async def register_user(self, email: str, password: str, name: str) -> User:
        """Register user and send verification."""
        # Create user
        user = User(...)
        self.session.add(user)
        await self.session.flush()
        
        # Delegate to verification service
        await self.verification_service.create_verification_token(user.id)
        await self.session.commit()
        return user
    
    async def verify_email(self, token: str) -> User:
        """Verify email (delegates to verification service)."""
        return await self.verification_service.verify_email(token)
    
    async def request_password_reset(self, email: str) -> None:
        """Request password reset (delegates to password reset service)."""
        return await self.password_reset_service.request_reset(email)
    
    async def reset_password(self, token: str, new_password: str) -> User:
        """Reset password (delegates to password reset service)."""
        return await self.password_reset_service.reset_password(token, new_password)
    
    # Keep core auth methods in AuthService
    async def login(self, email: str, password: str) -> Tuple[str, str, User]:
        """Authenticate and generate tokens."""
        ...
    
    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token."""
        ...
```

**Benefits**:

- Clearer single responsibilities
- Each service is smaller and easier to test
- AuthService becomes thin orchestrator
- Easier to maintain and extend individual workflows

**Trade-offs**:

- More files to manage
- Slight increase in complexity (more classes)
- Need to update imports in routers

**Recommendation**: Implement this if:

- AuthService continues growing (adding 2FA, social auth, etc.)
- You want clearer boundaries for testing
- Session Management will add more auth complexity

Otherwise, current AuthService is acceptable—it's cohesive even if broad.

### 3.2 Add DI Providers for New Services (If Extracted)

```python
# In src/api/dependencies.py

def get_verification_service(
    session: AsyncSession = Depends(get_session),
) -> VerificationService:
    return VerificationService(session)

def get_password_reset_service(
    session: AsyncSession = Depends(get_session),
) -> PasswordResetService:
    return PasswordResetService(session)
```

## Phase 4: Additional Test Coverage

### 4.1 Provider API Tests

**File**: `tests/api/routes/test_providers.py`

Add tests for:

- **Pagination edge cases**:
  - Empty result set
  - Page beyond total pages
  - Invalid per_page values (0, negative, >100)

- **Sorting edge cases**:
  - Invalid sort field (should 400)
  - Mixed case sort order ("DESC", "Desc", "desc")

- **Filtering**:
  - Filter by status with no results
  - Filter by non-existent provider_key

- **Alias conflicts**:
  - Create with duplicate alias (409)
  - Update to conflicting alias (409)

### 4.2 Authorization API Tests

**File**: `tests/api/routes/test_authorization.py` (new or extend existing)

Add tests for:

- **OAuth callback errors**:
  - State parameter mismatch (400)
  - Missing authorization code (400)
  - Error parameter from provider (400)
  - Provider not found (404)
  - Wrong user accessing callback (403)

- **Token refresh**:
  - No refresh token available (400)
  - Provider with error state
  - Token rotation scenarios

### 4.3 Auth API Tests

**File**: `tests/api/routes/test_auth.py`

Verify coverage for:

- Account lockout after failed attempts
- Weak password validation
- Duplicate email registration
- Email verification with expired token
- Password reset with expired token

## Phase 5: Documentation Updates

### 5.1 Update Architecture Docs

**File**: `docs/development/architecture/restful-api-design.md`

Add section:

```markdown
### Sub-Resource Pattern: Provider Authorization

Provider authorization is modeled as a sub-resource under providers:

- `POST /providers/{id}/authorization` - Initiate OAuth flow
- `GET /providers/{id}/authorization` - Check authorization status
- `GET /providers/{id}/authorization/callback` - OAuth callback
- `PATCH /providers/{id}/authorization` - Manual token refresh
- `DELETE /providers/{id}/authorization` - Revoke authorization

This follows RESTful sub-resource conventions where authorization
represents a nested resource relationship with the provider instance.
```

### 5.2 Update Testing Guide

**File**: `docs/development/guides/testing-guide.md`

Add section on service dependency overrides:

```markdown
### Testing with Service Dependencies

When testing routers that use service dependencies, override them
using FastAPI's dependency override mechanism:

```python
from src.api.dependencies import get_auth_service

def test_register_endpoint(client):
    mock_service = MagicMock(spec=AuthService)
    app.dependency_overrides[get_auth_service] = lambda: mock_service
    
    response = client.post("/api/v1/auth/register", json={...})
    
    mock_service.register_user.assert_called_once()
    app.dependency_overrides.clear()
```

## Implementation Phases

### Phase 1: Service DI (1-2 hours)

- [ ] Add service factories to dependencies.py
- [ ] Update auth_jwt.py to use DI
- [ ] Update provider_authorization.py to use DI
- [ ] Update affected tests
- [ ] Run all tests: `make test`
- [ ] Run linting: `make lint`

### Phase 2: Import Normalization (30 minutes)

- [ ] Move local imports to module level in providers.py
- [ ] Check other routers for local imports
- [ ] Run linting: `make lint`
- [ ] Run tests: `make test`

### Phase 3: Service Extraction ✅ COMPLETE

- [x] Create VerificationService (100% coverage)
- [x] Create PasswordResetService (95% coverage)
- [x] Refactor AuthService to delegate (88% coverage)
- [x] Add DI providers for new services
- [x] Update routers if needed
- [x] Update all tests (63 new tests added)
- [x] Run full test suite (395 tests passing, 86% coverage)

### Phase 4: Test Coverage (2-3 hours)

- [ ] Add provider pagination/sorting tests
- [ ] Add authorization callback error tests
- [ ] Add token refresh edge case tests
- [ ] Run coverage report: `make test`
- [ ] Verify coverage targets met

### Phase 5: Documentation (30 minutes)

- [ ] Update RESTful API design doc
- [ ] Update testing guide
- [ ] Add service extraction rationale (if applicable)
- [ ] Lint docs: `make lint-md`

## Rollback Strategy

Since we're in development:

- Each phase can be reverted independently via git
- Tests provide regression safety net
- No external API contracts to worry about

Recommended approach: Complete Phase 1-2 first (low risk, high value), then evaluate Phase 3 based on upcoming Session Management requirements.

## Success Criteria

- [ ] All tests passing (295+ tests)
- [ ] Code coverage maintained or improved (>76%)
- [ ] All linting checks pass
- [ ] Service DI standardized across routers
- [ ] No local imports in routers
- [ ] Documentation updated
- [ ] Clean git history with descriptive commits

## Next Steps After Refactoring

Once complete, the codebase will be ready for:

- Session Management implementation
- Additional provider integrations
- Enhanced audit logging
- Multi-factor authentication (if needed)

The improved DI patterns will make these features easier to test and maintain.
