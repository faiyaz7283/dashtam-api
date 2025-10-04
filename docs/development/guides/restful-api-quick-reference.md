# RESTful API Quick Reference

**Quick guide for developers building REST APIs in Dashtam**

---

## HTTP Methods Cheat Sheet

| Method | Purpose | Request Body | Response Body | Idempotent | Safe |
|--------|---------|--------------|---------------|------------|------|
| GET | Retrieve resource(s) | ❌ No | ✅ Yes | ✅ | ✅ |
| POST | Create resource | ✅ Yes | ✅ Yes | ❌ | ❌ |
| PUT | Replace resource | ✅ Yes | ✅ Yes | ✅ | ❌ |
| PATCH | Update resource | ✅ Yes | ✅ Yes | ❌ | ❌ |
| DELETE | Remove resource | ❌ No | Optional | ✅ | ❌ |

---

## Status Code Quick Reference

### Success (2xx)
```python
200  # OK - GET, PUT, PATCH success
201  # Created - POST success
202  # Accepted - Async processing
204  # No Content - DELETE success
```

### Client Errors (4xx)
```python
400  # Bad Request - Invalid data
401  # Unauthorized - No/invalid auth
403  # Forbidden - No permission
404  # Not Found - Resource doesn't exist
409  # Conflict - Duplicate resource
422  # Unprocessable - Validation error
429  # Too Many Requests - Rate limit
```

### Server Errors (5xx)
```python
500  # Internal Server Error
503  # Service Unavailable
```

---

## URL Patterns

### ✅ Good
```
GET    /api/v1/providers                    # List all
GET    /api/v1/providers/{id}               # Get one
POST   /api/v1/providers                    # Create
PATCH  /api/v1/providers/{id}               # Update
DELETE /api/v1/providers/{id}               # Delete
GET    /api/v1/users/{id}/providers         # Nested resource
POST   /api/v1/providers/{id}/refresh       # Action (exception)
```

### ❌ Bad
```
GET    /api/v1/getProviders                 # Verb in URL
POST   /api/v1/providers/create             # Redundant verb
GET    /api/v1/provider                     # Singular for collection
PATCH  /api/v1/updateProvider/{id}          # Verb in URL
```

---

## Endpoint Template

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from uuid import UUID
from typing import Optional, List

router = APIRouter()

# LIST - Get collection
@router.get("/providers")
async def list_providers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse[ProviderResponse]:
    """List all providers with pagination and filtering."""
    providers = await get_providers_service(
        user_id=current_user.id,
        skip=(page - 1) * per_page,
        limit=per_page,
        status=status,
        sort=sort,
        order=order
    )
    return providers

# GET - Retrieve single resource
@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user)
) -> ProviderResponse:
    """Get a specific provider by ID."""
    provider = await get_provider_service(provider_id)
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )
    
    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider"
        )
    
    return provider

# POST - Create resource
@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(
    request: CreateProviderRequest,
    current_user: User = Depends(get_current_user)
) -> ProviderResponse:
    """Create a new provider."""
    # Check for duplicates
    existing = await get_provider_by_alias(current_user.id, request.alias)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Provider with alias '{request.alias}' already exists"
        )
    
    provider = await create_provider_service(request, current_user.id)
    return provider

# PATCH - Update resource
@router.patch("/providers/{provider_id}")
async def update_provider(
    provider_id: UUID,
    request: UpdateProviderRequest,
    current_user: User = Depends(get_current_user)
) -> ProviderResponse:
    """Update a provider (partial update)."""
    provider = await get_provider_service(provider_id)
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )
    
    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider"
        )
    
    updated = await update_provider_service(provider_id, request)
    return updated

# DELETE - Remove resource
@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user)
) -> None:
    """Delete a provider."""
    provider = await get_provider_service(provider_id)
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found"
        )
    
    if provider.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this provider"
        )
    
    await delete_provider_service(provider_id)
    # No return with 204
```

---

## Request/Response Schemas

### Request Schema (POST/PATCH)

```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class CreateProviderRequest(BaseModel):
    """Schema for creating a new provider."""
    provider_key: str = Field(..., min_length=1, max_length=50)
    alias: str = Field(..., min_length=1, max_length=100)
    
    @field_validator('alias')
    @classmethod
    def alias_must_not_be_whitespace(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Alias cannot be empty or whitespace')
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "provider_key": "schwab",
                "alias": "My Retirement Account"
            }
        }

class UpdateProviderRequest(BaseModel):
    """Schema for updating a provider (all fields optional)."""
    alias: Optional[str] = Field(None, min_length=1, max_length=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "alias": "Updated Account Name"
            }
        }
```

### Response Schema

```python
from datetime import datetime
from uuid import UUID

class ProviderResponse(BaseModel):
    """Schema for provider responses."""
    id: UUID
    user_id: UUID
    provider_key: str
    alias: str
    created_at: datetime
    updated_at: datetime
    connection_status: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "223e4567-e89b-12d3-a456-426614174000",
                "provider_key": "schwab",
                "alias": "My Retirement Account",
                "created_at": "2025-10-04T10:00:00Z",
                "updated_at": "2025-10-04T10:00:00Z",
                "connection_status": "active"
            }
        }
```

### Paginated Response

```python
from typing import Generic, TypeVar, List

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response schema."""
    items: List[T]
    total: int
    page: int
    per_page: int
    pages: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "items": [...],
                "total": 100,
                "page": 1,
                "per_page": 50,
                "pages": 2
            }
        }
```

### Error Response

```python
class ErrorResponse(BaseModel):
    """Standard error response schema."""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    path: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Provider not found",
                "error_code": "PROVIDER_NOT_FOUND",
                "timestamp": "2025-10-04T10:00:00Z",
                "path": "/api/v1/providers/123"
            }
        }
```

---

## Common Patterns

### Pattern 1: Resource Existence Check

```python
provider = await get_provider_service(provider_id)
if not provider:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Provider {provider_id} not found"
    )
```

### Pattern 2: Authorization Check

```python
if provider.user_id != current_user.id:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this provider"
    )
```

### Pattern 3: Duplicate Check

```python
existing = await get_provider_by_alias(current_user.id, request.alias)
if existing:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Provider with alias '{request.alias}' already exists"
    )
```

### Pattern 4: Pagination

```python
skip = (page - 1) * per_page
items = await get_items(skip=skip, limit=per_page)
total = await count_items()

return PaginatedResponse(
    items=items,
    total=total,
    page=page,
    per_page=per_page,
    pages=math.ceil(total / per_page)
)
```

### Pattern 5: Filtering

```python
query = select(Provider).where(Provider.user_id == current_user.id)

if status:
    query = query.where(Provider.status == status)
if provider_key:
    query = query.where(Provider.provider_key == provider_key)
if search:
    query = query.where(Provider.alias.ilike(f"%{search}%"))

result = await session.execute(query)
return result.scalars().all()
```

### Pattern 6: Sorting

```python
# Validate sort field against whitelist
allowed_fields = ["created_at", "updated_at", "alias"]
if sort not in allowed_fields:
    raise HTTPException(400, f"Cannot sort by '{sort}'")

# Apply sorting
if order == "desc":
    query = query.order_by(getattr(Model, sort).desc())
else:
    query = query.order_by(getattr(Model, sort).asc())
```

---

## Query Parameter Conventions

```python
# Pagination
?page=2&per_page=50

# Filtering
?status=active&provider_key=schwab

# Sorting
?sort=created_at&order=desc

# Search
?search=retirement&q=401k

# Date ranges
?created_after=2025-01-01&created_before=2025-12-31

# Field selection (sparse fieldsets)
?fields=id,name,email

# Include related resources
?include=connection,tokens

# Combined
?page=1&per_page=25&status=active&sort=created_at&order=desc
```

---

## Error Handling Examples

### Validation Error (422)

```json
{
  "detail": "Validation error",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2025-10-04T10:00:00Z",
  "errors": [
    {
      "field": "email",
      "message": "Invalid email format",
      "type": "value_error.email"
    }
  ]
}
```

### Not Found (404)

```json
{
  "detail": "Provider 123e4567-e89b-12d3-a456-426614174000 not found",
  "error_code": "PROVIDER_NOT_FOUND",
  "timestamp": "2025-10-04T10:00:00Z"
}
```

### Forbidden (403)

```json
{
  "detail": "You don't have access to this provider",
  "error_code": "FORBIDDEN",
  "timestamp": "2025-10-04T10:00:00Z"
}
```

### Conflict (409)

```json
{
  "detail": "Provider with alias 'My Account' already exists",
  "error_code": "PROVIDER_CONFLICT",
  "timestamp": "2025-10-04T10:00:00Z"
}
```

---

## Authentication Pattern

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session)
) -> User:
    """Validate JWT token and return current user."""
    token = credentials.credentials
    
    try:
        # Decode and validate JWT
        payload = jwt_service.decode_token(token)
        jwt_service.verify_token_type(payload, "access")
        user_id = jwt_service.get_user_id_from_token(token)
        
        # Get user from database
        user = await get_user_by_id(session, user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        return user
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )

# Usage in endpoints
@router.get("/providers")
async def list_providers(
    current_user: User = Depends(get_current_user)  # Automatic auth
):
    pass
```

---

## Naming Conventions

### Resources (URLs)
```python
✅ /providers          # Plural nouns
✅ /users
✅ /tokens
✅ /user-preferences   # Kebab-case for multi-word

❌ /provider           # Singular
❌ /getProviders       # Verb
❌ /userPreferences    # camelCase
```

### Fields (JSON)
```python
✅ snake_case          # Python convention
{
    "provider_key": "schwab",
    "created_at": "2025-10-04T10:00:00Z",
    "is_active": true
}

❌ camelCase
{
    "providerKey": "schwab",
    "createdAt": "2025-10-04T10:00:00Z"
}
```

### Booleans
```python
✅ is_active, has_connection, can_edit
❌ active, connection, editable
```

### Dates
```python
✅ created_at, updated_at, deleted_at, expires_at
❌ created, creation_date, date_created
```

---

## Testing Template

```python
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

class TestProviderEndpoints:
    """Test suite for provider endpoints."""
    
    def test_list_providers_success(self, client: TestClient, auth_tokens: dict):
        """Test successful provider listing."""
        response = client.get(
            "/api/v1/providers",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
    
    def test_get_provider_success(
        self, client: TestClient, auth_tokens: dict, test_provider
    ):
        """Test getting a specific provider."""
        response = client.get(
            f"/api/v1/providers/{test_provider.id}",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_provider.id)
        assert data["alias"] == test_provider.alias
    
    def test_get_provider_not_found(self, client: TestClient, auth_tokens: dict):
        """Test getting non-existent provider returns 404."""
        fake_id = uuid4()
        response = client.get(
            f"/api/v1/providers/{fake_id}",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_create_provider_success(self, client: TestClient, auth_tokens: dict):
        """Test successful provider creation."""
        response = client.post(
            "/api/v1/providers",
            json={
                "provider_key": "schwab",
                "alias": "Test Account"
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["provider_key"] == "schwab"
        assert data["alias"] == "Test Account"
        assert "id" in data
    
    def test_create_provider_duplicate(
        self, client: TestClient, auth_tokens: dict, test_provider
    ):
        """Test creating duplicate provider returns 409."""
        response = client.post(
            "/api/v1/providers",
            json={
                "provider_key": "schwab",
                "alias": test_provider.alias  # Duplicate alias
            },
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()
    
    def test_update_provider_success(
        self, client: TestClient, auth_tokens: dict, test_provider
    ):
        """Test successful provider update."""
        response = client.patch(
            f"/api/v1/providers/{test_provider.id}",
            json={"alias": "Updated Name"},
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["alias"] == "Updated Name"
    
    def test_delete_provider_success(
        self, client: TestClient, auth_tokens: dict, test_provider
    ):
        """Test successful provider deletion."""
        response = client.delete(
            f"/api/v1/providers/{test_provider.id}",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        
        assert response.status_code == 204
        assert not response.content  # No body with 204
    
    def test_unauthorized_access(self, client: TestClient):
        """Test accessing endpoint without auth token."""
        response = client.get("/api/v1/providers")
        
        assert response.status_code == 403  # No auth header
```

---

## Quick Checklist

Before deploying a new endpoint, verify:

- [ ] Uses correct HTTP method (GET/POST/PATCH/DELETE)
- [ ] Returns appropriate status codes (200/201/204/404/etc)
- [ ] URL uses plural nouns, no verbs
- [ ] Requires authentication where needed
- [ ] Checks authorization (user owns resource)
- [ ] Validates input with Pydantic schemas
- [ ] Returns consistent response format
- [ ] Includes error handling
- [ ] Uses snake_case for JSON fields
- [ ] Supports pagination for collections
- [ ] Supports filtering/sorting where appropriate
- [ ] Has comprehensive tests
- [ ] Documented in OpenAPI/Swagger
- [ ] Follows existing patterns

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Verbs in URLs
```python
# Bad
@router.get("/getProviders")
@router.post("/createProvider")

# Good
@router.get("/providers")
@router.post("/providers")
```

### ❌ Mistake 2: Wrong Status Codes
```python
# Bad
@router.post("/providers")
async def create_provider(...):
    return provider  # Returns 200, should be 201

# Good
@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(...):
    return provider
```

### ❌ Mistake 3: No Pagination
```python
# Bad
@router.get("/providers")
async def list_providers():
    return await get_all_providers()  # Returns unbounded list

# Good
@router.get("/providers")
async def list_providers(
    page: int = 1,
    per_page: int = 50
):
    return await get_providers_paginated(page, per_page)
```

### ❌ Mistake 4: Exposing Implementation Details
```python
# Bad
{
    "id": 123,  # Internal DB ID
    "table_name": "providers",
    "sql_query": "SELECT ..."
}

# Good
{
    "id": "123e4567-e89b-12d3-a456-426614174000",  # UUID
    "provider_key": "schwab",
    "alias": "My Account"
}
```

### ❌ Mistake 5: Inconsistent Response Formats
```python
# Bad
@router.get("/providers/{id}")
async def get_provider(id):
    return provider  # Returns Provider object

@router.get("/providers")
async def list_providers():
    return {"data": providers, "count": 10}  # Different format

# Good - Consistent formats
@router.get("/providers/{id}")
async def get_provider(id) -> ProviderResponse:
    return provider

@router.get("/providers")
async def list_providers() -> PaginatedResponse[ProviderResponse]:
    return {"items": providers, "total": 10, ...}
```

---

## Resources

- **Full Architecture Doc**: `docs/development/architecture/restful-api-design.md`
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **HTTP Status Codes**: https://httpstatuses.com
- **REST API Tutorial**: https://restfulapi.net

---

**Last Updated**: 2025-10-04  
**Version**: 1.0
