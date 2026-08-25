# 5. Dual-Database Architecture for Structured Ledger and Kvitteringer Storage

* Status: accepted
* Date: 2026-08-25

## Context and Problem Statement

Peng handles two distinct classes of financial data with vastly different access patterns, storage footprints, and performance characteristics:
1. **Core Financial Ledger (`peng.sqlite`)**: High-concurrency, normalized relational data including bank accounts, consent lifecycles, user identity, rules, budgets, immutable postings, and category allocations. Queries are latency-sensitive and power the interactive dashboard, transaction list, and budget overviews.
2. **Receipt and Storebox Archive (`kvitteringer.db`)**: Semi-structured and unstructured receipt ingestion data, itemized receipt line items, store OCR scans, Storebox JSON exports, and full-text search indexes. Individual receipt payloads can be several megabytes each and are loaded or processed in bulk during automated background sync or email ingestion.

If both domains share a single SQLite database file:
* Bulk receipt ingestion and OCR indexing can cause write-lock contention (even with WAL mode enabled), delaying real-time UI queries.
* Database file size grows rapidly due to receipt blobs and JSON blobs, bloating regular ledger backups.
* Corruption or heavy schema migrations in receipt ingestion could jeopardize core ledger availability.

## Decision Drivers

* **Performance & Concurrency**: Ledger operations (bank sync, categorization, budget calculations) must never experience I/O or lock starvation from heavy receipt ingestion or Storebox ZIP processing.
* **Storage Optimization & Backup Strategy**: Core ledger snapshots (`peng.sqlite`) must remain compact for high-frequency point-in-time backups and fast restore.
* **Separation of Concerns**: Receipt itemization and merchant taxonomy mapping should be decoupled from the fundamental double-entry/posting data model.
* **Self-Hostable Simplicity**: Preserve SQLite's zero-configuration, file-based simplicity without requiring a separate database server (e.g. Postgres) for self-hosted instances.

## Considered Options

1. **Single SQLite Database (`peng.sqlite`)**: Store receipt tables (`receipts`, `receipt_items`, `raw_blobs`) alongside `posting` and `account`. (Causes database bloat, backup size amplification, and lock contention during large ZIP imports).
2. **Dual SQLite Architecture**:
   - `peng.sqlite` for core transactional and accounting models managed by SQLModel / SQLAlchemy.
   - `kvitteringer.db` for receipt metadata, Storebox archives, itemized product lines, and merchant matching indexes managed by dedicated SQLite connections.

## Decision Outcome

Option 2 was chosen and implemented:

### 1. Database Boundary Separation
* **Core Ledger (`peng.sqlite`)**:
  * Located at `$PENG_DATA_DIR/peng.sqlite`.
  * Configured with `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON`.
  * Managed via SQLModel / SQLAlchemy models (`Posting`, `PostingAllocation`, `Budget`, `Account`, `Household`, `InboundEmail`).
* **Kvitteringer Archive (`kvitteringer.db`)**:
  * Located at `$PENG_DATA_DIR/kvitteringer.db` (configured via `get_kvitteringer_db_path()`).
  * Dedicated connection pools with `timeout=30.0` and schema versioning via `kvitteringer_meta`.
  * Stores parsed Storebox receipts, itemized line items, receipt image paths, and merchant string similarity indexes.

### 2. Linking Mechanism
* Linkage between bank postings and receipts is maintained via light foreign reference keys (`peng_transaction_id` stored in receipt records) resolved on demand.
* Receipt matching services (`kvitteringer_service.py`) run asynchronously without holding locks on `peng.sqlite`.

### 3. Backup and Maintenance
* `app.core.storage.create_backup` and `prune_backups` independently snapshot `peng.sqlite` and `kvitteringer.db`.
* Upgrades or schema rebuilds in `kvitteringer.db` (e.g. `rebuild_kvitteringer_indexes`) can execute in isolation without taking down the core finance API.

## Consequences

* **Positive**:
  * Zero lock contention between background Storebox ingestion / OCR processing and user-facing transaction browsing.
  * Lightweight `peng.sqlite` (typically < 10 MB for years of transactions), enabling fast backups and minimal memory overhead.
  * Modularity: receipt ingestion subsystems can be developed, optimized, or cleared without affecting ledger integrity.
* **Negative**:
  * Foreign key constraints cannot span across the two physical database files via standard SQLite FK mechanisms; cross-database referential integrity is maintained at the application service layer.
