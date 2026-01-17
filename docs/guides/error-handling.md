# Error Handling Guide

**Purpose**: Comprehensive guide to RFC 9457 Problem Details error handling in Dashtam API.

**Audience**: Backend developers, API consumers, frontend developers.

## Overview

Dashtam uses **RFC 9457 Problem Details** as the standard error format across all API endpoints. This provides consistent, machine-readable error responses with structured metadata for debugging and user-facing error messages.

**Key Benefits**:

- **Consistent format**: All errors follow the same structure
- **Machine-readable**: Clients can parse errors programmatically
- **Debuggable**: Includes trace IDs for correlation with logs
- **User-friendly**: Structured field-level errors for form validation
- **Standards-compliant**: Follows IETF RFC 9457 specification

## RFC 9457 Problem Details Standard

RFC 9457 defines a standard JSON format for HTTP API errors. Every error response is a JSON object with these fields:

```json
{
  "type": "https://api.dashtam.com/errors/validation_failed",
  "title": "Validation Failed",
  "status": 400,
  "detail": "Request validation failed. Check 'errors' for details.",
  "instance": "/api/v1/users",
  "errors": [
    {
      "field": "email",
      "message": "Invalid email format",
      "code": "invalid_format"
    }
  ],
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Field Definitions

#### `type` (string, required)

**URL identifying the error type**. Provides machine-readable error classification.

**Format**: `https://api.dashtam.com/errors/{error_code}`

**Examples**:

- `https://api.dashtam.com/errors/not_found`
- `https://api.dashtam.com/errors/unauthorized`
- `https://api.dashtam.com/errors/validation_failed`

**Usage**: Clients should match on `type` URL for error handling logic (NOT on status codes).

#### `title` (string, required)

**Human-readable summary** of the error type. Same for all occurrences of this error type.

**Examples**:

- `"Resource Not Found"`
- `"Authentication Required"`
- `"Validation Failed"`

**Usage**: Display to users or use in logs. Consistent per error type.

#### `status` (integer, required)

**HTTP status code** for this error. Duplicates the HTTP response status for convenience.

**Examples**: `400`, `401`, `403`, `404`, `409`, `422`, `429`, `500`

#### `detail` (string, optional)

**Human-readable explanation** specific to this error occurrence. May include variable data.

**Examples**:

- `"User with email 'user@example.com' not found"`
- `"Access token expired at 2025-12-31T10:00:00Z"`
- `"Request validation failed. Check 'errors' for details."`

**Usage**: Display to users or include in error logs. Context-specific.

#### `instance` (string, optional)

**URI reference** identifying the specific occurrence. Usually the request path.

**Examples**:

- `"/api/v1/users/123"`
- `"/api/v1/sessions"`
- `"/api/v1/providers/schwab/callback"`

**Usage**: Correlate errors with specific API calls in logs.

#### `errors` (array, optional)

**Field-level validation errors**. Used for form validation failures.

Each error object contains:

- `field` (string): Field name that failed validation
- `message` (string): Human-readable error message
- `code` (string, optional): Machine-readable error code

**Example**:

```json
"errors": [
  {
    "field": "email",
    "message": "Invalid email format",
    "code": "invalid_format"
  },
  {
    "field": "password",
    "message": "Password must be at least 12 characters",
    "code": "min_length"
  }
]
```

**Usage**: Display field-specific errors next to form inputs.

#### `trace_id` (string, required)

**Unique identifier** for this error occurrence. Links error response to backend logs.

**Format**: UUID v4 (e.g., `550e8400-e29b-41d4-a716-446655440000`)

**Usage**: Include in support tickets. Search logs by trace_id to debug.

## ProblemDetails Schema

Dashtam defines the error schema in `src/schemas/error_schemas.py`:

```python
class FieldError(BaseModel):
    """Field-level validation error."""
    field: str
    message: str
    code: str | None = None

class ProblemDetails(BaseModel):
    """RFC 9457 Problem Details error response."""
    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[FieldError] | None = None
    trace_id: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "https://api.dashtam.com/errors/validation_failed",
                "title": "Validation Failed",
                "status": 400,
                "detail": "Request validation failed",
                "instance": "/api/v1/users",
                "errors": [
                    {"field": "email", "message": "Invalid format", "code": "invalid_format"}
                ],
                "trace_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    )
```

## ErrorResponseBuilder Usage

`ErrorResponseBuilder` is the primary interface for creating RFC 9457 error responses.

### Basic Usage

```python
from src.core.errors import ApplicationError, ApplicationErrorCode
from src.presentation.api.error_response_builder import ErrorResponseBuilder

# Create error from ApplicationError
error = ApplicationError(
    code=ApplicationErrorCode.NOT_FOUND,
    message="User not found",
    details={"user_id": "123"}
)

response = ErrorResponseBuilder.from_application_error(
    error=error,
    request_path="/api/v1/users/123"
)

# Returns JSONResponse with ProblemDetails body
return response
```

### With Field-Level Errors

```python
from src.schemas.error_schemas import FieldError

# Validation failure with field-level errors
error = ApplicationError(
    code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
    message="Request validation failed"
)

response = ErrorResponseBuilder.from_application_error(
    error=error,
    request_path="/api/v1/users",
    field_errors=[
        FieldError(field="email", message="Invalid email format", code="invalid_format"),
        FieldError(field="password", message="Too short", code="min_length")
    ]
)

return response
```

### With Custom Detail

```python
# Not found with specific detail
error = ApplicationError(
    code=ApplicationErrorCode.NOT_FOUND,
    message=f"User with email '{email}' not found"
)

response = ErrorResponseBuilder.from_application_error(
    error=error,
    request_path="/api/v1/users"
)

return response
```

## ApplicationErrorCode Reference

`ApplicationErrorCode` enum maps error types to HTTP status codes and RFC 9457 metadata.

Defined in `src/core/errors/application_error.py`:

```python
class ApplicationErrorCode(str, Enum):
    """Application-level error codes."""
    
    # 400 Bad Request
    COMMAND_VALIDATION_FAILED = "command_validation_failed"
    QUERY_VALIDATION_FAILED = "query_validation_failed"
    INVALID_REQUEST = "invalid_request"
    
    # 401 Unauthorized
    UNAUTHORIZED = "unauthorized"
    INVALID_CREDENTIALS = "invalid_credentials"
    TOKEN_EXPIRED = "token_expired"
    
    # 403 Forbidden
    FORBIDDEN = "forbidden"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    
    # 404 Not Found
    NOT_FOUND = "not_found"
    
    # 409 Conflict
    CONFLICT = "conflict"
    DUPLICATE_RESOURCE = "duplicate_resource"
    
    # 422 Unprocessable Entity
    BUSINESS_RULE_VIOLATION = "business_rule_violation"
    
    # 429 Too Many Requests
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    
    # 500 Internal Server Error
    INTERNAL_ERROR = "internal_error"
    EXTERNAL_SERVICE_ERROR = "external_service_error"
```

### HTTP Status Mapping

| ApplicationErrorCode | HTTP Status | Title |
|---------------------|-------------|-------|
| `COMMAND_VALIDATION_FAILED` | 400 | Validation Failed |
| `QUERY_VALIDATION_FAILED` | 400 | Validation Failed |
| `INVALID_REQUEST` | 400 | Bad Request |
| `UNAUTHORIZED` | 401 | Authentication Required |
| `INVALID_CREDENTIALS` | 401 | Authentication Required |
| `TOKEN_EXPIRED` | 401 | Authentication Required |
| `FORBIDDEN` | 403 | Access Denied |
| `INSUFFICIENT_PERMISSIONS` | 403 | Access Denied |
| `NOT_FOUND` | 404 | Resource Not Found |
| `CONFLICT` | 409 | Resource Conflict |
| `DUPLICATE_RESOURCE` | 409 | Resource Conflict |
| `BUSINESS_RULE_VIOLATION` | 422 | Business Rule Violation |
| `RATE_LIMIT_EXCEEDED` | 429 | Too Many Requests |
| `INTERNAL_ERROR` | 500 | Internal Server Error |
| `EXTERNAL_SERVICE_ERROR` | 500 | Internal Server Error |

## When to Use Field-Level Errors

Use the `errors` array for **form validation failures** where multiple fields may have errors.

### ✅ Use Field-Level Errors For

- User registration form validation
- Profile update validation
- Multi-field search filters
- Bulk operation validation

**Example**:

```json
{
  "type": "https://api.dashtam.com/errors/validation_failed",
  "title": "Validation Failed",
  "status": 400,
  "detail": "User registration failed validation",
  "instance": "/api/v1/users",
  "errors": [
    {"field": "email", "message": "Invalid email format", "code": "invalid_format"},
    {"field": "password", "message": "Password too short", "code": "min_length"},
    {"field": "terms", "message": "Must accept terms", "code": "required"}
  ],
  "trace_id": "..."
}
```

### ❌ Don't Use Field-Level Errors For

- Single resource not found (use `detail` instead)
- Authentication failures (no fields to report)
- Permission denials (not field-related)
- Rate limit exceeded (not field-related)

**Example** (correct - no field errors):

```json
{
  "type": "https://api.dashtam.com/errors/not_found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "User with ID '123' not found",
  "instance": "/api/v1/users/123",
  "trace_id": "..."
}
```

## Common Error Scenarios

### 1. Validation Error (400)

**Scenario**: User submits invalid form data.

**Request**:

```http
POST /api/v1/users
Content-Type: application/json

{
  "email": "invalid-email",
  "password": "short"
}
```

**Response**:

```http
HTTP/1.1 400 Bad Request
Content-Type: application/problem+json

{
  "type": "https://api.dashtam.com/errors/command_validation_failed",
  "title": "Validation Failed",
  "status": 400,
  "detail": "User registration validation failed",
  "instance": "/api/v1/users",
  "errors": [
    {"field": "email", "message": "Invalid email format", "code": "invalid_format"},
    {"field": "password", "message": "Must be at least 12 characters", "code": "min_length"}
  ],
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 2. Authentication Required (401)

**Scenario**: User attempts to access protected resource without valid token.

**Request**:

```http
GET /api/v1/accounts
Authorization: Bearer invalid-token
```

**Response**:

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/problem+json

{
  "type": "https://api.dashtam.com/errors/unauthorized",
  "title": "Authentication Required",
  "status": 401,
  "detail": "Invalid or expired access token",
  "instance": "/api/v1/accounts",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 3. Access Denied (403)

**Scenario**: User authenticated but lacks permission.

**Request**:

```http
DELETE /api/v1/users/456
Authorization: Bearer valid-token-for-user-123
```

**Response**:

```http
HTTP/1.1 403 Forbidden
Content-Type: application/problem+json

{
  "type": "https://api.dashtam.com/errors/forbidden",
  "title": "Access Denied",
  "status": 403,
  "detail": "You do not have permission to delete this user",
  "instance": "/api/v1/users/456",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 4. Resource Not Found (404)

**Scenario**: Requested resource does not exist.

**Request**:

```http
GET /api/v1/accounts/99999
Authorization: Bearer valid-token
```

**Response**:

```http
HTTP/1.1 404 Not Found
Content-Type: application/problem+json

{
  "type": "https://api.dashtam.com/errors/not_found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "Account with ID '99999' not found",
  "instance": "/api/v1/accounts/99999",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 5. Resource Conflict (409)

**Scenario**: User attempts to create resource that already exists.

**Request**:

```http
POST /api/v1/users
Content-Type: application/json

{
  "email": "existing@example.com",
  "password": "ValidPassword123!"
}
```

**Response**:

```http
HTTP/1.1 409 Conflict
Content-Type: application/problem+json

{
  "type": "https://api.dashtam.com/errors/conflict",
  "title": "Resource Conflict",
  "status": 409,
  "detail": "User with email 'existing@example.com' already exists",
  "instance": "/api/v1/users",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 6. Rate Limit Exceeded (429)

**Scenario**: User exceeds rate limit for endpoint.

**Request**:

```http
POST /api/v1/sessions
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

**Response**:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/problem+json
Retry-After: 60
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1735689600

{
  "type": "https://api.dashtam.com/errors/rate_limit_exceeded",
  "title": "Too Many Requests",
  "status": 429,
  "detail": "Rate limit exceeded. Try again in 60 seconds.",
  "instance": "/api/v1/sessions",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Client Error Handling Examples

### TypeScript/JavaScript

```typescript
interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  errors?: Array<{
    field: string;
    message: string;
    code?: string;
  }>;
  trace_id: string;
}

async function createUser(email: string, password: string) {
  try {
    const response = await fetch('/api/v1/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
      const error: ProblemDetails = await response.json();
      
      // Handle by error type (NOT status code)
      if (error.type.endsWith('/validation_failed')) {
        // Display field-level errors
        error.errors?.forEach(err => {
          showFieldError(err.field, err.message);
        });
      } else if (error.type.endsWith('/conflict')) {
        showMessage('User already exists');
      } else {
        // Generic error with trace ID
        showMessage(`Error: ${error.detail} (Trace: ${error.trace_id})`);
      }
      
      throw error;
    }

    return await response.json();
  } catch (error) {
    console.error('Request failed:', error);
    throw error;
  }
}
```

### Python Client

```python
import requests
from typing import Optional
from dataclasses import dataclass

@dataclass
class FieldError:
    field: str
    message: str
    code: Optional[str] = None

@dataclass
class ProblemDetails:
    type: str
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None
    errors: Optional[list[FieldError]] = None
    trace_id: str

def create_user(email: str, password: str):
    response = requests.post(
        'https://api.dashtam.com/api/v1/users',
        json={'email': email, 'password': password}
    )
    
    if not response.ok:
        error_data = response.json()
        
        # Parse into ProblemDetails
        problem = ProblemDetails(
            type=error_data['type'],
            title=error_data['title'],
            status=error_data['status'],
            detail=error_data.get('detail'),
            instance=error_data.get('instance'),
            errors=[
                FieldError(**e) for e in error_data.get('errors', [])
            ],
            trace_id=error_data['trace_id']
        )
        
        # Handle by error type
        if problem.type.endswith('/validation_failed'):
            for err in problem.errors or []:
                print(f"Field '{err.field}': {err.message}")
        elif problem.type.endswith('/conflict'):
            print("User already exists")
        else:
            print(f"Error: {problem.detail} (Trace: {problem.trace_id})")
        
        raise Exception(problem)
    
    return response.json()
```

## Debugging with trace_id

Every error response includes a `trace_id` that uniquely identifies the error occurrence. This links the error response to backend logs.

### User Reports Error

**User sees**:

```json
{
  "type": "https://api.dashtam.com/errors/internal_error",
  "title": "Internal Server Error",
  "status": 500,
  "detail": "An unexpected error occurred",
  "instance": "/api/v1/accounts/sync",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Developer Searches Logs

Search application logs for `trace_id`:

```bash
# CloudWatch Logs query
fields @timestamp, @message
| filter trace_id = "550e8400-e29b-41d4-a716-446655440000"
| sort @timestamp desc
```

**Logs reveal**:

```json
{
  "timestamp": "2025-12-31T21:30:00Z",
  "level": "ERROR",
  "message": "Account sync failed",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "error": "ConnectionTimeout: schwab.api.com timeout after 30s",
  "user_id": "123",
  "provider": "schwab"
}
```

**Result**: Developer identifies root cause (Schwab API timeout) and can investigate further or apply fix.

## Migration from AuthErrorResponse

**Breaking Change in v1.6.3**: `AuthErrorResponse` removed, replaced with RFC 9457 `ProblemDetails`.

### Old Format (Deprecated)

```json
{
  "error": "unauthorized",
  "message": "Invalid access token"
}
```

### New Format (RFC 9457)

```json
{
  "type": "https://api.dashtam.com/errors/unauthorized",
  "title": "Authentication Required",
  "status": 401,
  "detail": "Invalid access token",
  "instance": "/api/v1/accounts",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Migration Checklist

1. ✅ Update client error parsing to expect `ProblemDetails` format
2. ✅ Match on `type` URL instead of `error` string
3. ✅ Extract field errors from `errors` array (not root level)
4. ✅ Store/display `trace_id` for support tickets
5. ✅ Update error handling tests to assert `ProblemDetails` schema

## Result Types (Railway-Oriented Programming)

Dashtam uses **Result types** for explicit error handling across all layers. Domain functions return `Result[T, Error]` instead of raising exceptions.

**Architecture Flow**: Domain → Application → Presentation

- **Domain**: Returns `Result[T, DomainError]` (NO exceptions)
- **Application**: Wraps domain errors in `ApplicationError`
- **Presentation**: Converts to RFC 9457 `ProblemDetails` JSON

### Domain Layer Patterns

#### ValidationError (Field-Specific)

```python
from src.core.result import Result, Success, Failure
from src.core.errors import ValidationError
from src.core.enums import ErrorCode

# ✅ CORRECT: Return Failure with ValidationError
def validate_password(password: str) -> Result[str, ValidationError]:
    if len(password) < 12:
        return Failure(ValidationError(
            code=ErrorCode.PASSWORD_TOO_WEAK,
            message="Password must be at least 12 characters",
            field="password",
        ))
    return Success(password)

# ❌ WRONG: Don't raise exceptions in domain
def validate_password_wrong(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password too weak")  # NO!
    return password
```

#### NotFoundError (Resource Missing)

```python
from src.core.errors import NotFoundError

async def find_user(user_id: UUID) -> Result[User, NotFoundError]:
    user = await self.users.find_by_id(user_id)
    
    if not user:
        return Failure(NotFoundError(
            code=ErrorCode.USER_NOT_FOUND,
            message=f"User with ID '{user_id}' does not exist",
            resource_type="User",
            resource_id=str(user_id),
        ))
    
    return Success(user)
```

#### ConflictError (Duplicate Resource)

```python
from src.core.errors import ConflictError

async def register_user(email: str) -> Result[User, ConflictError]:
    existing = await self.users.find_by_email(email)
    
    if existing:
        return Failure(ConflictError(
            code=ErrorCode.EMAIL_ALREADY_EXISTS,
            message=f"User with email '{email}' already exists",
            resource_type="User",
            conflicting_field="email",
        ))
    
    user = User(email=email)
    return Success(user)
```

### Application Layer Patterns

#### Command Handler Error Mapping

```python
from src.core.errors import ApplicationError, ApplicationErrorCode

class RegisterUserHandler:
    async def handle(self, cmd: RegisterUserCommand) -> Result[UUID, ApplicationError]:
        """Register new user with error mapping."""
        result = await self.user_service.register_user(cmd.email, cmd.password)
        
        # Handle failure case first (isinstance pattern for kw_only dataclasses)
        if isinstance(result, Failure):
            err = result.error
            if isinstance(err, ValidationError):
                return Failure(error=ApplicationError(
                    code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
                    message=f"Registration failed: {err.message}",
                    domain_error=err,
                    details={"field": err.field},
                ))
            if isinstance(err, ConflictError):
                return Failure(error=ApplicationError(
                    code=ApplicationErrorCode.CONFLICT,
                    message="Registration failed: email already exists",
                    domain_error=err,
                ))
        
        # Success case
        user = result.value
        await self.event_bus.publish(UserRegistered(user_id=user.id))
        return Success(value=user.id)
```

#### Query Handler Error Mapping

```python
class GetUserHandler:
    async def handle(self, query: GetUser) -> Result[UserDTO, ApplicationError]:
        """Get user with error mapping."""
        result = await self.users.find_by_id(query.user_id)
        
        if isinstance(result, Failure):
            return Failure(error=ApplicationError(
                code=ApplicationErrorCode.NOT_FOUND,
                message=f"User not found: {result.error.message}",
                domain_error=result.error,
            ))
        
        return Success(value=UserDTO.from_entity(result.value))
```

### Presentation Layer Patterns

Routers dispatch to handlers and convert results to HTTP responses:

```python
from fastapi import APIRouter, Request, Depends
from src.presentation.api.error_response_builder import ErrorResponseBuilder

@router.post("/users", status_code=201)
async def create_user(
    data: UserCreateRequest,
    request: Request,
    handler: RegisterUserHandler = Depends(get_register_handler),
):
    """Create new user."""
    result = await handler.handle(RegisterUserCommand(email=data.email))
    
    if isinstance(result, Failure):
        return ErrorResponseBuilder.from_application_error(
            error=result.error,
            request_path=str(request.url.path),
        )
    
    return {"id": str(result.value), "email": data.email}
```

## Anti-Patterns (What NOT to Do)

### ❌ Don't Raise Exceptions in Domain

```python
# ❌ WRONG
def create_user(email: str) -> User:
    if not is_valid_email(email):
        raise ValueError("Invalid email")  # NO!
    return User(email=email)

# ✅ CORRECT
def create_user(email: str) -> Result[User, ValidationError]:
    if not is_valid_email(email):
        return Failure(ValidationError(...))
    return Success(User(email=email))
```

### ❌ Don't Use Try-Except for Business Logic

```python
# ❌ WRONG
try:
    user = create_user(email)
    return {"id": user.id}
except ValueError as e:
    return {"error": str(e)}  # NO!

# ✅ CORRECT
result = create_user(email)
if isinstance(result, Failure):
    return ErrorResponseBuilder.from_application_error(...)
return {"id": result.value.id}
```

### ❌ Don't Inline Error Responses

```python
# ❌ WRONG
@router.post("/users")
async def create_user(data: dict):
    if not data.get("email"):
        return {"error": "Email required"}, 400  # NO!

# ✅ CORRECT: Use ErrorResponseBuilder
@router.post("/users")
async def create_user(request: Request, handler=Depends()):
    result = await handler.handle(...)
    if isinstance(result, Failure):
        return ErrorResponseBuilder.from_application_error(...)
```

## Testing Error Paths

### Unit Tests (Domain Layer)

```python
def test_validation_error():
    """Test validation returns Failure."""
    result = create_user(email="invalid-email")
    
    assert isinstance(result, Failure)
    err = result.error
    assert isinstance(err, ValidationError)
    assert err.code == ErrorCode.INVALID_EMAIL
    assert err.field == "email"
```

### Integration Tests (Application Layer)

```python
async def test_command_handler_error_mapping():
    """Test handler maps domain errors to application errors."""
    handler = RegisterUserHandler(...)
    result = await handler.handle(RegisterUserCommand(email="invalid"))
    
    assert isinstance(result, Failure)
    err = result.error
    assert isinstance(err, ApplicationError)
    assert err.code == ApplicationErrorCode.COMMAND_VALIDATION_FAILED
    assert err.domain_error is not None
```

### API Tests (Presentation Layer)

```python
def test_api_returns_rfc7807(client):
    """Test API endpoint returns RFC 9457 response."""
    response = client.post("/api/v1/users", json={"email": "invalid"})
    
    assert response.status_code == 400
    data = response.json()
    assert data["type"].endswith("/errors/command_validation_failed")
    assert data["title"] == "Validation Failed"
    assert "errors" in data
    assert "trace_id" in data
```

## Best Practices

### For Backend Developers

1. **Always use Result types in domain layer** - No exceptions for business logic
2. **Map domain errors to application errors** - Add application context
3. **Use ErrorResponseBuilder for all API errors** - Consistent RFC 9457 format
4. **Choose appropriate ApplicationErrorCode** - Maps to correct HTTP status + RFC 9457 metadata
5. **Include contextual detail** - Help users understand what went wrong
6. **Add field errors for validation** - Use `errors` array for multi-field validation
7. **Never expose internal errors** - Map exceptions to generic INTERNAL_ERROR with trace_id
8. **Test error paths thoroughly** - Error handling is critical functionality
9. **Use isinstance() checks** - For kw_only dataclass Result types

### For API Consumers

1. **Match on `type` URL** - NOT on status codes (multiple error types can share status)
2. **Display field errors inline** - Show validation errors next to form fields
3. **Include trace_id in bug reports** - Essential for backend debugging
4. **Handle rate limits gracefully** - Respect `Retry-After` header
5. **Show user-friendly messages** - Use `detail` for user-facing error messages

## References

- **RFC 9457 Specification**: <https://tools.ietf.org/html/rfc7807>
- **Source Code**: `src/schemas/error_schemas.py`, `src/presentation/api/error_response_builder.py`
- **Route Metadata Registry**: `src/presentation/routers/api/v1/routes/registry.py` (error specs per endpoint)
- **Application Errors**: `src/core/errors/application_error.py`
- **Result Types**: `src/core/result.py`

---

**Created**: 2025-12-31 | **Last Updated**: 2026-01-10
