# Secrets Management Usage Guide

Practical how-to patterns for working with secrets in Dashtam.

**Architecture Reference**: `docs/architecture/secrets.md`

---

## Quick Start

### Access Secrets in Application Code

```python
from src.core.container import get_secrets
from src.core.result import Success, Failure

# Get secrets manager (auto-selects backend based on SECRETS_BACKEND)
secrets = get_secrets()

# Retrieve a secret
result = secrets.get_secret("database/url")

if isinstance(result, Success):
    db_url = result.value
    print(f"Database URL: {db_url}")
else:
    # Handle error
    print(f"Error: {result.error.message}")
```

### FastAPI Dependency Injection

```python
from fastapi import APIRouter, Depends
from src.core.container import get_secrets
from src.domain.protocols.secrets_protocol import SecretsProtocol

router = APIRouter()

@router.get("/config")
async def get_config(
    secrets: SecretsProtocol = Depends(get_secrets)
):
    """Endpoint that uses secrets."""
    result = secrets.get_secret("app/feature_flag")
    
    if isinstance(result, Success):
        return {"feature_enabled": result.value == "true"}
    return {"feature_enabled": False}
```

---

## Adding New Secrets

### Local Development (.env files)

Add secrets to your `.env.dev` file:

```bash
# env/.env.dev
# New secret: convert path slashes to underscores, uppercase
MY_NEW_SECRET=secret-value-here
CATEGORY_SUBCATEGORY_NAME=another-value
```

**Path Mapping Rule**: `category/subcategory/name` → `CATEGORY_SUBCATEGORY_NAME`

### Production (AWS Secrets Manager)

Create secrets via AWS CLI or Terraform:

```bash
# AWS CLI
aws secretsmanager create-secret \
  --name /dashtam/production/category/name \
  --secret-string "secret-value"

# Or via Terraform (recommended)
# See docs/architecture/secrets.md Section 11
```

---

## Accessing Secrets

### Single Value Secret

```python
from src.core.container import get_secrets
from src.core.result import Success

secrets = get_secrets()

# Get database URL
result = secrets.get_secret("database/url")
if isinstance(result, Success):
    database_url = result.value
```

### JSON Secret

```python
# Store JSON in env var or AWS:
# CONFIG_JSON='{"host": "localhost", "port": "5432"}'

result = secrets.get_secret_json("config/json")
if isinstance(result, Success):
    config = result.value
    host = config["host"]
    port = config["port"]
```

### Handle Missing Secrets

```python
from src.core.result import Success, Failure
from src.core.enums import ErrorCode

result = secrets.get_secret("optional/feature")

if isinstance(result, Failure):
    if result.error.code == ErrorCode.SECRET_NOT_FOUND:
        # Use default value
        value = "default"
    elif result.error.code == ErrorCode.SECRET_ACCESS_DENIED:
        # Log and raise
        raise RuntimeError("Cannot access secret")
else:
    value = result.value
```

---

## Testing

### Unit Tests: Mock the Protocol

```python
import pytest
from unittest.mock import Mock
from src.core.result import Success, Failure
from src.core.enums import ErrorCode
from src.domain.errors import SecretsError

def test_service_with_mocked_secrets():
    """Mock SecretsProtocol for unit tests."""
    # Create mock
    mock_secrets = Mock()
    mock_secrets.get_secret.return_value = Success(value="test-api-key")
    
    # Inject mock
    service = MyService(secrets=mock_secrets)
    
    # Test
    result = service.do_something()
    
    assert result == "expected"
    mock_secrets.get_secret.assert_called_once_with("api/key")

def test_service_handles_missing_secret():
    """Test behavior when secret not found."""
    mock_secrets = Mock()
    mock_secrets.get_secret.return_value = Failure(
        error=SecretsError(
            code=ErrorCode.SECRET_NOT_FOUND,
            message="Secret not found"
        )
    )
    
    service = MyService(secrets=mock_secrets)
    
    # Should handle gracefully
    result = service.do_something_with_fallback()
    assert result == "default-value"
```

### Integration Tests: Use Real EnvAdapter

```python
import os
from unittest.mock import patch
import pytest
from src.infrastructure.secrets.env_adapter import EnvAdapter

@pytest.mark.integration
def test_env_adapter_reads_real_env():
    """Test with real environment variables."""
    with patch.dict(os.environ, {"TEST_SECRET": "test-value"}):
        adapter = EnvAdapter()
        result = adapter.get_secret("test/secret")
        
        assert result.value == "test-value"
```

### Integration Tests: Mock AWS with Moto

```python
import boto3
import pytest
from moto import mock_aws
from src.infrastructure.secrets.aws_adapter import AWSAdapter

@pytest.mark.unit
@mock_aws
def test_aws_adapter_fetches_secret():
    """Test AWS adapter with moto mock."""
    # Setup mock secret
    client = boto3.client("secretsmanager", region_name="us-east-1")
    client.create_secret(
        Name="/dashtam/production/database/url",
        SecretString="postgresql://prod:pass@host:5432/db"
    )
    
    # Test
    adapter = AWSAdapter(environment="production")
    result = adapter.get_secret("database/url")
    
    assert result.value == "postgresql://prod:pass@host:5432/db"
```

### Test Container Backend Selection

```python
import os
from unittest.mock import patch
import pytest
from src.core.container import get_secrets

@pytest.mark.unit
def test_container_selects_env_adapter_by_default():
    """Test default backend is EnvAdapter."""
    with patch.dict(os.environ, {}, clear=True):
        get_secrets.cache_clear()
        
        with patch("src.infrastructure.secrets.env_adapter.EnvAdapter") as mock:
            mock.return_value = Mock()
            adapter = get_secrets()
            mock.assert_called_once()
```

---

## Common Patterns

### Pattern 1: Service with Injected Secrets

```python
from src.domain.protocols.secrets_protocol import SecretsProtocol
from src.core.result import Success

class PaymentService:
    """Service that requires API credentials."""
    
    def __init__(self, secrets: SecretsProtocol):
        self._secrets = secrets
    
    def process_payment(self, amount: float) -> bool:
        result = self._secrets.get_secret("payment/api_key")
        
        if isinstance(result, Success):
            api_key = result.value
            # Use api_key for payment processing
            return True
        
        # Log error, handle gracefully
        return False
```

### Pattern 2: Lazy Secret Loading

```python
class ConfigService:
    """Load secrets only when needed."""
    
    def __init__(self, secrets: SecretsProtocol):
        self._secrets = secrets
        self._api_key: str | None = None
    
    @property
    def api_key(self) -> str:
        if self._api_key is None:
            result = self._secrets.get_secret("external/api_key")
            if isinstance(result, Success):
                self._api_key = result.value
            else:
                raise RuntimeError(f"Cannot load API key: {result.error.message}")
        return self._api_key
```

### Pattern 3: Secret Refresh After Rotation

```python
def refresh_credentials():
    """Call after rotating secrets in AWS/Vault."""
    secrets = get_secrets()
    secrets.refresh_cache()  # Clear cached values
    
    # Next access fetches fresh values
    result = secrets.get_secret("database/password")
```

---

## Environment Configuration

### Development

```bash
# env/.env.dev
SECRETS_BACKEND=env  # Uses .env files (default)
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/dashtam_dev
SECRET_KEY=dev-secret-key-change-in-prod
```

### Production

```bash
# ECS Task Definition or .env.production
SECRETS_BACKEND=aws
AWS_REGION=us-east-1
ENVIRONMENT=production
# Secrets loaded from AWS Secrets Manager:
# /dashtam/production/database/url
# /dashtam/production/secret/key
```

---

## Troubleshooting

### Secret Not Found

**Symptoms**: `Failure(SecretsError(code=SECRET_NOT_FOUND, ...))`

**Solutions**:

1. **EnvAdapter**: Check env var name mapping
   - `database/url` → `DATABASE_URL`
   - Verify `.env` file is loaded

2. **AWSAdapter**: Check secret path
   - Full path: `/dashtam/{environment}/{secret_path}`
   - Verify AWS credentials and IAM permissions

### Access Denied (AWS)

**Symptoms**: `Failure(SecretsError(code=SECRET_ACCESS_DENIED, ...))`

**Solutions**:

1. Check IAM policy allows `secretsmanager:GetSecretValue`
2. Verify resource ARN matches secret path
3. Check AWS credentials are configured

### Invalid JSON

**Symptoms**: `Failure(SecretsError(code=SECRET_INVALID_JSON, ...))`

**Solutions**:

1. Validate JSON format in secret value
2. Use `get_secret()` instead if not JSON

---

**See Also**:

- `docs/architecture/secrets.md` - Full architecture details
- `docs/architecture/dependency-injection.md` - Container patterns

---

**Created**: 2025-12-05 | **Last Updated**: 2026-01-10
