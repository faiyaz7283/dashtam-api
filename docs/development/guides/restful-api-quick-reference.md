# RESTful API Quick Reference

A comprehensive quick reference guide for developers building RESTful APIs following Dashtam's established patterns, conventions, and best practices.

## Overview

This guide provides quick reference information for building REST APIs in Dashtam. You'll learn HTTP method usage, status codes, URL patterns, endpoint implementation, and testing strategies.

### What You'll Learn

- How to use HTTP methods correctly (GET, POST, PUT, PATCH, DELETE)
- Proper HTTP status codes for different scenarios
- RESTful URL design patterns and conventions
- Request/response schema design with Pydantic
- Common implementation patterns (pagination, filtering, authentication)
- Error handling and testing approaches

### When to Use This Guide

Use this guide when:

- Building new API endpoints in Dashtam
- Reviewing existing endpoints for REST compliance
- Need quick reference for HTTP methods and status codes
- Implementing common patterns like pagination or filtering
- Troubleshooting API design issues

## Prerequisites

Before using this guide, ensure you have:

- [ ] Dashtam development environment running
- [ ] Understanding of FastAPI framework
- [ ] Access to database models and schemas
- [ ] Familiarity with async/await patterns

**Required Tools:**

- FastAPI - Latest version
- SQLModel/SQLAlchemy - For database operations
- Pydantic v2 - For request/response schemas
- Pytest - For testing

**Required Knowledge:**

- Basic understanding of REST architectural principles
- HTTP methods and status codes
- Python async programming
- Database query patterns

## Step-by-Step Instructions

### Step 1: Choose Correct HTTP Method

Use this reference to select the appropriate HTTP method for your endpoint.

**HTTP Methods Reference:**

| Method | Purpose | Request Body | Response Body | Idempotent | Safe |
|--------|---------|--------------|---------------|------------|------|
| GET | Retrieve resource(s) | No | Yes | Yes | Yes |
| POST | Create resource | Yes | Yes | No | No |
| PUT | Replace resource | Yes | Yes | Yes | No |
| PATCH | Update resource | Yes | Yes | No | No |
| DELETE | Remove resource | No | Optional | Yes | No |

**What This Means:**

- **Idempotent:** Multiple identical requests have the same effect as a single request
- **Safe:** Request does not modify server state (read-only)

### Step 2: Select Appropriate Status Codes

Choose the correct HTTP status code based on the operation result.

**Success Status Codes (2xx):**

```python
200  # OK - GET, PUT, PATCH success
201  # Created - POST success
202  # Accepted - Async processing
204  # No Content - DELETE success
```

**Client Error Status Codes (4xx):**

```python
400  # Bad Request - Invalid data
401  # Unauthorized - No/invalid auth
403  # Forbidden - No permission
404  # Not Found - Resource doesn't exist
409  # Conflict - Duplicate resource
422  # Unprocessable - Validation error
429  # Too Many Requests - Rate limit
```

**Server Error Status Codes (5xx):**

```python
500  # Internal Server Error
503  # Service Unavailable
```

### Step 3: Design RESTful URLs

Follow these URL patterns for consistent, RESTful endpoint design.

**Good URL Patterns:**

```text
GET    /api/v1/providers                    # List all
GET    /api/v1/providers/{id}               # Get one
POST   /api/v1/providers                    # Create
PATCH  /api/v1/providers/{id}               # Update
DELETE /api/v1/providers/{id}               # Delete
GET    /api/v1/users/{id}/providers         # Nested resource
POST   /api/v1/providers/{id}/refresh       # Action (exception)
```

**Bad URL Patterns (Avoid These):**

```text
GET    /api/v1/getProviders                 # Verb in URL
POST   /api/v1/providers/create             # Redundant verb
GET    /api/v1/provider                     # Singular for collection
PATCH  /api/v1/updateProvider/{id}          # Verb in URL
```

**URL Design Rules:**

- Use plural nouns for resources (`/providers`, not `/provider`)
- No verbs in URLs (use HTTP methods instead)
- Use hyphens for multi-word resources (`/provider-connections`)
- Keep URLs hierarchical (`/users/{id}/providers`)

### Step 4: Implement Request/Response Schemas

Design Pydantic schemas for request validation and response serialization.

**Request Schema (POST/PATCH):**

```python path=null start=null
from pydantic import BaseModel, Field
from typing import Optional

class CreateProviderRequest(BaseModel):
    """Request schema for creating a provider."""
    provider_key: str = Field(..., description="Provider identifier")
    alias: str = Field(..., min_length=1, description="Display name")

class UpdateProviderRequest(BaseModel):
    """Request schema for updating a provider."""
    alias: Optional[str] = Field(None, min_length=1)
```

**Response Schema:**

```python path=null start=null
from datetime import datetime
from uuid import UUID

class ProviderResponse(BaseModel):
    """Response schema for provider endpoints."""
    id: UUID
    provider_key: str
    alias: str
    is_connected: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2
```

**Paginated Response:**

```python path=null start=null
from typing import Generic, TypeVar, List

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    page: int
    per_page: int
```

**Error Response:**

```python path=null start=null
class ErrorResponse(BaseModel):
    """Standard error response format."""
    detail: str
    error_code: Optional[str] = None
```

### Step 5: Add Authentication and Authorization

Include authentication dependencies and authorization checks.

**Authentication Dependency:**

```python path=null start=null
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Validate JWT token and return current user."""
    token = credentials.credentials
    user = await verify_jwt_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return user
```

**Authorization Check:**

```python path=null start=null
async def verify_provider_ownership(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Provider:
    """Verify user owns the provider."""
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.user_id == current_user.id
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    return provider
```

### Step 6: Handle Common Patterns

Implement common API patterns for robust endpoints.

#### Pattern 1: Resource Existence Check

```python path=null start=null
# Check if resource exists before operation
result = await session.execute(
    select(Provider).where(Provider.id == provider_id)
)
provider = result.scalar_one_or_none()

if not provider:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Provider not found"
    )
```

#### Pattern 2: Duplicate Check

```python path=null start=null
# Check for duplicates before creation
result = await session.execute(
    select(Provider).where(
        Provider.user_id == user_id,
        Provider.alias == alias
    )
)
existing = result.scalar_one_or_none()

if existing:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Provider with this alias already exists"
    )
```

#### Pattern 3: Pagination

```python path=null start=null
async def list_providers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session)
):
    """List providers with pagination."""
    # Get total count
    count_result = await session.execute(
        select(func.count(Provider.id))
    )
    total = count_result.scalar_one()
    
    # Get paginated items
    offset = (page - 1) * per_page
    result = await session.execute(
        select(Provider)
        .offset(offset)
        .limit(per_page)
    )
    providers = result.scalars().all()
    
    return PaginatedResponse(
        items=providers,
        total=total,
        page=page,
        per_page=per_page
    )
```

#### Pattern 4: Filtering

```python path=null start=null
async def list_providers(
    is_connected: Optional[bool] = Query(None),
    provider_key: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session)
):
    """List providers with optional filters."""
    stmt = select(Provider)
    
    if is_connected is not None:
        stmt = stmt.where(Provider.is_connected == is_connected)
    
    if provider_key is not None:
        stmt = stmt.where(Provider.provider_key == provider_key)
    
    result = await session.execute(stmt)
    return result.scalars().all()
```

#### Pattern 5: Sorting

```python path=null start=null
from typing import Literal

async def list_providers(
    sort_by: Literal["created_at", "alias"] = Query("created_at"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    session: AsyncSession = Depends(get_session)
):
    """List providers with sorting."""
    stmt = select(Provider)
    
    # Apply sorting
    if sort_order == "asc":
        stmt = stmt.order_by(getattr(Provider, sort_by).asc())
    else:
        stmt = stmt.order_by(getattr(Provider, sort_by).desc())
    
    result = await session.execute(stmt)
    return result.scalars().all()
```

#### Pattern 6: Query Parameter Conventions

```python path=null start=null
# Pagination
page: int = Query(1, ge=1)
per_page: int = Query(50, ge=1, le=100)

# Filtering
is_active: Optional[bool] = Query(None)
provider_key: Optional[str] = Query(None)

# Sorting
sort_by: str = Query("created_at")
sort_order: Literal["asc", "desc"] = Query("desc")

# Search
search: Optional[str] = Query(None, min_length=2)
```

## Examples

### Example 1: Complete CRUD Endpoint Implementation

This example shows a complete provider endpoint with all CRUD operations.

**Router Implementation:**

```python path=null start=null
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID
from typing import Optional

from src.core.database import get_session
from src.schemas.provider import (
    CreateProviderRequest,
    UpdateProviderRequest,
    ProviderResponse,
    PaginatedProviderResponse
)
from src.models.provider import Provider
from src.api.deps import get_current_user
from src.models.user import User

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])

@router.get("", response_model=PaginatedProviderResponse)
async def list_providers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    List all providers for the current user.
    
    Supports pagination with page and per_page query parameters.
    """
    # Get total count
    count_result = await session.execute(
        select(func.count(Provider.id)).where(
            Provider.user_id == current_user.id
        )
    )
    total = count_result.scalar_one()
    
    # Get paginated items
    offset = (page - 1) * per_page
    result = await session.execute(
        select(Provider)
        .where(Provider.user_id == current_user.id)
        .offset(offset)
        .limit(per_page)
    )
    providers = result.scalars().all()
    
    return {
        "items": providers,
        "total": total,
        "page": page,
        "per_page": per_page
    }

@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a specific provider by ID."""
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.user_id == current_user.id
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    return provider

@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    request: CreateProviderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new provider."""
    # Check for duplicate alias
    result = await session.execute(
        select(Provider).where(
            Provider.user_id == current_user.id,
            Provider.alias == request.alias
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provider with this alias already exists"
        )
    
    # Create provider
    provider = Provider(
        user_id=current_user.id,
        provider_key=request.provider_key,
        alias=request.alias
    )
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    
    return provider

@router.patch("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    request: UpdateProviderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update an existing provider."""
    # Get provider with ownership check
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.user_id == current_user.id
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    # Update fields
    if request.alias is not None:
        provider.alias = request.alias
    
    await session.commit()
    await session.refresh(provider)
    
    return provider

@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a provider."""
    # Get provider with ownership check
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.user_id == current_user.id
        )
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found"
        )
    
    await session.delete(provider)
    await session.commit()
```

### Example 2: Comprehensive Test Suite

This example shows a complete test suite for provider endpoints.

**Test Implementation:**

```python path=null start=null
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

### Example 3: Error Handling

This example shows proper error handling for different scenarios.

**Validation Error (422):**

```python path=null start=null
# Request with invalid data
{
    "alias": "",  # Too short
    "provider_key": "invalid"
}

# Response
{
    "detail": [
        {
            "loc": ["body", "alias"],
            "msg": "String should have at least 1 character",
            "type": "string_too_short"
        }
    ]
}
```

**Not Found Error (404):**

```python path=null start=null
# Response for non-existent resource
{
    "detail": "Provider not found"
}
```

**Forbidden Error (403):**

```python path=null start=null
# Response when user tries to access another user's resource
{
    "detail": "Provider not found"  # Don't reveal existence
}
```

**Conflict Error (409):**

```python path=null start=null
# Response when creating duplicate resource
{
    "detail": "Provider with this alias already exists"
}
```

### Example 4: Naming Conventions

Follow these naming conventions for consistency.

**Resources (URLs):**

```text
/providers        # Plural, lowercase
/provider-types   # Hyphen for multi-word
/oauth-tokens     # Consistent format
```

**Fields (JSON):**

```python path=null start=null
# Use snake_case for all fields
{
    "provider_key": "schwab",
    "is_connected": true,
    "created_at": "2025-10-20T12:00:00Z",
    "user_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Booleans:**

```python path=null start=null
# Good
is_active
has_connection
can_edit

# Bad
active
connection
editable
```

**Dates:**

```python path=null start=null
# Good
created_at
updated_at
deleted_at
expires_at

# Bad
created
creation_date
date_created
```

## Verification

How to verify your REST API endpoints are working correctly.

### Check 1: HTTP Method and Status Code Verification

Test each endpoint returns correct HTTP status codes.

```bash
# Test GET endpoint (200 OK)
curl -X GET https://localhost:8000/api/v1/providers \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -k

# Test POST endpoint (201 Created)
curl -X POST https://localhost:8000/api/v1/providers \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"provider_key":"schwab","alias":"test"}' \
  -k

# Test DELETE endpoint (204 No Content)
curl -X DELETE https://localhost:8000/api/v1/providers/$PROVIDER_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -k
```

**Expected Results:**

- GET returns 200 with JSON body
- POST returns 201 with created resource
- DELETE returns 204 with no body

### Check 2: Response Format Consistency

Verify all endpoints return consistent JSON structures.

```bash
# Verify paginated response format
curl https://localhost:8000/api/v1/providers \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -k | jq

# Expected format:
# {
#   "items": [...],
#   "total": 10,
#   "page": 1,
#   "per_page": 50
# }
```

### Check 3: Error Handling

Test error scenarios return proper status codes and messages.

```bash
# Test 404 handling
curl https://localhost:8000/api/v1/providers/nonexistent-id \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -k

# Expected: 404 with {"detail": "Provider not found"}

# Test 401 handling (no auth)
curl https://localhost:8000/api/v1/providers -k

# Expected: 401 or 403 with auth error message
```

## Troubleshooting

### Issue 1: Wrong Status Code Returned

**Symptoms:**

- POST endpoint returns 200 instead of 201
- DELETE endpoint returns 200 instead of 204
- Successful operations return incorrect status codes

**Cause:** Missing explicit status_code parameter in route decorator.

**Solution:**

```python path=null start=null
# Add explicit status codes to route decorators
@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(...):
    return provider

@router.delete("/providers/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(...):
    # Return None or nothing for 204
    pass
```

### Issue 2: Inconsistent Response Format

**Symptoms:**

- Different endpoints return different JSON structures
- Missing pagination in collection endpoints
- Field names vary between endpoints

**Cause:** Not using consistent schema classes for responses.

**Solution:**

```python path=null start=null
# Use consistent schema classes
@router.get("/providers", response_model=PaginatedProviderResponse)
@router.get("/providers/{id}", response_model=ProviderResponse)
@router.post("/providers", response_model=ProviderResponse)

# Define standard response schemas
class PaginatedProviderResponse(BaseModel):
    items: List[ProviderResponse]
    total: int
    page: int
    per_page: int
```

### Issue 3: Validation Errors Not Helpful

**Symptoms:**

- Generic "validation failed" messages
- No field-specific error details
- Users don't know what to fix

**Cause:** Missing or poor field validation in Pydantic schemas.

**Solution:**

```python path=null start=null
# Use Pydantic field validation with clear messages
class CreateProviderRequest(BaseModel):
    alias: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Provider display name"
    )
    provider_key: str = Field(
        ...,
        pattern="^[a-z_]+$",
        description="Provider identifier (lowercase, underscores only)"
    )
```

### Issue 4: Authorization Bypass

**Symptoms:**

- Users can access other users' resources
- No ownership checks in endpoints
- Security vulnerabilities

**Cause:** Missing authorization checks in endpoint logic.

**Solution:**

```python path=null start=null
# Always check resource ownership
result = await session.execute(
    select(Provider).where(
        Provider.id == provider_id,
        Provider.user_id == current_user.id  # Ownership check
    )
)
provider = result.scalar_one_or_none()

if not provider:
    # Return 404, don't reveal if resource exists
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Provider not found"
    )
```

## Best Practices

Follow these best practices for consistent, maintainable REST APIs.

### API Design Principles

- **Use Plural Nouns:** `/providers`, not `/provider`
- **HTTP Method Semantics:** GET for retrieval, POST for creation, PATCH for updates
- **Consistent Status Codes:** 200/201/204 for success, 400/404/409 for client errors
- **Resource-Based URLs:** `/providers/{id}`, not `/getProvider`
- **Pagination for Collections:** Always paginate list endpoints
- **Authentication Required:** Protect all endpoints except public ones
- **Authorization Checks:** Verify user owns resources before operations
- **Input Validation:** Use Pydantic schemas for all requests
- **Error Response Format:** Consistent error structure across all endpoints

### Schema Design Patterns

- **Separate Request/Response Schemas:** Different models for input and output
- **Optional Fields for Updates:** Use `Optional[T]` for PATCH requests
- **Field Validation:** Add `Field()` with constraints and descriptions
- **Type Safety:** Use proper types (UUID, datetime, enums)
- **from_attributes:** Enable for ORM model conversion (Pydantic v2)

### Security Best Practices

- **Always Authenticate:** Require JWT tokens for protected endpoints
- **Check Ownership:** Verify user owns resources before access
- **Don't Reveal Existence:** Return 404 for both missing and unauthorized resources
- **Rate Limiting:** Implement rate limits for API protection
- **Input Sanitization:** Validate and sanitize all user input
- **HTTPS Only:** Use TLS for all API communication

### Testing Best Practices

- **Test All Methods:** GET, POST, PATCH, DELETE for each resource
- **Test Error Cases:** 404, 409, 422, 403, 401 scenarios
- **Test Pagination:** Verify page boundaries and limits
- **Test Authorization:** Verify users can't access others' resources
- **Test Validation:** Verify Pydantic validation works correctly

### Common Mistakes to Avoid

- **Verbs in URLs:** Don't use `/getProviders`, `/createProvider`
- **Wrong Status Codes:** Don't return 200 for POST creation (use 201)
- **No Pagination:** Don't return unbounded lists
- **Inconsistent Naming:** Don't mix camelCase and snake_case
- **Missing Auth:** Don't leave sensitive endpoints unprotected
- **Poor Error Messages:** Don't return generic "Bad Request" without details
- **Exposing Implementation:** Don't leak database details or SQL in responses

### Quick Checklist

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

## Next Steps

After mastering REST API patterns, consider:

- [ ] Review existing endpoints for REST compliance
- [ ] Add comprehensive tests for all endpoints
- [ ] Implement pagination for collection endpoints
- [ ] Add filtering and sorting where appropriate
- [ ] Document all endpoints in OpenAPI/Swagger
- [ ] Review error handling and status codes
- [ ] Implement rate limiting for API protection
- [ ] Add request/response logging for debugging
- [ ] Set up API monitoring and alerting
- [ ] Review [RESTful API Design Architecture](../architecture/restful-api-design.md)

## References

- [RESTful API Design Architecture](../architecture/restful-api-design.md) - Complete architecture guide
- [REST API Audit Report](../../reviews/REST_API_AUDIT_REPORT_2025-10-05.md) - Compliance review
- [Schema Design Patterns](../architecture/schemas-design.md) - Pydantic schema guide
- [Testing Guide](testing-guide.md) - Complete testing documentation
- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Official FastAPI docs
- [Pydantic v2 Documentation](https://docs.pydantic.dev/2.0/) - Schema validation
- [HTTP Status Codes](https://httpstatuses.com/) - Complete reference

---

## Document Information

**Template:** guide-template.md
**Created:** 2025-10-05
**Last Updated:** 2025-10-20
