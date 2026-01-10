# Balance Snapshots API

## Overview

This document describes the balance snapshot API endpoints for Dashtam.
Balance snapshots provide historical balance tracking for portfolio analytics and charting.

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
| Balance Snapshots | GET | `/balance-snapshots` | Get latest snapshots for user |
| Balance History | GET | `/accounts/{id}/balance-history` | Get balance history for account |
| Balance Snapshots | GET | `/accounts/{id}/balance-snapshots` | List recent snapshots for account |

---

## Get Latest Snapshots

### GET /balance-snapshots

Get the most recent balance snapshot for each of the user's accounts. Useful for portfolio summary dashboards.

**Request:**

```bash
curl -k -X GET "{BASE_URL}/balance-snapshots" \
  -H "Authorization: Bearer <access_token>"
```

**Success Response (200 OK):**

```json
{
  "snapshots": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "account_id": "123e4567-e89b-12d3-a456-426614174000",
      "balance": "25000.00",
      "available_balance": "24500.00",
      "holdings_value": "22000.00",
      "cash_value": "3000.00",
      "currency": "USD",
      "source": "holdings_sync",
      "captured_at": "2025-12-26T10:00:00Z",
      "created_at": "2025-12-26T10:00:00Z",
      "change_amount": "500.00",
      "change_percent": 2.04
    }
  ],
  "total_count": 1,
  "total_balance_by_currency": {
    "USD": "25000.00"
  }
}
```

**Notes:**

- Returns one snapshot per account (the most recent)
- `change_amount` and `change_percent` compare to the previous snapshot

---

## Get Balance History

### GET /accounts/{id}/balance-history

Get balance history for an account within a date range. Useful for building portfolio value charts.

**Request:**

```bash
curl -k -X GET "{BASE_URL}/accounts/123e4567-e89b-12d3-a456-426614174000/balance-history?start_date=2025-01-01T00:00:00Z&end_date=2025-12-31T23:59:59Z" \
  -H "Authorization: Bearer <access_token>"
```

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| id | UUID | Yes | Account unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| start_date | datetime | Yes | Start of date range (ISO 8601) |
| end_date | datetime | Yes | End of date range (ISO 8601) |
| source | string | No | Filter by snapshot source |

**Success Response (200 OK):**

```json
{
  "snapshots": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "account_id": "123e4567-e89b-12d3-a456-426614174000",
      "balance": "20000.00",
      "available_balance": "19500.00",
      "holdings_value": "17000.00",
      "cash_value": "3000.00",
      "currency": "USD",
      "source": "account_sync",
      "captured_at": "2025-01-15T10:00:00Z",
      "created_at": "2025-01-15T10:00:00Z",
      "change_amount": null,
      "change_percent": null
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "account_id": "123e4567-e89b-12d3-a456-426614174000",
      "balance": "22500.00",
      "available_balance": "22000.00",
      "holdings_value": "19500.00",
      "cash_value": "3000.00",
      "currency": "USD",
      "source": "holdings_sync",
      "captured_at": "2025-06-15T10:00:00Z",
      "created_at": "2025-06-15T10:00:00Z",
      "change_amount": "2500.00",
      "change_percent": 12.5
    }
  ],
  "total_count": 2,
  "start_balance": "20000.00",
  "end_balance": "22500.00",
  "total_change_amount": "2500.00",
  "total_change_percent": 12.5,
  "currency": "USD"
}
```

**Error Responses:**

- `400 Bad Request` - Invalid date range
- `404 Not Found` - Account not found
- `403 Forbidden` - Not authorized to access this account

---

## List Recent Snapshots

### GET /accounts/{id}/balance-snapshots

List recent balance snapshots for an account. Returns snapshots in reverse chronological order (most recent first).

**Request:**

```bash
curl -k -X GET "{BASE_URL}/accounts/123e4567-e89b-12d3-a456-426614174000/balance-snapshots?limit=30" \
  -H "Authorization: Bearer <access_token>"
```

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| id | UUID | Yes | Account unique identifier |

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| limit | integer | No | Maximum snapshots to return (1-100, default: 30) |
| source | string | No | Filter by snapshot source |

**Success Response (200 OK):**

Same structure as Balance History response.

**Error Responses:**

- `404 Not Found` - Account not found
- `403 Forbidden` - Not authorized to access this account

---

## Response Fields

### Snapshot Object

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Snapshot unique identifier |
| account_id | UUID | Account FK |
| balance | string | Total account balance (Decimal) |
| available_balance | string | Available balance (nullable) |
| holdings_value | string | Total holdings value (nullable) |
| cash_value | string | Cash balance (nullable) |
| currency | string | ISO 4217 currency code |
| source | string | How snapshot was captured (see below) |
| captured_at | datetime | When balance was captured |
| created_at | datetime | Record creation timestamp |
| change_amount | string | Change from previous snapshot (nullable) |
| change_percent | float | Percentage change from previous (nullable) |

### Snapshot Sources

| Value | Description |
|-------|-------------|
| account_sync | Captured during account data sync |
| holdings_sync | Captured during holdings sync operation |
| manual_sync | User-initiated sync request |
| scheduled_sync | Automated background sync job |
| initial_connection | First sync after provider connection |

---

## Error Response Format (RFC 7807)

All errors follow RFC 7807 Problem Details format:

```json
{
  "type": "https://api.dashtam.com/errors/not_found",
  "title": "Not Found",
  "status": 404,
  "detail": "Account not found",
  "instance": "/api/v1/accounts/550e8400-e29b-41d4-a716-446655440000/balance-history",
  "trace_id": "abc123-def456-ghi789"
}
```

---

## Use Cases

### Portfolio Value Chart

Build a line chart showing portfolio value over time:

```bash
# Get 1 year of balance history
curl -k -X GET "{BASE_URL}/accounts/{account_id}/balance-history?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z" \
  -H "Authorization: Bearer <access_token>"

# Response includes start_balance, end_balance, total_change_percent
# for easy performance summary
```

### Portfolio Summary Dashboard

Get current balance for all accounts:

```bash
# Get latest snapshot for each account
curl -k -X GET "{BASE_URL}/balance-snapshots" \
  -H "Authorization: Bearer <access_token>"

# Response includes total_balance_by_currency for aggregate totals
```

### Filter by Sync Type

Get only user-initiated sync snapshots:

```bash
curl -k -X GET "{BASE_URL}/accounts/{account_id}/balance-snapshots?source=manual_sync&limit=10" \
  -H "Authorization: Bearer <access_token>"
```

---

## Rate Limiting

Balance snapshot endpoints use standard rate limiting:

| Policy | Max Requests | Refill Rate | Scope | Endpoints |
|--------|--------------|-------------|-------|----------|
| API_READ | 100 | 100/min | User | All balance snapshot endpoints |

**Rate Limit Headers (RFC 6585):**

```text
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1699488000
Retry-After: 60  (only on 429)
```

---

## Implementation References

- **Route Registry**: All balance snapshot endpoints are defined in `src/presentation/routers/api/v1/routes/registry.py` with rate limit policies and auth requirements.
- **Handler Module**: `src/presentation/routers/api/v1/balance_snapshots.py`
- **Snapshot Capture**: Snapshots automatically created during account and holdings sync operations.

---

**Created**: 2025-12-26 | **Last Updated**: 2026-01-10
