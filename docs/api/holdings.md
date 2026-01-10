# Holdings API

## Overview

This document describes the holdings (positions) API endpoints for Dashtam.
Holdings represent current security positions in investment accounts.

**Base URL**: `{BASE_URL}` (used in examples below)

| Environment | BASE_URL |
|-------------|----------|
| Development | `https://dashtam.local/api/v1` |
| Test | `https://test.dashtam.local/api/v1` |
| Production | `https://api.dashtam.com/api/v1` |

**Authentication**: All endpoints require JWT Bearer token.

---

## Endpoints Summary

| Resource | Method | Endpoint | Description |
|----------|--------|----------|-------------|
| Holdings | GET | `/holdings` | List all holdings for user |
| Holdings | GET | `/accounts/{id}/holdings` | List holdings for account |
| Holdings Syncs | POST | `/accounts/{id}/holdings/syncs` | Sync holdings from provider |

---

## List All Holdings

### GET /holdings

List all holdings for the authenticated user across all accounts.

**Request:**

```bash
curl -k -X GET "{BASE_URL}/holdings" \
  -H "Authorization: Bearer <access_token>"
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| active_only | boolean | No | Only return active holdings (default: true) |
| asset_type | string | No | Filter by asset type (equity, etf, option, etc.) |
| symbol | string | No | Filter by security symbol (e.g., AAPL) |

**Success Response (200 OK):**

```json
{
  "holdings": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "account_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider_holding_id": "schwab_037833100_AAPL",
      "symbol": "AAPL",
      "security_name": "Apple Inc.",
      "asset_type": "equity",
      "quantity": "100.00000000",
      "cost_basis": "15000.00",
      "market_value": "17500.00",
      "currency": "USD",
      "average_price": "150.00",
      "current_price": "175.00",
      "unrealized_gain_loss": "2500.00",
      "unrealized_gain_loss_percent": "16.67",
      "is_active": true,
      "is_profitable": true,
      "last_synced_at": "2025-12-26T10:00:00Z",
      "created_at": "2025-12-01T10:00:00Z",
      "updated_at": "2025-12-26T10:00:00Z"
    }
  ],
  "total_count": 1,
  "active_count": 1,
  "total_market_value_by_currency": {
    "USD": "17500.00"
  },
  "total_cost_basis_by_currency": {
    "USD": "15000.00"
  },
  "total_unrealized_gain_loss_by_currency": {
    "USD": "2500.00"
  }
}
```

---

## List Holdings by Account

### GET /accounts/{id}/holdings

List all holdings for a specific account.

**Request:**

```bash
curl -k -X GET "{BASE_URL}/accounts/123e4567-e89b-12d3-a456-426614174000/holdings" \
  -H "Authorization: Bearer <access_token>"
```

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| id | UUID | Yes | Account unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| active_only | boolean | No | Only return active holdings (default: true) |
| asset_type | string | No | Filter by asset type |

**Success Response (200 OK):**

Same structure as List All Holdings response.

**Error Responses:**

- `404 Not Found` - Account not found
- `403 Forbidden` - Not authorized to access this account

---

## Sync Holdings

### POST /accounts/{id}/holdings/syncs

Sync holdings from provider for a specific account. Fetches latest position data from the provider and updates the database.

**Request:**

```bash
curl -k -X POST "{BASE_URL}/accounts/123e4567-e89b-12d3-a456-426614174000/holdings/syncs" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "force": false
  }'
```

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| id | UUID | Yes | Account unique identifier |

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| force | boolean | No | Force sync even if recently synced (default: false) |

**Success Response (201 Created):**

```json
{
  "created": 2,
  "updated": 5,
  "unchanged": 10,
  "errors": 0,
  "message": "Holdings sync completed successfully",
  "holdings_created": 2,
  "holdings_updated": 5,
  "holdings_deactivated": 1
}
```

**Error Responses:**

- `404 Not Found` - Account not found
- `403 Forbidden` - Not authorized to sync this account
- `429 Too Many Requests` - Sync rate limit exceeded (try again later)
- `502 Bad Gateway` - Provider API error

---

## Response Fields

### Holding Object

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Holding unique identifier |
| account_id | UUID | Account FK |
| provider_holding_id | string | Provider's unique position ID |
| symbol | string | Security ticker symbol (e.g., "AAPL") |
| security_name | string | Full security name |
| asset_type | string | Asset type (see below) |
| quantity | string | Number of shares/units (Decimal) |
| cost_basis | string | Total cost paid (Decimal) |
| market_value | string | Current market value (Decimal) |
| currency | string | ISO 4217 currency code |
| average_price | string | Average cost per share (nullable) |
| current_price | string | Current market price (nullable) |
| unrealized_gain_loss | string | Computed gain/loss (nullable) |
| unrealized_gain_loss_percent | string | Gain/loss percentage (nullable) |
| is_active | boolean | Whether position is active |
| is_profitable | boolean | Whether market_value > cost_basis |
| last_synced_at | datetime | Last sync timestamp (nullable) |
| created_at | datetime | Creation timestamp |
| updated_at | datetime | Last update timestamp |

### Asset Types

| Value | Description |
|-------|-------------|
| equity | Stocks (common, preferred) |
| etf | Exchange-traded funds |
| option | Options contracts |
| mutual_fund | Mutual funds |
| fixed_income | Bonds, CDs, treasuries |
| futures | Futures contracts |
| cryptocurrency | Crypto assets |
| cash_equivalent | Money market, etc. |
| other | Unknown/other |

---

## Error Response Format (RFC 7807)

All errors follow RFC 7807 Problem Details format:

```json
{
  "type": "https://api.dashtam.com/errors/not_found",
  "title": "Not Found",
  "status": 404,
  "detail": "Account not found",
  "instance": "/api/v1/accounts/550e8400-e29b-41d4-a716-446655440000/holdings",
  "trace_id": "abc123-def456-ghi789"
}
```

---

## Example: Portfolio Analysis

Fetch holdings and calculate portfolio allocation:

```bash
# Get all holdings
curl -k -X GET "{BASE_URL}/holdings?active_only=true" \
  -H "Authorization: Bearer <access_token>" | jq '.total_market_value_by_currency'

# Filter by asset type
curl -k -X GET "{BASE_URL}/holdings?asset_type=equity" \
  -H "Authorization: Bearer <access_token>"

# Filter by symbol
curl -k -X GET "{BASE_URL}/holdings?symbol=AAPL" \
  -H "Authorization: Bearer <access_token>"
```

---

## Rate Limiting

Holdings endpoints use standard rate limiting:

| Policy | Max Requests | Refill Rate | Scope | Endpoints |
|--------|--------------|-------------|-------|----------|
| API_READ | 100 | 100/min | User | `GET /holdings`, `GET /accounts/{id}/holdings` |
| PROVIDER_SYNC | 10 | 5/min | User+Provider | `POST /accounts/{id}/holdings/syncs` |

**Rate Limit Headers (RFC 6585):**

```text
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1699488000
Retry-After: 60  (only on 429)
```

---

## Implementation References

- **Route Registry**: All holdings endpoints are defined in `src/presentation/routers/api/v1/routes/registry.py` with rate limit policies and auth requirements.
- **Handler Module**: `src/presentation/routers/api/v1/holdings.py`
- **Domain Events**: Holdings sync emits `HoldingsSyncAttempted`, `HoldingsSyncSucceeded`, `HoldingsSyncFailed` events.
- **Balance Snapshot**: Holdings sync automatically captures balance snapshots for portfolio tracking.

---

**Created**: 2025-12-26 | **Last Updated**: 2026-01-10
