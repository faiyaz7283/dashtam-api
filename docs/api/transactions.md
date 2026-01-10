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
  "transaction_subtype": "buy",
  "status": "settled",
  "transaction_date": "2025-12-01",
  "settlement_date": "2025-12-03",
  "amount": "-1500.00",
  "currency": "USD",
  "description": "Buy 10 AAPL @ $150.00",
  "symbol": "AAPL",
  "asset_type": "equity",
  "quantity": "10.0",
  "price": "150.00",
  "fees": "0.00",
  "net_amount": "-1500.00",
  "cusip": "037833100",
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
      "transaction_subtype": "buy",
      "status": "settled",
      "transaction_date": "2025-12-01",
      "amount": "-1500.00",
      "currency": "USD",
      "description": "Buy 10 AAPL @ $150.00",
      "symbol": "AAPL",
      "asset_type": "equity",
      "quantity": "10.0",
      "price": "150.00"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "account_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider_transaction_id": "TXN87654321",
      "transaction_type": "income",
      "transaction_subtype": "dividend",
      "status": "settled",
      "transaction_date": "2025-11-15",
      "amount": "25.50",
      "currency": "USD",
      "description": "AAPL Dividend",
      "symbol": "AAPL",
      "asset_type": "equity",
      "quantity": null,
      "price": null
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

## Error Response Format (RFC 7807)

All errors follow RFC 7807 Problem Details format:

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

**Created**: 2025-12-04 | **Last Updated**: 2025-12-04
