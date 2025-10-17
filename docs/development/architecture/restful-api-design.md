# RESTful API Architecture

## Table of Contents

- [Overview](#overview)
- [Context](#context)
- [Architecture Goals](#architecture-goals)
- [Design Decisions](#design-decisions)
  - [Decision 1: Client-Server Separation](#decision-1-client-server-separation)
  - [Decision 2: Stateless Communication](#decision-2-stateless-communication)
  - [Decision 3: Explicit Cacheability](#decision-3-explicit-cacheability)
  - [Decision 4: Uniform Interface](#decision-4-uniform-interface)
  - [Decision 5: Layered System Architecture](#decision-5-layered-system-architecture)
- [Components](#components)
  - [Resource Naming](#resource-naming)
  - [Resource Hierarchy](#resource-hierarchy)
  - [Special Cases](#special-cases)
- [HTTP Methods](#http-methods)
  - [Standard Methods](#standard-methods)
  - [Method Usage](#method-usage)
    - [GET - Retrieve Resources](#get---retrieve-resources)
    - [POST - Create Resources](#post---create-resources)
    - [PUT - Replace Resources](#put---replace-resources)
    - [PATCH - Update Resources](#patch---update-resources)
    - [DELETE - Remove Resources](#delete---remove-resources)
- [Status Codes](#status-codes)
  - [Success Codes (2xx)](#success-codes-2xx)
  - [Client Error Codes (4xx)](#client-error-codes-4xx)
  - [Server Error Codes (5xx)](#server-error-codes-5xx)
  - [Status Code Examples](#status-code-examples)
- [URL Structure](#url-structure)
  - [Base URL Format](#base-url-format)
  - [URL Conventions](#url-conventions)
  - [Query Parameters](#query-parameters)
- [Request/Response Formats](#requestresponse-formats)
  - [Content Type](#content-type)
  - [Request Format](#request-format)
  - [Response Format](#response-format)
  - [Date/Time Format](#datetime-format)
- [Versioning Strategy](#versioning-strategy)
  - [URI Versioning (Current Approach)](#uri-versioning-current-approach)
  - [Version in Code](#version-in-code)
- [Error Handling](#error-handling)
  - [Standard Error Response](#standard-error-response)
  - [Error Examples](#error-examples)
  - [Exception Handling](#exception-handling)
- [Pagination](#pagination)
  - [Offset-Based Pagination (Current)](#offset-based-pagination-current)
  - [Cursor-Based Pagination (Future)](#cursor-based-pagination-future)
- [Filtering & Sorting](#filtering--sorting)
  - [Filtering](#filtering)
  - [Sorting](#sorting)
- [Security Considerations](#security-considerations)
  - [Authentication & Authorization](#authentication--authorization)
    - [Authentication](#authentication)
    - [Authorization](#authorization)
  - [Rate Limiting](#rate-limiting)
    - [Implementation (Future)](#implementation-future)
    - [Rate Limit Headers](#rate-limit-headers)
  - [Caching](#caching)
    - [Cache Headers](#cache-headers)
    - [Conditional Requests](#conditional-requests)
- [HATEOAS](#hateoas)
  - [Hypermedia Links (Optional)](#hypermedia-links-optional)
- [Best Practices](#best-practices)
  - [Do's ✅](#dos-)
  - [Don'ts ❌](#donts-)
- [Implementation Details](#implementation-details)
- [Performance Considerations](#performance-considerations)
  - [Caching Benefits](#caching-benefits)
  - [Pagination Performance](#pagination-performance)
  - [Stateless Scalability](#stateless-scalability)
- [Testing Strategy](#testing-strategy)
  - [REST Compliance Testing](#rest-compliance-testing)
  - [Test Coverage](#test-coverage)
- [Future Enhancements](#future-enhancements)
- [References](#references)
- [Document Information](#document-information)

---

## Overview

This document establishes the RESTful API design standards for the Dashtam application. All API endpoints must follow these guidelines to ensure consistency, maintainability, and adherence to industry best practices.

Dashtam implements a REST-compliant API architecture that provides a uniform interface for financial data access across web, mobile, and third-party integrations.

---

## Context

Dashtam's API serves as the primary interface for all client applications accessing financial data from multiple provider integrations.

**Operating Environment:**

- **Framework**: FastAPI (async Python web framework)
- **API Consumers**: Web frontend, mobile apps, potential third-party integrations
- **Data Sources**: Multiple financial providers (Charles Schwab, future: Plaid, Chase, etc.)
- **Deployment**: Containerized services behind API gateway/load balancer
- **Authentication**: JWT-based stateless authentication

**System Constraints:**

- **Stateless requirement**: No server-side session storage (horizontal scalability)
- **Multi-client support**: Single API serves multiple client types
- **Provider diversity**: Must abstract differences across financial providers
- **Security compliance**: Financial data requires strict access control
- **Performance needs**: Support high request volumes with caching

**Key Requirements:**

1. **Consistency**: Uniform patterns across all endpoints
2. **Discoverability**: Clear, predictable URL structure
3. **Extensibility**: Easy to add new resources and providers
4. **Client-agnostic**: Works for web, mobile, and API integrations
5. **Standards compliance**: Follow REST architectural constraints

---

## Architecture Goals

1. **Resource-Oriented Design** - Model API around resources (nouns) not actions (verbs)
2. **Stateless Communication** - Each request contains all information needed; no server-side sessions
3. **Cacheability** - Responses explicitly indicate cacheability to improve performance
4. **Uniform Interface** - Consistent patterns, conventions, and error handling across all endpoints
5. **Layered Architecture** - Support intermediaries (proxies, load balancers, API gateways) transparently
6. **Industry Standards Compliance** - Follow RESTful API best practices and HTTP specifications

---

## Design Decisions

### Decision 1: Client-Server Separation

**Decision**: Separate client and server responsibilities; server exposes resources via HTTP/JSON, clients consume them.

```mermaid
flowchart LR
    Client[Client<br/>Frontend] <-->|HTTP/JSON| Server[Server<br/>FastAPI]
```

**Rationale**:

- Enables independent evolution of client and server
- Supports multiple client types (web, mobile, third-party)
- Improves portability and scalability

**Trade-offs**:

- Requires network communication (latency)
- Must design stable API contracts

### Decision 2: Stateless Communication

**Decision**: Each request must be self-contained with all required information; no server-side session storage.

**Rationale**:

- Enables horizontal scalability (any server can handle any request)
- Simplifies server implementation (no session management)
- Improves reliability (no session loss on server restart)

**Implementation**:

✅ **Good (Stateless)**:

```http
GET /api/v1/providers
Authorization: Bearer eyJhbGci...  # JWT contains user identity
```

❌ **Bad (Stateful)**:

```http
GET /api/v1/providers
Cookie: session_id=abc123  # Server must track sessions
```

**Trade-offs**:

- Larger requests (auth token in every request)
- Client must manage auth state

### Decision 3: Explicit Cacheability

**Decision**: Responses must explicitly indicate whether they can be cached using Cache-Control headers.

**Rationale**:

- Reduces server load for frequently accessed resources
- Improves client performance (faster responses)
- Supports CDN and browser caching

**Implementation**:

```python
@router.get("/providers/{provider_id}")
async def get_provider(provider_id: UUID):
    return Response(
        content=json.dumps(provider_data),
        headers={"Cache-Control": "max-age=3600"}  # Cache for 1 hour
    )
```

**Trade-offs**:

- Cached data may be stale
- Must carefully choose cache duration per resource

### Decision 4: Uniform Interface

**Decision**: All endpoints follow consistent patterns for resource identification, manipulation, and representation.

**Rationale**:

- Simplifies client development (predictable patterns)
- Reduces learning curve for API consumers
- Enables generic HTTP tooling

**Principles**:

- **Resource identification**: URLs identify resources (`/providers/{id}`)
- **Resource manipulation**: Standard HTTP methods (GET, POST, PATCH, DELETE)
- **Self-descriptive messages**: Responses include Content-Type headers
- **Hypermedia**: Links to related resources (optional for Dashtam)

**Trade-offs**:

- May not perfectly map complex operations to CRUD
- Requires discipline to maintain consistency

### Decision 5: Layered System Architecture

**Decision**: Support transparent intermediaries (load balancers, API gateways, proxies) between client and server.

**Rationale**:

- Enables horizontal scaling behind load balancer
- Supports API gateway for cross-cutting concerns (auth, rate limiting)
- Allows caching layers for performance

**Architecture**:

```mermaid
flowchart LR
    Client --> LB[Load Balancer]
    LB --> GW[API Gateway]
    GW --> API[FastAPI Server]
    API --> DB[(Database)]
```

**Trade-offs**:

- Added complexity in infrastructure
- Potential latency from additional hops

---

## Components

### Resource Naming

**Resources are nouns, not verbs. Use plural names for collections.**

✅ **Good:**

```bash
/providers           # Collection
/providers/{id}      # Individual resource
/users               # Collection
/users/{id}/tokens   # Sub-resource collection
```

❌ **Bad:**

```bash
/getProviders        # Verb in URL
/provider            # Singular for collection
/user/{id}/getTokens # Verb in URL
```

### Resource Hierarchy

Model relationships through URL structure:

```bash
/users                                    # All users
/users/{user_id}                          # Specific user
/users/{user_id}/providers                # User's providers
/users/{user_id}/providers/{provider_id}  # Specific provider
```

### Special Cases

**Non-CRUD Operations** (actions that don't map to resources):

Use **controller-style** endpoints as a last resort:

```bash
POST /providers/{id}/refresh    # Refresh provider tokens
POST /providers/{id}/sync       # Sync provider data
POST /auth/login                # Login action
POST /auth/logout               # Logout action
```

**Note:** These are acceptable when the operation is truly an action, not a resource state change.

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

**Rules:**

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

**Rules:**

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

**Rules:**

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

**Rules:**

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

**Rules:**

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

```text
https://api.dashtam.com/api/v1/{resource}/{id}/{sub-resource}
└───────────┬─────────┘└┬─┘└┬┘ └──┬─────┘ └─┬┘ └─────┬──────┘
            │           │   │     │         │        │
          Domain       API Ver  Resource    ID   Sub-resource
```

### URL Conventions

1. **Use lowercase and hyphens:**

   ```text
   ✅ /user-preferences
   ❌ /userPreferences
   ❌ /user_preferences
   ```

2. **No trailing slashes:**

   ```text
   ✅ /providers
   ❌ /providers/
   ```

3. **Use path for required params, query for optional:**

   ```text
   ✅ /providers/{id}?include=connection
   ❌ /providers?id={id}
   ```

4. **Nest resources logically:**

   ```text
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

**Conventions:**

- Use `snake_case` for field names (Python convention)
- Include only necessary fields
- Validate with Pydantic schemas

### Response Format

**Success Response:**

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "provider_key": "schwab",
  "alias": "My Schwab Account",
  "created_at": "2025-10-04T10:00:00Z",
  "connection_status": "active"
}
```

**Collection Response:**

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

**Error Response:**

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

```text
https://api.dashtam.com/api/v1/providers
https://api.dashtam.com/api/v2/providers  # Future version
```

**Advantages:**

- Simple and explicit
- Easy to route
- Clear in browser/logs

**When to version:**

- Breaking changes to request/response format
- Removing endpoints
- Changing authentication method

**Backward compatibility:**

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

**Single Error:**

```json
{
  "detail": "Provider not found",
  "error_code": "PROVIDER_NOT_FOUND",
  "timestamp": "2025-10-04T10:00:00Z",
  "path": "/api/v1/providers/123"
}
```

**Validation Errors:**

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

**Response:**

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

**Usage:**

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

**Usage:**

```http
GET /api/v1/providers?sort=created_at&order=desc
```

---

## Security Considerations

### Authentication & Authorization

#### Authentication

Use Bearer tokens (JWT):

```http
GET /api/v1/providers
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

#### Authorization

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

### Rate Limiting

#### Implementation (Future)

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

#### Rate Limit Headers

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1696435200
```

---

### Caching

#### Cache Headers

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

#### Conditional Requests

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

## Implementation Details

See sections above for detailed implementation guidance:

- Resource Design (Components)
- HTTP Methods
- Status Codes
- URL Structure
- Request/Response Formats
- Versioning Strategy
- Error Handling
- Pagination
- Filtering & Sorting

---

## Performance Considerations

### Caching Benefits

**Impact**: Properly implemented caching reduces server load and improves response times.

- **GET requests**: Cache stable resources (e.g., provider details)
- **Cache-Control headers**: Use `max-age` for time-based expiration
- **ETags**: Support conditional requests for fresher data validation

**Performance Gain**: 50-90% reduction in API calls for cached resources.

### Pagination Performance

**Impact**: Prevents large dataset transfers that slow responses.

- **Offset-based** (current): Simple but slower for deep pages
- **Cursor-based** (future): Better performance for large datasets
- **Default limit**: 100 items prevents accidental large queries

### Stateless Scalability

**Impact**: Stateless design enables horizontal scaling.

- Any server can handle any request (no session affinity)
- Load balancer distributes traffic evenly
- Easy to add/remove servers

---

## Testing Strategy

### REST Compliance Testing

- **Contract testing**: Verify API adheres to OpenAPI specification
- **Status code validation**: Ensure correct HTTP codes returned
- **URL pattern testing**: Check resource-oriented URL structure
- **Method testing**: Verify GET is safe, PUT/DELETE are idempotent

### Test Coverage

- **Unit tests**: Schema validation, error response format
- **Integration tests**: Full endpoint testing with database
- **E2E tests**: Complete user flows across multiple endpoints
- **Smoke tests**: Critical path validation (auth, providers, etc.)

**Target**: 85%+ coverage for API endpoint code.

---

## Future Enhancements

🔲 **HATEOAS Implementation** - Add hypermedia links in responses for discoverability  
🔲 **Cursor-Based Pagination** - Improved performance for large datasets  
🔲 **Rate Limiting** - Prevent API abuse with Redis-based rate limits  
🔲 **GraphQL Alternative** - Consider GraphQL for complex client queries  
🔲 **API Versioning in Headers** - Move from URL to Accept header versioning  
🔲 **Webhook Support** - Push notifications for async operations  
🔲 **Bulk Operations** - Batch create/update endpoints for efficiency  

---

## References

- [REST API Tutorial](https://restfulapi.net/)
- [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines/blob/vNext/Guidelines.md)
- [Google API Design Guide](https://cloud.google.com/apis/design)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [HTTP Status Codes](https://httpstatuses.com/)

**Related Dashtam Documents:**

- [JWT Authentication](jwt-authentication.md) - Authentication and authorization patterns
- [Schemas Design](schemas-design.md) - Request/response schema patterns
- [Async vs Sync Patterns](async-vs-sync-patterns.md) - Service implementation patterns
- [JWT Auth Quick Reference](../guides/jwt-auth-quick-reference.md) - Quick reference guide
- [RESTful API Quick Reference](../guides/restful-api-quick-reference.md) - Quick reference guide

---

## Document Information

**Category:** Architecture  
**Created:** 2025-10-04  
**Last Updated:** 2025-10-16  
**Status:** Active Standard  
**Applies To:** All API endpoints in Dashtam
