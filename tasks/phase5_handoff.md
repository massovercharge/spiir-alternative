# Peng Refactoring — Phase 5 Handoff Prompt

> **Task Context:** This document serves as the kickoff and context handoff for executing **Phase 5 (P3: DevOps Hardening & Architecture Decision Records)** of the Peng full-stack refactoring initiative.
> **Current Status:** Phases 1 through 4 are **100% complete and verified**. `./scripts/check.sh` passes completely across Ruff linting, backend Pytest, frontend Vitest, and the Vite production build.

---

## 1. Project Rules & Core Conventions
- 🔴 **Pengebeløb:** All monetary values MUST be stored and handled as `INTEGER` representing the minor unit (øre for DKK, cents for EUR/USD). Never use float math for financial conversions.
- 🔴 **i18n:** All UI text must be routed through `react-i18next` (`da` and `en`).
- **Docs:** Maintain the architecture decision records (ADRs) in `docs/architecture/decisions/`.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, etc.). Commits go directly to `main`.
- **Code Style:** Backend uses `ruff` (max line length 100). Frontend uses `eslint` + `prettier`.
- **Verification Gate:** `./scripts/check.sh` runs backend linting, backend tests, frontend Vitest tests, and `npm run build`.

---

## 2. Completed Work (Phases 1–4 Summary)
- **Phase 1 (P0: Critical Bug Fixes):**
  - Removed error suppression in `scripts/check.sh`.
  - Fixed `PostingAllocation` constructor runtime `TypeError` in `csv_service.py` + tests in `test_csv_import.py`.
  - Fixed `Category` constructor crash (`sub_name="Kontooverførsel"`) in `transfer_service.py` + tests in `test_transfers.py`.
- **Phase 2 (P1: Minor-Unit Arithmetic & Storage):**
  - Converted float arithmetic to `to_minor()` in `transaction_service.py`, `insights_service.py:get_averages()`, `csv_service.py`.
  - Automated backup rotation (`prune_backups`, max 5 snapshots) in `storage.py`.
  - Refactored `budget_service.py:generate_budget_suggestion()` to be side-effect-free + added `POST /api/budgets/apply-suggestions` and `test_budgets.py`.
- **Phase 3 (P1: Performance, Security & Logging):**
  - Batched DB commits in `sync_service.py` (every 100 transactions and at end).
  - Eliminated $N+1$ query overhead in `rules_service.py:apply_rules_to_uncategorized()` + cached compiled regexes with `@functools.lru_cache`.
  - Sanitized sensitive token logs and migrated to standard `logging.getLogger("peng.<module>")` in `bank_service.py`, `household_service.py`, `worker.py`, and `transaction_service.py`.
  - Added inbound email webhook secret validation (`INBOUND_EMAIL_WEBHOOK_SECRET`) in `config.py`, `inbound.py`, and `email-worker.js`.
- **Phase 4 (P2: Frontend Modularity & Testing):**
  - Decomposed monolithic `frontend/src/api/client.ts` (1,050+ lines) into `http.ts`, `types/index.ts`, and domain modules under `frontend/src/api/domains/` (`transactions.ts`, `accounts.ts`, `budgets.ts`, `categories.ts`, `insights.ts`, `households.ts`, `rules.ts`, `inbound.ts`).
  - Standardized hardcoded UI strings with `t(...)` in `TransactionsPage.tsx` and `BudgetsPage.tsx` across `da.json` and `en.json`.
  - Created Vitest suite (`client.test.ts`, `i18n.test.ts`) integrated into `scripts/check.sh`.

---

## 3. Phase 5 Execution Checklist (What Needs to Be Done)

### Story 5.1: Container Hardening (`Dockerfile`)
- **Target File:** `Dockerfile`
- **Objective:** Run the container as a non-privileged `peng` user instead of `root`.
- **Requirements:**
  1. Create a system group and user: `groupadd -g 1000 peng && useradd -u 1000 -g peng -s /bin/bash -m peng`.
  2. Ensure data directories exist and have proper ownership:
     - `/app/data`
     - `/app/data/backups`
     - `/app/data/kvitteringer`
     - `/app/data/storebox-downloads`
     - `/app/data/local_secrets`
  3. Set ownership: `chown -R peng:peng /app/data`.
  4. Add `USER peng` directive before `CMD` / `ENTRYPOINT`.
  5. If supervisord / nginx is used in production multi-stage, ensure `/var/run`, `/var/log/nginx`, and cache directories are writeable by `peng`.

### Story 5.2: Architecture Decision Records (ADRs)
Create two new Architecture Decision Records under `docs/architecture/decisions/` conforming to standard ADR format:
1. **`docs/architecture/decisions/0004-split-transactions-and-allocations.md`**:
   - **Title:** `4. Split Bank Postings and Category Allocations`
   - **Status:** `Accepted`
   - **Context:** Financial transactions from bank sync / CSV need to support 1-to-many category splits, separate audit trails, and strict integer minor-unit arithmetic (øre/cents).
   - **Decision:** Split into `Posting` (immutable raw bank transaction with `amount_minor`) and `PostingAllocation` (mutable category assignment with `amount_minor` and `household_id`).
   - **Consequences:** Cleaner accounting, trivial split-transaction support, eliminated float rounding bugs.

2. **`docs/architecture/decisions/0005-dual-database-kvitteringer-storage.md`**:
   - **Title:** `5. Dual-Database Architecture for Structured Ledger and Kvitteringer Storage`
   - **Status:** `Accepted`
   - **Context:** Peng manages structured relational financial ledger data (`peng.sqlite`) and unstructured receipt/Storebox payloads (`kvitteringer.db`).
   - **Decision:** Maintain two distinct SQLite databases to isolate heavy text/JSON receipt payloads, prevent locking issues on high-frequency sync, and enable independent backup/restore cycles.
   - **Consequences:** Clear boundary of concerns, zero contention between receipt OCR/linking and bank transaction queries, lightweight core database.

---

## 4. Final Quality Gate Verification
After completing Phase 5, run:
```bash
./scripts/check.sh
```
All checks must pass with exit code 0.
