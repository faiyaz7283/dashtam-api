# Secrets Management Architecture

## Overview

This document describes the secrets management implementation for Dashtam,
following hexagonal architecture principles with clear separation between
domain protocols and infrastructure adapters. The architecture provides
multi-tier secrets management (local .env files for development, AWS Secrets
Manager for production) with a read-only, environment-agnostic interface.

---

## 1. Key Principles

### 1.1 Core Principles

- ✅ **Hexagonal Architecture**: Domain defines protocol (port), infrastructure
  provides adapters
- ✅ **Read-Only Access**: Apps consume secrets but cannot modify (principle of
  least privilege)
- ✅ **Environment Abstraction**: Same code works across all environments
  (dev/test/prod)
- ✅ **Dependency Injection**: Container pattern selects correct adapter via
  `SECRETS_BACKEND`
- ✅ **Security First**: No hardcoded secrets, encryption at rest/transit,
  automatic rotation support
- ✅ **Cost Effective**: Free local dev (.env), ~$4/month production (AWS
  Secrets Manager)

### 1.2 Multi-Tier Strategy

| Environment | Backend | Cost | Use Case |
|------------|---------|------|----------|
| **Local Development** | `.env` files | Free | Fast, offline, no dependencies |
| **Testing** | Fake/Mocked | Free | Hardcoded test values, isolation |
| **CI/CD** | GitHub Secrets | Free | Platform-managed encryption |
| **Staging** | AWS Secrets Manager | ~$4/mo | Production-like setup |
| **Production** | AWS Secrets Manager | ~$4/mo | Auto rotation, audit |

---

## 2. Hexagonal Architecture

### 2.1 Layer Responsibilities

```text
┌─────────────────────────────────────────────────────────┐
│ Domain Layer (Port/Protocol)                            │
│ - SecretsProtocol defines interface                     │
│ - Pure Python (no external dependencies)                │
│ - Read-only methods only                                │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ implements
                          │
┌─────────────────────────────────────────────────────────┐
│ Infrastructure Layer (Adapters)                         │
│ - EnvAdapter (local .env files)                  │
│ - AWSAdapter (AWS Secrets Manager)               │
│ - VaultAdapter (HashiCorp Vault)                 │
│ - Each adapter handles caching, error handling          │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ uses
                          │
┌─────────────────────────────────────────────────────────┐
│ Core Layer (Container)                                  │
│ - get_secrets() creates correct adapter                 │
│ - Reads SECRETS_BACKEND env var                         │
│ - Follows Composition Root pattern                      │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │ uses
                          │
┌─────────────────────────────────────────────────────────┐
│ Application Layer (Settings)                            │
│ - Settings.from_secrets_manager() classmethod           │
│ - Loads config from any secrets backend                 │
│ - Auto-detects backend from environment                 │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Dependency Flow

- **Domain** → Defines `SecretsProtocol` (no dependencies)
- **Infrastructure** → Implements protocol with adapters (boto3, hvac)
- **Core/Container** → Creates correct adapter based on configuration
- **Application** → Consumes secrets via protocol (backend-agnostic)

**Benefits**:

- Domain layer remains pure (no external dependencies)
- Easy to add new backends (just implement protocol)
- Testable (mock protocol, no patching boto3)
- Configuration-driven (change backend via env var)

---

## 3. Domain Layer - Protocol Definition

### 3.1 SecretsProtocol Interface

```python
# src/domain/protocols/secrets_protocol.py
from typing import Protocol, Dict, Any


class SecretsProtocol(Protocol):
    """Protocol for secrets management systems.
    
    Applications are READ-ONLY consumers of secrets.
    Secret provisioning is an admin operation (Terraform, AWS CLI).
    
    Implementations:
    - EnvAdapter: Local development (.env files)
    - AWSAdapter: Production (AWS Secrets Manager)
    - VaultAdapter: Alternative (HashiCorp Vault)
    """
    
    def get_secret(self, secret_path: str) -> str:
        """Get single secret value.
        
        Args:
            secret_path: Path like 'database/url' or 'schwab/api_key'
            
        Returns:
            Secret value as string
            
        Raises:
            SecretNotFoundError: If secret doesn't exist
        """
        ...
    
    def get_secret_json(self, secret_path: str) -> Dict[str, Any]:
        """Get secret as parsed JSON dictionary.
        
        Args:
            secret_path: Path to JSON-formatted secret
            
        Returns:
            Parsed JSON as dictionary
            
        Raises:
            SecretNotFoundError: If secret doesn't exist
            ValueError: If secret is not valid JSON
        """
        ...
    
    def refresh_cache(self) -> None:
        """Clear cached secrets to reload after rotation.
        
        Call this after rotating secrets in backend system.
        Next get_secret() call will fetch fresh value.
        """
        ...
```

### 3.2 Error Handling

**Follows error-handling-architecture.md standards**: Infrastructure adapters
catch exceptions and return Result types. Domain never raises exceptions.

```python
# src/core/errors.py - Domain errors (already exist)
from dataclasses import dataclass

@dataclass(frozen=True, slots=True, kw_only=True)
class SecretsError(DomainError):
    """Secrets-related errors."""
    pass

# Error codes
class ErrorCode(Enum):
    # ... existing codes ...
    SECRET_NOT_FOUND = "secret_not_found"
    SECRET_ACCESS_DENIED = "secret_access_denied"
    SECRET_INVALID_JSON = "secret_invalid_json"
```

### 3.3 Why Read-Only?

**Principle of least privilege**:

- ✅ Apps cannot modify/delete secrets (reduced blast radius)
- ✅ Secret creation is admin operation (Terraform, AWS CLI, web console)
- ✅ Industry standard (AWS, Vault, GCP Secret Manager, Azure Key Vault)
- ✅ Simpler protocol (only 3 methods vs 10+ for write operations)
- ✅ Audit trail: Only admins provision secrets (not applications)

---

## 4. Infrastructure Layer - Adapters

### 4.1 EnvAdapter (Local Development)

**Purpose**: Load secrets from `.env` files for local development.

**File**: `src/infrastructure/secrets/env_adapter.py`

```python
# src/infrastructure/secrets/env_adapter.py
import os
import json
from typing import Dict, Any
from src.core.result import Result, Success, Failure
from src.core.errors import SecretsError, ErrorCode


class EnvAdapter:
    """Local development secrets from .env files.
    
    Converts secret paths to environment variable names:
    - 'database/url' → DATABASE_URL
    - 'schwab/api_key' → SCHWAB_API_KEY
    """
    
    def __init__(self):
        """No initialization needed for env vars."""
        pass
    
    def get_secret(self, secret_path: str) -> Result[str, SecretsError]:
        """Get secret from environment variable.
        
        Args:
            secret_path: Path like 'database/url'
            
        Returns:
            Success(secret_value) or Failure(SecretsError)
        """
        env_var_name = secret_path.replace("/", "_").upper()
        secret_value = os.getenv(env_var_name)
        
        if secret_value is None:
            return Failure(SecretsError(
                code=ErrorCode.SECRET_NOT_FOUND,
                message=f"Environment variable not found: {env_var_name}",
                details={"secret_path": secret_path}
            ))
        
        return Success(secret_value)
    
    def get_secret_json(self, secret_path: str) -> Result[dict[str, Any], SecretsError]:
        """Get secret as parsed JSON."""
        result = self.get_secret(secret_path)
        
        match result:
            case Success(secret_value):
                try:
                    return Success(json.loads(secret_value))
                except json.JSONDecodeError:
                    return Failure(SecretsError(
                        code=ErrorCode.SECRET_INVALID_JSON,
                        message=f"Secret is not valid JSON: {secret_path}",
                    ))
            case Failure(error):
                return Failure(error)
    
    def refresh_cache(self) -> None:
        """No-op for env vars (always fresh)."""
        pass
```

**Benefits**:

- ✅ No external dependencies
- ✅ Works offline
- ✅ Fast (no network calls)
- ✅ Familiar to developers (.env files)

### 4.2 AWSAdapter (Production)

**Purpose**: Load secrets from AWS Secrets Manager with caching.

**File**: `src/infrastructure/secrets/aws_adapter.py`

```python
# src/infrastructure/secrets/aws_adapter.py
import json
import boto3
from typing import Dict, Any
from src.core.result import Result, Success, Failure
from src.core.errors import SecretsError, ErrorCode


class AWSAdapter:
    """Production secrets from AWS Secrets Manager.
    
    Features:
    - In-memory caching (reduce API calls, cost)
    - Hierarchical naming: /dashtam/{env}/{category}/{name}
    - Automatic retry with exponential backoff
    """
    
    def __init__(self, environment: str, region: str = "us-east-1"):
        """Initialize AWS Secrets Manager client.
        
        Args:
            environment: 'staging' or 'production'
            region: AWS region for secrets
        """
        self.client = boto3.client('secretsmanager', region_name=region)
        self.environment = environment
        self._cache: Dict[str, str] = {}
    
    def get_secret(self, secret_path: str) -> Result[str, SecretsError]:
        """Get secret from AWS Secrets Manager.
        
        Args:
            secret_path: Path like 'database/url'
            
        Returns:
            Success(secret_value) or Failure(SecretsError)
        """
        secret_id = f"/dashtam/{self.environment}/{secret_path}"
        
        # Check cache first
        if secret_id in self._cache:
            return Success(self._cache[secret_id])
        
        try:
            response = self.client.get_secret_value(SecretId=secret_id)
            secret_value = response['SecretString']
            
            # Cache for future calls
            self._cache[secret_id] = secret_value
            return Success(secret_value)
            
        except self.client.exceptions.ResourceNotFoundException:
            return Failure(SecretsError(
                code=ErrorCode.SECRET_NOT_FOUND,
                message=f"Secret not found in AWS: {secret_id}",
            ))
        except Exception as e:
            return Failure(SecretsError(
                code=ErrorCode.SECRET_ACCESS_DENIED,
                message=f"Failed to access AWS secret: {secret_id}",
                details={"error": str(e)}
            ))
    
    def get_secret_json(self, secret_path: str) -> Result[dict[str, Any], SecretsError]:
        """Get secret as parsed JSON."""
        result = self.get_secret(secret_path)
        
        match result:
            case Success(secret_value):
                try:
                    return Success(json.loads(secret_value))
                except json.JSONDecodeError:
                    return Failure(SecretsError(
                        code=ErrorCode.SECRET_INVALID_JSON,
                        message=f"Secret is not valid JSON: {secret_path}",
                    ))
            case Failure(error):
                return Failure(error)
    
    def refresh_cache(self) -> None:
        """Clear cache to force reload on next access."""
        self._cache.clear()
```

**Caching Strategy**:

- Cache secrets in memory to reduce AWS API calls
- Cost: $0.05 per 10,000 API calls
- Without cache: ~100,000 calls/month = $0.50
- With cache: ~1,000 calls/month (startup only) = $0.005
- **Savings**: 99% reduction in API costs

**Secret Rotation**:

```python
# After rotating secret in AWS console or Terraform
secrets_manager.refresh_cache()  # Clear cache
new_value = secrets_manager.get_secret("database/password")  # Fetches fresh
```

### 4.3 VaultAdapter (Alternative)

**Purpose**: Load secrets from HashiCorp Vault (optional).

**File**: `src/infrastructure/secrets/vault_adapter.py`

```python
# src/infrastructure/secrets/vault_adapter.py
import json
import hvac
from typing import Dict, Any
from src.core.result import Result, Success, Failure
from src.core.errors import SecretsError, ErrorCode


class VaultAdapter:
    """Secrets from HashiCorp Vault (optional backend).
    
    Use case: Organizations already using Vault infrastructure.
    """
    
    def __init__(self, environment: str, vault_addr: str, vault_token: str):
        """Initialize Vault client.
        
        Args:
            environment: 'staging' or 'production'
            vault_addr: Vault server URL
            vault_token: Authentication token
        """
        self.client = hvac.Client(url=vault_addr, token=vault_token)
        self.environment = environment
        self._cache: Dict[str, str] = {}
        
        if not self.client.is_authenticated():
            # Initialization failure - raise exception here (not in get_secret)
            raise RuntimeError("Vault authentication failed")
    
    def get_secret(self, secret_path: str) -> Result[str, SecretsError]:
        """Get secret from Vault KV v2."""
        vault_path = f"dashtam/{self.environment}/{secret_path}"
        
        if vault_path in self._cache:
            return Success(self._cache[vault_path])
        
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=vault_path
            )
            secret_value = response['data']['data']['value']
            
            self._cache[vault_path] = secret_value
            return Success(secret_value)
            
        except hvac.exceptions.InvalidPath:
            return Failure(SecretsError(
                code=ErrorCode.SECRET_NOT_FOUND,
                message=f"Secret not found in Vault: {vault_path}",
            ))
        except Exception as e:
            return Failure(SecretsError(
                code=ErrorCode.SECRET_ACCESS_DENIED,
                message=f"Failed to access Vault secret: {vault_path}",
                details={"error": str(e)}
            ))
    
    def get_secret_json(self, secret_path: str) -> Result[dict[str, Any], SecretsError]:
        """Get secret as parsed JSON."""
        result = self.get_secret(secret_path)
        
        match result:
            case Success(secret_value):
                try:
                    return Success(json.loads(secret_value))
                except json.JSONDecodeError:
                    return Failure(SecretsError(
                        code=ErrorCode.SECRET_INVALID_JSON,
                        message=f"Secret is not valid JSON: {secret_path}",
                    ))
            case Failure(error):
                return Failure(error)
    
    def refresh_cache(self) -> None:
        """Clear cache."""
        self._cache.clear()
```

---

## 5. Configuration Examples

### 5.1 Environment-Specific Configuration

**Local Development**:

```bash
# env/.env.dev
ENVIRONMENT=development
SECRETS_BACKEND=env  # Uses .env files (default)

# Secrets as env vars
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/dashtam_dev
SCHWAB_API_KEY=your-dev-key
SCHWAB_API_SECRET=your-dev-secret
```

**Staging**:

```bash
# Set in ECS task definition or .env.staging
ENVIRONMENT=staging
SECRETS_BACKEND=aws
AWS_REGION=us-east-1

# Secrets fetched from AWS:
# /dashtam/staging/database/url
# /dashtam/staging/schwab/api_key
# /dashtam/staging/schwab/api_secret
```

**Production**:

```bash
# Set in ECS task definition
ENVIRONMENT=production
SECRETS_BACKEND=aws
AWS_REGION=us-east-1

# Secrets fetched from AWS:
# /dashtam/production/database/url
# /dashtam/production/schwab/api_key
# /dashtam/production/schwab/api_secret
```

---

## 6. Centralized Dependency Injection

### 6.1 Container Integration

**Secrets use the centralized container pattern** (see
`dependency-injection-architecture.md`):

```python
# src/core/container.py
from functools import lru_cache
from src.domain.protocols.secrets_protocol import SecretsProtocol
from src.core.config import settings

@lru_cache()
def get_secrets() -> SecretsProtocol:
    """Get secrets manager singleton (app-scoped).
    
    Container owns factory logic - decides which adapter based on SECRETS_BACKEND.
    This follows the Composition Root pattern (industry best practice).
    
    Returns correct adapter based on SECRETS_BACKEND environment variable:
        - 'env': EnvAdapter (local development)
        - 'aws': AWSAdapter (production)
    
    Returns:
        Secrets manager implementing SecretsProtocol.
    
    Usage:
        # Application Layer (direct use)
        secrets = get_secrets()
        db_url = secrets.get_secret("database/url")
        
        # Presentation Layer (FastAPI Depends)
        secrets: SecretsProtocol = Depends(get_secrets)
    """
    import os
    
    backend = os.getenv("SECRETS_BACKEND", "env")
    
    if backend == "aws":
        from src.infrastructure.secrets.aws_adapter import AWSAdapter
        region = os.getenv("AWS_REGION", "us-east-1")
        return AWSAdapter(environment=settings.environment, region=region)
    elif backend == "env":
        from src.infrastructure.secrets.env_adapter import EnvAdapter
        return EnvAdapter()
    else:
        raise ValueError(f"Unsupported SECRETS_BACKEND: {backend}")
```

### 6.2 Settings Class with Secrets Support

```python
# src/core/config.py
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from src.domain.protocols.secrets_protocol import SecretsProtocol


class Settings(BaseSettings):
    """Application configuration with multi-tier secrets support."""
    
    # Core settings
    environment: str = "development"
    debug: bool = False
    
    # Database
    database_url: str
    
    # Charles Schwab API
    schwab_api_key: str
    schwab_api_secret: str
    schwab_redirect_uri: str
    
    # Security
    secret_key: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @classmethod
    def from_secrets_manager(cls, secrets: SecretsProtocol) -> "Settings":
        """Load settings from any secrets backend (AWS, Vault, etc).
        
        Args:
            secrets: Secrets adapter implementing SecretsProtocol
            
        Returns:
            Settings instance with values from secrets backend
        """
        environment = os.getenv("ENVIRONMENT", "production")
        
        return cls(
            environment=environment,
            debug=environment != "production",
            
            # Load secrets via protocol (backend-agnostic)
            database_url=secrets.get_secret("database/url"),
            schwab_api_key=secrets.get_secret("schwab/api_key"),
            schwab_api_secret=secrets.get_secret("schwab/api_secret"),
            schwab_redirect_uri=secrets.get_secret("schwab/redirect_uri"),
            secret_key=secrets.get_secret("app/secret_key"),
        )


@lru_cache()
def get_settings() -> Settings:
    """Get settings singleton with auto-detected secrets backend.
    
    Returns:
        Settings instance (cached for performance)
        
    Behavior:
        - SECRETS_BACKEND=env: Load from .env file (default)
        - SECRETS_BACKEND=aws: Load from AWS Secrets Manager
        - SECRETS_BACKEND=vault: Load from HashiCorp Vault
    
    Note:
        Settings can also use get_secrets() from container for
        dynamic secret loading after application startup.
    """
    secrets_backend = os.getenv("SECRETS_BACKEND", "env")
    
    if secrets_backend != "env":
        # Production: Use secrets manager via container
        from src.core.container import get_secrets
        secrets = get_secrets()
        return Settings.from_secrets_manager(secrets)
    else:
        # Development: Use .env files
        return Settings()
```

### 6.3 Usage in Application

```python
# src/main.py
from src.core.config import get_settings
from src.core.container import get_secrets

# Settings singleton (loaded at startup)
settings = get_settings()  # Auto-detects backend

# Secrets manager (for dynamic secret access)
secrets = get_secrets()  # Same backend as settings

# Both work seamlessly
print(settings.database_url)  # Loaded at startup
api_key = secrets.get_secret("schwab/api_key")  # Dynamic access
```

### 6.4 Benefits of Container Pattern

- ✅ **Single source of truth**: All dependencies in `src/core/container.py`
- ✅ **Easy to test**: Mock container, not individual adapters
- ✅ **Consistent pattern**: Same as cache and database
- ✅ **Type safe**: Returns protocol types, IDE autocomplete works

---

## 7. Secret Naming Convention

### 7.1 Hierarchical Structure

```text
/dashtam/{environment}/{category}/{name}

Examples:
/dashtam/production/database/url
/dashtam/production/database/password
/dashtam/production/schwab/api_key
/dashtam/production/schwab/api_secret
/dashtam/production/schwab/redirect_uri
/dashtam/production/app/secret_key
/dashtam/staging/database/url
```

### 7.2 Benefits

- ✅ **Environment Isolation**: Cannot accidentally use prod secrets in
  staging
- ✅ **Logical Grouping**: Related secrets grouped by category (database,
  schwab, app)
- ✅ **IAM Policies**: Grant access by prefix (`/dashtam/staging/*`)
- ✅ **Audit Trail**: CloudTrail logs show which environment accessed
- ✅ **Terraform Management**: Easy to manage with
  `aws_secretsmanager_secret` resources

### 7.3 Environment Variable Mapping

For `EnvAdapter`, paths map to env vars:

| Secret Path | Environment Variable |
|------------|---------------------|
| `database/url` | `DATABASE_URL` |
| `schwab/api_key` | `SCHWAB_API_KEY` |
| `schwab/api_secret` | `SCHWAB_API_SECRET` |
| `app/secret_key` | `APP_SECRET_KEY` |

**Rule**: Replace `/` with `_`, convert to uppercase.

---

## 8. Security Considerations

### 8.1 Principle of Least Privilege

- ✅ **Read-Only Protocol**: Apps cannot modify/delete secrets
- ✅ **IAM Policies**: Grant minimum required permissions
- ✅ **No Secrets in Code**: All secrets from external backends
- ✅ **No Secrets in Logs**: Never log secret values

### 8.2 Encryption

**At Rest**:

- AWS Secrets Manager: AES-256 with AWS KMS
- HashiCorp Vault: AES-256-GCM with transit encryption
- Local .env: Filesystem permissions (600), not committed to git

**In Transit**:

- AWS API: TLS 1.2+ (HTTPS only)
- Vault API: TLS 1.2+ (HTTPS only)
- Local: N/A (in-process)

### 8.3 Secret Rotation

**AWS Secrets Manager**:

- Manual rotation: Update secret in AWS Console → Call `refresh_cache()`
- Automatic rotation: Lambda function rotates → App cache expires after TTL
- Zero downtime: Dual secrets during rotation (AWSCURRENT, AWSPREVIOUS)

**Best Practice**: Rotate secrets every 90 days (compliance requirement).

### 8.4 Audit Trail

**AWS CloudTrail**:

- Logs all `GetSecretValue` calls
- Tracks: Who accessed, when, from which IP, success/failure
- Retention: 90 days default, unlimited with S3 export

**HashiCorp Vault**:

- Built-in audit logs
- Tracks: Who accessed, when, from which path, success/failure

---

## 9. Testing Strategy

### 9.1 Unit Tests - Protocol Mocking

**Mock the protocol** (not boto3 internals):

```python
# tests/unit/test_domain_secrets_protocol.py
from typing import Dict, Any
from src.domain.protocols.secrets_protocol import SecretsProtocol


class FakeSecretsProvider:
    """Fake implementation for unit tests."""
    
    def __init__(self, secrets: Dict[str, str]):
        self._secrets = secrets
    
    def get_secret(self, secret_path: str) -> str:
        return self._secrets[secret_path]
    
    def get_secret_json(self, secret_path: str) -> Dict[str, Any]:
        import json
        return json.loads(self._secrets[secret_path])
    
    def refresh_cache(self) -> None:
        pass


def test_settings_from_secrets_manager():
    """Test Settings loads from secrets protocol."""
    fake_secrets = FakeSecretsProvider({
        "database/url": "postgresql://user:pass@host:5432/db",
        "schwab/api_key": "test-key",
        "schwab/api_secret": "test-secret",
        "schwab/redirect_uri": "https://test.com/callback",
        "app/secret_key": "test-secret-key",
    })
    
    settings = Settings.from_secrets_manager(fake_secrets)
    
    assert settings.database_url == "postgresql://user:pass@host:5432/db"
    assert settings.schwab_api_key == "test-key"
```

### 9.2 Unit Tests - Container Pattern

```python
# tests/unit/test_core_container_secrets.py
import os
import pytest
from src.core.container import get_secrets
from src.infrastructure.secrets.env_adapter import EnvAdapter
from src.infrastructure.secrets.aws_adapter import AWSAdapter


def test_container_creates_env_adapter_by_default(monkeypatch):
    """Container creates EnvAdapter when SECRETS_BACKEND=env."""
    monkeypatch.setenv("SECRETS_BACKEND", "env")
    get_secrets.cache_clear()  # Clear singleton cache
    
    adapter = get_secrets()
    
    assert isinstance(adapter, EnvAdapter)


def test_container_creates_aws_adapter(monkeypatch):
    """Container creates AWSAdapter when SECRETS_BACKEND=aws."""
    monkeypatch.setenv("SECRETS_BACKEND", "aws")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    get_secrets.cache_clear()  # Clear singleton cache
    
    adapter = get_secrets()
    
    assert isinstance(adapter, AWSAdapter)
```

### 9.3 Integration Tests - AWS Secrets Manager (Mocked)

Use **moto** to mock AWS Secrets Manager:

```python
# tests/integration/test_secrets_aws.py
import boto3
import pytest
from moto import mock_secretsmanager
from src.infrastructure.secrets.aws_adapter import AWSAdapter


@mock_secretsmanager
def test_aws_adapter_get_secret():
    """Test AWS adapter fetches secret correctly."""
    # Setup: Create mock secret in moto
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(
        Name='/dashtam/production/database/url',
        SecretString='postgresql://prod:pass@prod:5432/dashtam'
    )
    
    # Test: Fetch secret via adapter
    adapter = AWSAdapter(environment='production', region='us-east-1')
    secret_value = adapter.get_secret('database/url')
    
    assert secret_value == 'postgresql://prod:pass@prod:5432/dashtam'


@mock_secretsmanager
def test_aws_adapter_caching():
    """Test AWS adapter caches secrets (reduces API calls)."""
    client = boto3.client('secretsmanager', region_name='us-east-1')
    client.create_secret(
        Name='/dashtam/production/database/url',
        SecretString='postgresql://prod:pass@prod:5432/dashtam'
    )
    
    adapter = AWSAdapter(environment='production', region='us-east-1')
    
    # First call: Fetches from AWS (cached)
    value1 = adapter.get_secret('database/url')
    
    # Second call: Returns cached value (no AWS call)
    value2 = adapter.get_secret('database/url')
    
    assert value1 == value2
    assert '/dashtam/production/database/url' in adapter._cache
```

### 9.4 Coverage Target

- **Unit tests**: 15 tests (factory, protocol mocking)
- **Integration tests (AWS)**: 20 tests (mocked with moto)
- **Integration tests (Vault)**: 10 tests (optional, mocked with vault-dev-server)
- **Cache tests**: 10 tests (verify caching, refresh_cache)
- **Total**: 55+ tests
- **Coverage target**: 90%

---

## 10. Implementation Checklist

### 10.1 Domain Layer

- [ ] Create `src/domain/protocols/secrets_protocol.py`
- [ ] Define `SecretsProtocol` with 3 methods (get_secret, get_secret_json, refresh_cache)
- [ ] Define custom exceptions (SecretNotFoundError, SecretAccessError)
- [ ] Add Google-style docstrings

### 10.2 Infrastructure Layer

- [ ] Create `src/infrastructure/secrets/` directory
- [ ] Implement `EnvAdapter` (local dev)
- [ ] Implement `AWSAdapter` (production) with caching
- [ ] Implement `VaultAdapter` (optional)
- [ ] Add error handling (try/except with custom exceptions)

### 10.3 Container Integration

- [x] Container `get_secrets()` implements backend selection
- [x] Support SECRETS_BACKEND env var (env, aws, vault)
- [x] Validate required env vars for each backend
- [x] No separate factory module (Composition Root pattern)

### 10.4 Settings Integration

- [ ] Update `src/core/config.py`
- [ ] Add `Settings.from_secrets_manager()` classmethod
- [ ] Update `get_settings()` to auto-detect backend
- [ ] Maintain backward compatibility (.env files still work)

### 10.5 Testing

- [ ] Unit tests: Protocol mocking (10 tests)
- [ ] Unit tests: Factory pattern (15 tests)
- [ ] Integration tests: AWS adapter with moto (20 tests)
- [ ] Integration tests: Secret caching (10 tests)
- [ ] All tests passing (55+ tests)
- [ ] Coverage: 90%+

### 10.6 Documentation

- [ ] Update `docs/architecture/` with this document
- [ ] Update `~/starter/clean-slate-reference.md` Section 8 reference
- [ ] Add usage examples to `WARP.md` Section 12
- [ ] Document secret naming convention
- [ ] Document IAM permissions for AWS

### 10.7 Dependencies

- [ ] Add `boto3` to `pyproject.toml` (AWS)
- [ ] Add `hvac` to `pyproject.toml` (Vault, optional)
- [ ] Add `moto[secretsmanager]` to dev dependencies (testing)
- [ ] Run `uv sync` to install dependencies

---

## 11. AWS Secrets Manager Setup (Production)

### 11.1 Create Secrets via Terraform

```hcl
# terraform/secrets.tf
resource "aws_secretsmanager_secret" "database_url" {
  name        = "/dashtam/production/database/url"
  description = "PostgreSQL connection URL for production"
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql://user:pass@prod.rds.amazonaws.com:5432/dashtam"
}

resource "aws_secretsmanager_secret" "schwab_api_key" {
  name        = "/dashtam/production/schwab/api_key"
  description = "Charles Schwab API key"
}

resource "aws_secretsmanager_secret_version" "schwab_api_key" {
  secret_id     = aws_secretsmanager_secret.schwab_api_key.id
  secret_string = var.schwab_api_key  # From terraform.tfvars (not in git)
}
```

### 11.2 IAM Policy for ECS Task

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:/dashtam/production/*"
      ]
    }
  ]
}
```

### 11.3 Cost Estimation

- **Storage**: $0.40/secret/month
- **API Calls**: $0.05 per 10,000 calls
- **Typical usage**: 5 secrets × $0.40 = $2.00/month
- **With caching**: ~1,000 calls/month = $0.005
- **Total**: ~$2.00/month (vs $0 for .env, but with rotation, audit,
  encryption)

---

## 12. Migration Path

### 12.1 Phase 1: Local Development (Current)

```bash
# env/.env.dev
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/dashtam_dev
SCHWAB_API_KEY=dev-key
SCHWAB_API_SECRET=dev-secret
```

**No changes needed!** Existing .env files continue to work.

### 12.2 Phase 2: Staging (AWS Secrets Manager)

```bash
# In ECS task definition or .env.staging
ENVIRONMENT=staging
SECRETS_BACKEND=aws
AWS_REGION=us-east-1
```

**Create secrets in AWS**:

```bash
aws secretsmanager create-secret \
  --name /dashtam/staging/database/url \
  --secret-string "postgresql://staging:pass@staging.rds:5432/dashtam"
```

### 12.3 Phase 3: Production (AWS Secrets Manager)

Same as staging, but with `ENVIRONMENT=production` and production secret paths.

---

## 13. Benefits Summary

### 13.1 Hexagonal Architecture

- ✅ **Domain purity**: SecretsProtocol has no external dependencies
- ✅ **Testability**: Mock protocol instead of patching boto3
- ✅ **Flexibility**: Add new backends by implementing protocol
- ✅ **Maintainability**: Clear separation of concerns

### 13.2 Multi-Tier Strategy

- ✅ **Development**: Fast, offline, free (.env files)
- ✅ **Production**: Secure, auditable, rotatable (AWS Secrets Manager)
- ✅ **Cost effective**: ~$4/month vs $0, but with security features
- ✅ **Zero code changes**: Same code works in all environments

### 13.3 Security

- ✅ **Encryption**: At rest (AES-256) and in transit (TLS 1.2+)
- ✅ **Audit trail**: CloudTrail logs all secret access
- ✅ **Rotation**: Manual or automatic secret rotation
- ✅ **Access control**: IAM policies restrict secret access
- ✅ **Compliance**: Meets PCI-DSS, SOC 2, HIPAA requirements

### 13.4 Developer Experience

- ✅ **No workflow changes**: Local dev still uses .env files
- ✅ **Auto-detection**: Factory selects backend automatically
- ✅ **Type safety**: Protocol ensures consistent interface
- ✅ **Error handling**: Clear exceptions for missing/inaccessible secrets

---

## 14. References

- **AWS Secrets Manager**: <https://docs.aws.amazon.com/secretsmanager/>
- **HashiCorp Vault**: <https://www.vaultproject.io/docs>
- **Python Protocols**: <https://peps.python.org/pep-0544/>

---

**Created**: 2025-11-13 | **Last Updated**: 2025-11-13
