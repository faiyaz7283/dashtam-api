# Adding New Providers Guide

Comprehensive guide for integrating new financial providers into Dashtam.

---

## Overview

**Purpose**: This guide provides a complete, step-by-step process for adding new financial providers to Dashtam. Following this guide ensures architectural compliance, proper testing, and maintainable code.

**Target Audience**: Developers adding new provider integrations.

**Time Estimate**: 2-4 days depending on provider API complexity.

### What You'll Create

Adding a new provider involves creating/modifying these components:

| Layer | Components | Files |
|-------|------------|-------|
| Infrastructure | Provider adapter, API clients, Mappers | 5-8 files |
| Configuration | Settings, Environment variables | 2-4 files |
| Container | Factory registration | 1 file |
| Database | Provider seed data | 1 file |
| Tests | Unit, API, Integration tests | 4-6 files |
| Documentation | Provider-specific guide | 1 file |

---

## Phase 1: Pre-Development Research

Before writing code, gather this information about the provider:

### 1.1 API Documentation Review

- [ ] Locate provider's API documentation
- [ ] Identify API base URLs (sandbox vs production)
- [ ] Document rate limits and quotas
- [ ] Note any IP whitelisting requirements

### 1.2 Authentication Mechanism

Identify which credential type applies:

| Credential Type | Description | Examples |
|-----------------|-------------|----------|
| `oauth2` | OAuth 2.0 Authorization Code flow | Schwab, Fidelity, TD Ameritrade |
| `api_key` | Static API key/secret pair | Some market data providers |
| `link_token` | Third-party linking flow | Aggregators with embedded flows |
| `certificate` | mTLS certificate-based | Institutional APIs |
| `custom` | Provider-specific mechanism | Varies |

Document:

- [ ] Authentication mechanism type
- [ ] Token lifetimes (access, refresh)
- [ ] Token refresh behavior (rotation? same token?)
- [ ] Required scopes/permissions

### 1.3 Data Model Mapping Analysis

Review provider's data structures and map to Dashtam's domain:

**Accounts Mapping:**

| Provider Field | Dashtam Field | Transformation |
|----------------|---------------|----------------|
| `accountId` | `provider_account_id` | Direct |
| `type` | `account_type` | Map to `AccountType` enum |
| `balance` | `balance` (Money) | Create Money value object |
| ... | ... | ... |

**Transactions Mapping:**

| Provider Field | Dashtam Field | Transformation |
|----------------|---------------|----------------|
| `transactionId` | `provider_transaction_id` | Direct |
| `type` | `transaction_type` | Map to `TransactionType` enum |
| `subtype` | `subtype` | Map to `TransactionSubtype` enum |
| ... | ... | ... |

### 1.4 Checklist Completion

Before proceeding, confirm:

- [ ] API credentials obtained (sandbox account)
- [ ] OAuth redirect URI registered (if OAuth)
- [ ] Data mapping analysis complete
- [ ] Rate limits documented

---

## Phase 2: Configuration Setup

### 2.1 Add Provider Settings

Add settings to `src/core/config.py`:

```python
# Provider: {NewProvider} Configuration
{provider}_api_key: str | None = Field(
    default=None,
    description="{Provider Name} API key",
)
{provider}_api_secret: str | None = Field(
    default=None,
    description="{Provider Name} API secret",
)
{provider}_redirect_uri: str | None = Field(
    default=None,
    description="{Provider Name} OAuth redirect URI",
)
{provider}_environment: str = Field(
    default="sandbox",
    description="{Provider Name} environment (sandbox/production)",
)
```

### 2.2 Update Environment Files

Add to all `.env.*.example` files:

```bash
# {Provider Name} Configuration
{PROVIDER}_API_KEY=
{PROVIDER}_API_SECRET=
{PROVIDER}_REDIRECT_URI=https://dashtam.local/oauth/{provider}/callback
{PROVIDER}_ENVIRONMENT=sandbox
```

Files to update:

- `env/.env.dev.example`
- `env/.env.test.example`
- `env/.env.ci.example`
- `env/.env.prod.example`

---

## Phase 3: Infrastructure Implementation

### 3.1 Create Provider Directory Structure

```bash
mkdir -p src/infrastructure/providers/{provider}
mkdir -p src/infrastructure/providers/{provider}/api
mkdir -p src/infrastructure/providers/{provider}/mappers
```

Create this structure:

```text
src/infrastructure/providers/{provider}/
├── __init__.py                    # Exports: {Provider}Provider
├── {provider}_provider.py         # Main provider adapter
├── api/
│   ├── __init__.py               # Exports: API clients
│   ├── accounts_api.py           # Account API client
│   └── transactions_api.py       # Transaction API client
└── mappers/
    ├── __init__.py               # Exports: Mappers
    ├── account_mapper.py         # Account data mapper
    └── transaction_mapper.py     # Transaction data mapper
```

### 3.2 Implement Provider Adapter

Create `src/infrastructure/providers/{provider}/{provider}_provider.py`:

```python
"""
{Provider Name} provider adapter.

Implements ProviderProtocol for {Provider Name} API integration.
Handles OAuth flow, account sync, and transaction sync.

Reference:
    - {Provider API docs URL}
    - docs/architecture/provider-integration-architecture.md
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import structlog
from src.core.result import Failure, Result, Success
from src.domain.errors.provider_error import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from src.infrastructure.providers.provider_types import (
    OAuthTokens,
    ProviderAccountData,
    ProviderTransactionData,
)

if TYPE_CHECKING:
    from datetime import date
    from src.core.config import Settings

logger = structlog.get_logger(__name__)


class {Provider}Provider:
    """
    {Provider Name} provider adapter implementing ProviderProtocol.
    
    Responsibilities:
        - OAuth 2.0 token exchange and refresh
        - Account data fetching via {Provider} API
        - Transaction data fetching with date filtering
        
    All methods return Result types (railway-oriented programming).
    
    Usage:
        provider = {Provider}Provider(settings=settings)
        result = await provider.exchange_code_for_tokens(code)
        if isinstance(result, Success):
            tokens = result.value
    """
    
    # API Base URLs
    _OAUTH_BASE_URL = "https://api.{provider}.com/oauth"
    _API_BASE_URL = "https://api.{provider}.com/v1"
    
    def __init__(self, settings: "Settings") -> None:
        """Initialize provider with settings.
        
        Args:
            settings: Application settings with provider credentials.
        """
        self._settings = settings
        self._logger = logger.bind(provider=self.slug)
    
    @property
    def slug(self) -> str:
        """Unique provider identifier."""
        return "{provider}"
    
    # =========================================================================
    # OAuth Methods
    # =========================================================================
    
    def get_authorization_url(self, state: str) -> str:
        """Generate OAuth authorization URL.
        
        Args:
            state: CSRF token (stored in session, validated on callback).
            
        Returns:
            Full authorization URL for redirect.
        """
        from urllib.parse import urlencode
        
        params = {
            "response_type": "code",
            "client_id": self._settings.{provider}_api_key,
            "redirect_uri": self._settings.{provider}_redirect_uri,
            "scope": "accounts transactions",  # Adjust per provider
            "state": state,
        }
        return f"{self._OAUTH_BASE_URL}/authorize?{urlencode(params)}"
    
    async def exchange_code_for_tokens(
        self, authorization_code: str
    ) -> Result[OAuthTokens, ProviderAuthenticationError | ProviderUnavailableError]:
        """Exchange authorization code for access and refresh tokens.
        
        Args:
            authorization_code: Code from OAuth callback.
            
        Returns:
            Success(OAuthTokens) if exchange successful.
            Failure(ProviderAuthenticationError) if code invalid/expired.
            Failure(ProviderUnavailableError) if provider API down.
        """
        self._logger.info("exchanging_code_for_tokens")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._OAUTH_BASE_URL}/token",
                    headers=self._get_auth_headers(),
                    data={
                        "grant_type": "authorization_code",
                        "code": authorization_code,
                        "redirect_uri": self._settings.{provider}_redirect_uri,
                    },
                    timeout=30.0,
                )
            except httpx.RequestError as e:
                self._logger.error("token_exchange_network_error", error=str(e))
                return Failure(error=ProviderUnavailableError(
                    message=f"{self.slug} API unavailable: {e}",
                ))
            
            if response.status_code != 200:
                self._logger.warning(
                    "token_exchange_failed",
                    status_code=response.status_code,
                )
                return Failure(error=ProviderAuthenticationError(
                    message=f"Token exchange failed: {response.status_code}",
                ))
            
            data = response.json()
            return Success(value=OAuthTokens(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_in=data.get("expires_in", 1800),
                token_type=data.get("token_type", "Bearer"),
                scope=data.get("scope"),
            ))
    
    async def refresh_access_token(
        self, refresh_token: str
    ) -> Result[OAuthTokens, ProviderAuthenticationError | ProviderUnavailableError]:
        """Refresh access token using refresh token.
        
        Handles token rotation detection - returns new refresh_token
        only if provider rotated it.
        
        Args:
            refresh_token: Current refresh token.
            
        Returns:
            Success(OAuthTokens) with new tokens.
            Failure(ProviderAuthenticationError) if refresh token invalid.
            Failure(ProviderUnavailableError) if provider API down.
        """
        self._logger.info("refreshing_access_token")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._OAUTH_BASE_URL}/token",
                    headers=self._get_auth_headers(),
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                    timeout=30.0,
                )
            except httpx.RequestError as e:
                self._logger.error("token_refresh_network_error", error=str(e))
                return Failure(error=ProviderUnavailableError(
                    message=f"{self.slug} API unavailable: {e}",
                ))
            
            if response.status_code != 200:
                self._logger.warning(
                    "token_refresh_failed",
                    status_code=response.status_code,
                )
                return Failure(error=ProviderAuthenticationError(
                    message=f"Token refresh failed: {response.status_code}",
                ))
            
            data = response.json()
            
            # Only include refresh_token if provider rotated it
            new_refresh_token = data.get("refresh_token")
            
            return Success(value=OAuthTokens(
                access_token=data["access_token"],
                refresh_token=new_refresh_token,  # None if no rotation
                expires_in=data.get("expires_in", 1800),
                token_type=data.get("token_type", "Bearer"),
                scope=data.get("scope"),
            ))
    
    # =========================================================================
    # Data Fetching Methods
    # =========================================================================
    
    async def fetch_accounts(
        self, access_token: str
    ) -> Result[
        list[ProviderAccountData],
        ProviderAuthenticationError | ProviderUnavailableError,
    ]:
        """Fetch all accounts for authenticated user.
        
        Args:
            access_token: Valid access token.
            
        Returns:
            Success(list[ProviderAccountData]) with account data.
            Failure(ProviderAuthenticationError) if token invalid.
            Failure(ProviderUnavailableError) if provider API down.
        """
        from src.infrastructure.providers.{provider}.mappers import (
            {Provider}AccountMapper,
        )
        
        self._logger.info("fetching_accounts")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._API_BASE_URL}/accounts",
                    headers=self._get_bearer_headers(access_token),
                    timeout=30.0,
                )
            except httpx.RequestError as e:
                self._logger.error("fetch_accounts_network_error", error=str(e))
                return Failure(error=ProviderUnavailableError(
                    message=f"{self.slug} API unavailable: {e}",
                ))
            
            if response.status_code == 401:
                return Failure(error=ProviderAuthenticationError(
                    message="Access token expired or invalid",
                ))
            
            if response.status_code != 200:
                return Failure(error=ProviderUnavailableError(
                    message=f"Failed to fetch accounts: {response.status_code}",
                ))
            
            data = response.json()
            mapper = {Provider}AccountMapper()
            accounts = [mapper.map(account) for account in data.get("accounts", [])]
            
            self._logger.info("accounts_fetched", count=len(accounts))
            return Success(value=accounts)
    
    async def fetch_transactions(
        self,
        access_token: str,
        provider_account_id: str,
        start_date: "date | None" = None,
        end_date: "date | None" = None,
    ) -> Result[
        list[ProviderTransactionData],
        ProviderAuthenticationError | ProviderUnavailableError,
    ]:
        """Fetch transactions for a specific account.
        
        Args:
            access_token: Valid access token.
            provider_account_id: Provider's account identifier.
            start_date: Optional start date for filtering.
            end_date: Optional end date for filtering.
            
        Returns:
            Success(list[ProviderTransactionData]) with transaction data.
            Failure(ProviderAuthenticationError) if token invalid.
            Failure(ProviderUnavailableError) if provider API down.
        """
        from src.infrastructure.providers.{provider}.mappers import (
            {Provider}TransactionMapper,
        )
        
        self._logger.info(
            "fetching_transactions",
            account_id=provider_account_id,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
        )
        
        params = {}
        if start_date:
            params["startDate"] = start_date.isoformat()
        if end_date:
            params["endDate"] = end_date.isoformat()
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._API_BASE_URL}/accounts/{provider_account_id}/transactions",
                    headers=self._get_bearer_headers(access_token),
                    params=params,
                    timeout=30.0,
                )
            except httpx.RequestError as e:
                self._logger.error("fetch_transactions_network_error", error=str(e))
                return Failure(error=ProviderUnavailableError(
                    message=f"{self.slug} API unavailable: {e}",
                ))
            
            if response.status_code == 401:
                return Failure(error=ProviderAuthenticationError(
                    message="Access token expired or invalid",
                ))
            
            if response.status_code != 200:
                return Failure(error=ProviderUnavailableError(
                    message=f"Failed to fetch transactions: {response.status_code}",
                ))
            
            data = response.json()
            mapper = {Provider}TransactionMapper()
            transactions = [
                mapper.map(txn) for txn in data.get("transactions", [])
            ]
            
            self._logger.info("transactions_fetched", count=len(transactions))
            return Success(value=transactions)
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _get_auth_headers(self) -> dict[str, str]:
        """Get HTTP Basic Auth headers for token endpoints."""
        import base64
        
        credentials = (
            f"{self._settings.{provider}_api_key}:"
            f"{self._settings.{provider}_api_secret}"
        )
        b64 = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
    
    def _get_bearer_headers(self, access_token: str) -> dict[str, str]:
        """Get Bearer token headers for API endpoints."""
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
```

### 3.3 Implement Account Mapper

Create `src/infrastructure/providers/{provider}/mappers/account_mapper.py`:

```python
"""
{Provider Name} account data mapper.

Maps {Provider} account API responses to Dashtam's ProviderAccountData.
Handles all field transformations and type conversions.
"""

from decimal import Decimal

from src.infrastructure.providers.provider_types import ProviderAccountData


class {Provider}AccountMapper:
    """Maps {Provider} account data to ProviderAccountData.
    
    Responsibilities:
        - Field name mapping (provider → Dashtam)
        - Type conversions (strings → Decimal, etc.)
        - Account type normalization
        - Missing field handling
    """
    
    # Map provider account types to Dashtam AccountType values
    _ACCOUNT_TYPE_MAP = {
        "BROKERAGE": "brokerage",
        "IRA": "traditional_ira",
        "ROTH_IRA": "roth_ira",
        "CHECKING": "checking",
        "SAVINGS": "savings",
        # Add more mappings as needed
    }
    
    def map(self, raw: dict) -> ProviderAccountData:
        """Map provider account response to ProviderAccountData.
        
        Args:
            raw: Raw account data from provider API.
            
        Returns:
            ProviderAccountData with normalized fields.
        """
        # Map account type (use lowercase for unknown types)
        provider_type = raw.get("type", "").upper()
        account_type = self._ACCOUNT_TYPE_MAP.get(
            provider_type, provider_type.lower()
        )
        
        return ProviderAccountData(
            provider_account_id=raw["accountId"],
            account_number_masked=self._mask_account_number(
                raw.get("accountNumber", "")
            ),
            name=raw.get("displayName", raw.get("accountId", "")),
            account_type=account_type,
            balance=Decimal(str(raw.get("balance", 0))),
            available_balance=(
                Decimal(str(raw["availableBalance"]))
                if "availableBalance" in raw
                else None
            ),
            currency=raw.get("currency", "USD"),
            is_active=raw.get("isActive", True),
            raw_data=raw,
        )
    
    def _mask_account_number(self, account_number: str) -> str:
        """Mask account number for display (show last 4 digits)."""
        if len(account_number) <= 4:
            return account_number
        return "*" * (len(account_number) - 4) + account_number[-4:]
```

### 3.4 Implement Transaction Mapper

Create `src/infrastructure/providers/{provider}/mappers/transaction_mapper.py`:

```python
"""
{Provider Name} transaction data mapper.

Maps {Provider} transaction API responses to Dashtam's ProviderTransactionData.
Handles two-level type classification (type + subtype).
"""

from datetime import date
from decimal import Decimal

from src.infrastructure.providers.provider_types import ProviderTransactionData


class {Provider}TransactionMapper:
    """Maps {Provider} transaction data to ProviderTransactionData.
    
    Implements two-level classification:
        - transaction_type: High-level category (TRADE, TRANSFER, etc.)
        - subtype: Specific action (BUY, SELL, DEPOSIT, etc.)
    """
    
    # Map provider transaction types to Dashtam types
    _TYPE_MAP = {
        "BUY": ("trade", "buy"),
        "SELL": ("trade", "sell"),
        "DIVIDEND": ("income", "dividend"),
        "INTEREST": ("income", "interest"),
        "DEPOSIT": ("transfer", "deposit"),
        "WITHDRAWAL": ("transfer", "withdrawal"),
        "FEE": ("fee", "account_fee"),
        # Add more mappings
    }
    
    # Map provider status to Dashtam TransactionStatus
    _STATUS_MAP = {
        "COMPLETED": "settled",
        "PENDING": "pending",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
    }
    
    def map(self, raw: dict) -> ProviderTransactionData:
        """Map provider transaction response to ProviderTransactionData.
        
        Args:
            raw: Raw transaction data from provider API.
            
        Returns:
            ProviderTransactionData with normalized fields.
        """
        # Get type mapping (defaults to "other")
        provider_type = raw.get("type", "").upper()
        txn_type, subtype = self._TYPE_MAP.get(
            provider_type, ("other", "other")
        )
        
        # Map status
        provider_status = raw.get("status", "").upper()
        status = self._STATUS_MAP.get(provider_status, "settled")
        
        return ProviderTransactionData(
            provider_transaction_id=raw["transactionId"],
            transaction_type=txn_type,
            subtype=subtype,
            amount=Decimal(str(raw.get("amount", 0))),
            currency=raw.get("currency", "USD"),
            description=raw.get("description", ""),
            transaction_date=self._parse_date(raw.get("transactionDate")),
            settlement_date=self._parse_date(raw.get("settlementDate")),
            symbol=raw.get("symbol"),
            quantity=(
                Decimal(str(raw["quantity"]))
                if "quantity" in raw
                else None
            ),
            unit_price=(
                Decimal(str(raw["price"]))
                if "price" in raw
                else None
            ),
            commission=(
                Decimal(str(raw["commission"]))
                if "commission" in raw
                else None
            ),
            status=status,
            raw_data=raw,
        )
    
    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse date string to date object."""
        if not date_str:
            return None
        # Adjust format based on provider's date format
        return date.fromisoformat(date_str[:10])
```

### 3.5 Create Module Exports

Create `src/infrastructure/providers/{provider}/__init__.py`:

```python
"""
{Provider Name} provider integration.

Exports:
    {Provider}Provider: Main provider adapter implementing ProviderProtocol.
"""

from src.infrastructure.providers.{provider}.{provider}_provider import (
    {Provider}Provider,
)

__all__ = ["{Provider}Provider"]
```

Create `src/infrastructure/providers/{provider}/mappers/__init__.py`:

```python
"""
{Provider Name} data mappers.

Exports:
    {Provider}AccountMapper: Maps account data to ProviderAccountData.
    {Provider}TransactionMapper: Maps transaction data to ProviderTransactionData.
"""

from src.infrastructure.providers.{provider}.mappers.account_mapper import (
    {Provider}AccountMapper,
)
from src.infrastructure.providers.{provider}.mappers.transaction_mapper import (
    {Provider}TransactionMapper,
)

__all__ = ["{Provider}AccountMapper", "{Provider}TransactionMapper"]
```

---

## Phase 4: Container Registration

### 4.1 Register Provider in Factory

Update `src/core/container/providers.py`:

```python
def get_provider(slug: str) -> "ProviderProtocol":
    """Get financial provider adapter by slug."""
    match slug:
        case "schwab":
            from src.infrastructure.providers.schwab import SchwabProvider
            # ... existing code ...
            return SchwabProvider(settings=settings)
        
        case "{provider}":
            from src.infrastructure.providers.{provider} import {Provider}Provider
            
            # Validate required settings
            if not settings.{provider}_api_key or not settings.{provider}_api_secret:
                raise ValueError(
                    f"Provider '{slug}' not configured. "
                    "Set {PROVIDER}_API_KEY and {PROVIDER}_API_SECRET in environment."
                )
            
            return {Provider}Provider(settings=settings)
        
        case _:
            raise ValueError(f"Unknown provider: {slug}. Supported: 'schwab', '{provider}'")
```

---

## Phase 5: Database Seeding

### 5.1 Add Provider Seed

Update `alembic/seeds/provider_seeder.py`:

```python
DEFAULT_PROVIDERS = [
    # Existing Schwab entry...
    {
        "slug": "{provider}",
        "name": "{Provider Name}",
        "credential_type": "oauth2",  # or api_key, link_token, etc.
        "description": "Connect your {Provider Name} account to sync accounts and transactions.",
        "website_url": "https://www.{provider}.com",
        "is_active": True,  # Set False until fully implemented
    },
]
```

### 5.2 Run Migration

```bash
# Apply seed
make migrate
```

---

## Phase 6: Testing

### 6.1 Test File Structure

Create these test files:

```text
tests/
├── unit/
│   ├── test_infrastructure_{provider}_oauth.py      # OAuth flow tests
│   ├── test_infrastructure_{provider}_account_mapper.py  # Account mapper tests
│   └── test_infrastructure_{provider}_transaction_mapper.py  # Transaction mapper tests
├── api/
│   └── test_{provider}_oauth_callbacks.py           # API endpoint tests
└── integration/
    └── test_{provider}_sync_handlers.py             # Handler integration tests
```

### 6.2 Unit Tests: Provider OAuth (~20-30 tests)

Test coverage for `{provider}_provider.py`:

```python
"""
Unit tests for {Provider} OAuth methods.

Uses pytest-httpx to mock HTTP responses.
"""

import pytest
from httpx import Response
from pytest_httpx import HTTPXMock

from src.core.result import Failure, Success
from src.infrastructure.providers.{provider} import {Provider}Provider


class TestExchangeCodeForTokens:
    """Tests for exchange_code_for_tokens method."""
    
    async def test_success_returns_tokens(
        self, httpx_mock: HTTPXMock, provider: {Provider}Provider
    ):
        """Valid code returns access and refresh tokens."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.{provider}.com/oauth/token",
            json={
                "access_token": "test_access",
                "refresh_token": "test_refresh",
                "expires_in": 1800,
                "token_type": "Bearer",
            },
        )
        
        result = await provider.exchange_code_for_tokens("valid_code")
        
        assert isinstance(result, Success)
        assert result.value.access_token == "test_access"
        assert result.value.refresh_token == "test_refresh"
    
    async def test_invalid_code_returns_failure(
        self, httpx_mock: HTTPXMock, provider: {Provider}Provider
    ):
        """Invalid code returns authentication error."""
        httpx_mock.add_response(
            method="POST",
            url="https://api.{provider}.com/oauth/token",
            status_code=400,
            json={"error": "invalid_grant"},
        )
        
        result = await provider.exchange_code_for_tokens("invalid_code")
        
        assert isinstance(result, Failure)
    
    async def test_network_error_returns_unavailable(
        self, httpx_mock: HTTPXMock, provider: {Provider}Provider
    ):
        """Network error returns provider unavailable error."""
        httpx_mock.add_exception(httpx.RequestError("Connection failed"))
        
        result = await provider.exchange_code_for_tokens("code")
        
        assert isinstance(result, Failure)


class TestRefreshAccessToken:
    """Tests for refresh_access_token method."""
    
    async def test_success_no_rotation(
        self, httpx_mock: HTTPXMock, provider: {Provider}Provider
    ):
        """Token refresh without rotation returns None for refresh_token."""
        httpx_mock.add_response(
            method="POST",
            json={
                "access_token": "new_access",
                "expires_in": 1800,
            },  # No refresh_token in response
        )
        
        result = await provider.refresh_access_token("current_refresh")
        
        assert isinstance(result, Success)
        assert result.value.access_token == "new_access"
        assert result.value.refresh_token is None  # No rotation
    
    async def test_success_with_rotation(
        self, httpx_mock: HTTPXMock, provider: {Provider}Provider
    ):
        """Token refresh with rotation returns new refresh_token."""
        httpx_mock.add_response(
            method="POST",
            json={
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_in": 1800,
            },
        )
        
        result = await provider.refresh_access_token("current_refresh")
        
        assert isinstance(result, Success)
        assert result.value.refresh_token == "new_refresh"


@pytest.fixture
def provider(test_settings):
    """Create provider instance with test settings."""
    return {Provider}Provider(settings=test_settings)
```

### 6.3 Unit Tests: Mappers (~40-60 tests each)

Test coverage for mappers:

```python
"""
Unit tests for {Provider} account mapper.
"""

import pytest
from decimal import Decimal

from src.infrastructure.providers.{provider}.mappers import {Provider}AccountMapper


class TestAccountMapping:
    """Tests for account field mapping."""
    
    def test_maps_required_fields(self):
        """Maps all required fields correctly."""
        raw = {
            "accountId": "ACC123",
            "accountNumber": "1234567890",
            "displayName": "My Account",
            "type": "BROKERAGE",
            "balance": 10000.50,
            "currency": "USD",
        }
        
        mapper = {Provider}AccountMapper()
        result = mapper.map(raw)
        
        assert result.provider_account_id == "ACC123"
        assert result.account_number_masked == "******7890"
        assert result.name == "My Account"
        assert result.account_type == "brokerage"
        assert result.balance == Decimal("10000.50")
        assert result.currency == "USD"
    
    def test_maps_account_types(self):
        """Maps all known account types correctly."""
        test_cases = [
            ("BROKERAGE", "brokerage"),
            ("IRA", "traditional_ira"),
            ("ROTH_IRA", "roth_ira"),
            ("CHECKING", "checking"),
            ("UNKNOWN_TYPE", "unknown_type"),  # Falls through
        ]
        
        mapper = {Provider}AccountMapper()
        for provider_type, expected in test_cases:
            raw = {"accountId": "1", "type": provider_type}
            result = mapper.map(raw)
            assert result.account_type == expected
    
    def test_handles_missing_optional_fields(self):
        """Handles missing optional fields gracefully."""
        raw = {"accountId": "1", "type": "CHECKING"}
        
        mapper = {Provider}AccountMapper()
        result = mapper.map(raw)
        
        assert result.available_balance is None
        assert result.balance == Decimal("0")
```

### 6.4 API Tests: OAuth Callbacks (~10-15 tests)

```python
"""
API tests for {Provider} OAuth callback endpoint.

Uses real app with dependency overrides.
"""

import pytest
from starlette.testclient import TestClient

from src.main import app


class TestOAuthCallback:
    """Tests for /oauth/{provider}/callback endpoint."""
    
    def test_success_creates_connection(
        self, client: TestClient, mock_provider
    ):
        """Valid callback creates provider connection."""
        response = client.get(
            "/oauth/{provider}/callback",
            params={"code": "valid_code", "state": "valid_state"},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["provider_slug"] == "{provider}"
        assert data["status"] == "active"
    
    def test_missing_code_returns_400(self, client: TestClient):
        """Missing code parameter returns 400."""
        response = client.get(
            "/oauth/{provider}/callback",
            params={"state": "valid_state"},
        )
        
        assert response.status_code == 400
    
    def test_invalid_state_returns_400(self, client: TestClient):
        """Invalid state parameter returns 400 (CSRF protection)."""
        response = client.get(
            "/oauth/{provider}/callback",
            params={"code": "code", "state": "invalid_state"},
        )
        
        assert response.status_code == 400


@pytest.fixture
def client():
    """Test client with real app."""
    return TestClient(app)
```

### 6.5 Integration Tests: Sync Handlers (~10-15 tests)

```python
"""
Integration tests for {Provider} sync handlers.

Tests handler + real database persistence.
"""

import pytest
from uuid import uuid4

from src.application.commands import SyncAccounts, SyncTransactions
from src.core.container import get_sync_accounts_handler


class TestSyncAccountsHandler:
    """Integration tests for account sync with {Provider}."""
    
    async def test_syncs_accounts_to_database(
        self, db_session, mock_provider, connection_id
    ):
        """Syncs accounts from provider to database."""
        handler = get_sync_accounts_handler(db_session)
        
        result = await handler.handle(SyncAccounts(
            connection_id=connection_id,
            user_id=uuid4(),
        ))
        
        assert result.is_success()
        # Verify accounts persisted in database
```

### 6.6 Test Coverage Requirements

| Component | Minimum Coverage |
|-----------|------------------|
| Provider adapter | 90% |
| Account mapper | 95% |
| Transaction mapper | 95% |
| API endpoints | 85% |
| Sync handlers | 85% |

Run coverage check:

```bash
make test
# Check coverage report for provider files
```

---

## Phase 7: Quality Verification

### 7.1 Lint and Format

```bash
make lint
make format
```

### 7.2 Type Check

```bash
make type-check
```

### 7.3 Run All Tests

```bash
make test
```

### 7.4 Build Documentation

```bash
make docs-build
```

---

## Phase 8: Documentation

### 8.1 Create Provider Guide

Create `docs/guides/{provider}-integration.md`:

```markdown
# {Provider Name} Integration

Guide for connecting {Provider Name} accounts to Dashtam.

## Prerequisites

- {Provider Name} account
- API credentials from {Provider} developer portal

## Setup

1. Register application at {Provider Developer Portal URL}
2. Configure redirect URI: `https://dashtam.local/oauth/{provider}/callback`
3. Add credentials to environment:
   ```bash
   {PROVIDER}_API_KEY=your_api_key
   {PROVIDER}_API_SECRET=your_api_secret
   ```

## Connecting Account

1. Navigate to Settings → Connections
2. Click "Add {Provider Name}"
3. Log in to {Provider Name} and authorize access
4. Your accounts will sync automatically

## Supported Features

- Account sync
- Transaction history
- Automatic token refresh

## Troubleshooting

### "Token expired" error

Click "Reconnect" to re-authorize access.

### Missing transactions

{Provider Name} may have a delay in transaction availability.

```markdown

---

## Phase 9: Holdings Support (Optional)

If the provider supports holdings/positions data, implement these additional components.

### 9.1 Check Provider Capability

Not all providers support holdings. Check your provider's API documentation for:

- Position/holdings endpoint availability
- Data fields returned (quantity, cost basis, market value, etc.)
- Real-time vs end-of-day data

### 9.2 Implement fetch_holdings Method

Add to your provider adapter (`{provider}_provider.py`):

```python
async def fetch_holdings(
    self,
    access_token: str,
    provider_account_id: str,
) -> Result[
    list[ProviderHoldingData],
    ProviderAuthenticationError | ProviderUnavailableError,
]:
    """Fetch holdings (positions) for a specific account.
    
    Args:
        access_token: Valid access token.
        provider_account_id: Provider's account identifier.
        
    Returns:
        Success(list[ProviderHoldingData]) with holding data.
        Failure(ProviderAuthenticationError) if token invalid.
        Failure(ProviderUnavailableError) if provider API down.
    """
    from src.infrastructure.providers.{provider}.mappers import (
        {Provider}HoldingMapper,
    )
    
    self._logger.info(
        "fetching_holdings",
        account_id=provider_account_id,
    )
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{self._API_BASE_URL}/accounts/{provider_account_id}/positions",
                headers=self._get_bearer_headers(access_token),
                timeout=30.0,
            )
        except httpx.RequestError as e:
            self._logger.error("fetch_holdings_network_error", error=str(e))
            return Failure(error=ProviderUnavailableError(
                message=f"{self.slug} API unavailable: {e}",
            ))
        
        if response.status_code == 401:
            return Failure(error=ProviderAuthenticationError(
                message="Access token expired or invalid",
            ))
        
        if response.status_code != 200:
            return Failure(error=ProviderUnavailableError(
                message=f"Failed to fetch holdings: {response.status_code}",
            ))
        
        data = response.json()
        mapper = {Provider}HoldingMapper()
        holdings = mapper.map_holdings(data.get("positions", []))
        
        self._logger.info("holdings_fetched", count=len(holdings))
        return Success(value=holdings)
```

### 9.3 Implement Holding Mapper

Create `src/infrastructure/providers/{provider}/mappers/holding_mapper.py`:

```python
"""
{Provider Name} holding (position) mapper.

Maps {Provider} position API responses to ProviderHoldingData.
"""

from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from src.domain.protocols.provider_protocol import ProviderHoldingData

logger = structlog.get_logger(__name__)

# Provider asset type → Dashtam asset type mapping
{PROVIDER}_ASSET_TYPE_MAP: dict[str, str] = {
    "EQUITY": "equity",
    "STOCK": "equity",
    "ETF": "etf",
    "MUTUAL_FUND": "mutual_fund",
    "OPTION": "option",
    "FIXED_INCOME": "fixed_income",
    "BOND": "fixed_income",
    "CASH_EQUIVALENT": "cash_equivalent",
    "MONEY_MARKET": "cash_equivalent",
    "CRYPTO": "cryptocurrency",
    # Add provider-specific mappings
}


class {Provider}HoldingMapper:
    """Mapper for converting {Provider} position data to ProviderHoldingData.
    
    Handles:
    - Extracting data from provider's JSON structure
    - Mapping asset types to Dashtam types
    - Converting numeric values to Decimal
    - Generating unique position identifiers
    """
    
    def map_holding(self, data: dict[str, Any]) -> ProviderHoldingData | None:
        """Map single position JSON to ProviderHoldingData.
        
        Args:
            data: Single position object from provider API.
            
        Returns:
            ProviderHoldingData if mapping succeeds, None if invalid.
        """
        try:
            return self._map_holding_internal(data)
        except (KeyError, TypeError, InvalidOperation, ValueError) as e:
            logger.warning(
                "{provider}_holding_mapping_failed",
                error=str(e),
            )
            return None
    
    def map_holdings(
        self, data_list: list[dict[str, Any]]
    ) -> list[ProviderHoldingData]:
        """Map list of position JSON objects.
        
        Skips invalid positions, never raises exceptions.
        """
        holdings: list[ProviderHoldingData] = []
        for data in data_list:
            holding = self.map_holding(data)
            if holding is not None:
                holdings.append(holding)
        return holdings
    
    def _map_holding_internal(self, data: dict[str, Any]) -> ProviderHoldingData | None:
        """Internal mapping logic."""
        # Extract required fields (adjust for provider's JSON structure)
        symbol = data.get("symbol")
        if not symbol:
            return None
        
        # Get asset type
        provider_asset_type = data.get("assetType", "UNKNOWN")
        asset_type = {PROVIDER}_ASSET_TYPE_MAP.get(
            provider_asset_type.upper(), "other"
        )
        
        # Parse quantities and values
        quantity = self._parse_decimal(data.get("quantity", 0))
        if quantity == Decimal("0"):
            return None  # Skip zero positions
        
        cost_basis = self._parse_decimal(data.get("costBasis", 0))
        market_value = self._parse_decimal(data.get("marketValue", 0))
        
        # Generate unique position ID
        position_id = f"{self._provider_slug}_{symbol}_{data.get('cusip', '')}"
        
        return ProviderHoldingData(
            provider_holding_id=position_id,
            symbol=symbol,
            security_name=data.get("description", symbol),
            asset_type=asset_type,
            quantity=quantity,
            cost_basis=cost_basis,
            market_value=market_value,
            currency=data.get("currency", "USD"),
            average_price=self._parse_decimal_optional(data.get("averagePrice")),
            current_price=self._parse_decimal_optional(data.get("lastPrice")),
            raw_data=data,
        )
    
    @property
    def _provider_slug(self) -> str:
        return "{provider}"
    
    def _parse_decimal(self, value: Any) -> Decimal:
        """Parse numeric value to Decimal."""
        if value is None:
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal("0")
    
    def _parse_decimal_optional(self, value: Any) -> Decimal | None:
        """Parse numeric value, returning None for missing."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
```

### 9.4 Update Mapper Exports

Update `src/infrastructure/providers/{provider}/mappers/__init__.py`:

```python
from src.infrastructure.providers.{provider}.mappers.holding_mapper import (
    {Provider}HoldingMapper,
)

__all__ = [
    "{Provider}AccountMapper",
    "{Provider}TransactionMapper",
    "{Provider}HoldingMapper",  # Add this
]
```

### 9.5 Add Holdings Tests

Create `tests/unit/test_infrastructure_{provider}_holding_mapper.py`:

```python
"""Unit tests for {Provider} holding mapper."""

import pytest
from decimal import Decimal

from src.infrastructure.providers.{provider}.mappers import {Provider}HoldingMapper


class TestHoldingMapping:
    """Tests for holding field mapping."""
    
    def test_maps_required_fields(self):
        """Maps all required fields correctly."""
        raw = {
            "symbol": "AAPL",
            "description": "Apple Inc.",
            "assetType": "EQUITY",
            "quantity": 100,
            "costBasis": 15000.00,
            "marketValue": 17500.00,
            "currency": "USD",
        }
        
        mapper = {Provider}HoldingMapper()
        result = mapper.map_holding(raw)
        
        assert result is not None
        assert result.symbol == "AAPL"
        assert result.security_name == "Apple Inc."
        assert result.asset_type == "equity"
        assert result.quantity == Decimal("100")
        assert result.cost_basis == Decimal("15000.00")
        assert result.market_value == Decimal("17500.00")
    
    def test_maps_asset_types(self):
        """Maps all known asset types correctly."""
        test_cases = [
            ("EQUITY", "equity"),
            ("ETF", "etf"),
            ("OPTION", "option"),
            ("MUTUAL_FUND", "mutual_fund"),
            ("UNKNOWN_TYPE", "other"),
        ]
        
        mapper = {Provider}HoldingMapper()
        for provider_type, expected in test_cases:
            raw = {"symbol": "TEST", "assetType": provider_type, "quantity": 1}
            result = mapper.map_holding(raw)
            assert result.asset_type == expected
    
    def test_skips_zero_quantity(self):
        """Skips positions with zero quantity."""
        raw = {"symbol": "AAPL", "quantity": 0}
        
        mapper = {Provider}HoldingMapper()
        result = mapper.map_holding(raw)
        
        assert result is None
    
    def test_handles_missing_optional_fields(self):
        """Handles missing optional fields gracefully."""
        raw = {"symbol": "AAPL", "quantity": 100}
        
        mapper = {Provider}HoldingMapper()
        result = mapper.map_holding(raw)
        
        assert result is not None
        assert result.average_price is None
        assert result.current_price is None
```

---

## Phase 10: Balance Tracking (Automatic)

Balance snapshots are created automatically during sync operations. No provider-specific implementation required.

### 10.1 How Balance Tracking Works

When accounts or holdings are synced, the sync handlers automatically capture balance snapshots:

```python
# In sync handlers (already implemented in application layer)
from src.domain.entities.balance_snapshot import BalanceSnapshot
from src.domain.enums import SnapshotSource
from uuid_extensions import uuid7

# After syncing account data:
snapshot = BalanceSnapshot(
    id=uuid7(),
    account_id=account.id,
    balance=account.balance,
    available_balance=account.available_balance,
    holdings_value=total_holdings_value,  # From holdings sync
    cash_value=account.cash_balance,
    currency=account.currency,
    source=SnapshotSource.ACCOUNT_SYNC,  # or HOLDINGS_SYNC
)
await snapshot_repo.save(snapshot)
```

### 10.2 Snapshot Sources

Snapshots are tagged with their source:

| Source | When Created |
|--------|-------------|
| `ACCOUNT_SYNC` | During account data sync |
| `HOLDINGS_SYNC` | During holdings sync |
| `MANUAL_SYNC` | User-initiated refresh |
| `SCHEDULED_SYNC` | Background job |
| `INITIAL_CONNECTION` | First sync after connection |

### 10.3 Providing Additional Balance Data

If your provider returns detailed balance breakdown, capture it in account data:

```python
# In account mapper, extract provider's balance details
return ProviderAccountData(
    provider_account_id=raw["accountId"],
    balance=total_balance,
    available_balance=raw.get("availableBalance"),  # If provided
    # ... other fields
    raw_data=raw,  # Full response preserved for metadata
)
```

The sync handler will use `raw_data` to populate `provider_metadata` in snapshots.

---

## Quick Reference: Files Checklist

### Must Create

- [ ] `src/infrastructure/providers/{provider}/__init__.py`
- [ ] `src/infrastructure/providers/{provider}/{provider}_provider.py`
- [ ] `src/infrastructure/providers/{provider}/api/__init__.py`
- [ ] `src/infrastructure/providers/{provider}/api/accounts_api.py` (optional, can be in provider)
- [ ] `src/infrastructure/providers/{provider}/mappers/__init__.py`
- [ ] `src/infrastructure/providers/{provider}/mappers/account_mapper.py`
- [ ] `src/infrastructure/providers/{provider}/mappers/transaction_mapper.py`
- [ ] `tests/unit/test_infrastructure_{provider}_oauth.py`
- [ ] `tests/unit/test_infrastructure_{provider}_account_mapper.py`
- [ ] `tests/unit/test_infrastructure_{provider}_transaction_mapper.py`
- [ ] `docs/guides/{provider}-integration.md`

### Must Modify

- [ ] `src/core/config.py` - Add provider settings
- [ ] `src/core/container/providers.py` - Register in factory
- [ ] `alembic/seeds/provider_seeder.py` - Add seed data
- [ ] `env/.env.dev.example` - Add config template
- [ ] `env/.env.test.example` - Add config template
- [ ] `env/.env.ci.example` - Add config template
- [ ] `env/.env.prod.example` - Add config template

---

## Verification Checklist

Before submitting PR:

- [ ] All tests pass (`make test`)
- [ ] Lint passes (`make lint`)
- [ ] Type check passes (`make type-check`)
- [ ] Coverage meets targets (90%+ for provider, 95%+ for mappers)
- [ ] Documentation builds (`make docs-build`)
- [ ] Provider-specific guide created
- [ ] Container factory updated
- [ ] Seed data added
- [ ] Environment examples updated

---

**Created**: 2025-12-26 | **Last Updated**: 2025-12-26
