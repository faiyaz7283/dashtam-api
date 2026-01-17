# Transaction Operations API

## Overview

This document describes the transaction API endpoints for Dashtam.
Transactions represent historical financial activity (trades, deposits, withdrawals, transfers).

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
| Transactions | GET | `/transactions/{id}` | Get transaction details |
| Transaction Syncs | POST | `/transactions/syncs` | Sync transactions from provider |
| Account Transactions | GET | `/accounts/{id}/transactions` | List transactions for an account |

---

## Get Transaction

### GET /transactions/{id}

Get details of a specific transaction.

**Request:**

```bash
curl -k -X GET "{BASE_URL}/transactions/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer <access_token>"
```

**Success Response (200 OK):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "account_id": "123e4567-e89b-12d3-a456-426614174000",
  "provider_transaction_id": "TXN12345678",
  "transaction_type": "trade",
  "subtype": "buy",
  "status": "settled",
  "amount_value": "-1500.00",
  "amount_currency": "USD",
  "description": "Buy 10 AAPL @ $150.00",
  "asset_type": "equity",
  "symbol": "AAPL",
  "security_name": "Apple Inc.",
  "quantity": "10.0",
  "unit_price_amount": "150.00",
  "unit_price_currency": "USD",
  "commission_amount": "0.00",
  "commission_currency": "USD",
  "transaction_date": "2025-12-01",
  "settlement_date": "2025-12-03",
  "is_trade": true,
  "is_transfer": false,
  "is_income": false,
  "is_fee": false,
  "is_debit": true,
  "is_credit": false,
  "is_settled": true,
  "created_at": "2025-12-01T10:00:00Z",
  "updated_at": "2025-12-01T10:00:00Z"
}
```

**Error Responses:**

- `404 Not Found` - Transaction not found
- `403 Forbidden` - Not authorized to access this transaction

---

## Sync Transactions

### POST /transactions/syncs

Sync transactions from a provider connection. Fetches transaction history from provider.

**Request:**

```bash
curl -k -X POST "{BASE_URL}/transactions/syncs" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "connection_id": "123e4567-e89b-12d3-a456-426614174000",
    "account_id": "456e7890-e89b-12d3-a456-426614174001",
    "start_date": "2025-01-01",
    "end_date": "2025-12-04",
    "force": false
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| connection_id | UUID | Yes | Provider connection to sync from |
| account_id | UUID | No | Specific account to sync (syncs all if omitted) |
| start_date | date | No | Start date for transaction range (default: 30 days ago) |
| end_date | date | No | End date for transaction range (default: today) |
| force | boolean | No | Force sync even if recently synced (default: false) |

**Success Response (201 Created):**

```json
{
  "created": 15,
  "updated": 3,
  "unchanged": 82,
  "errors": 0,
  "message": "Successfully synced 100 transactions",
  "transactions_created": 15,
  "transactions_updated": 3
}
```

**Error Responses:**

- `404 Not Found` - Connection or account not found
- `403 Forbidden` - Not authorized to sync
- `429 Too Many Requests` - Sync rate limit exceeded

**Notes:**

- Maximum date range is typically 1 year (provider dependent)
- Transactions are identified by provider_transaction_id for upsert
- Connection must be in ACTIVE status

---

## List Transactions by Account

### GET /accounts/{id}/transactions

List transactions for a specific account with pagination and filters.

**Request:**

```bash
curl -k -X GET "{BASE_URL}/accounts/123e4567-e89b-12d3-a456-426614174000/transactions" \
  -H "Authorization: Bearer <access_token>"
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| limit | integer | No | Max results (1-100, default: 50) |
| offset | integer | No | Results to skip (default: 0) |
| transaction_type | string | No | Filter by type (e.g., "trade", "transfer") |
| start_date | date | No | Filter from date (inclusive) |
| end_date | date | No | Filter to date (inclusive) |

**Example with Filters:**

```bash
curl -k -X GET "{BASE_URL}/accounts/123e4567-e89b-12d3-a456-426614174000/transactions?start_date=2025-11-01&end_date=2025-12-01&limit=25" \
  -H "Authorization: Bearer <access_token>"
```

**Success Response (200 OK):**

```json
{
  "transactions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "account_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider_transaction_id": "TXN12345678",
      "transaction_type": "trade",
      "subtype": "buy",
      "status": "settled",
      "amount_value": "-1500.00",
      "amount_currency": "USD",
      "description": "Buy 10 AAPL @ $150.00",
      "asset_type": "equity",
      "symbol": "AAPL",
      "security_name": "Apple Inc.",
      "quantity": "10.0",
      "unit_price_amount": "150.00",
      "unit_price_currency": "USD",
      "commission_amount": "0.00",
      "commission_currency": "USD",
      "transaction_date": "2025-12-01",
      "settlement_date": "2025-12-03",
      "is_trade": true,
      "is_transfer": false,
      "is_income": false,
      "is_fee": false,
      "is_debit": true,
      "is_credit": false,
      "is_settled": true,
      "created_at": "2025-12-01T10:00:00Z",
      "updated_at": "2025-12-01T10:00:00Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "account_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider_transaction_id": "TXN87654321",
      "transaction_type": "income",
      "subtype": "dividend",
      "status": "settled",
      "amount_value": "25.50",
      "amount_currency": "USD",
      "description": "AAPL Dividend",
      "asset_type": "equity",
      "symbol": "AAPL",
      "security_name": "Apple Inc.",
      "quantity": null,
      "unit_price_amount": null,
      "unit_price_currency": null,
      "commission_amount": null,
      "commission_currency": null,
      "transaction_date": "2025-11-15",
      "settlement_date": "2025-11-17",
      "is_trade": false,
      "is_transfer": false,
      "is_income": true,
      "is_fee": false,
      "is_debit": false,
      "is_credit": true,
      "is_settled": true,
      "created_at": "2025-11-15T10:00:00Z",
      "updated_at": "2025-11-15T10:00:00Z"
    }
  ],
  "total_count": 150,
  "has_more": true
}
```

**Error Responses:**

- `404 Not Found` - Account not found
- `403 Forbidden` - Not authorized to access this account

---

## Transaction Types

| Type | Description |
|------|-------------|
| trade | Security buy/sell transactions |
| transfer | Money movement (deposit, withdrawal, transfer) |
| income | Dividends, interest, distributions |
| fee | Account fees, commissions |
| other | Miscellaneous transactions |

---

## Transaction Subtypes

### Trade Subtypes

| Subtype | Description |
|---------|-------------|
| buy | Purchase securities |
| sell | Sell securities |
| short_sell | Short sale |
| buy_to_cover | Cover short position |

### Transfer Subtypes

| Subtype | Description |
|---------|-------------|
| deposit | Cash deposit |
| withdrawal | Cash withdrawal |
| transfer_in | Transfer from another account |
| transfer_out | Transfer to another account |
| wire_in | Incoming wire transfer |
| wire_out | Outgoing wire transfer |
| ach_in | Incoming ACH transfer |
| ach_out | Outgoing ACH transfer |

### Income Subtypes

| Subtype | Description |
|---------|-------------|
| dividend | Stock dividend |
| interest | Interest income |
| capital_gain | Capital gain distribution |
| return_of_capital | Return of capital |

### Fee Subtypes

| Subtype | Description |
|---------|-------------|
| commission | Trading commission |
| management_fee | Account management fee |
| margin_interest | Margin interest charge |
| other_fee | Miscellaneous fees |

---

## Transaction Status Values

| Status | Description |
|--------|-------------|
| pending | Transaction initiated, not yet settled |
| settled | Transaction completed and settled |
| failed | Transaction failed |
| cancelled | Transaction cancelled |

---

## Asset Types

| Type | Description |
|------|-------------|
| equity | Common/preferred stock |
| option | Options contracts |
| etf | Exchange-traded funds |
| mutual_fund | Mutual funds |
| bond | Bonds and fixed income |
| future | Futures contracts |
| crypto | Cryptocurrency |
| cash | Cash/money market |
| other | Other asset types |

---

## Error Response Format (RFC 9457)

All errors follow RFC 9457 Problem Details format:

```json
{
  "type": "https://api.dashtam.com/errors/not_found",
  "title": "Not Found",
  "status": 404,
  "detail": "Transaction not found",
  "instance": "/api/v1/transactions/550e8400-e29b-41d4-a716-446655440000",
  "trace_id": "abc123-def456-ghi789"
}
```

---

## Rate Limiting

Transaction endpoints use standard rate limiting:

| Policy | Max Requests | Refill Rate | Scope | Endpoints |
|--------|--------------|-------------|-------|----------|
| API_READ | 100 | 100/min | User | `GET /transactions/{id}`, `GET /accounts/{id}/transactions` |
| PROVIDER_SYNC | 10 | 5/min | User+Provider | `POST /transactions/syncs` |

**Rate Limit Headers (RFC 6585):**

```text
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1699488000
Retry-After: 60  (only on 429)
```

---

## Implementation References

- **Route Registry**: All transaction endpoints are defined in `src/presentation/routers/api/v1/routes/registry.py` with rate limit policies and auth requirements.
- **Handler Module**: `src/presentation/routers/api/v1/transactions.py`
- **Domain Events**: Transaction sync emits `TransactionSyncAttempted`, `TransactionSyncSucceeded`, `TransactionSyncFailed` events.

---

**Created**: 2025-12-04 | **Last Updated**: 2026-01-10
