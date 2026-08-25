# 4. Split Bank Postings and Category Allocations

* Status: accepted
* Date: 2026-08-25

## Context and Problem Statement

In earlier iterations of personal finance platforms (including legacy versions of the application and typical bank exports), a single transaction record was overloaded to represent both the raw bank event and its user categorization. This created several critical design flaws:
1. **No Split Transactions**: When a user makes a combined purchase (e.g. 800 DKK at Bilka consisting of 600 DKK Dagligvarer and 200 DKK Tøj), a 1:1 transaction table cannot allocate the single bank posting to multiple categories without distorting the raw bank balance or duplicating rows.
2. **Loss of Auditability & Sync Invalidation**: If the user modifies dates, descriptions, or amounts to fit their personal budgeting, syncing incremental updates or reconciling balances from PSD2 Open Banking APIs (Enable Banking) becomes hazardous and prone to data corruption.
3. **Floating-Point Rounding**: Splitting transactions using floating-point math often resulted in fractional penny/øre errors where sum of split parts did not equal the transaction total.

## Decision Drivers

* **Immutability of Bank Events**: Raw bank postings received via PSD2 Open Banking or CSV imports must remain immutable representations of financial truth.
* **1-to-Many Category Splits**: Users must be able to divide any single bank transaction across $N$ arbitrary category allocations with custom notes and tags.
* **Invariant Integrity**: The sum of allocation amounts must always equal the parent posting amount (`sum(PostingAllocation.amount_minor) == Posting.amount_minor`).
* **Multi-Tenant Isolation**: Both postings and allocations must enforce household-level tenancy and multi-user collaboration.
* **Strict Minor-Unit Arithmetic**: All monetary quantities must be stored and computed as integer minor units (`amount_minor: int`).

## Considered Options

1. **Monolithic Transaction Table with Split Sub-table**: Keep standard transactions in `Transaction` and only create sub-rows for split transactions. (Leads to dual querying paths where non-split and split queries need `UNION` or complex conditional joins).
2. **Normalized 1:N Posting + PostingAllocation Model**: Every bank transaction produces exactly one `Posting` and at least one `PostingAllocation`. Simple transactions have 1 allocation; split transactions have $N \ge 2$ allocations.

## Decision Outcome

Option 2 was chosen and implemented in the V3 data model:

### 1. Model Separation
* **`Posting`**: Represents the immutable financial posting from the bank.
  * Unique ID format: `eb:<account_uid>:<entry_reference>` (or `csv:<account_uid>:<hash>`).
  * Stores raw bank metadata: `booking_date`, `original_description`, `amount_minor`, `currency`, `debtor_name`, `creditor_name`, `merchant_category_code`, `balance_after_transaction_minor`.
  * Linked to `Account` and consolidated `Payee`.
* **`PostingAllocation`**: Represents the mutable user categorization and split breakdown.
  * Fields: `posting_id` (FK to `Posting`), `category_id` (FK to `Category`), `amount_minor`, `note`, `is_extraordinary`, `item_name`, `item_cluster_id`.
  * Many-to-many relationship with `Tag` via `PostingAllocationTagLink`.

### 2. Integrity and Querying
* Monthly insights, category spending, and budget comparisons aggregate directly from `PostingAllocation`.
* Account balances and bank reconciliation aggregate directly from `Posting`.
* Splitting a transaction is a transaction-safe operation updating or replacing `PostingAllocation` rows while keeping the `Posting` untouched.

## Consequences

* **Positive**:
  * Clean accounting architecture with unambiguous separation of raw bank data vs. user modifications.
  * Trivial split transaction management without schema anomalies or special-casing in reporting queries.
  * Perfect mathematical accuracy when combined with integer minor-unit math (ADR-0001).
  * Seamless re-categorization and rule evaluation without altering raw bank descriptions or timestamps.
* **Negative**:
  * Queries joining postings with allocations require standard relational joins (`Posting` $\leftrightarrow$ `PostingAllocation`).
  * Creating a transaction from scratch or import requires inserting both a `Posting` and initial `PostingAllocation`.
