# 6. Client-Side Bookmarklet and Webhook Ingestion for Coop Digital Receipts

* Status: accepted
* Date: 2026-08-31

## Context and Problem Statement

A substantial portion of Danish consumer grocery spending occurs within Coop Danmark chains (365discount, SuperBrugsen, Kvickly, Dagli'Brugsen). While Storebox covers several retail chains (Salling Group, REMA 1000, etc.), Coop operates its own proprietary digital receipts platform exposed via `medlem.coop.dk` and the Coop app.

Coop does not provide a public API or webhook for third-party personal finance management tools to ingest receipts. Direct server-side scraping would require storing sensitive user passwords / MitID session tokens on the Peng server, which introduces security liabilities, 2FA breakage, and frequent maintenance overhead when authentication workflows change.

## Decision Drivers

* **Security & Zero-Credential Storage**: Peng should never store or handle user Coop passwords, 2FA credentials, or MitID tokens on the server.
* **Low Friction User Experience**: Ingesting receipts should be achievable in 1-click from any modern browser.
* **Multi-Source Receipt Engine**: The ingestion pipeline must integrate cleanly into Peng's dual-database model (`kvitteringer.db`) alongside Storebox.
* **Resilience & Offline Capability**: Support both direct automatic push (via inbound webhook token) and offline JSON export/upload.

## Considered Options

1. **Server-Side Headless Scraping (Playwright/Puppeteer)**: Run headless browser sessions on the Peng server requiring user credentials.
   * *Cons*: Extreme security risk storing credentials, breaks with 2FA/MitID, high resource footprint on low-spec self-hosted hardware.
2. **Client-Side Bookmarklet with Inbound Ingestion Token**: Provide a lightweight JavaScript bookmarklet that executes within the user's authenticated session on `medlem.coop.dk`.
   * *Pros*: Zero credential sharing, leverages existing browser session, fast concurrent fetching, direct sync to Peng or downloadable JSON.

## Decision Outcome

Option 2 was chosen and implemented:

1. **Client-Side Bookmarklet (`coopBookmarklet.ts`)**:
   * Evaluates inside `https://medlem.coop.dk/`.
   * Paginates through `/umbraco/api/receiptsapi/get` and fetches itemized HTML bodies via `/umbraco/api/receiptsapi/getdetails`.
   * Parses line items, quantities, discounts, and totals in the browser.
   * Directly posts the JSON payload to `/api/inbound/coop/{inbound_token}` on the user's Peng instance, with a fallback to local `.json` file download.

2. **Backend Processing (`coop_service.py` & `kvitteringer_service.py`)**:
   * Validates the schema of incoming Coop receipts.
   * Merges and deduplicates receipts in `kvitteringer.db`.
   * Links receipts to bank postings via fuzzy timestamp, amount matching in minor units (integer øre), and store name normalizers.

## Consequences

* **Positive**:
  * Safe and private: user credentials never touch the Peng backend.
  * Fast ingestion: bookmarklet processes dozens of receipts in seconds.
  * Unified receipt experience: Storebox and Coop receipts are queried and matched identically across the app.
* **Negative**:
  * Requires the user to trigger the bookmarklet periodically (semi-automated rather than fully automated background fetch).
