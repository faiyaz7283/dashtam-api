# REST API Compliance Review

**Project**: Dashtam  
**Review Date**: 2025-10-04  
**Reviewer**: AI Assistant  
**Status**: ⚠️ Needs Improvements

---

## Executive Summary

This document reviews all existing API endpoints in the Dashtam application against REST architectural principles and industry best practices. The review identifies non-RESTful patterns, inconsistencies, and opportunities for improvement.

### Overall Assessment

| Category | Status | Score |
|----------|--------|-------|
| HTTP Method Usage | ⚠️ Mostly Compliant | 7/10 |
| URL Design | ❌ Needs Work | 4/10 |
| Status Codes | ✅ Good | 8/10 |
| Response Format | ⚠️ Inconsistent | 6/10 |
| Error Handling | ✅ Good | 8/10 |
| Resource Modeling | ⚠️ Mixed | 5/10 |
| **Overall REST Compliance** | **⚠️ Moderate** | **6.3/10** |

---

## Current API Structure

### Base URL
```
https://api.dashtam.com/api/v1
```

### Current Endpoints

#### 1. Authentication (JWT) - `/api/v1/auth`
```
POST   /api/v1/auth/register
POST   /api/v1/auth/verify-email
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
POST   /api/v1/auth/password-reset/request
POST   /api/v1/auth/password-reset/confirm
GET    /api/v1/auth/me
PATCH  /api/v1/auth/me
```

#### 2. OAuth Provider Authentication - `/api/v1/auth`
```
GET    /api/v1/auth/{provider_id}/authorize
GET    /api/v1/auth/{provider_id}/authorize/redirect
GET    /api/v1/auth/{provider_id}/callback
POST   /api/v1/auth/{provider_id}/refresh
GET    /api/v1/auth/{provider_id}/status
DELETE /api/v1/auth/{provider_id}/disconnect
```

#### 3. Provider Management - `/api/v1/providers`
```
GET    /api/v1/providers/available
GET    /api/v1/providers/configured
POST   /api/v1/providers/create
GET    /api/v1/providers/
GET    /api/v1/providers/{provider_id}
DELETE /api/v1/providers/{provider_id}
```

#### 4. Health Check
```
GET    /api/v1/health
GET    /health
GET    /
```

---

## Issues & Non-Compliance

### 🔴 Critical Issues (Must Fix)

#### Issue #1: RPC-Style Endpoint - `/providers/create`
**Current:**
```http
POST /api/v1/providers/create
```

**Problem:**
- Uses RPC-style URL with verb in path
- Violates REST principle of resource-oriented URLs
- Redundant - POST method already implies creation

**Impact:** High - Violates core REST principle

**REST Compliant:**
```http
POST /api/v1/providers
```

**File:** `src/api/v1/providers.py:103`

**Fix:**
```python
# Change from:
@router.post("/create", response_model=ProviderResponse)

# To:
@router.post("/", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
```

---

#### Issue #2: Action-Based Endpoints in Auth
**Current:**
```http
GET    /api/v1/auth/{provider_id}/authorize
GET    /api/v1/auth/{provider_id}/authorize/redirect
POST   /api/v1/auth/{provider_id}/refresh
DELETE /api/v1/auth/{provider_id}/disconnect
```

**Problem:**
- Uses verbs in URLs (authorize, redirect, refresh, disconnect)
- Mixes OAuth flow with resource management
- Not following resource-oriented design
- Inconsistent with REST principles

**Impact:** High - Confuses resource hierarchy and actions

**Analysis:**
While OAuth flows naturally involve actions (authorize, callback), these should be modeled as state transitions of a connection resource, not separate action endpoints.

**REST Compliant Alternative:**
```http
# Model as connection/authorization resource
POST   /api/v1/providers/{provider_id}/authorization        # Initiate auth
GET    /api/v1/providers/{provider_id}/authorization        # Get auth status/URL
GET    /api/v1/providers/{provider_id}/authorization/callback  # OAuth callback
DELETE /api/v1/providers/{provider_id}/authorization        # Disconnect

# Or model as nested connection resource
POST   /api/v1/providers/{provider_id}/connection           # Connect
GET    /api/v1/providers/{provider_id}/connection           # Connection status
PATCH  /api/v1/providers/{provider_id}/connection           # Refresh/update
DELETE /api/v1/providers/{provider_id}/connection           # Disconnect
```

**Files:**
- `src/api/v1/auth.py:54-379`

---

#### Issue #3: Overlapping Route Prefixes
**Current:**
```python
# Both mounted at /auth prefix
api_router.include_router(auth_oauth_router, prefix="/auth", tags=["oauth"])
api_router.include_router(auth_jwt_router, prefix="/auth", tags=["authentication"])
```

**Problem:**
- Two different routers mounted at same prefix
- JWT auth and OAuth auth mixed together
- `/auth` doesn't represent a single resource type
- Causes confusion about what `/auth` endpoints do

**Impact:** High - Violates single responsibility and resource clarity

**REST Compliant:**
```python
# Separate concerns clearly
api_router.include_router(auth_jwt_router, prefix="/auth", tags=["authentication"])
api_router.include_router(providers_router, prefix="/providers", tags=["providers"])

# OAuth flows belong to provider connections, not auth
# Move OAuth endpoints to /providers/{id}/connection or similar
```

**File:** `src/api/v1/__init__.py:17-23`

---

### ⚠️ Major Issues (Should Fix)

#### Issue #4: Inconsistent Collection Endpoints
**Current:**
```http
GET /api/v1/providers/           # List user providers
GET /api/v1/providers/available  # Different semantic - list provider types
GET /api/v1/providers/configured # Different semantic - list provider types
```

**Problem:**
- `/providers/` returns user's provider instances
- `/providers/available` returns provider types/templates
- `/providers/configured` returns provider types/templates
- Same collection URL has different meanings based on sub-path

**Impact:** Medium - Confusing resource model

**REST Compliant:**
```http
# User's provider instances
GET /api/v1/providers                    # List user's providers
POST /api/v1/providers                   # Create provider instance
GET /api/v1/providers/{id}               # Get specific provider
PATCH /api/v1/providers/{id}             # Update provider
DELETE /api/v1/providers/{id}            # Delete provider

# Provider types/catalog (separate resource)
GET /api/v1/provider-types               # List all types
GET /api/v1/provider-types/{key}         # Get specific type info

# Or as a filter
GET /api/v1/provider-types?configured=true
```

**Files:**
- `src/api/v1/providers.py:61-101`
- `src/api/v1/providers.py:179-217`

---

#### Issue #5: Multi-Word Resource Naming
**Current:**
```http
POST /api/v1/auth/password-reset/request
POST /api/v1/auth/password-reset/confirm
```

**Problem:**
- Uses kebab-case correctly ✅
- But represents action-oriented design, not resource-oriented
- Nested paths for workflow steps

**Impact:** Medium - Not resource-oriented

**REST Compliant:**
```http
# Model as password-reset resource
POST   /api/v1/password-resets              # Create reset request
PATCH  /api/v1/password-resets/{token}      # Complete reset with new password

# Or as user sub-resource
POST   /api/v1/users/password-resets        # Request reset
PATCH  /api/v1/users/password-resets/{token}  # Confirm reset
```

**File:** `src/api/v1/auth_jwt.py:246-305`

---

#### Issue #6: Missing Status Codes
**Current:**
```python
@router.post("/create", response_model=ProviderResponse)
async def create_provider_instance(...):
    # Returns 200 by default, should be 201
```

**Problem:**
- POST endpoint doesn't specify 201 Created status
- Default 200 OK doesn't communicate resource creation

**Impact:** Medium - Incorrect semantic meaning

**REST Compliant:**
```python
@router.post("/", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(...):
```

**File:** `src/api/v1/providers.py:103`

---

#### Issue #7: Inconsistent Response Formats
**Current:**
```python
# Some endpoints return structured response
{"message": "...", "provider_id": "...", "alias": "..."}

# Some return model responses
ProviderResponse(...)

# Some return simple dict
{"message": "..."}
```

**Problem:**
- No consistent envelope format
- Mix of ad-hoc dicts and Pydantic models
- Makes client integration harder

**Impact:** Medium - Reduces API predictability

**REST Compliant:**
```python
# Always use Pydantic models for responses
class ProviderResponse(BaseModel):
    ...

class MessageResponse(BaseModel):
    message: str

# Or use consistent envelope
class ApiResponse(BaseModel, Generic[T]):
    data: T
    message: Optional[str] = None
```

**Files:**
- `src/api/v1/auth.py` (multiple locations)
- `src/api/v1/providers.py` (multiple locations)

---

### ℹ️ Minor Issues (Nice to Have)

#### Issue #8: Missing Pagination
**Current:**
```python
@router.get("/", response_model=List[ProviderResponse])
async def list_user_providers(...):
    # Returns all providers, no pagination
```

**Problem:**
- Returns unbounded list
- Could cause performance issues with many providers
- No pagination support

**Impact:** Low (currently) - Will become high as data grows

**REST Compliant:**
```python
@router.get("/")
async def list_user_providers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
) -> PaginatedResponse[ProviderResponse]:
    ...
```

**File:** `src/api/v1/providers.py:179`

---

#### Issue #9: No Filtering/Sorting Support
**Current:**
```python
@router.get("/", response_model=List[ProviderResponse])
async def list_user_providers(...):
    # No query parameters for filtering or sorting
```

**Problem:**
- Cannot filter by status, provider_key, etc.
- Cannot sort results
- Limited client flexibility

**Impact:** Low - Quality of life improvement

**REST Compliant:**
```python
@router.get("/")
async def list_user_providers(
    status: Optional[str] = None,
    provider_key: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
):
    ...
```

**File:** `src/api/v1/providers.py:179`

---

#### Issue #10: Missing PATCH Support
**Current:**
```python
# No PATCH endpoint for providers
# Can only DELETE or view
```

**Problem:**
- Cannot update provider alias or other fields
- Forces DELETE + POST for updates

**Impact:** Low - Feature gap, not REST violation

**REST Compliant:**
```python
@router.patch("/{provider_id}")
async def update_provider(
    provider_id: UUID,
    request: UpdateProviderRequest,
    ...
) -> ProviderResponse:
    ...
```

**File:** `src/api/v1/providers.py` (missing)

---

#### Issue #11: GET with Side Effects
**Current:**
```python
@router.get("/{provider_id}/authorize/redirect")
async def redirect_to_authorization(...):
    # GET that performs redirect
    return RedirectResponse(url=result["auth_url"])
```

**Problem:**
- GET should be idempotent and safe (no side effects)
- Redirects are technically side effects (browser navigation)
- Should use POST for actions with side effects

**Impact:** Low - Common pattern in OAuth, but technically not RESTful

**Note:** This is a common OAuth pattern and may be acceptable as a pragmatic exception. However, strictly speaking, initiating an authorization flow should be POST.

**File:** `src/api/v1/auth.py:100-115`

---

#### Issue #12: Singular Resource Path for User
**Current:**
```http
GET   /api/v1/auth/me
PATCH /api/v1/auth/me
```

**Problem:**
- Uses `me` instead of proper resource identifier
- Not strictly RESTful (though common practice)

**Impact:** Low - Common convention, widely accepted

**Alternative (Strictly RESTful):**
```http
GET   /api/v1/users/{user_id}
PATCH /api/v1/users/{user_id}

# Or with implicit current user
GET   /api/v1/users/current
PATCH /api/v1/users/current
```

**Note:** `/me` is a widely accepted convention and is acceptable as a pragmatic shortcut. Consider keeping it unless strict REST compliance is required.

**File:** `src/api/v1/auth_jwt.py:308-382`

---

## Positive Observations ✅

### What's Working Well

1. **Consistent UUID Usage**
   - All resources use UUIDs, not sequential IDs ✅
   - Good for security and scalability

2. **Proper HTTP Methods**
   - GET for retrieval ✅
   - POST for creation ✅
   - DELETE for removal ✅
   - PATCH for updates ✅

3. **Good Error Handling**
   - Returns appropriate 404 for not found ✅
   - Returns 403 for authorization failures ✅
   - Returns 400 for validation errors ✅
   - Returns 409 for conflicts ✅

4. **Authentication**
   - Proper JWT implementation ✅
   - Dependency injection for auth ✅
   - Secure token handling ✅

5. **Versioning**
   - API versioned at `/api/v1` ✅
   - Clean version prefix structure ✅

6. **Response Models**
   - Using Pydantic models for validation ✅
   - Type hints throughout ✅

7. **Security**
   - Authorization checks on all protected endpoints ✅
   - Resource ownership validation ✅

---

## Recommendations

### Priority 1: Critical Fixes (Week 1)

#### 1.1 Fix `/providers/create` Endpoint
```python
# Change URL from /create to /
@router.post("/", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(...):
```

**Effort:** Low (30 minutes)  
**Impact:** High  
**Breaking Change:** Yes - Update client code

---

#### 1.2 Separate OAuth and JWT Auth Routes
```python
# In src/api/v1/__init__.py
api_router.include_router(auth_jwt_router, prefix="/auth", tags=["authentication"])
api_router.include_router(providers_router, prefix="/providers", tags=["providers"])

# Move OAuth endpoints to provider sub-resources
# /api/v1/providers/{id}/connection
```

**Effort:** Medium (4 hours)  
**Impact:** High  
**Breaking Change:** Yes - Significant URL restructure

---

#### 1.3 Separate Provider Types from Provider Instances
```python
# New endpoints structure
GET /api/v1/provider-types              # Catalog of available types
GET /api/v1/provider-types/{key}        # Specific type info

GET /api/v1/providers                   # User's provider instances
POST /api/v1/providers                  # Create instance
```

**Effort:** Medium (3 hours)  
**Impact:** High  
**Breaking Change:** Yes - URL changes

---

### Priority 2: Important Improvements (Week 2)

#### 2.1 Redesign OAuth Flow as Resource
```python
# Treat connection/authorization as a resource

# Initiate authorization (returns auth URL)
POST /api/v1/providers/{id}/authorization
# Response: {"auth_url": "...", "state": "..."}

# OAuth callback
GET /api/v1/providers/{id}/authorization/callback?code=...&state=...

# Check connection status
GET /api/v1/providers/{id}/authorization
# Response: {"status": "connected", "expires_at": "...", ...}

# Refresh connection
PATCH /api/v1/providers/{id}/authorization
# Triggers token refresh

# Disconnect
DELETE /api/v1/providers/{id}/authorization
```

**Effort:** High (8 hours)  
**Impact:** High  
**Breaking Change:** Yes - Complete OAuth flow redesign

---

#### 2.2 Redesign Password Reset as Resource
```python
# Request password reset
POST /api/v1/password-resets
Body: {"email": "user@example.com"}
Response: 202 Accepted

# Verify token (optional, check if valid)
GET /api/v1/password-resets/{token}

# Complete password reset
PATCH /api/v1/password-resets/{token}
Body: {"new_password": "..."}
Response: 200 OK
```

**Effort:** Medium (3 hours)  
**Impact:** Medium  
**Breaking Change:** Yes - URL changes

---

#### 2.3 Add Pagination to List Endpoints
```python
@router.get("/", response_model=PaginatedResponse[ProviderResponse])
async def list_providers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    ...
):
```

**Effort:** Medium (2 hours)  
**Impact:** Medium  
**Breaking Change:** Yes - Response format changes

---

### Priority 3: Enhancements (Week 3+)

#### 3.1 Add Provider Update Endpoint
```python
@router.patch("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    request: UpdateProviderRequest,
    ...
):
```

**Effort:** Low (1 hour)  
**Impact:** Low  
**Breaking Change:** No - New endpoint

---

#### 3.2 Add Filtering and Sorting
```python
@router.get("/")
async def list_providers(
    status: Optional[str] = None,
    provider_key: Optional[str] = None,
    search: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
):
```

**Effort:** Medium (3 hours)  
**Impact:** Low  
**Breaking Change:** No - Backward compatible

---

#### 3.3 Standardize Response Envelopes
```python
# Define standard response wrapper
class ApiResponse(BaseModel, Generic[T]):
    data: T
    meta: Optional[Dict[str, Any]] = None

# Or keep flat responses but ensure consistency
# All responses should be Pydantic models, not dicts
```

**Effort:** High (6 hours)  
**Impact:** Medium  
**Breaking Change:** Depends on approach

---

## Implementation Roadmap

### Phase 1: Quick Wins (Week 1) - Non-Breaking
- ✅ Add 201 status code to create endpoints
- ✅ Add pagination support (backward compatible)
- ✅ Add PATCH endpoint for provider updates
- ✅ Add filtering/sorting support

**Breaking Changes:** None  
**Client Updates:** Optional (can benefit from new features)

---

### Phase 2: URL Cleanup (Week 2) - Breaking Changes
- ⚠️ Change `/providers/create` to POST `/providers`
- ⚠️ Separate `/provider-types` from `/providers`
- ⚠️ Update tests

**Breaking Changes:** Yes  
**Client Updates:** Required  
**Version:** Keep v1, document deprecations

---

### Phase 3: Major Refactor (Week 3-4) - Breaking Changes
- ⚠️ Redesign OAuth flow as connection resource
- ⚠️ Separate OAuth routes from JWT auth routes
- ⚠️ Redesign password reset flow
- ⚠️ Update all tests
- ⚠️ Update documentation

**Breaking Changes:** Yes  
**Client Updates:** Required  
**Version:** Consider v2 API

---

### Phase 4: Polish (Ongoing)
- Standardize response formats
- Add comprehensive OpenAPI documentation
- Add rate limiting headers
- Add HATEOAS links (optional)
- Performance optimization

---

## Migration Strategy

### Option 1: Gradual Migration (Recommended)
1. **Keep existing v1 endpoints** - Don't break anything
2. **Add v2 endpoints** with REST compliance
3. **Deprecate v1** with 6-month notice
4. **Remove v1** after deprecation period

**Pros:**
- No immediate breaking changes
- Smooth transition period
- Clients can migrate at their own pace

**Cons:**
- Maintain two API versions temporarily
- More code to maintain

---

### Option 2: In-Place Updates
1. **Announce breaking changes** with release notes
2. **Update all endpoints** at once in v1
3. **Bump to v1.1** or v2.0
4. **Provide migration guide**

**Pros:**
- Single codebase
- Faster cleanup
- Forces clients to update

**Cons:**
- Breaking change for all clients
- Requires coordinated deployment
- Higher risk

---

### Option 3: Feature Flags
1. **Add feature flags** for new vs old behavior
2. **Deploy both versions** behind flags
3. **Gradually migrate clients**
4. **Remove old code** when done

**Pros:**
- Can test both versions
- Rollback capability
- Gradual migration

**Cons:**
- Complex codebase temporarily
- More testing required

---

## Proposed New API Structure (v2)

### Authentication
```http
# User authentication
POST   /api/v2/auth/register
POST   /api/v2/auth/login
POST   /api/v2/auth/refresh
POST   /api/v2/auth/logout
GET    /api/v2/auth/me
PATCH  /api/v2/auth/me

# Email verification
POST   /api/v2/email-verifications
GET    /api/v2/email-verifications/{token}

# Password resets
POST   /api/v2/password-resets
GET    /api/v2/password-resets/{token}
PATCH  /api/v2/password-resets/{token}
```

### Provider Types (Catalog)
```http
GET    /api/v2/provider-types
GET    /api/v2/provider-types/{key}
```

### Provider Instances
```http
# CRUD operations
GET    /api/v2/providers
POST   /api/v2/providers
GET    /api/v2/providers/{id}
PATCH  /api/v2/providers/{id}
DELETE /api/v2/providers/{id}

# Connection/Authorization (OAuth flow)
POST   /api/v2/providers/{id}/authorization
GET    /api/v2/providers/{id}/authorization
GET    /api/v2/providers/{id}/authorization/callback
PATCH  /api/v2/providers/{id}/authorization
DELETE /api/v2/providers/{id}/authorization

# Or alternative naming
POST   /api/v2/providers/{id}/connection
GET    /api/v2/providers/{id}/connection
PATCH  /api/v2/providers/{id}/connection
DELETE /api/v2/providers/{id}/connection
```

### Health & Monitoring
```http
GET    /api/v2/health
GET    /health
GET    /
```

---

## Testing Requirements

### Before Refactoring
- ✅ Comprehensive test coverage exists for current endpoints
- ✅ Document current API behavior
- ✅ Create baseline performance metrics

### During Refactoring
- ⚠️ Update tests for each changed endpoint
- ⚠️ Add tests for new REST features (pagination, filtering, etc.)
- ⚠️ Ensure backward compatibility tests pass (if gradual migration)

### After Refactoring
- ✅ 100% test coverage on refactored endpoints
- ✅ Integration tests for full workflows
- ✅ Performance regression tests
- ✅ API contract tests

---

## Documentation Updates Required

1. **OpenAPI/Swagger Spec**
   - Update all endpoint descriptions
   - Add response examples
   - Document query parameters
   - Add error response schemas

2. **Migration Guide**
   - Old → New endpoint mapping
   - Code examples for each change
   - Timeline and deprecation notices

3. **API Reference**
   - Update quick reference guide
   - Update architecture documentation
   - Add troubleshooting section

4. **Client SDKs**
   - Update SDK generators
   - Version SDK libraries
   - Update SDK documentation

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing clients | High | High | Gradual migration with v2 |
| Incomplete migration | Medium | High | Comprehensive test coverage |
| Performance regression | Low | Medium | Load testing before release |
| Security vulnerabilities | Low | High | Security audit of changes |
| Database migration issues | Low | Medium | OAuth changes don't affect DB |
| Documentation lag | High | Medium | Update docs with code changes |

---

## Success Metrics

### Code Quality
- [ ] REST compliance score > 9/10
- [ ] Test coverage > 90%
- [ ] Zero critical linting errors
- [ ] All endpoints follow consistent patterns

### Performance
- [ ] Response times < 200ms (p95)
- [ ] Support 1000+ req/sec
- [ ] Database query count optimized

### Developer Experience
- [ ] OpenAPI spec 100% accurate
- [ ] All endpoints have examples
- [ ] Migration guide complete
- [ ] Client SDKs updated

---

## Next Steps

### Immediate Actions (This Week)
1. ✅ Review this document with team
2. ⏳ Decide on migration strategy (Option 1, 2, or 3)
3. ⏳ Prioritize fixes based on business impact
4. ⏳ Create GitHub issues for each fix
5. ⏳ Set timeline for implementation

### Short Term (Next 2 Weeks)
1. ⏳ Implement Priority 1 fixes
2. ⏳ Update test suite
3. ⏳ Update documentation
4. ⏳ Announce changes to clients

### Long Term (Next Month)
1. ⏳ Complete all priority 2 fixes
2. ⏳ Plan v2 API if needed
3. ⏳ Deprecate old endpoints
4. ⏳ Monitor adoption metrics

---

## Appendix: REST Compliance Checklist

Use this checklist to verify REST compliance for any endpoint:

### URL Design
- [ ] Uses nouns, not verbs
- [ ] Uses plural nouns for collections
- [ ] Uses hierarchical structure for relationships
- [ ] Uses kebab-case for multi-word resources
- [ ] No trailing slashes
- [ ] Doesn't expose implementation details

### HTTP Methods
- [ ] GET for retrieval (safe, idempotent)
- [ ] POST for creation (not idempotent)
- [ ] PUT for full replacement (idempotent)
- [ ] PATCH for partial update
- [ ] DELETE for removal (idempotent)

### Status Codes
- [ ] 200 OK for successful GET/PUT/PATCH
- [ ] 201 Created for successful POST
- [ ] 204 No Content for successful DELETE
- [ ] 400 Bad Request for validation errors
- [ ] 401 Unauthorized for auth failures
- [ ] 403 Forbidden for permission denials
- [ ] 404 Not Found for missing resources
- [ ] 409 Conflict for duplicate resources

### Request/Response
- [ ] JSON for request/response bodies
- [ ] Consistent field naming (snake_case)
- [ ] Proper content-type headers
- [ ] Pagination for collections
- [ ] Filtering via query parameters
- [ ] Sorting via query parameters

### Error Handling
- [ ] Consistent error response format
- [ ] Descriptive error messages
- [ ] Error codes when appropriate
- [ ] Validation errors with field details

### Documentation
- [ ] OpenAPI/Swagger documentation
- [ ] Request/response examples
- [ ] Error response examples
- [ ] Authentication requirements clear

---

## References

- [RESTful API Design Guide](./restful-api-design.md)
- [RESTful API Quick Reference](../guides/restful-api-quick-reference.md)
- [RFC 7231 - HTTP/1.1 Semantics](https://tools.ietf.org/html/rfc7231)
- [RFC 6749 - OAuth 2.0](https://tools.ietf.org/html/rfc6749)
- [REST API Tutorial](https://restfulapi.net)

---

**Document Version**: 1.0  
**Last Updated**: 2025-10-04  
**Next Review**: 2025-11-04
