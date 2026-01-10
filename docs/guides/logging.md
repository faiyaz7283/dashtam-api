# Structured Logging Usage Guide

Practical guide for using structured logging in Dashtam.

**Architecture Reference**: `docs/architecture/logging.md`

---

## Quick Start

### Basic Logging

```python
from src.core.container import get_logger

logger = get_logger()

# Structured logging - use key-value context, NOT f-strings
logger.info("User registered", user_id=str(user_id), email=user.email)
logger.warning("Rate limit approaching", current=45, limit=50)
logger.error("Database connection failed", error=exc, retry_count=3)
```

### In FastAPI Endpoints

```python
from fastapi import Depends
from src.core.container import get_logger
from src.domain.protocols.logger_protocol import LoggerProtocol
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id

@router.post("/users", status_code=201)
async def create_user(
    data: UserCreate,
    logger: LoggerProtocol = Depends(get_logger),
):
    trace_id = get_trace_id() or ""
    
    logger.info(
        "Creating user",
        email=data.email,
        trace_id=trace_id,
    )
    
    # ... business logic ...
    
    return {"id": user_id}
```

### In Command/Query Handlers

```python
from src.core.container import get_logger
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id

class RegisterUserHandler:
    def __init__(self):
        self._logger = get_logger()
    
    async def handle(self, cmd: RegisterUser) -> Result[UUID, ApplicationError]:
        trace_id = get_trace_id() or ""
        
        self._logger.info(
            "User registration started",
            email=cmd.email,
            trace_id=trace_id,
        )
        
        # ... handler logic ...
```

---

## Log Levels

| Level | Use Case | Example |
|-------|----------|---------|
| **DEBUG** | Detailed diagnostic info (dev only) | `logger.debug("Cache lookup", key="user:123", found=True)` |
| **INFO** | Normal business events | `logger.info("User registered", user_id="...")` |
| **WARNING** | Degraded but operational | `logger.warning("Rate limit approaching", current=45, limit=50)` |
| **ERROR** | Operation failed, system continues | `logger.error("Email send failed", error=exc, retry_count=3)` |
| **CRITICAL** | System-wide failure, immediate attention | `logger.critical("Database unreachable", error=exc)` |

---

## Context Binding

Bind context once for all subsequent logs:

```python
# Without binding - repetitive
logger.info("Step 1", trace_id=trace_id, user_id=user_id)
logger.info("Step 2", trace_id=trace_id, user_id=user_id)
logger.info("Step 3", trace_id=trace_id, user_id=user_id)

# With binding - clean
request_logger = logger.bind(trace_id=trace_id, user_id=user_id)
request_logger.info("Step 1")  # trace_id, user_id auto-included
request_logger.info("Step 2")
request_logger.info("Step 3")
```

Use `bind()` or `with_context()` (alias):

```python
# Equivalent methods
bound_logger = logger.bind(request_id="req-123")
bound_logger = logger.with_context(request_id="req-123")
```

---

## Error Logging

Log errors with exception details:

```python
try:
    result = await external_api.call()
except ExternalAPIError as exc:
    logger.error(
        "External API call failed",
        error=exc,  # Automatically extracts error_type, error_message
        endpoint="/accounts",
        retry_count=3,
        trace_id=get_trace_id() or "",
    )
```

For critical failures requiring immediate attention:

```python
logger.critical(
    "Database connection pool exhausted",
    error=exc,
    active_connections=0,
    max_connections=50,
    trace_id=get_trace_id() or "",
)
```

---

## Trace ID Pattern

Always include `trace_id` for request correlation:

```python
from src.presentation.routers.api.middleware.trace_middleware import get_trace_id

# get_trace_id() returns str | None
# Use `or ""` pattern for type safety
trace_id = get_trace_id() or ""

logger.info("Operation started", trace_id=trace_id)
```

The `TraceMiddleware` automatically:

1. Generates UUID7 trace ID per request
2. Stores in `ContextVar` for retrieval
3. Adds `X-Trace-Id` response header

---

## Stack Traces (Without Exceptions)

Use `stack_info=True` to attach a stack trace without an exception:

```python
# Debug "how did we get here?" scenarios
logger.info("Unexpected state reached", stack_info=True, state="invalid")

# Output includes "stack" field with full call stack:
# {"event": "Unexpected state reached", "state": "invalid", 
#  "stack": "Stack (most recent call last):\n  File ..."}
```

Useful for debugging complex call chains where you need to trace execution path but no exception occurred.

---

## Security Rules

**NEVER log**:

- ❌ Passwords (plaintext or hashed)
- ❌ API keys, tokens, secrets
- ❌ OAuth access/refresh tokens
- ❌ SSNs, credit card numbers
- ❌ Session IDs, CSRF tokens

**Safe to log**:

- ✅ User IDs (UUIDs)
- ✅ Email addresses
- ✅ Error codes and messages
- ✅ Request paths, HTTP methods
- ✅ Performance metrics

**Sanitize user input**:

```python
# ❌ WRONG - direct user input
logger.info("Search query", query=user_input)

# ✅ CORRECT - truncate and sanitize
safe_query = user_input[:100].replace("\n", "").replace("\r", "")
logger.info("Search query", query=safe_query, query_length=len(user_input))
```

---

## Environment Configuration

Logging backend is selected automatically by `get_logger()`:

| ENVIRONMENT | Adapter | Output |
|-------------|---------|--------|
| `development` | ConsoleAdapter | Human-readable with colors |
| `testing` | ConsoleAdapter | JSON format |
| `ci` | ConsoleAdapter | JSON format |
| `production` | CloudWatchAdapter | AWS CloudWatch Logs |

No code changes needed between environments.

---

## Testing with Mocked Logger

```python
from unittest.mock import MagicMock
from src.domain.protocols.logger_protocol import LoggerProtocol

@pytest.fixture
def mock_logger():
    return MagicMock(spec=LoggerProtocol)

async def test_handler_logs_success(mock_logger):
    handler = MyHandler(logger=mock_logger)
    
    await handler.handle(MyCommand(...))
    
    # Verify logging called
    mock_logger.info.assert_called_once_with(
        "Operation completed",
        result="success",
        trace_id=mock.ANY,
    )
```

---

## Common Patterns

### Performance Logging

```python
import time

async def sync_accounts(user_id: UUID):
    start_time = time.time()
    trace_id = get_trace_id() or ""
    
    logger.info("Account sync started", user_id=str(user_id), trace_id=trace_id)
    
    try:
        # ... sync logic ...
        
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Account sync completed",
            user_id=str(user_id),
            account_count=len(accounts),
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Account sync failed",
            error=exc,
            user_id=str(user_id),
            duration_ms=duration_ms,
            trace_id=trace_id,
        )
        raise
```

### External API Logging

```python
async def call_provider_api(endpoint: str):
    trace_id = get_trace_id() or ""
    
    logger.debug("API request", endpoint=endpoint, trace_id=trace_id)
    
    response = await http_client.get(endpoint)
    
    logger.info(
        "API response",
        endpoint=endpoint,
        status_code=response.status_code,
        duration_ms=response.elapsed.total_seconds() * 1000,
        trace_id=trace_id,
    )
    
    return response
```

---

## Troubleshooting

### Logs Not Appearing

1. Check `LOG_LEVEL` in `.env` (DEBUG, INFO, WARNING, ERROR)
2. Verify logger is injected via `Depends(get_logger)` or `get_logger()`
3. Ensure `trace_id` is passed (helps with filtering)

### Missing Context in Logs

1. Use `bind()` for request-scoped context
2. Include `trace_id` in all logs
3. Verify context is passed as keyword arguments, not in f-string

### Type Error with `get_trace_id()`

```python
# get_trace_id() returns str | None
# Use `or ""` pattern:
trace_id = get_trace_id() or ""
```

---

**Created**: 2025-12-05 | **Last Updated**: 2025-12-05
