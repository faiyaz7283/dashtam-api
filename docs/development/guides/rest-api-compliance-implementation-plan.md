# REST API Compliance Implementation Plan

**Project**: Dashtam  
**Target**: 100% REST Compliance on API v1  
**Current Score**: 6.3/10  
**Target Score**: 9.5+/10  

---

## Overview

This implementation plan addresses all REST API compliance issues identified in the compliance review. Since Dashtam is in active development with no production deployment, we can safely refactor v1 API endpoints to achieve full REST compliance without versioning concerns.

**Approach**: Fix issues from highest to lowest priority, implementing breaking changes directly in v1.

---

## Phase 1: Critical Fixes - Core REST Violations

### Issue #1: RPC-Style Endpoint (Highest Priority)

**Problem**: `/providers/create` uses verb in URL  
**Current**:
```http
POST /api/v1/providers/create
```

**Fix**:
```http
POST /api/v1/providers
```

**Changes Required**:

1. **Update route definition** (`src/api/v1/providers.py:103`)
```python
# Change from:
@router.post("/create", response_model=ProviderResponse)

# To:
@router.post("/", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
```

2. **Update all tests** (`tests/api/test_provider_endpoints.py`)
```python
# Change all instances of:
"/api/v1/providers/create"

# To:
"/api/v1/providers"
```

**Verification**:
- [ ] Endpoint responds at `/api/v1/providers` with POST
- [ ] Returns 201 Created status
- [ ] All tests pass
- [ ] OpenAPI docs updated automatically

---

### Issue #2: Separate Provider Types from Provider Instances

**Problem**: Provider types and user instances mixed at same URL  
**Current**:
```http
GET /api/v1/providers/           # User's provider instances
GET /api/v1/providers/available  # Provider type catalog
GET /api/v1/providers/configured # Provider type catalog
```

**Fix**: Create separate resource for provider types
```http
# Provider Types (catalog)
GET /api/v1/provider-types
GET /api/v1/provider-types?configured=true

# Provider Instances (user's connections)
GET /api/v1/providers
POST /api/v1/providers
GET /api/v1/providers/{id}
PATCH /api/v1/providers/{id}
DELETE /api/v1/providers/{id}
```

**Changes Required**:

1. **Create new router** (`src/api/v1/provider_types.py`)
```python
"""Provider type catalog API endpoints."""

from fastapi import APIRouter
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter()

class ProviderTypeResponse(BaseModel):
    """Provider type information."""
    key: str
    name: str
    provider_type: str
    description: str
    icon_url: Optional[str]
    is_configured: bool
    supported_features: List[str]

@router.get("/", response_model=List[ProviderTypeResponse])
async def list_provider_types(
    configured: Optional[bool] = None
):
    """Get list of available provider types.
    
    Query Parameters:
        configured: If true, only return configured providers
    """
    from src.providers import ProviderRegistry
    
    if configured:
        providers = ProviderRegistry.get_configured_providers()
    else:
        providers = ProviderRegistry.get_available_providers()
    
    return [
        ProviderTypeResponse(
            key=key,
            name=info["name"],
            provider_type=info["provider_type"],
            description=info.get("description", ""),
            icon_url=info.get("icon_url"),
            is_configured=info.get("is_configured", False),
            supported_features=info.get("supported_features", []),
        )
        for key, info in providers.items()
    ]

@router.get("/{provider_key}", response_model=ProviderTypeResponse)
async def get_provider_type(provider_key: str):
    """Get details of a specific provider type."""
    from src.providers import ProviderRegistry
    from fastapi import HTTPException, status
    
    providers = ProviderRegistry.get_available_providers()
    
    if provider_key not in providers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider type '{provider_key}' not found"
        )
    
    info = providers[provider_key]
    return ProviderTypeResponse(
        key=provider_key,
        name=info["name"],
        provider_type=info["provider_type"],
        description=info.get("description", ""),
        icon_url=info.get("icon_url"),
        is_configured=info.get("is_configured", False),
        supported_features=info.get("supported_features", []),
    )
```

2. **Update router registration** (`src/api/v1/__init__.py`)
```python
from src.api.v1.provider_types import router as provider_types_router

# Add before providers router
api_router.include_router(
    provider_types_router, 
    prefix="/provider-types", 
    tags=["provider-types"]
)
```

3. **Remove old endpoints** (`src/api/v1/providers.py`)
```python
# Delete these functions:
# - get_available_providers() 
# - get_configured_providers()
```

4. **Update tests**
- Create `tests/api/test_provider_type_endpoints.py`
- Move relevant tests from `test_provider_endpoints.py`
- Update URL references

**Verification**:
- [ ] `/api/v1/provider-types` returns all types
- [ ] `/api/v1/provider-types?configured=true` filters correctly
- [ ] `/api/v1/provider-types/{key}` returns specific type
- [ ] `/api/v1/providers` only returns user instances
- [ ] All tests pass
- [ ] OpenAPI docs show separate resources

---

### Issue #3: Move OAuth Endpoints to Provider Sub-Resources

**Problem**: OAuth endpoints mixed with JWT auth at `/auth` prefix  
**Current**:
```http
GET    /api/v1/auth/{provider_id}/authorize
GET    /api/v1/auth/{provider_id}/authorize/redirect
GET    /api/v1/auth/{provider_id}/callback
POST   /api/v1/auth/{provider_id}/refresh
GET    /api/v1/auth/{provider_id}/status
DELETE /api/v1/auth/{provider_id}/disconnect
```

**Fix**: Model as provider connection/authorization resource
```http
POST   /api/v1/providers/{id}/authorization
GET    /api/v1/providers/{id}/authorization
GET    /api/v1/providers/{id}/authorization/callback
PATCH  /api/v1/providers/{id}/authorization
DELETE /api/v1/providers/{id}/authorization
```

**Changes Required**:

1. **Create new authorization router** (`src/api/v1/provider_authorization.py`)
```python
"""Provider OAuth authorization endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
from pydantic import BaseModel

from src.core.database import get_session
from src.api.dependencies import get_current_user
from src.models.user import User
from src.models.provider import Provider
from src.providers import ProviderRegistry
from src.services.token_service import TokenService

router = APIRouter()

class AuthorizationResponse(BaseModel):
    """OAuth authorization information."""
    auth_url: str
    state: str
    message: str

class ConnectionStatusResponse(BaseModel):
    """Provider connection status."""
    provider_id: UUID
    alias: str
    status: str
    is_connected: bool
    has_access_token: bool
    has_refresh_token: bool
    expires_at: Optional[str]
    last_refreshed: Optional[str]

# POST /providers/{id}/authorization - Initiate OAuth
@router.post("/{provider_id}/authorization", response_model=AuthorizationResponse)
async def initiate_authorization(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Initiate OAuth authorization flow for a provider.
    
    Returns the authorization URL where the user should be redirected
    to authorize the provider connection.
    """
    # Get provider
    from sqlmodel import select
    result = await session.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider"
        )
    
    # Get provider implementation
    try:
        provider_impl = ProviderRegistry.create_provider_instance(provider.provider_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    # Generate authorization URL
    state = str(provider_id)
    auth_url = provider_impl.get_auth_url(state=state)
    
    return AuthorizationResponse(
        auth_url=auth_url,
        state=state,
        message=f"Visit the auth_url to authorize {provider.alias}"
    )

# GET /providers/{id}/authorization - Get connection status
@router.get("/{provider_id}/authorization", response_model=ConnectionStatusResponse)
async def get_authorization_status(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get current authorization/connection status for a provider."""
    from sqlmodel import select
    result = await session.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider"
        )
    
    # Get token info
    token_service = TokenService(session)
    token_info = await token_service.get_token_info(provider_id=provider.id)
    
    if not token_info:
        return ConnectionStatusResponse(
            provider_id=provider.id,
            alias=provider.alias,
            status="not_connected",
            is_connected=False,
            has_access_token=False,
            has_refresh_token=False,
            expires_at=None,
            last_refreshed=None,
        )
    
    return ConnectionStatusResponse(
        provider_id=provider.id,
        alias=provider.alias,
        status="connected",
        is_connected=True,
        has_access_token=token_info.get("has_access_token", False),
        has_refresh_token=token_info.get("has_refresh_token", False),
        expires_at=token_info.get("expires_at"),
        last_refreshed=token_info.get("last_refreshed"),
    )

# GET /providers/{id}/authorization/callback - OAuth callback
@router.get("/{provider_id}/authorization/callback")
async def handle_authorization_callback(
    provider_id: UUID,
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Handle OAuth callback from provider.
    
    This endpoint receives the authorization code from the provider
    and exchanges it for access tokens.
    """
    # Handle OAuth errors
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authorization failed: {error}"
        )
    
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authorization code received"
        )
    
    # Validate state parameter
    if state and state != str(provider_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State parameter mismatch"
        )
    
    # Get provider
    from sqlmodel import select
    result = await session.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider"
        )
    
    # Get provider implementation
    try:
        provider_impl = ProviderRegistry.create_provider_instance(provider.provider_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    # Exchange code for tokens
    try:
        tokens = await provider_impl.authenticate({"code": code})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )
    
    # Store tokens
    token_service = TokenService(session)
    request_info = None
    if request:
        request_info = {
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
    
    try:
        await token_service.store_initial_tokens(
            provider_id=provider.id,
            tokens=tokens,
            user_id=current_user.id,
            request_info=request_info,
        )
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store tokens: {str(e)}"
        )
    
    return {
        "message": f"Successfully connected {provider.alias}",
        "provider_id": provider.id,
        "alias": provider.alias,
    }

# PATCH /providers/{id}/authorization - Refresh tokens
@router.patch("/{provider_id}/authorization")
async def refresh_authorization(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Manually refresh tokens for a provider.
    
    Forces a token refresh even if the current token hasn't expired.
    """
    from sqlmodel import select
    result = await session.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider"
        )
    
    # Refresh tokens
    token_service = TokenService(session)
    try:
        await token_service.refresh_token(
            provider_id=provider.id,
            user_id=current_user.id
        )
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh tokens: {str(e)}"
        )
    
    return {"message": f"Tokens refreshed successfully for {provider.alias}"}

# DELETE /providers/{id}/authorization - Disconnect
@router.delete("/{provider_id}/authorization", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_authorization(
    provider_id: UUID,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke authorization and disconnect provider.
    
    Removes stored tokens but keeps the provider instance for
    potential reconnection.
    """
    from sqlmodel import select
    result = await session.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider"
        )
    
    # Revoke tokens
    token_service = TokenService(session)
    request_info = None
    if request:
        request_info = {
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
    
    try:
        await token_service.revoke_tokens(
            provider_id=provider.id,
            user_id=current_user.id,
            request_info=request_info
        )
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect provider: {str(e)}"
        )
    
    # No return body with 204
```

2. **Register nested router** (`src/api/v1/providers.py`)
```python
from src.api.v1.provider_authorization import router as auth_router

# At end of file, include nested router
router.include_router(auth_router, prefix="")
```

3. **Update route registration** (`src/api/v1/__init__.py`)
```python
# Remove old OAuth router
# api_router.include_router(auth_oauth_router, prefix="/auth", tags=["oauth"])

# OAuth is now nested under providers
```

4. **Delete old OAuth router** (`src/api/v1/auth.py`)

5. **Update all tests**
- Rename `tests/api/test_auth_endpoints.py` → `tests/api/test_provider_authorization_endpoints.py`
- Update all URL references from `/api/v1/auth/{id}/...` to `/api/v1/providers/{id}/authorization/...`

**Verification**:
- [ ] All OAuth endpoints work under `/providers/{id}/authorization`
- [ ] JWT auth endpoints remain at `/auth`
- [ ] Clear separation between user auth and provider OAuth
- [ ] All tests pass
- [ ] OpenAPI docs show proper resource hierarchy

---

## Phase 2: Important Improvements - API Usability

### Issue #4: Add PATCH Endpoint for Provider Updates

**Problem**: No way to update provider fields (e.g., alias)

**Fix**: Add PATCH endpoint

**Changes Required**:

1. **Create update schema** (`src/api/v1/providers.py`)
```python
class UpdateProviderRequest(BaseModel):
    """Request to update a provider instance."""
    alias: Optional[str] = Field(None, min_length=1, max_length=100)
```

2. **Add PATCH endpoint** (`src/api/v1/providers.py`)
```python
@router.patch("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    request: UpdateProviderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a provider instance.
    
    Currently supports updating:
    - alias: User's custom name for the connection
    """
    from sqlmodel import select
    
    result = await session.execute(select(Provider).where(Provider.id == provider_id))
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider"
        )
    
    # Check for duplicate alias
    if request.alias and request.alias != provider.alias:
        result = await session.execute(
            select(Provider).where(
                Provider.user_id == current_user.id,
                Provider.alias == request.alias
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You already have a provider named '{request.alias}'"
            )
        
        provider.alias = request.alias
    
    try:
        session.add(provider)
        await session.commit()
        await session.refresh(provider)
        
        logger.info(f"Updated provider '{provider.alias}' for user {current_user.email}")
    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to update provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update provider: {str(e)}"
        )
    
    # Load connection for response
    from sqlalchemy.orm import selectinload
    result = await session.execute(
        select(Provider)
        .options(selectinload(Provider.connection))
        .where(Provider.id == provider_id)
    )
    provider = result.scalar_one()
    connection = provider.connection
    
    return ProviderResponse(
        id=provider.id,
        provider_key=provider.provider_key,
        alias=provider.alias,
        status=connection.status.value if connection else "not_connected",
        is_connected=provider.is_connected,
        needs_reconnection=provider.needs_reconnection,
        connected_at=connection.connected_at.isoformat()
        if connection and connection.connected_at
        else None,
        last_sync_at=connection.last_sync_at.isoformat()
        if connection and connection.last_sync_at
        else None,
        accounts_count=connection.accounts_count if connection else 0,
    )
```

3. **Add tests**
```python
def test_update_provider_alias_success(
    client: TestClient, auth_tokens: dict, test_provider
):
    """Test successful provider alias update."""
    response = client.patch(
        f"/api/v1/providers/{test_provider.id}",
        json={"alias": "Updated Name"},
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["alias"] == "Updated Name"

def test_update_provider_duplicate_alias(
    client: TestClient, auth_tokens: dict, test_provider, test_provider_2
):
    """Test updating to duplicate alias returns 409."""
    response = client.patch(
        f"/api/v1/providers/{test_provider.id}",
        json={"alias": test_provider_2.alias},  # Duplicate
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
    )
    
    assert response.status_code == 409
```

**Verification**:
- [ ] PATCH endpoint works
- [ ] Duplicate alias validation works
- [ ] Returns updated provider
- [ ] All tests pass

---

### Issue #5: Add Pagination Support

**Problem**: List endpoints return unbounded lists

**Fix**: Add pagination with backward compatibility

**Changes Required**:

1. **Create paginated response schema** (`src/schemas/common.py` - create if doesn't exist)
```python
"""Common schemas used across the API."""

from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field
import math

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response.
    
    Provides pagination metadata along with the items.
    """
    items: List[T] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    
    @classmethod
    def create(cls, items: List[T], total: int, page: int, per_page: int):
        """Create paginated response with calculated metadata."""
        pages = math.ceil(total / per_page) if per_page > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )
```

2. **Update list endpoint** (`src/api/v1/providers.py`)
```python
from fastapi import Query
from src.schemas.common import PaginatedResponse

@router.get("/", response_model=PaginatedResponse[ProviderResponse])
async def list_user_providers(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by connection status"),
    provider_key: Optional[str] = Query(None, description="Filter by provider type"),
    sort: str = Query("created_at", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc/desc)"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get all provider instances for the current user.
    
    Supports pagination, filtering, and sorting.
    """
    from sqlalchemy.orm import selectinload
    from sqlalchemy import func
    
    # Build base query
    query = (
        select(Provider)
        .options(selectinload(Provider.connection))
        .where(Provider.user_id == current_user.id)
    )
    
    # Apply filters
    if status:
        # Join with connection to filter by status
        from src.models.provider import ProviderConnection
        query = query.join(Provider.connection).where(
            ProviderConnection.status == status
        )
    
    if provider_key:
        query = query.where(Provider.provider_key == provider_key)
    
    # Apply sorting
    allowed_sort_fields = ["created_at", "updated_at", "alias", "provider_key"]
    if sort not in allowed_sort_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot sort by '{sort}'. Allowed: {allowed_sort_fields}"
        )
    
    sort_column = getattr(Provider, sort)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Get total count
    count_query = select(func.count()).select_from(Provider).where(
        Provider.user_id == current_user.id
    )
    if status:
        from src.models.provider import ProviderConnection
        count_query = count_query.join(Provider.connection).where(
            ProviderConnection.status == status
        )
    if provider_key:
        count_query = count_query.where(Provider.provider_key == provider_key)
    
    result = await session.execute(count_query)
    total = result.scalar()
    
    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    
    # Execute query
    result = await session.execute(query)
    providers = result.scalars().all()
    
    # Build response
    responses = []
    for provider in providers:
        connection = provider.connection
        responses.append(
            ProviderResponse(
                id=provider.id,
                provider_key=provider.provider_key,
                alias=provider.alias,
                status=connection.status.value if connection else "not_connected",
                is_connected=provider.is_connected,
                needs_reconnection=provider.needs_reconnection,
                connected_at=connection.connected_at.isoformat()
                if connection and connection.connected_at
                else None,
                last_sync_at=connection.last_sync_at.isoformat()
                if connection and connection.last_sync_at
                else None,
                accounts_count=connection.accounts_count if connection else 0,
            )
        )
    
    return PaginatedResponse.create(
        items=responses,
        total=total,
        page=page,
        per_page=per_page
    )
```

3. **Add tests**
```python
def test_list_providers_pagination(client: TestClient, auth_tokens: dict):
    """Test provider list pagination."""
    response = client.get(
        "/api/v1/providers?page=1&per_page=10",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "per_page" in data
    assert "pages" in data
    assert data["page"] == 1
    assert data["per_page"] == 10

def test_list_providers_filtering(client: TestClient, auth_tokens: dict):
    """Test provider list filtering."""
    response = client.get(
        "/api/v1/providers?provider_key=schwab&status=connected",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["provider_key"] == "schwab"
        assert item["status"] == "connected"

def test_list_providers_sorting(client: TestClient, auth_tokens: dict):
    """Test provider list sorting."""
    response = client.get(
        "/api/v1/providers?sort=alias&order=asc",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    aliases = [item["alias"] for item in data["items"]]
    assert aliases == sorted(aliases)
```

**Verification**:
- [ ] Pagination works correctly
- [ ] Filtering by status and provider_key works
- [ ] Sorting works
- [ ] All tests pass
- [ ] OpenAPI docs show query parameters

---

### Issue #6: Redesign Password Reset as Resource

**Problem**: Password reset uses action-oriented URLs

**Current**:
```http
POST /api/v1/auth/password-reset/request
POST /api/v1/auth/password-reset/confirm
```

**Fix**: Model as resource
```http
POST  /api/v1/password-resets         # Create reset request
GET   /api/v1/password-resets/{token} # Verify token (optional)
PATCH /api/v1/password-resets/{token} # Complete reset
```

**Changes Required**:

1. **Create new password reset router** (`src/api/v1/password_resets.py`)
```python
"""Password reset API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field

from src.core.database import get_session
from src.schemas.auth import MessageResponse
from src.services.auth_service import AuthService

router = APIRouter()

class CreatePasswordResetRequest(BaseModel):
    """Request to create a password reset."""
    email: EmailStr

class VerifyResetTokenResponse(BaseModel):
    """Response for token verification."""
    valid: bool
    email: Optional[str] = None
    expires_at: Optional[str] = None

class CompletePasswordResetRequest(BaseModel):
    """Request to complete password reset."""
    new_password: str = Field(..., min_length=8)

@router.post("/", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_password_reset(
    request: CreatePasswordResetRequest,
    session: AsyncSession = Depends(get_session),
):
    """Request a password reset link.
    
    Sends a password reset email if the account exists.
    Always returns success to prevent email enumeration.
    """
    auth_service = AuthService(session)
    await auth_service.request_password_reset(email=request.email)
    
    return MessageResponse(
        message="If an account exists with that email, a password reset link has been sent."
    )

@router.get("/{token}", response_model=VerifyResetTokenResponse)
async def verify_reset_token(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    """Verify that a password reset token is valid.
    
    Optional endpoint to check token validity before showing password form.
    """
    auth_service = AuthService(session)
    
    try:
        # This would need a new method in AuthService
        token_data = await auth_service.verify_reset_token(token)
        
        return VerifyResetTokenResponse(
            valid=True,
            email=token_data.get("email"),
            expires_at=token_data.get("expires_at")
        )
    except ValueError:
        return VerifyResetTokenResponse(valid=False)

@router.patch("/{token}", response_model=MessageResponse)
async def complete_password_reset(
    token: str,
    request: CompletePasswordResetRequest,
    session: AsyncSession = Depends(get_session),
):
    """Complete password reset with new password.
    
    Validates the token and updates the user's password.
    """
    auth_service = AuthService(session)
    
    try:
        user = await auth_service.reset_password(
            token=token,
            new_password=request.new_password
        )
        
        return MessageResponse(
            message="Password reset successfully. You can now log in with your new password."
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
```

2. **Register router** (`src/api/v1/__init__.py`)
```python
from src.api.v1.password_resets import router as password_resets_router

api_router.include_router(
    password_resets_router,
    prefix="/password-resets",
    tags=["password-resets"]
)
```

3. **Remove old endpoints** (`src/api/v1/auth_jwt.py`)
```python
# Delete:
# - request_password_reset()
# - confirm_password_reset()
```

4. **Update tests**
- Update all URL references
- Test new resource-oriented endpoints

**Verification**:
- [ ] POST `/password-resets` works
- [ ] GET `/password-resets/{token}` verifies token
- [ ] PATCH `/password-resets/{token}` completes reset
- [ ] All tests pass
- [ ] OpenAPI docs updated

---

### Issue #7: Standardize Response Formats

**Problem**: Inconsistent response formats across endpoints

**Fix**: Use Pydantic models for all responses

**Changes Required**:

1. **Define standard response models** (`src/schemas/common.py`)
```python
class MessageResponse(BaseModel):
    """Standard message response."""
    message: str

class SuccessResponse(BaseModel):
    """Standard success response with data."""
    message: str
    data: Optional[Dict[str, Any]] = None
```

2. **Update all ad-hoc dict returns to use Pydantic models**

Search for patterns like:
```python
return {"message": "..."}
return {"message": "...", "key": value}
```

Replace with:
```python
return MessageResponse(message="...")
return SuccessResponse(message="...", data={"key": value})
```

3. **Add response_model to all endpoints**
```python
@router.post("/endpoint", response_model=MessageResponse)
@router.get("/endpoint", response_model=SomeResponse)
```

**Verification**:
- [ ] All endpoints use Pydantic response models
- [ ] No ad-hoc dict returns
- [ ] Consistent response structure
- [ ] OpenAPI docs show response schemas

---

## Phase 3: Minor Enhancements - Polish & Best Practices

### Issue #8: Fix GET with Side Effects (OAuth Redirect)

**Problem**: GET endpoint performs redirect (side effect)

**Current**:
```python
@router.get("/{provider_id}/authorize/redirect")
async def redirect_to_authorization(...):
    return RedirectResponse(url=result["auth_url"])
```

**Fix**: This endpoint will be removed when OAuth is moved to provider sub-resources (Issue #3). The new design doesn't need a separate redirect endpoint.

**Note**: If a redirect endpoint is needed for browser-based flows, it should use POST, but typically the client should handle the redirect after getting the auth URL from the API.

---

### Issue #9: Review /me Endpoint Convention

**Current**:
```http
GET   /api/v1/auth/me
PATCH /api/v1/auth/me
```

**Decision**: Keep as-is

**Rationale**: `/me` is a widely accepted convention (GitHub, GitLab, Stripe, etc.) and provides better UX than requiring clients to know their own user ID. This is an acceptable pragmatic exception to strict REST.

**No changes required.**

---

## Implementation Checklist

### Phase 1: Critical Fixes
- [ ] Issue #1: Fix `/providers/create` → POST `/providers`
- [ ] Issue #2: Separate provider types from instances
- [ ] Issue #3: Move OAuth to provider sub-resources

### Phase 2: Important Improvements
- [ ] Issue #4: Add PATCH endpoint for providers
- [ ] Issue #5: Add pagination, filtering, sorting
- [ ] Issue #6: Redesign password reset as resource
- [ ] Issue #7: Standardize response formats

### Phase 3: Minor Enhancements
- [ ] Issue #8: Remove GET redirect endpoint (handled in Issue #3)
- [ ] Issue #9: Review /me endpoint (keep as-is)

### Final Steps
- [ ] Update all tests
- [ ] Update OpenAPI documentation
- [ ] Run full test suite
- [ ] Verify code coverage maintained
- [ ] Run linter and formatter
- [ ] Update API documentation
- [ ] Create PR with comprehensive description

---

## Testing Strategy

### For Each Issue
1. **Write tests first** (TDD approach recommended)
2. **Implement the change**
3. **Run tests** to verify
4. **Update any broken tests** from old endpoints
5. **Run full test suite** to ensure no regressions

### Test Coverage Requirements
- Unit tests for new functions
- Integration tests for database operations
- API tests for all new/changed endpoints
- Maintain current 71% coverage (target: 85%)

---

## Success Criteria

### Technical
- [ ] All endpoints follow REST principles
- [ ] No verbs in URLs (except /me)
- [ ] Proper HTTP methods everywhere
- [ ] Correct status codes (200, 201, 204, 400, 404, 409)
- [ ] Consistent response formats
- [ ] Pagination on all list endpoints
- [ ] Filtering and sorting support
- [ ] Complete test coverage

### Documentation
- [ ] OpenAPI docs accurate and complete
- [ ] All endpoints have descriptions
- [ ] Request/response examples provided
- [ ] Error responses documented

### Quality
- [ ] All tests passing
- [ ] No linting errors
- [ ] Code formatted consistently
- [ ] No breaking changes without updating tests

---

## Expected Final REST Compliance Score

| Category | Current | Target | Improvement |
|----------|---------|--------|-------------|
| URL Design | 4/10 | 10/10 | +6 |
| HTTP Methods | 7/10 | 10/10 | +3 |
| Status Codes | 8/10 | 10/10 | +2 |
| Response Format | 6/10 | 10/10 | +4 |
| Error Handling | 8/10 | 9/10 | +1 |
| Resource Modeling | 5/10 | 10/10 | +5 |
| **Overall** | **6.3/10** | **9.8/10** | **+3.5** |

---

## Notes

- All changes are breaking changes, but this is acceptable since v1 hasn't been released
- No need for v2 API - refactor v1 directly
- Update tests as you go to maintain coverage
- Run full test suite after each phase
- Document changes in commit messages

---

**Ready to start?** Begin with Phase 1, Issue #1 (simplest fix) and work through each issue systematically.
