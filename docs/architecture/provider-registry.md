# Provider Integration Registry Architecture

## Overview

The **Provider Integration Registry** implements the Registry Pattern to serve as the single source of truth for all provider integrations in Dashtam. This pattern eliminates manual coordination across multiple files, prevents drift, and enforces consistency for adding new financial data providers.

### What is the Registry Pattern?

The Registry Pattern maintains a centralized catalog of pluggable components (providers) with their metadata and capabilities. Rather than requiring developers to manually update multiple files when adding a provider, the registry serves as the single source of truth that drives all provider-related functionality.

### Implementation Status

**Version**: v1.6.0  
**Status**: ✅ Implemented

### Problem Statement

Before the Provider Integration Registry, adding a new provider required coordinating 8+ manual steps across multiple files:

1. Define provider enum in `src/domain/providers/enums.py`
2. Add provider implementation in `src/infrastructure/providers/`
3. Update container's `OAUTH_PROVIDERS` set (if OAuth)
4. Add provider factory in `src/core/container/providers.py`
5. Update settings validation logic
6. Implement OAuth callback routes (if OAuth)
7. Update database seeds with provider entry
8. Update documentation

**Drift Risks Identified**:

- Manual `OAUTH_PROVIDERS` set in container could diverge from actual OAuth implementations
- Settings validation logic spread across container and provider classes
- Provider capabilities not explicitly documented in code
- No compile-time verification that all providers have required metadata

**Example of Drift**: During registry implementation, Alpaca was found to be missing from the manual `OAUTH_PROVIDERS` set despite being OAuth-capable, demonstrating the exact drift risk the registry pattern prevents.

### Solution

The Provider Integration Registry centralizes all provider metadata in `src/domain/providers/registry.py`:

```python
PROVIDER_REGISTRY: list[ProviderMetadata] = [
    ProviderMetadata(
        slug=Provider.SCHWAB,
        display_name="Charles Schwab",
        category=ProviderCategory.BROKERAGE,
        auth_type=ProviderAuthType.OAUTH,
        capabilities=[ProviderCapability.ACCOUNTS, ProviderCapability.TRANSACTIONS],
        required_settings=["schwab_app_key", "schwab_app_secret"],
    ),
    # ... more providers
]
```

**Registry-Driven Container**:

The container now uses the registry as its source of truth:

- **Provider lookup**: `get_provider_metadata(slug)` validates provider exists
- **OAuth filtering**: `get_oauth_providers()` replaces manual `OAUTH_PROVIDERS` set
- **Settings validation**: Uses `metadata.required_settings` for centralized checks
- **Lazy instantiation**: Match/case still handles concrete implementations

### Benefits

#### Developer Experience

- **Single entry point**: Add provider to registry → automatic wiring
- **Self-documenting**: Metadata includes display names, categories, capabilities
- **Type safety**: Enums prevent typos, IDE autocomplete works

#### Maintainability

- **Zero drift**: Registry is single source of truth
- **Explicit capabilities**: What each provider supports is visible in code
- **Centralized validation**: Required settings in one place

#### Testing

- **Self-enforcing**: Tests fail if registry incomplete
- **Gap detection**: Automated tests verify all providers have metadata
- **No manual checks**: Compliance verified on every test run

### Architecture Alignment

The Provider Integration Registry follows Dashtam's hexagonal architecture principles:

- **Domain layer**: Registry defines provider metadata and enums (`src/domain/providers/registry.py`)
- **Infrastructure layer**: Concrete provider implementations (`src/infrastructure/providers/`)
- **Application layer**: Container uses registry to wire dependencies (`src/core/container/providers.py`)

The registry respects the dependency rule: Domain defines the catalog, infrastructure provides implementations, application layer orchestrates.

## Registry Structure

### File Location

- **Registry**: `src/domain/providers/registry.py`
- **Exports**: `src/domain/providers/__init__.py`

### Core Components

#### 1. ProviderCategory Enum

Classifies providers by financial service type.

```python
class ProviderCategory(str, Enum):
    """Provider categories for organization."""

    BROKERAGE = "brokerage"
    BANK = "bank"
    CRYPTO = "crypto"
    RETIREMENT = "retirement"
    INVESTMENT = "investment"
    OTHER = "other"
```

**Usage**: Organizational grouping, future filtering in UI.

#### 2. ProviderAuthType Enum

Defines authentication mechanism for each provider.

```python
class ProviderAuthType(str, Enum):
    """Provider authentication types."""

    OAUTH = "oauth"              # OAuth 2.0 flow
    API_KEY = "api_key"          # Direct API key authentication
    FILE_IMPORT = "file_import"  # CSV/file-based import
    LINK_TOKEN = "link_token"    # Third-party link token (e.g., Plaid)
    CERTIFICATE = "certificate"  # Certificate-based auth
```

**Usage**:

- Container determines which provider factory to use
- OAuth callback routes registered only for OAuth providers
- Documentation generation for auth setup

#### 3. ProviderMetadata Dataclass

Central metadata structure for each provider.

```python
@dataclass(frozen=True, kw_only=True)
class ProviderMetadata:
    """Metadata for a provider integration.
    
    Attributes:
        slug: Unique provider identifier (from Provider enum).
        display_name: Human-readable provider name.
        category: Provider category (BROKERAGE, BANK, etc.).
        auth_type: Authentication mechanism.
        capabilities: Supported features (ACCOUNTS, TRANSACTIONS, etc.).
        required_settings: Environment variables required for this provider.
    """

    slug: Provider
    display_name: str
    category: ProviderCategory
    auth_type: ProviderAuthType
    capabilities: list[ProviderCapability]
    required_settings: list[str]
```

**Design Decisions**:

- `frozen=True`: Immutable after creation (registry entries are read-only)
- `kw_only=True`: Forces keyword arguments for clarity
- `required_settings`: Lists env var names without prefixes (e.g., `"schwab_app_key"` not `"SCHWAB_APP_KEY"`)

#### 4. PROVIDER_REGISTRY

The single source of truth for all providers.

```python
PROVIDER_REGISTRY: list[ProviderMetadata] = [
    # OAuth providers
    ProviderMetadata(
        slug=Provider.SCHWAB,
        display_name="Charles Schwab",
        category=ProviderCategory.BROKERAGE,
        auth_type=ProviderAuthType.OAUTH,
        capabilities=[ProviderCapability.ACCOUNTS, ProviderCapability.TRANSACTIONS],
        required_settings=["schwab_app_key", "schwab_app_secret"],
    ),
    # API key providers
    ProviderMetadata(
        slug=Provider.ALPACA,
        display_name="Alpaca Markets",
        category=ProviderCategory.BROKERAGE,
        auth_type=ProviderAuthType.API_KEY,
        capabilities=[ProviderCapability.ACCOUNTS, ProviderCapability.TRANSACTIONS],
        required_settings=[],  # API key passed per-request
    ),
    # File import providers
    ProviderMetadata(
        slug=Provider.CHASE_FILE,
        display_name="Chase (File Import)",
        category=ProviderCategory.BANK,
        auth_type=ProviderAuthType.FILE_IMPORT,
        capabilities=[ProviderCapability.TRANSACTIONS],
        required_settings=[],  # No persistent credentials
    ),
]
```

**Ordering**: Grouped by auth type for readability.

### Helper Functions

The registry provides 5 helper functions for common queries.

#### 1. get_provider_metadata

Look up metadata for a specific provider.

```python
def get_provider_metadata(slug: Provider) -> ProviderMetadata:
    """Retrieve metadata for a specific provider.
    
    Args:
        slug: Provider identifier.
        
    Returns:
        Provider metadata.
        
    Raises:
        ValueError: If provider not found in registry.
    """
```

**Usage**: Container validation, settings checks.

#### 2. get_all_provider_slugs

Get list of all registered provider slugs.

```python
def get_all_provider_slugs() -> list[Provider]:
    """Get all registered provider slugs."""
```

**Usage**: API endpoint listings, documentation generation.

#### 3. get_oauth_providers

Get set of OAuth provider slugs.

```python
def get_oauth_providers() -> set[Provider]:
    """Get all OAuth providers.
    
    Returns:
        Set of OAuth provider slugs.
    """
```

**Usage**: Container's `is_oauth_provider()`, OAuth callback route registration.

#### 4. get_providers_by_category

Filter providers by category.

```python
def get_providers_by_category(category: ProviderCategory) -> list[ProviderMetadata]:
    """Get all providers in a category.
    
    Args:
        category: Provider category to filter by.
        
    Returns:
        List of matching provider metadata.
    """
```

**Usage**: Future UI grouping, provider discovery.

#### 5. get_statistics

Get registry statistics for testing/auditing.

```python
def get_statistics() -> dict[str, int]:
    """Get registry statistics.
    
    Returns:
        Dict with total providers, OAuth count, category counts.
    """
```

**Usage**: Compliance tests, monitoring dashboards.

## Current Providers

### Registered Providers (3)

| Slug | Display Name | Category | Auth Type | Capabilities | Settings |
|------|--------------|----------|-----------|--------------|----------|
| `SCHWAB` | Charles Schwab | Brokerage | OAuth | Accounts, Transactions | `schwab_app_key`, `schwab_app_secret` |
| `ALPACA` | Alpaca Markets | Brokerage | API Key | Accounts, Transactions | None (per-request) |
| `CHASE_FILE` | Chase (File Import) | Bank | File Import | Transactions | None (file-based) |

### Provider Distribution

**By Category**:

- Brokerage: 2 (Schwab, Alpaca)
- Bank: 1 (Chase File)

**By Auth Type**:

- OAuth: 1 (Schwab)
- API Key: 1 (Alpaca)
- File Import: 1 (Chase File)

**Statistics** (as of v1.6.0):

```python
{
    "total_providers": 3,
    "oauth_providers": 1,
    "categories": {
        "brokerage": 2,
        "bank": 1
    }
}
```

## Adding New Providers

### Prerequisites

Before adding a provider to the registry:

1. **Provider enum entry**: Add to `src/domain/providers/enums.py`
2. **Infrastructure implementation**: Create provider class in `src/infrastructure/providers/`
3. **Settings configuration**: Define required env vars
4. **Database seed**: Add provider entry to `alembic/seeds/provider_seeder.py`

### Step-by-Step Process

#### Step 1: Add to Registry

Add entry to `PROVIDER_REGISTRY` in `src/domain/providers/registry.py`:

```python
PROVIDER_REGISTRY: list[ProviderMetadata] = [
    # ... existing providers
    ProviderMetadata(
        slug=Provider.FIDELITY,
        display_name="Fidelity Investments",
        category=ProviderCategory.BROKERAGE,
        auth_type=ProviderAuthType.OAUTH,
        capabilities=[
            ProviderCapability.ACCOUNTS,
            ProviderCapability.TRANSACTIONS,
            ProviderCapability.HOLDINGS,
        ],
        required_settings=["fidelity_client_id", "fidelity_client_secret"],
    ),
]
```

#### Step 2: Update Container Factory

Add provider case to `get_provider()` in `src/core/container/providers.py`:

```python
match slug:
    case Provider.FIDELITY:
        return FidelityProvider(
            client_id=settings.fidelity_client_id,
            client_secret=settings.fidelity_client_secret,
        )
    # ... other cases
```

#### Step 3: Run Self-Enforcing Tests

```bash
make test-unit FILE="tests/unit/test_provider_registry_compliance.py"
```

Tests automatically verify:

- ✅ Provider in registry
- ✅ Display name present
- ✅ Capabilities defined
- ✅ Required settings specified
- ✅ OAuth filtering correct (if OAuth)
- ✅ Category valid

#### Step 4: Register OAuth Callback (if OAuth)

OAuth providers automatically included in callback routes via registry lookup. No manual registration needed.

### Registry Entry Templates

#### OAuth Provider

```python
ProviderMetadata(
    slug=Provider.PROVIDER_NAME,
    display_name="Provider Display Name",
    category=ProviderCategory.BROKERAGE,  # or BANK, CRYPTO, etc.
    auth_type=ProviderAuthType.OAUTH,
    capabilities=[
        ProviderCapability.ACCOUNTS,
        ProviderCapability.TRANSACTIONS,
        ProviderCapability.HOLDINGS,  # Optional
    ],
    required_settings=["provider_client_id", "provider_client_secret"],
)
```

#### API Key Provider

```python
ProviderMetadata(
    slug=Provider.PROVIDER_NAME,
    display_name="Provider Display Name",
    category=ProviderCategory.BROKERAGE,
    auth_type=ProviderAuthType.API_KEY,
    capabilities=[ProviderCapability.ACCOUNTS, ProviderCapability.TRANSACTIONS],
    required_settings=[],  # API keys typically passed per-request
)
```

#### File Import Provider

```python
ProviderMetadata(
    slug=Provider.PROVIDER_NAME,
    display_name="Provider Display Name",
    category=ProviderCategory.BANK,
    auth_type=ProviderAuthType.FILE_IMPORT,
    capabilities=[ProviderCapability.TRANSACTIONS],  # Typically transactions only
    required_settings=[],  # No persistent credentials
)
```

### Validation

The container's `get_provider()` now validates providers using the registry:

1. **Registry lookup**: Checks provider exists in registry
2. **Settings validation**: Verifies required settings present
3. **Lazy instantiation**: Creates provider instance only when needed

```python
def get_provider(slug: Provider) -> ProviderProtocol:
    """Get provider implementation (Registry-Driven).
    
    Validates provider exists in registry and required settings are present.
    """
    # Step 1: Registry validation
    metadata = get_provider_metadata(slug)  # Raises ValueError if not in registry
    
    # Step 2: Settings validation
    settings = get_settings()
    for setting in metadata.required_settings:
        if not hasattr(settings, setting) or not getattr(settings, setting):
            raise ValueError(f"Missing required setting: {setting}")
    
    # Step 3: Lazy instantiation
    match slug:
        case Provider.SCHWAB:
            return SchwabProvider(...)
        # ... other providers
```

## Helper Functions

### Function Reference

| Function | Purpose | Returns | Usage |
|----------|---------|---------|-------|
| `get_provider_metadata(slug)` | Look up provider metadata | `ProviderMetadata` | Container validation, settings checks |
| `get_all_provider_slugs()` | List all registered providers | `list[Provider]` | API listings, documentation |
| `get_oauth_providers()` | Get OAuth provider set | `set[Provider]` | OAuth callback routing |
| `get_providers_by_category(cat)` | Filter by category | `list[ProviderMetadata]` | UI grouping, discovery |
| `get_statistics()` | Registry statistics | `dict[str, int]` | Compliance tests, monitoring |

### Usage Examples

#### Container Integration

```python
# Before: Manual set (drift risk)
OAUTH_PROVIDERS = {"schwab"}  # Could diverge from reality

# After: Registry-driven (zero drift)
def is_oauth_provider(slug: Provider) -> bool:
    """Check if provider uses OAuth (Registry-Driven)."""
    return slug in get_oauth_providers()
```

#### Settings Validation

```python
# Before: Hardcoded checks
if slug == Provider.SCHWAB:
    if not settings.schwab_app_key or not settings.schwab_app_secret:
        raise ValueError("Missing Schwab credentials")

# After: Registry-driven
metadata = get_provider_metadata(slug)
for setting in metadata.required_settings:
    if not getattr(settings, setting, None):
        raise ValueError(f"Missing required setting: {setting}")
```

#### OAuth Callback Registration

```python
# Get all OAuth providers for callback routes
oauth_providers = get_oauth_providers()
for provider_slug in oauth_providers:
    metadata = get_provider_metadata(provider_slug)
    register_callback(provider_slug, f"/oauth/{provider_slug.value}/callback")
```

## Testing

### Test Strategy

The Provider Integration Registry uses a **self-enforcing test strategy** where compliance tests automatically verify registry completeness.

**Test Location**: `tests/unit/test_provider_registry_compliance.py`

**Test Count**: 19 tests (18 passed, 1 skipped)

**Coverage**: 100% for `src/domain/providers/registry.py`

### Test Classes

#### 1. TestProviderRegistryCompleteness

Verifies all providers have required metadata.

**Tests** (10):

- `test_all_providers_have_display_names`: Every provider has human-readable name
- `test_registry_slugs_are_unique`: No duplicate slugs
- `test_all_providers_have_capabilities`: Every provider defines at least one capability
- `test_all_providers_have_required_settings`: Settings list present (empty is valid)
- `test_oauth_providers_match_registry`: OAuth filtering accurate
- `test_get_provider_metadata_returns_correct_data`: Metadata lookup works
- `test_get_oauth_providers_filters_correctly`: OAuth set contains only OAuth providers
- `test_get_statistics_accurate`: Statistics helper returns correct counts
- `test_provider_categories_valid`: All categories are recognized enum values
- `test_all_providers_can_be_instantiated`: (Skipped - requires settings validation)

#### 2. TestProviderRegistryIntegration

Tests container integration with registry.

**Tests** (4):

- `test_is_oauth_provider_matches_registry`: Container's OAuth check uses registry
- `test_get_providers_by_category_returns_correct_providers`: Category filtering works
- `test_container_fails_for_unknown_provider`: Unknown provider raises ValueError
- `test_container_error_message_lists_supported_providers`: Error message helpful

#### 3. TestProviderRegistryStatistics

Snapshot tests for current provider distribution.

**Tests** (5):

- `test_current_provider_count`: Registry contains 3 providers (as of v1.6.0)
- `test_current_oauth_provider_count`: 1 OAuth provider (Schwab)
- `test_schwab_in_registry`: Schwab explicitly registered
- `test_alpaca_in_registry`: Alpaca explicitly registered
- `test_chase_file_in_registry`: Chase File explicitly registered

**Purpose**: These tests document the current state and fail when new providers are added without updating the expected counts.

### Self-Enforcing Pattern

When adding a new provider:

1. **Add to registry** → Tests automatically verify completeness
2. **Run tests** → Fails if metadata incomplete
3. **Add missing metadata** → Tests pass
4. **Update snapshot tests** → Document new state

**Example Failure** (incomplete metadata):

```python
# If you add this to registry:
ProviderMetadata(
    slug=Provider.FIDELITY,
    display_name="Fidelity",
    category=ProviderCategory.BROKERAGE,
    auth_type=ProviderAuthType.OAUTH,
    capabilities=[],  # ❌ EMPTY - test will fail
    required_settings=["fidelity_client_id", "fidelity_client_secret"],
)
```

**Test output**:

```text
FAILED test_all_providers_have_capabilities
AssertionError: Provider FIDELITY has no capabilities defined
```

### Running Tests

```bash
# Run registry compliance tests only
make test-unit FILE="tests/unit/test_provider_registry_compliance.py"

# Run all tests with coverage
make test

# Check registry coverage specifically
docker compose -f compose/docker-compose.test.yml exec -T app \
  uv run pytest tests/unit/test_provider_registry_compliance.py \
  --cov=src/domain/providers \
  --cov-report=term-missing
```

### Coverage Target

- **Registry module**: 100% (achieved ✅)
- **Container providers module**: 95%+ (part of full test suite)

## Future Enhancements

### Potential Improvements

#### 1. Dynamic Capability Detection

**Current**: Capabilities manually specified in registry.

**Future**: Providers self-report capabilities via protocol.

```python
class ProviderProtocol(Protocol):
    def get_capabilities(self) -> list[ProviderCapability]:
        """Return supported capabilities."""
```

**Benefit**: Registry automatically synchronized with provider implementation.

**Tradeoff**: More complex, requires provider instances to determine capabilities.

#### 2. Provider Configuration Schemas

**Current**: `required_settings` is a list of strings.

**Future**: Use Pydantic models for type-safe provider configuration.

```python
class SchwabConfig(BaseModel):
    app_key: SecretStr
    app_secret: SecretStr
    base_url: HttpUrl = "https://api.schwabapi.com"

@dataclass
class ProviderMetadata:
    # ...
    config_schema: type[BaseModel]
```

**Benefit**: Type-safe configuration, validation at startup.

#### 3. Provider Discovery API

**Current**: Providers statically defined in registry.

**Future**: REST API endpoint for provider discovery.

```http
GET /api/v1/providers
{
  "providers": [
    {
      "slug": "schwab",
      "display_name": "Charles Schwab",
      "category": "brokerage",
      "auth_type": "oauth",
      "capabilities": ["accounts", "transactions"]
    }
  ]
}
```

**Benefit**: Frontend can dynamically render provider selection UI.

#### 4. Provider Health Checks

**Current**: No provider availability tracking.

**Future**: Registry includes health check endpoints.

```python
@dataclass
class ProviderMetadata:
    # ...
    health_check_url: str | None = None
    health_check_interval: int = 300  # seconds
```

**Benefit**: Monitor provider API availability, surface outages to users.

#### 5. Provider Feature Flags

**Current**: Providers always enabled if in registry.

**Future**: Feature flags for gradual rollouts.

```python
@dataclass
class ProviderMetadata:
    # ...
    enabled: bool = True
    beta: bool = False
    min_version: str | None = None  # Minimum Dashtam version required
```

**Benefit**: Disable problematic providers without code changes, beta testing.

### Migration Considerations

When implementing enhancements:

1. **Backward compatibility**: Existing registry entries must work without modification
2. **Self-enforcing tests**: Add compliance tests for new metadata fields
3. **Documentation**: Update architecture docs and provider guides
4. **Default values**: New fields should have sensible defaults (no breaking changes)

### Non-Goals

The Provider Integration Registry is **NOT** intended for:

- **Runtime plugin loading**: Providers are statically compiled, not dynamically loaded
- **Third-party provider SDKs**: Registry is for Dashtam-native providers only
- **Provider versioning**: Single version of each provider in registry
- **Provider dependencies**: Registry doesn't model provider-to-provider dependencies

## References

- **Pattern Documentation**: `docs/architecture/registry.md`
- **Provider Guide**: `docs/guides/adding-providers.md`
- **Domain Events Registry**: `docs/architecture/domain-events.md` (F7.7 - similar pattern)
- **Provider Enums**: `src/domain/providers/enums.py`
- **Provider Capabilities**: `src/domain/providers/capabilities.py`

## Changelog

- **v1.6.0** (2025-12-31): Initial Provider Integration Registry implementation (F8.1)

**Last Updated**: 2026-01-10
