# Chase File Import Guide

Import financial data from Chase QFX/OFX files into Dashtam.

---

## Overview

The Chase File Import feature allows you to upload QFX (Quicken Financial Exchange) or OFX (Open Financial Exchange) files exported from Chase Bank. This enables importing:

- **Account information** - Account type, number, and balance
- **Transaction history** - All transactions in the file
- **Balance snapshots** - Point-in-time balance records

### Key Features

- **No OAuth required** - Upload files directly without connecting to Chase
- **Duplicate detection** - Transactions are deduplicated by FITID (Financial Transaction ID)
- **Safe re-upload** - Upload the same file multiple times without creating duplicates
- **Automatic account creation** - Accounts are created/updated based on file metadata

---

## Prerequisites

- Dashtam development environment running (`make dev-up`)
- QFX or OFX file exported from Chase Bank
- Authenticated user session with valid JWT token

---

## Exporting Files from Chase

### Step 1: Log in to Chase

Navigate to [chase.com](https://www.chase.com) and log in to your account.

### Step 2: Download Activity

1. Go to your account activity page
2. Click **Download account activity**
3. Select **Quicken (QFX)** or **Microsoft Money (OFX)** format
4. Choose your date range
5. Click **Download**

The file will download with a `.qfx` or `.ofx` extension.

---

## API Usage

### Upload File

Upload a Chase QFX/OFX file to import accounts and transactions.

**Endpoint**: `POST /api/v1/imports`

**Content-Type**: `multipart/form-data`

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | Yes | QFX or OFX file to import |

**Example Request (curl)**:

```bash
curl -X POST https://dashtam.local/api/v1/imports \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -F "file=@/path/to/chase-statement.qfx"
```

**Example Request (Python)**:

```python
import httpx

async def import_chase_file(access_token: str, file_path: str):
    async with httpx.AsyncClient() as client:
        with open(file_path, "rb") as f:
            response = await client.post(
                "https://dashtam.local/api/v1/imports",
                headers={"Authorization": f"Bearer {access_token}"},
                files={"file": (file_path.split("/")[-1], f, "application/x-ofx")},
            )
        return response.json()
```

**Success Response** (201 Created):

```json
{
  "provider_slug": "chase_file",
  "accounts_imported": 1,
  "transactions_imported": 42,
  "accounts_updated": 0,
  "transactions_skipped": 0,
  "message": "Successfully imported 1 account(s) and 42 transaction(s)"
}
```

**Error Responses**:

| Status | Description |
|--------|-------------|
| 400 | Invalid file format or parsing error |
| 401 | Missing or invalid authentication |
| 415 | Unsupported file format (not QFX/OFX) |
| 500 | Internal server error |

### List Supported Formats

Get the list of supported file import formats.

**Endpoint**: `GET /api/v1/imports/formats`

**Example Request**:

```bash
curl -X GET https://dashtam.local/api/v1/imports/formats \
  -H "Authorization: Bearer ${ACCESS_TOKEN}"
```

**Response**:

```json
{
  "formats": [
    {
      "format": "qfx",
      "name": "Quicken Financial Exchange",
      "extensions": [".qfx"],
      "providers": ["chase_file"]
    },
    {
      "format": "ofx",
      "name": "Open Financial Exchange",
      "extensions": [".ofx"],
      "providers": ["chase_file"]
    }
  ]
}
```

---

## How It Works

### File Parsing

The QFX/OFX parser extracts data using the industry-standard OFX format:

```text
QFX/OFX File
    │
    ├── Bank Account Info (BANKACCTFROM)
    │   ├── Bank ID (routing number)
    │   ├── Account ID (masked for display)
    │   └── Account Type (CHECKING, SAVINGS, etc.)
    │
    ├── Statement Info (STMTRS)
    │   ├── Currency (USD)
    │   └── Balance (ledger balance at statement date)
    │
    └── Transaction List (STMTTRN)
        └── For each transaction:
            ├── FITID (unique transaction ID)
            ├── Type (DEBIT, CREDIT, etc.)
            ├── Date (posted date)
            ├── Amount (signed decimal)
            └── Description (payee name)
```

### Account Mapping

| OFX Field | Dashtam Field | Notes |
|-----------|---------------|-------|
| `ACCTID` | `provider_account_id` | Full account number |
| `ACCTID` | `account_number_masked` | Last 4 digits shown |
| `ACCTTYPE` | `account_type` | Mapped to AccountType enum |
| `LEDGERBAL.BALAMT` | `balance` | Current balance |
| `CURDEF` | `currency` | Default: USD |

### Transaction Mapping

| OFX Field | Dashtam Field | Notes |
|-----------|---------------|-------|
| `FITID` | `provider_transaction_id` | Used for deduplication |
| `TRNTYPE` | `transaction_type` / `subtype` | Two-level classification |
| `TRNAMT` | `amount` | Absolute value stored |
| `DTPOSTED` | `transaction_date` | Parsed from OFX date format |
| `NAME` | `description` | Payee or memo |
| `MEMO` | `description` (fallback) | If NAME not present |

### Transaction Type Classification

OFX transaction types are mapped to Dashtam's two-level classification:

| OFX Type | Dashtam Type | Dashtam Subtype |
|----------|--------------|-----------------|
| `CREDIT` | `income` | `deposit` |
| `DEBIT` | `expense` | `withdrawal` |
| `XFER` | `transfer` | `transfer` |
| `CHECK` | `expense` | `check` |
| `ATM` | `expense` | `atm` |
| `POS` | `expense` | `purchase` |
| `FEE` | `fee` | `account_fee` |
| `INT` | `income` | `interest` |
| `DIV` | `income` | `dividend` |
| `DIRECTDEBIT` | `expense` | `payment` |
| `DIRECTDEP` | `income` | `direct_deposit` |

---

## Duplicate Detection

Transactions are uniquely identified by their **FITID** (Financial Transaction ID). When you upload a file:

1. Parser extracts all transactions with FITIDs
2. For each transaction, check if FITID exists in database
3. **New FITIDs** → Create new transaction records
4. **Existing FITIDs** → Skip (already imported)

This ensures:

- Safe re-upload of the same file
- Overlapping date ranges handled correctly
- No duplicate transactions ever created

---

## Account Auto-Creation

When importing a file for a new account:

1. Parser extracts account number and type from file
2. Provider connection created for user (type: `FILE_IMPORT`)
3. Account entity created with masked account number
4. Subsequent imports to same account update the balance

Account matching uses `provider_account_id` (the full account number from the file).

---

## Example Workflow

### First-Time Import

```bash
# 1. Export QFX from Chase (save as chase-checking.qfx)

# 2. Upload the file
curl -X POST https://dashtam.local/api/v1/imports \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -F "file=@chase-checking.qfx"

# Response:
# {
#   "accounts_imported": 1,
#   "transactions_imported": 150,
#   "accounts_updated": 0,
#   "transactions_skipped": 0
# }

# 3. View imported accounts
curl https://dashtam.local/api/v1/accounts \
  -H "Authorization: Bearer ${ACCESS_TOKEN}"

# 4. View transactions
curl "https://dashtam.local/api/v1/transactions?account_id=${ACCOUNT_ID}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}"
```

### Monthly Update

```bash
# Download new statement from Chase (includes some overlap)
curl -X POST https://dashtam.local/api/v1/imports \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -F "file=@chase-december.qfx"

# Response shows only new transactions imported:
# {
#   "accounts_imported": 0,
#   "transactions_imported": 45,
#   "accounts_updated": 1,
#   "transactions_skipped": 105
# }
```

---

## Troubleshooting

### Error: "Unsupported file format"

**Cause**: File extension is not `.qfx` or `.ofx`.

**Solution**: Ensure you're uploading a valid QFX/OFX file. CSV files are not supported.

### Error: "Failed to parse file"

**Cause**: File is corrupted or not valid OFX format.

**Solutions**:

1. Re-download the file from Chase
2. Ensure file wasn't modified after download
3. Check file opens in Quicken or Money if available

### No transactions imported (but file has data)

**Cause**: All transactions already exist (FITIDs match).

**This is expected** - the system prevents duplicates. Check the `transactions_skipped` count.

### Account balance incorrect

**Cause**: Balance reflects the statement date, not today.

**Note**: The balance in QFX files is point-in-time (when statement was generated). For real-time balances, use OAuth-based providers.

### Error: "Provider not found"

**Cause**: The `chase_file` provider is not seeded in the database.

**Solution**: Run migrations to seed the provider:

```bash
make migrate
```

---

## Technical Details

### Supported File Formats

| Format | Extensions | MIME Types |
|--------|------------|------------|
| QFX | `.qfx` | `application/x-ofx`, `application/vnd.intu.qfx` |
| OFX | `.ofx` | `application/x-ofx`, `application/ofx` |

### Parser Library

Uses [ofxparse](https://pypi.org/project/ofxparse/) for parsing OFX/QFX files.

### Provider Credentials

File-based providers use `FILE_IMPORT` credential type. No actual credentials are stored - just a placeholder to satisfy the provider connection requirements.

### Balance Snapshots

Each import creates a balance snapshot with:

- `source`: `ACCOUNT_SYNC`
- `balance`: Ledger balance from file
- `captured_at`: Timestamp of import

---

## Limitations

1. **Statement data only** - No real-time balance or pending transactions
2. **Chase-specific parsing** - May not work with other bank's QFX files
3. **Manual upload required** - No automatic sync (by design)
4. **Historical data** - Balance reflects statement date, not current

---

## Future Enhancements

- [ ] Support for additional banks (Bank of America, Wells Fargo)
- [ ] CSV file import support
- [ ] Batch file upload (multiple files at once)
- [ ] Scheduled file watching (local directory)

---

**Created**: 2025-12-27 | **Last Updated**: 2026-01-10
