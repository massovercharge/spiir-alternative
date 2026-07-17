---
name: Enable Banking API
description: Provides domain knowledge about the Enable Banking Open Banking API — endpoints, authentication, session lifecycle, transaction structure, rate limits, and supported banks.
---

# Enable Banking API

## Purpose

Provides domain knowledge about the Enable Banking Open Banking API — endpoints, authentication, session lifecycle, transaction structure, rate limits, and supported Danish banks. Reference this when orchestrating `app/sync_service.py` for API-based transaction sync.

## API Overview

Enable Banking provides PSD2-compliant access to bank account data across 2,500+ European banks. Peng uses it for fast, reliable transaction sync.

- **API Base URL**: `https://api.enablebanking.com`
- **Authentication**: JWT signed with RSA private key (PS256 algorithm)
- **Data Format**: JSON, ISO 20022 inspired field names
- **Rate Limit**: Max 4 account information requests per day per account (PSD2 regulation)

## Authentication

### JWT Structure
The `sync_service.py` helper handles JWT generation. Conceptually:
- **Issuer**: `enablebanking.com`
- **Audience**: `api.enablebanking.com`
- **Algorithm**: PS256 (RSA-PSS with SHA-256)
- **Expiry**: 1 hour from creation
- **Payload**: includes `app_id` from config

### Config
Configured via environment variables:
- `ENABLEBANKING_APP_ID`: your application ID
- `ENABLEBANKING_PRIVATE_KEY_PATH`: Path to the private `.pem` key.

## Session Lifecycle

### Consent Flow
1. **Initiate**: `sync_service.py` starts auth flow.
2. **MitID**: User authenticates in browser.
3. **HTTPS Relay**: Bank redirects to callback URL with a `code`.
4. **Session**: Code exchanged for session_id via POST to `/sessions`.
5. **Active**: Session provides access to account data for 90-180 days.

### Session States
| State | Meaning | Action |
|-------|---------|--------|
| `active` | Consent valid, API accessible | Proceed with sync |
| `expired` | Consent period ended | Re-run auth for new consent |
| `revoked` | Bank-side revocation | Re-run auth |
| `no_session` | No session file exists | Run setup + auth |

## API Endpoints

### POST /auth
Initiate consent. Returns `url` for user to visit.

### POST /sessions
Exchange authorization code for session. Returns `session_id` and `accounts`.

### GET /sessions/{session_id}/accounts
List accounts linked to the session. Returns account UIDs, IBANs, names, currencies.

### GET /accounts/{uid}/transactions
Fetch transactions. Parameters:
- `date_from` (required): YYYY-MM-DD
- `date_to` (optional): YYYY-MM-DD (defaults to today)
- `continuation_key` (optional): for pagination

### GET /accounts/{uid}/balances
Fetch current balances. Returns balance type, amount, currency, and date.

**Response structure**:
```json
{
  "balances": [
    {
      "balance_amount": {"amount": "12543.25", "currency": "DKK"},
      "balance_type": "CLBD",
      "reference_date": "2026-02-03"
    },
    {
      "balance_amount": {"amount": "12100.00", "currency": "DKK"},
      "balance_type": "ITAV",
      "reference_date": "2026-02-03"
    }
  ]
}
```

**Balance type codes**:
| Type | Description | Use Case |
|------|-------------|----------|
| `CLBD` | Closing booked balance | End of day settled — most accurate, prefer this |
| `ITAV` | Intraday available | Current available funds — fallback if CLBD missing |
| `XPCD` | Expected balance | Projected balance including pending |

**Parsing priority**: Prefer `CLBD` over `ITAV` over `XPCD`. Extract `balance_amount.amount` as the balance value.

## Transaction Structure

Enable Banking returns transactions in this JSON format:

```json
{
  "bank_transaction_code": {"code": "12", "description": "Kortbetaling"},
  "booking_date": "2026-01-15",
  "booking_date_time": "2026-01-15T14:30:00Z",
  "credit_debit_indicator": "DBIT",
  "creditor": {"name": "FØTEX"},
  "debtor": {"name": "Peer Jakobsen"},
  "entry_reference": "5561990681",
  "remittance_information": ["Dankort-køb", "FØTEX 4123"],
  "status": "BOOK",
  "transaction_amount": {"amount": "847.50", "currency": "DKK"},
  "balance_after_transaction": {"amount": "12543.25", "currency": "DKK", "credit_debit_indicator": "CRDT"},
  "value_date": "2026-01-15"
}
```

### Key Fields
| Field | Description |
|-------|-------------|
| `booking_date` | Transaction date (already YYYY-MM-DD) |
| `credit_debit_indicator` | `DBIT` = debit (expense), `CRDT` = credit (income) |
| `transaction_amount.amount` | Positive number as string |
| `transaction_amount.currency` | ISO currency code |
| `creditor.name` | Recipient (present on debits) |
| `debtor.name` | Sender (present on credits) |
| `remittance_information` | Array of description strings |
| `balance_after_transaction` | Running balance (for tx_hash) |
| `status` | `BOOK` (booked), `PDNG` (pending), `INFO` (informational) |
| `entry_reference` | Bank's reference number |
| `bank_transaction_code` | Transaction type code and description |

### Transaction Status Values
- **BOOK**: Booked, final — include in sync
- **PDNG**: Pending, not yet final — skip (may change or disappear)
- **INFO**: Informational, not a real transaction — skip

Only sync transactions with `status: BOOK`.

## PSD2 Rate Limits

### Regulation
PSD2 (Payment Services Directive 2) limits account information requests to **4 per day per account**. This is a European banking regulation.

### Rate Limit Strategy
- Sync once per day during normal use
- If testing, be mindful of the 4/day limit
- Rate resets at midnight UTC
- Error when exceeded: `rate_limit` with message explaining the constraint

## Supported Danish Banks

Enable Banking supports these Danish banks (non-exhaustive):

### Major Banks
- Nykredit
- Danske Bank
- Nordea
- Jyske Bank
- Sydbank
- Spar Nord

### ASPSP Names
When running auth, use the bank's name as registered with Enable Banking. Common Danish bank names:
- `Nykredit` (not "nykredit" — use proper case)
- `Danske Bank`
- `Nordea`
- `Jyske Bank`
- `Sydbank`
- `Lunar`

## Error Codes

| Error | Meaning | Resolution |
|-------|---------|------------|
| `401 Unauthorized` | JWT invalid or expired | Check RSA key and app_id |
| `403 Forbidden` | Consent missing or expired | Re-run auth for new consent |
| `404 Not Found` | Invalid session or account UID | Verify session is active |
| `429 Too Many Requests` | PSD2 rate limit exceeded | Wait until tomorrow |
| `503 Service Unavailable` | Bank API temporarily down | Retry later |

## Known Limitations
- PSD2 rate limit (4/day/account) means no real-time balance checking
- Transaction descriptions from API may differ from browser export CSV (banks format them differently)
- `balance_after_transaction` is optional — some banks don't provide it for all transaction types
- Session can be revoked bank-side without notice (user changed consent settings)
- ASPSP names must match Enable Banking's registry (case-sensitive)
