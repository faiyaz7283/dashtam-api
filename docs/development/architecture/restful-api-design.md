# RESTful API Architecture

**Last Updated**: 2025-10-04  
**Status**: Active Standard  
**Applies To**: All API endpoints in Dashtam

---

## Table of Contents

1. [Introduction](#introduction)
2. [REST Principles](#rest-principles)
3. [Resource Design](#resource-design)
4. [HTTP Methods](#http-methods)
5. [Status Codes](#status-codes)
6. [URL Structure](#url-structure)
7. [Request/Response Formats](#requestresponse-formats)
8. [Versioning Strategy](#versioning-strategy)
9. [Error Handling](#error-handling)
10. [Pagination](#pagination)
11. [Filtering & Sorting](#filtering--sorting)
12. [Authentication & Authorization](#authentication--authorization)
13. [Rate Limiting](#rate-limiting)
14. [Caching](#caching)
15. [HATEOAS](#hateoas)
16. [Best Practices](#best-practices)

---

## Introduction

This document establishes the RESTful API design standards for the Dashtam application. All API endpoints must follow these guidelines to ensure consistency, maintainability, and adherence to industry best practices.

### Design Philosophy

- **Resource-Oriented**: APIs are designed around resources (nouns) not actions (verbs)
- **Stateless**: Each request contains all information needed to process it
- **Cacheable**: Responses explicitly indicate cacheability
- **Uniform Interface**: Consistent patterns across all endpoints
- **Layered System**: Architecture supports intermediaries (proxies, gateways)

---

## REST Principles

### 1. Client-Server Separation

The API server and client are independent. The server exposes resources; clients consume them.

```
┌─────────────┐         HTTP/JSON         ┌─────────────┐
│   Client    │ ◄──────────────────────► │   Server    │
│ (Frontend)  │                           │ (FastAPI)   │
└─────────────┘                           └─────────────┘
```

### 2. Statelessness

Each request is self-contained. Session state is stored client-side (e.g., JWT tokens).

**✅ Good (Stateless)**:
```http
GET /api/v1/providers
Authorization: Bearer eyJhbGci...
```

**❌ Bad (Stateful)**:
```http
GET /api/v1/providers
Cookie: session_id=abc123
```

### 3. Cacheability

Responses define whether they can be cached.

```python
@router.get("/providers/{provider_id}")
async def get_provider(provider_id: UUID):
    return Response(
        content=json.dumps(provider_data),
        headers={"Cache-Control": "max-age=3600"}  # Cache for 1 hour
    )
```

### 4. Uniform Interface

All endpoints follow consistent patterns:
- **Resource identification**: URLs identify resources
- **Resource manipulation**: Use standard HTTP methods
- **Self-descriptive messages**: Responses include media type
- **Hypermedia**: Links to related resources (optional)

### 5. Layered System

Architecture supports intermediaries without client knowledge.

```
Client → Load Balancer → API Gateway → FastAPI Server → Database
```

---

## Resource Design

### Resource Naming

**Resources are nouns, not verbs. Use plural names for collections.**

✅ **Good**:
```
/providers           # Collection
/providers/{id}      # Individual resource
/users               # Collection
/users/{id}/tokens   # Sub-resource collection
```

❌ **Bad**:
```
/getProviders        # Verb in URL
/provider            # Singular for collection
/user/{id}/getTokens # Verb in URL
```

### Resource Hierarchy

Model relationships through URL structure:

```
/users                          # All users
/users/{user_id}                # Specific user
/users/{user_id}/providers      # User's providers
/users/{user_id}/providers/{provider_id}  # Specific provider
```

### Special Cases

**Non-CRUD Operations** (actions that don't map to resources):

Use **controller-style** endpoints as a last resort:

```
POST /providers/{id}/refresh    # Refresh provider tokens
POST /providers/{id}/sync       # Sync provider data
POST /auth/login                # Login action
POST /auth/logout               # Logout action
```

**Note**: These are acceptable when the operation is truly an action, not a resource state change.

---

## HTTP Methods

### Standard Methods

| Method | Purpose | Idempotent | Safe | Cache |
|--------|---------|------------|------|-------|
| GET | Retrieve resource(s) | ✅ Yes | ✅ Yes | ✅ Yes |
| POST | Create resource | ❌ No | ❌ No | ❌ No |
| PUT | Replace resource | ✅ Yes | ❌ No | ❌ No |
| PATCH | Update resource | ❌ No | ❌ No | ❌ No |
| DELETE | Remove resource | ✅ Yes | ❌ No | ❌ No |
| HEAD | Get headers only | ✅ Yes | ✅ Yes | ✅ Yes |
| OPTIONS | Get allowed methods | ✅ Yes | ✅ Yes | ✅ Yes |

### Method Usage

#### GET - Retrieve Resources

```python
# Get collection
@router.get("/providers")
async def list_providers(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
) -> List[ProviderResponse]:
    """List all providers for current user."""
    return providers

# Get single resource
@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user)
) -> ProviderResponse:
    """Get specific provider by ID."""
    return provider
```

**Rules**:
- Never modify data with GET
- Support pagination for collections
- Return 404 if resource not found
- Return 200 with data on success

#### POST - Create Resources

```python
@router.post("/providers", status_code=status.HTTP_201_CREATED)
async def create_provider(
    request: CreateProviderRequest,
    current_user: User = Depends(get_current_user)
) -> ProviderResponse:
    """Create a new provider."""
    provider = await create_provider_service(request, current_user.id)
    
    # Return 201 Created with Location header
    return Response(
        content=provider.json(),
        status_code=201,
        headers={"Location": f"/api/v1/providers/{provider.id}"}
    )
```

**Rules**:
- Return 201 Created on success
- Include `Location` header with new resource URL
- Return created resource in response body
- Use 400 for validation errors
- Use 409 for conflicts (e.g., duplicate)

#### PUT - Replace Resources

```python
@router.put("/providers/{provider_id}")
async def replace_provider(
    provider_id: UUID,
    request: ReplaceProviderRequest,  # Requires ALL fields
    current_user: User = Depends(get_current_user)
) -> ProviderResponse:
    """Completely replace a provider."""
    provider = await replace_provider_service(provider_id, request)
    return provider
```

**Rules**:
- Replace entire resource
- Require all fields in request
- Return 200 with updated resource
- Return 404 if resource doesn't exist
- Idempotent (same request = same result)

#### PATCH - Update Resources

```python
@router.patch("/providers/{provider_id}")
async def update_provider(
    provider_id: UUID,
    request: UpdateProviderRequest,  # Optional fields only
    current_user: User = Depends(get_current_user)
) -> ProviderResponse:
    """Partially update a provider."""
    provider = await update_provider_service(provider_id, request)
    return provider
```

**Rules**:
- Update only specified fields
- All fields optional in request
- Return 200 with updated resource
- Return 404 if resource doesn't exist

#### DELETE - Remove Resources

```python
@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_user)
) -> None:
    """Delete a provider."""
    await delete_provider_service(provider_id, current_user.id)
    # No response body with 204
```

**Rules**:
- Return 204 No Content (no response body)
- OR return 200 with deleted resource info
- Return 404 if already deleted
- Idempotent (multiple deletes = same result)

---

## Status Codes

### Success Codes (2xx)

| Code | Name | Usage |
|------|------|-------|
| 200 | OK | Successful GET, PUT, PATCH, DELETE (with body) |
| 201 | Created | Successful POST creating new resource |
| 202 | Accepted | Request accepted for async processing |
| 204 | No Content | Successful DELETE (no response body) |

### Client Error Codes (4xx)

| Code | Name | Usage |
|------|------|-------|
| 400 | Bad Request | Invalid request body, validation errors |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Authenticated but not authorized |
| 404 | Not Found | Resource doesn't exist |
| 405 | Method Not Allowed | HTTP method not supported for resource |
| 409 | Conflict | Resource conflict (e.g., duplicate) |
| 422 | Unprocessable Entity | Validation errors (detailed) |
| 429 | Too Many Requests | Rate limit exceeded |

### Server Error Codes (5xx)

| Code | Name | Usage |
|------|------|-------|
| 500 | Internal Server Error | Unexpected server error |
| 502 | Bad Gateway | Upstream service error |
| 503 | Service Unavailable | Server overloaded or maintenance |
| 504 | Gateway Timeout | Upstream timeout |

### Status Code Examples

```python
from fastapi import HTTPException, status

# 400 - Bad Request
if not request.email:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Email is required"
    )

# 401 - Unauthorized
if not token:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"}
    )

# 403 - Forbidden
if provider.user_id != current_user.id:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this provider"
    )

# 404 - Not Found
if not provider:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Provider {provider_id} not found"
    )

# 409 - Conflict
if existing_provider:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Provider with alias '{alias}' already exists"
    )

# 422 - Unprocessable Entity (Pydantic handles this automatically)
class CreateProviderRequest(BaseModel):
    provider_key: str = Field(..., min_length=1)
    alias: str = Field(..., min_length=1, max_length=100)
```

---

## URL Structure

### Base URL Format

```
https://api.dashtam.com/api/v1/{resource}/{id}/{sub-resource}
└─────────┬────────┘ └┬┘ └┬┘ └─┬───┘ └┬┘ └─────┬──────┘
          │          │   │    │      │        │
        Domain      API Ver  Resource ID  Sub-resource
```

### URL Conventions

1. **Use lowercase and hyphens**:
   ```
   ✅ /user-preferences
   ❌ /userPreferences
   ❌ /user_preferences
   ```

2. **No trailing slashes**:
   ```
   ✅ /providers
   ❌ /providers/
   ```

3. **Use path for required params, query for optional**:
   ```
   ✅ /providers/{id}?include=connection
   ❌ /providers?id={id}
   ```

4. **Nest resources logically**:
   ```
   ✅ /users/{user_id}/providers
   ❌ /user-providers?user_id={id}
   ```

### Query Parameters

Use query parameters for:
- Filtering: `?status=active`
- Sorting: `?sort=created_at&order=desc`
- Pagination: `?page=2&limit=50`
- Field selection: `?fields=id,name,email`
- Search: `?q=search+term`

```python
@router.get("/providers")
async def list_providers(
    status: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    # Apply filters and return paginated results
    pass
```

---

## Request/Response Formats

### Content Type

Always use JSON for request/response bodies:

```http
Content-Type: application/json
Accept: application/json
```

### Request Format

```json
{
  "provider_key": "schwab",
  "alias": "My Schwab Account"
}
```

**Conventions**:
- Use `snake_case` for field names (Python convention)
- Include only necessary fields
- Validate with Pydantic schemas

### Response Format

**Success Response**:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "provider_key": "schwab",
  "alias": "My Schwab Account",
  "created_at": "2025-10-04T10:00:00Z",
  "connection_status": "active"
}
```

**Collection Response**:
```json
{
  "items": [
    {"id": "...", "name": "..."},
    {"id": "...", "name": "..."}
  ],
  "total": 100,
  "page": 1,
  "per_page": 50,
  "pages": 2
}
```

**Error Response**:
```json
{
  "detail": "Provider not found",
  "error_code": "PROVIDER_NOT_FOUND",
  "timestamp": "2025-10-04T10:00:00Z"
}
```

### Date/Time Format

Always use ISO 8601 with timezone:

```python
from datetime import datetime, timezone

# Correct
created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# In response
"created_at": "2025-10-04T10:00:00Z"  # UTC
"created_at": "2025-10-04T10:00:00-04:00"  # With timezone offset
```

---

## Versioning Strategy

### URI Versioning (Current Approach)

Version is in the URL path:

```
https://api.dashtam.com/api/v1/providers
https://api.dashtam.com/api/v2/providers  # Future version
```

**Advantages**:
- Simple and explicit
- Easy to route
- Clear in browser/logs

**When to version**:
- Breaking changes to request/response format
- Removing endpoints
- Changing authentication method

**Backward compatibility**:
- Add new fields (non-breaking)
- Deprecate, don't remove (with warnings)
- Support old version for at least 6 months

### Version in Code

```python
# src/api/v1/__init__.py
from fastapi import APIRouter

api_router = APIRouter(prefix="/v1")

# Mount on app
app.include_router(api_router, prefix="/api")
```

---

## Error Handling

### Standard Error Response

```python
from pydantic import BaseModel
from datetime import datetime, timezone

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    path: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None  # For validation errors
```

### Error Examples

**Single Error**:
```json
{
  "detail": "Provider not found",
  "error_code": "PROVIDER_NOT_FOUND",
  "timestamp": "2025-10-04T10:00:00Z",
  "path": "/api/v1/providers/123"
}
```

**Validation Errors**:
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
    },
    {
      "field": "password",
      "message": "Must be at least 8 characters",
      "type": "value_error.str.too_short"
    }
  ]
}
```

### Exception Handling

```python
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "error_code": "VALIDATION_ERROR",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": str(request.url.path),
            "errors": [
                {
                    "field": ".".join(str(loc) for loc in err["loc"][1:]),
                    "message": err["msg"],
                    "type": err["type"]
                }
                for err in exc.errors()
            ]
        }
    )
```

---

## Pagination

### Offset-Based Pagination (Current)

```python
@router.get("/providers")
async def list_providers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse[ProviderResponse]:
    skip = (page - 1) * per_page
    providers = await get_providers(skip=skip, limit=per_page)
    total = await count_providers()
    
    return PaginatedResponse(
        items=providers,
        total=total,
        page=page,
        per_page=per_page,
        pages=math.ceil(total / per_page)
    )
```

**Response**:
```json
{
  "items": [...],
  "total": 100,
  "page": 2,
  "per_page": 50,
  "pages": 2,
  "_links": {
    "self": "/api/v1/providers?page=2&per_page=50",
    "first": "/api/v1/providers?page=1&per_page=50",
    "prev": "/api/v1/providers?page=1&per_page=50",
    "next": null,
    "last": "/api/v1/providers?page=2&per_page=50"
  }
}
```

### Cursor-Based Pagination (Future)

For real-time feeds and large datasets:

```python
@router.get("/providers")
async def list_providers(
    cursor: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100)
):
    providers, next_cursor = await get_providers_cursor(cursor, limit)
    
    return {
        "items": providers,
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None
    }
```

---

## Filtering & Sorting

### Filtering

```python
@router.get("/providers")
async def list_providers(
    status: Optional[str] = None,  # Filter by status
    provider_key: Optional[str] = None,  # Filter by type
    search: Optional[str] = None,  # Full-text search
    created_after: Optional[datetime] = None,  # Date range
    current_user: User = Depends(get_current_user)
):
    query = select(Provider).where(Provider.user_id == current_user.id)
    
    if status:
        query = query.where(Provider.status == status)
    if provider_key:
        query = query.where(Provider.provider_key == provider_key)
    if search:
        query = query.where(Provider.alias.ilike(f"%{search}%"))
    if created_after:
        query = query.where(Provider.created_at >= created_after)
    
    providers = await session.execute(query)
    return providers.scalars().all()
```

**Usage**:
```http
GET /api/v1/providers?status=active&provider_key=schwab&search=retirement
```

### Sorting

```python
@router.get("/providers")
async def list_providers(
    sort: str = Query("created_at", regex="^[a-z_]+$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_user)
):
    # Validate sort field
    allowed_fields = ["created_at", "updated_at", "alias"]
    if sort not in allowed_fields:
        raise HTTPException(400, f"Cannot sort by '{sort}'")
    
    # Build query
    query = select(Provider)
    if order == "desc":
        query = query.order_by(getattr(Provider, sort).desc())
    else:
        query = query.order_by(getattr(Provider, sort).asc())
    
    return await session.execute(query)
```

**Usage**:
```http
GET /api/v1/providers?sort=created_at&order=desc
```

---

## Authentication & Authorization

### Authentication

Use Bearer tokens (JWT):

```http
GET /api/v1/providers
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Authorization

Check permissions in dependencies:

```python
async def get_current_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    if not current_user.email_verified:
        raise HTTPException(
            status_code=403,
            detail="Email verification required"
        )
    return current_user

@router.post("/providers")
async def create_provider(
    request: CreateProviderRequest,
    current_user: User = Depends(get_current_verified_user)  # Verified only
):
    pass
```

---

## Rate Limiting

### Implementation (Future)

```python
from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/providers")
@limiter.limit("100/minute")  # 100 requests per minute
async def list_providers(request: Request):
    pass
```

### Rate Limit Headers

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1696435200
```

---

## Caching

### Cache Headers

```python
from fastapi import Response

@router.get("/providers/{provider_id}")
async def get_provider(provider_id: UUID) -> Response:
    provider = await get_provider_service(provider_id)
    
    return Response(
        content=provider.json(),
        headers={
            "Cache-Control": "private, max-age=3600",  # Cache for 1 hour
            "ETag": f'"{hash(provider)}"',  # Entity tag
            "Last-Modified": provider.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
        }
    )
```

### Conditional Requests

```python
@router.get("/providers/{provider_id}")
async def get_provider(
    provider_id: UUID,
    if_none_match: Optional[str] = Header(None),
    if_modified_since: Optional[str] = Header(None)
):
    provider = await get_provider_service(provider_id)
    etag = f'"{hash(provider)}"'
    
    # Check ETag
    if if_none_match == etag:
        return Response(status_code=304)  # Not Modified
    
    # Check Last-Modified
    if if_modified_since:
        client_time = datetime.strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S GMT")
        if provider.updated_at <= client_time:
            return Response(status_code=304)
    
    return provider
```

---

## HATEOAS

### Hypermedia Links (Optional)

Include links to related resources:

```json
{
  "id": "123",
  "alias": "My Account",
  "_links": {
    "self": {
      "href": "/api/v1/providers/123"
    },
    "connection": {
      "href": "/api/v1/providers/123/connection"
    },
    "tokens": {
      "href": "/api/v1/providers/123/tokens"
    },
    "refresh": {
      "href": "/api/v1/providers/123/refresh",
      "method": "POST"
    }
  }
}
```

---

## Best Practices

### Do's ✅

1. **Use nouns for resources, not verbs**
   - `/users` not `/getUsers`

2. **Use plural names for collections**
   - `/providers` not `/provider`

3. **Use HTTP methods correctly**
   - GET for reading, POST for creating, etc.

4. **Return appropriate status codes**
   - 404 for not found, 201 for created

5. **Provide comprehensive error messages**
   - Help developers debug issues

6. **Version your API**
   - `/api/v1/` in URL

7. **Use pagination for collections**
   - Never return unbounded lists

8. **Support filtering and sorting**
   - Allow clients to request what they need

9. **Document your API**
   - Use OpenAPI/Swagger

10. **Be consistent**
    - Follow same patterns everywhere

### Don'ts ❌

1. **Don't use verbs in URLs**
   - ❌ `/createProvider`
   - ✅ `POST /providers`

2. **Don't nest too deeply**
   - ❌ `/users/{id}/providers/{id}/tokens/{id}/refresh`
   - ✅ `/tokens/{id}/refresh`

3. **Don't return sensitive data**
   - Never include passwords, secrets

4. **Don't ignore HTTP methods**
   - Use POST for creation, not GET

5. **Don't return inconsistent formats**
   - Same resource = same structure

6. **Don't break backward compatibility**
   - Version instead

7. **Don't use cryptic error codes**
   - Provide clear messages

8. **Don't forget authentication**
   - Secure all endpoints

9. **Don't expose implementation details**
   - Abstract internal structure

10. **Don't ignore performance**
    - Cache, paginate, index

---

## References

- [REST API Tutorial](https://restfulapi.net/)
- [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines/blob/vNext/Guidelines.md)
- [Google API Design Guide](https://cloud.google.com/apis/design)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [HTTP Status Codes](https://httpstatuses.com/)

---

**Document Version**: 1.0  
**Last Reviewed**: 2025-10-04  
**Next Review**: 2025-04-04
