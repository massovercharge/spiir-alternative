# Peng Refactoring Backlog & Execution Plan

## 1. Overview

This document defines the actionable, prioritized engineering backlog derived from the full-stack code review. Tasks are grouped into 5 thematic Epics ordered by priority and impact.

---

## 2. Prioritized Epics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REFACTORING EPICS & PHASING                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  EPIC 1: Critical Bug Fixes & Deployment Safety (Priority: P0 / Immediate)  │
│  EPIC 2: Money Arithmetic, Migrations & Data Integrity (Priority: P1)       │
│  EPIC 3: Backend Performance, Query Optimization & Security (Priority: P1)  │
│  EPIC 4: Frontend Modularity, i18n & E2E Testing (Priority: P2)             │
│  EPIC 5: Architecture Hardening, Container Security & ADRs (Priority: P3)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Backlog & Acceptance Criteria

### Epic 1: Critical Bug Fixes & Deployment Safety (P0)

#### Story 1.1: Fix Script Error Suppression in `scripts/check.sh`
- **File:** `scripts/check.sh`
- **Problem:** `2>/dev/null || true` suppresses test and lint errors, allowing failing code to deploy.
- **Tasks:**
  1. Remove `2>/dev/null || true` from Ruff and Pytest execution lines.
  2. Enforce strict exit code validation so `check.sh` aborts on any failure.
- **Acceptance Criteria:**
  - Running `./scripts/check.sh` fails with non-zero exit code if any test fails or Ruff reports lint errors.

#### Story 1.2: Fix Runtime `TypeError` in `csv_service.py`
- **File:** `backend/app/services/csv_service.py`
- **Problem:** `PostingAllocation(..., description=description)` throws `TypeError` because `description` is not a field on `PostingAllocation`.
- **Tasks:**
  1. Remove `description=description` from `PostingAllocation` constructor.
  2. Map Spiir description properly to `Posting.original_description` and `PostingAllocation.note`.
  3. Add a unit test `backend/tests/test_csv_import.py`.
- **Acceptance Criteria:**
  - Importing a standard Spiir CSV export file completes with HTTP 200 and imports all rows without exceptions.

#### Story 1.3: Fix `Category` Constructor Crash in `transfer_service.py`
- **File:** `backend/app/services/transfer_service.py`
- **Problem:** `Category(id=..., name="Kontooverførsel")` uses `name` instead of `sub_name`.
- **Tasks:**
  1. Update line 51 to `Category(id=transfer_cat_id, main_name="Vis ikke", sub_name="Kontooverførsel", ...)`.
  2. Add unit test asserting `detect_internal_transfers()` succeeds when the transfer category does not initially exist in DB.
- **Acceptance Criteria:**
  - Transfer detection runs cleanly on fresh databases without `TypeError`.

---

### Epic 2: Minor-Unit Money Arithmetic, Migrations & Data Integrity (P1)

#### Story 2.1: Enforce Strict Minor-Unit Integer Arithmetic Across All Services
- **Files:** `backend/app/services/transaction_service.py`, `backend/app/services/insights_service.py`, `backend/app/services/csv_service.py`, `backend/app/services/budget_service.py`
- **Tasks:**
  1. Replace `int(amount_value * 100)` in `transaction_service.py` with `to_minor(str(amount_value))`.
  2. Refactor `insights_service.py:get_averages` to compute totals and averages natively on integer minor units before formatting.
  3. Refactor `csv_service.py:_parse_amount` to use `to_minor(Decimal(clean))`.
- **Acceptance Criteria:**
  - All financial calculations preserve exact integer minor units without float roundtrip loss.

#### Story 2.2: Implement Automated Backup Rotation & Retention Policy
- **Files:** `backend/app/core/storage.py`, `backend/app/services/kvitteringer_service.py`
- **Tasks:**
  1. Add `prune_backups(prefix: str, max_keep: int = 5)` helper in `storage.py`.
  2. Prune old `.bak` files automatically after creating a new backup.
  3. Clean up the 50+ orphaned `.bak` files in `backend/data/backups/`.
- **Acceptance Criteria:**
  - `data/backups/` maintains at most 5 backup snapshots per database file.

#### Story 2.3: Prevent Side-Effect DB Mutations in Budget Suggestion Read API
- **File:** `backend/app/services/budget_service.py`
- **Tasks:**
  1. Remove automatic `db.add(Budget(...))` and `db.commit()` from `generate_budget_suggestion()`.
  2. Create a separate explicit endpoint `POST /api/budgets/apply-suggestions` if the user chooses to persist suggested budgets.
- **Acceptance Criteria:**
  - Calling `GET` or `POST /api/budgets/generate` returns suggestion data without inserting unconfirmed rows.

---

### Epic 3: Backend Performance, Query Optimization & Security (P1)

#### Story 3.1: Batch DB Commits in Sync Service
- **File:** `backend/app/services/sync_service.py`
- **Tasks:**
  1. Replace per-transaction `db.commit()` inside the sync loop with `db.flush()` and a single `db.commit()` per account or chunk of 100 transactions.
- **Acceptance Criteria:**
  - Enable Banking sync executes significantly faster with minimal SQLite write lock holding time.

#### Story 3.2: Eliminate $N+1$ Queries in Categorization Rules Engine
- **File:** `backend/app/services/rules_service.py`
- **Tasks:**
  1. Use `selectinload(Posting.allocations)` in `apply_rules_to_uncategorized()` instead of querying `PostingAllocation` per posting in a loop.
  2. Implement an in-memory LRU cache for compiled regex patterns keyed by `(pattern, is_regex, partial_match)`.
- **Acceptance Criteria:**
  - Categorizing uncategorized transactions performs a single batch query for allocations.

#### Story 3.3: Remove Plaintext Sensitive Logging & Standardize Logger
- **Files:** `backend/app/services/bank_service.py`, `backend/app/services/household_service.py`, `backend/app/worker.py`
- **Tasks:**
  1. Remove raw JSON payload dumps and debug prints from `bank_service.py` and `household_service.py`.
  2. Replace all `print(...)` statements with `logging.getLogger("peng.<service>")`.
- **Acceptance Criteria:**
  - Logs are structured, level-controlled, and contain no raw bank tokens or credentials.

#### Story 3.4: Add Inbound Webhook Secret Authentication
- **Files:** `backend/app/api/routers/inbound.py`, `deploy/cloudflare/email-worker.js`, `backend/app/core/config.py`
- **Tasks:**
  1. Add `INBOUND_EMAIL_WEBHOOK_SECRET` environment variable support in backend.
  2. Verify secret header `X-Webhook-Secret` or bearer token in `inbound.py`.
  3. Update Cloudflare email worker to forward the secret.
- **Acceptance Criteria:**
  - Unauthenticated requests to `/api/inbound/email` are rejected with HTTP 401.

---

### Epic 4: Frontend Modularity, i18n & Testing (P2)

#### Story 4.1: Decompose Monolithic `frontend/src/api/client.ts`
- **Files:** `frontend/src/api/client.ts` -> `src/api/http.ts`, `src/api/types/`, `src/features/*/api/`
- **Tasks:**
  1. Extract HTTP client, headers, and token management into `api/http.ts`.
  2. Extract data interfaces into `api/types/`.
  3. Group React Query hooks by domain into feature directories (`features/transactions`, `features/budgets`, `features/accounts`, `features/households`).
- **Acceptance Criteria:**
  - `client.ts` is replaced by modular, domain-driven API modules with no file exceeding 250 lines.

#### Story 4.2: Resolve All Hardcoded Strings & Translation Inconsistencies
- **Files:** `frontend/src/pages/TransactionsPage.tsx`, `frontend/src/pages/BudgetsPage.tsx`, `frontend/src/i18n/locales/da.json`, `frontend/src/i18n/locales/en.json`
- **Tasks:**
  1. Add missing keys for `"Vælg alle"`, `"poster valgt"`, `"Husk denne fremover?"`, and `"Nej tak"`.
  2. Replace `isDa ? ... : ...` in `TransactionsPage.tsx` with parameterized translation key.
  3. Use locale-aware currency formatter for all amount displays.
- **Acceptance Criteria:**
  - Switching between English and Danish translates 100% of UI elements without hardcoded Danish text.

#### Story 4.3: Add Frontend Vitest & Playwright Test Suite
- **Files:** `frontend/src/**/*.test.tsx`, `frontend/e2e/`
- **Tasks:**
  1. Add Vitest component unit tests for `CategoryPicker.tsx`, `TransactionFilters.tsx`, and `MonthGrid.tsx`.
  2. Add Playwright E2E smoke test verifying login, transaction list display, and household switcher.
  3. Ensure `npm test` runs and passes cleanly in CI.
- **Acceptance Criteria:**
  - `npm test` runs Vitest suite and passes with 100% success.

---

### Epic 5: Container Hardening & Architecture Documentation (P3)

#### Story 5.1: Harden Production Docker Container
- **File:** `Dockerfile`
- **Tasks:**
  1. Create a non-root `peng` system user in Stage 2.
  2. Set ownership of `/data` and `/app` to `peng:peng` and add `USER peng`.
- **Acceptance Criteria:**
  - Container executes under non-root UID 1000.

#### Story 5.2: Document Missing ADRs
- **Files:** `docs/architecture/decisions/0004-split-transactions-and-allocations.md`, `docs/architecture/decisions/0005-dual-database-kvitteringer-storage.md`
- **Tasks:**
  1. Document ADR-0004 covering `Posting` vs `PostingAllocation` design and multi-split mathematics.
  2. Document ADR-0005 covering `peng.sqlite` vs `kvitteringer.db` boundary and receipt ingestion pipeline.
- **Acceptance Criteria:**
  - ADR index is up to date and reflects the V3 architecture.
