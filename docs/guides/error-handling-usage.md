# Error Handling Usage Guide

Practical guide for using Dashtam's RFC 7807-compliant error handling system.

## Overview

Dashtam uses **Result types** (railway-oriented programming) for explicit error handling across all layers, with RFC 7807 Problem Details for HTTP responses.

**Architecture**: Domain → Application → Presentation

- **Domain**: Returns `Result[T, DomainError]` (NO exceptions)
- **Application**: Wraps domain errors in `ApplicationError`
- **Presentation**: Converts to RFC 7807 `ProblemDetails` JSON

---

## Quick Start

### Domain Layer: Return Results, Not Exceptions

```python
from src.core.result import Result, Success, Failure
from src.core.enums import ErrorCode
from src.core.errors import ValidationError

def create_user(email: str) -> Result[User, ValidationError]:
    """Create user with validation."""
    if not is_valid_email(email):
        return Failure(ValidationError(
            code=ErrorCode.INVALID_EMAIL,
            message="Email address format is invalid",
            field="email",
        ))
    
    user = User(email=email)
    return Success(user)
```

### Application Layer: Wrap Domain Errors

```python
from src.core.result import Result, Success, Failure
from src.application.errors import ApplicationError, ApplicationErrorCode

class CreateUserHandler:
    async def handle(self, cmd: CreateUserCommand) -> Result[UUID, ApplicationError]:
        """Handle user creation."""
        result = await self.user_service.create_user(cmd.email)
        
        match result:
            case Success(user):
                return Success(user.id)
            
            case Failure(ValidationError() as err):
                return Failure(ApplicationError(
                    code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
                    message="User creation failed: validation error",
                    domain_error=err,
                ))
```

### Presentation Layer: Convert to RFC 7807

```python
from fastapi import APIRouter, Request, Depends
from src.presentation.api.v1.errors import ErrorResponseBuilder

@router.post("/users", status_code=201)
async def create_user(
    data: UserCreateRequest,
    request: Request,
    handler: CreateUserHandler = Depends(),
    trace_id: str = Depends(get_trace_id),
):
    """Create new user."""
    result = await handler.handle(CreateUserCommand(email=data.email))
    
    match result:
        case Success(user_id):
            return {"id": str(user_id), "email": data.email}
        
        case Failure(error):
            return ErrorResponseBuilder.from_application_error(
                error=error,
                request=request,
                trace_id=trace_id,
            )
```

**Result**: RFC 7807 JSON response

```json
{
  "type": "https://api.dashtam.com/errors/command_validation_failed",
  "title": "Validation Failed",
  "status": 400,
  "detail": "User creation failed: validation error",
  "instance": "/api/v1/users",
  "errors": [
    {
      "field": "email",
      "code": "invalid_email",
      "message": "Email address format is invalid"
    }
  ],
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Domain Layer Patterns

### ValidationError (Field-Specific)

```python
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

### NotFoundError (Resource Missing)

```python
from src.core.errors import NotFoundError
from src.core.enums import ErrorCode

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

### ConflictError (Duplicate Resource)

```python
from src.core.errors import ConflictError
from src.core.enums import ErrorCode

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

### AuthenticationError (Invalid Credentials)

```python
from src.core.errors import AuthenticationError
from src.core.enums import ErrorCode

async def authenticate(email: str, password: str) -> Result[User, AuthenticationError]:
    user = await self.users.find_by_email(email)
    
    if not user or not verify_password(password, user.password_hash):
        return Failure(AuthenticationError(
            code=ErrorCode.INVALID_CREDENTIALS,
            message="Invalid email or password",
        ))
    
    return Success(user)
```

---

## Application Layer Patterns

### Command Handler Error Mapping

```python
from src.application.errors import ApplicationError, ApplicationErrorCode

class RegisterUserHandler:
    async def handle(self, cmd: RegisterUserCommand) -> Result[UUID, ApplicationError]:
        """Register new user with error mapping."""
        result = await self.user_service.register_user(cmd.email, cmd.password)
        
        match result:
            case Success(user):
                await self.event_bus.publish(UserRegistered(user_id=user.id))
                return Success(user.id)
            
            case Failure(ValidationError() as err):
                return Failure(ApplicationError(
                    code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
                    message=f"Registration failed: {err.message}",
                    domain_error=err,
                    details={"field": err.field},
                ))
            
            case Failure(ConflictError() as err):
                return Failure(ApplicationError(
                    code=ApplicationErrorCode.CONFLICT,
                    message="Registration failed: email already exists",
                    domain_error=err,
                ))
```

### Query Handler Error Mapping

```python
class GetUserHandler:
    async def handle(self, query: GetUser) -> Result[UserDTO, ApplicationError]:
        """Get user with error mapping."""
        result = await self.users.find_by_id(query.user_id)
        
        match result:
            case Success(user):
                return Success(UserDTO.from_entity(user))
            
            case Failure(NotFoundError() as err):
                return Failure(ApplicationError(
                    code=ApplicationErrorCode.NOT_FOUND,
                    message=f"User not found: {err.message}",
                    domain_error=err,
                ))
```

### Multiple Error Types

```python
async def handle(self, cmd: Command) -> Result[T, ApplicationError]:
    """Handle with multiple possible error types."""
    result = await self.service.execute(cmd)
    
    match result:
        case Success(value):
            return Success(value)
        
        case Failure(ValidationError() as err):
            return Failure(ApplicationError(
                code=ApplicationErrorCode.COMMAND_VALIDATION_FAILED,
                message="Validation failed",
                domain_error=err,
            ))
        
        case Failure(AuthenticationError() as err):
            return Failure(ApplicationError(
                code=ApplicationErrorCode.UNAUTHORIZED,
                message="Authentication required",
                domain_error=err,
            ))
        
        case Failure(AuthorizationError() as err):
            return Failure(ApplicationError(
                code=ApplicationErrorCode.FORBIDDEN,
                message="Access denied",
                domain_error=err,
            ))
```

---

## Presentation Layer Patterns

### Standard Endpoint Pattern

```python
@router.post("/resource", status_code=201)
async def create_resource(
    data: ResourceCreateRequest,
    request: Request,
    handler: CreateResourceHandler = Depends(),
    trace_id: str = Depends(get_trace_id),
):
    """Standard pattern for all endpoints."""
    result = await handler.handle(CreateResourceCommand(**data.model_dump()))
    
    match result:
        case Success(resource_id):
            return {"id": str(resource_id)}
        
        case Failure(error):
            return ErrorResponseBuilder.from_application_error(
                error=error,
                request=request,
                trace_id=trace_id,
            )
```

### GET Endpoint (Query)

```python
@router.get("/users/{user_id}")
async def get_user(
    user_id: UUID,
    request: Request,
    handler: GetUserHandler = Depends(),
    trace_id: str = Depends(get_trace_id),
):
    """GET endpoint pattern."""
    result = await handler.handle(GetUser(user_id=user_id))
    
    match result:
        case Success(user_dto):
            return user_dto
        
        case Failure(error):
            return ErrorResponseBuilder.from_application_error(
                error=error,
                request=request,
                trace_id=trace_id,
            )
```

---

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
match result:
    case Success(user):
        return {"id": user.id}
    case Failure(error):
        return ErrorResponseBuilder.from_application_error(...)
```

### ❌ Don't Inline Error Responses

```python
# ❌ WRONG
@router.post("/users")
async def create_user(data: dict):
    if not data.get("email"):
        return {"error": "Email required"}, 400  # NO!

# ✅ CORRECT
@router.post("/users")
async def create_user(request: Request, handler=Depends(), trace_id=Depends()):
    result = await handler.handle(...)
    match result:
        case Failure(error):
            return ErrorResponseBuilder.from_application_error(...)
```

### ❌ Don't Mix Error Handling Styles

```python
# ❌ WRONG: Mixing exceptions and Results
def process_data(data: str) -> Result[Data, Error]:
    if not data:
        raise ValueError("Data required")  # Inconsistent!
    return Success(Data(data))

# ✅ CORRECT: Consistent Result types
def process_data(data: str) -> Result[Data, ValidationError]:
    if not data:
        return Failure(ValidationError(...))
    return Success(Data(data))
```

---

## Testing Error Paths

### Unit Tests (Domain)

```python
def test_validation_error():
    """Test validation returns Failure."""
    result = create_user(email="invalid-email")
    
    match result:
        case Failure(ValidationError() as err):
            assert err.code == ErrorCode.INVALID_EMAIL
            assert err.field == "email"
        case _:
            pytest.fail("Expected ValidationError")
```

### Integration Tests (Application)

```python
async def test_command_handler_error_mapping():
    """Test handler maps domain errors to application errors."""
    handler = CreateUserHandler(...)
    result = await handler.handle(CreateUserCommand(email="invalid"))
    
    match result:
        case Failure(ApplicationError() as err):
            assert err.code == ApplicationErrorCode.COMMAND_VALIDATION_FAILED
            assert err.domain_error is not None
        case _:
            pytest.fail("Expected ApplicationError")
```

### API Tests (Presentation)

```python
def test_api_returns_rfc7807(client):
    """Test API endpoint returns RFC 7807 response."""
    response = client.post("/users", json={"email": "invalid"})
    
    assert response.status_code == 400
    data = response.json()
    assert data["type"].endswith("/errors/command_validation_failed")
    assert data["title"] == "Validation Failed"
    assert "errors" in data
```

---

## Common HTTP Status Mappings

| ApplicationErrorCode | HTTP Status | Title |
| -------------------- | ----------- | ----- |
| `COMMAND_VALIDATION_FAILED` | 400 | Validation Failed |
| `UNAUTHORIZED` | 401 | Authentication Required |
| `FORBIDDEN` | 403 | Access Denied |
| `NOT_FOUND` | 404 | Resource Not Found |
| `CONFLICT` | 409 | Resource Conflict |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate Limit Exceeded |
| `COMMAND_EXECUTION_FAILED` | 500 | Command Execution Failed |
| `QUERY_FAILED` | 500 | Query Failed |

---

## Best Practices

1. **Always use Result types in domain layer** - No exceptions for business logic
2. **Map domain errors to application errors** - Add application context
3. **Use ErrorResponseBuilder for all API errors** - Consistent RFC 7807 format
4. **Include trace_id in all error responses** - Essential for debugging
5. **Test error paths thoroughly** - Error handling is critical functionality
6. **Keep error messages user-friendly** - No technical jargon or stack traces
7. **Use pattern matching** - Clean, explicit error handling

---

**Created**: 2025-11-19 | **Last Updated**: 2025-11-19
