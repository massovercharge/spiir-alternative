# Peng Refactoring Session — Senior Engineer Handoff Prompt

Copy and paste the prompt below into the next session to begin the phased refactoring.

---

```markdown
You are a senior software engineer pair programming on the **Peng** project (self-hostable, bank-agnostic personal finance app inspired by Spiir).

## 🛠️ Project Context & Rules
- **Stack:** FastAPI, SQLite (SQLModel/SQLAlchemy), React 18 (Vite, TypeScript, TailwindCSS).
- 🔴 **Pengebeløb:** All monetary values MUST be stored and handled as `INTEGER` representing the minor unit (øre for DKK, cents for EUR/USD). Do NOT use `float` or `DECIMAL` in the database, and never use float math for monetary conversions.
- 🔴 **i18n:** All UI text must be routed through `react-i18next` (support `da` and `en`). No hardcoded Danish text in UI components or templates.
- **Code Style & Testing:** Backend uses `ruff` (max line length 100) and `pytest`. Frontend uses `eslint`, `prettier`, and `vitest`.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`).

---

## 📚 Code Review Phase References
A comprehensive full-stack code review has been completed. Each refactoring task below links directly to its in-depth analysis and specifications in `docs/code_review/`:
- 📋 [**README.md**](docs/code_review/README.md): Executive summary, architecture scorecard, and top defect matrix.
- 🚀 [**refactoring_backlog.md**](docs/code_review/refactoring_backlog.md): Epics, user stories, acceptance criteria, and priority rankings.
- 🏛️ [**Phase 1: Architecture & Data Models**](docs/code_review/phase1_architecture_data_models.md): Multi-tenancy filter nuances, minor-unit money compliance, dual-database boundaries, and backup retention.
- ⚙️ [**Phase 2: Backend Services & Security**](docs/code_review/phase2_backend_services_security.md): Domain service audit (all 16 services), runtime exceptions, commit bottlenecks, $N+1$ queries, and webhook security.
- 🔌 [**Phase 3: API Layer, Schemas & Testing**](docs/code_review/phase3_backend_api_schemas_testing.md): FastAPI routers, Pydantic response models, exception handling, and pytest coverage gaps.
- 🎨 [**Phase 4: Frontend State & UI/UX**](docs/code_review/phase4_frontend_state_ui.md): React 18 patterns, `api/client.ts` decomposition, i18n violations, and Vitest setup.
- 🚢 [**Phase 5: DevOps, Deployment & Docs**](docs/code_review/phase5_devops_deployment_docs.md): Container hardening, `scripts/check.sh` fix, Cloudflare worker HMAC signing, and missing ADRs.

---

## 🎯 Refactoring Execution Plan (Starting with Most Critical)

Execute the refactoring in the following prioritized phases. Always consult the corresponding phase documentation in `docs/code_review/` before and during each task. Run tests and linting after each phase:

### Phase 1: Critical Bug Fixes & Deployment Safety (P0 — Immediate)
*See [Phase 5 Review (§3.1)](docs/code_review/phase5_devops_deployment_docs.md#31-critical-scriptschecksh-error-suppression), [Phase 2 Review (§2.1 & §2.2)](docs/code_review/phase2_backend_services_security.md#21-csv_servicepy-spiir-csv-import-service), and [Backlog Epic 1](docs/code_review/refactoring_backlog.md#epic-1-critical-bug-fixes--deployment-safety-p0).*

1. **Fix `scripts/check.sh` Error Suppression:**
   - *Reference:* [Phase 5 Review (§3.1)](docs/code_review/phase5_devops_deployment_docs.md#31-critical-scriptschecksh-error-suppression) & [Backlog Story 1.1](docs/code_review/refactoring_backlog.md#story-11-fix-script-error-suppression-in-scriptschecksh).
   - In `scripts/check.sh`, remove `2>/dev/null || true` from the `ruff` and `pytest` lines so linting and test failures abort deployment.
2. **Fix Runtime Crash in `backend/app/services/csv_service.py`:**
   - *Reference:* [Phase 2 Review (§2.1)](docs/code_review/phase2_backend_services_security.md#21-csv_servicepy-spiir-csv-import-service) & [Backlog Story 1.2](docs/code_review/refactoring_backlog.md#story-12-fix-runtime-typeerror-in-csv_servicepy).
   - In `backend/app/services/csv_service.py:193`, remove invalid `description=description` argument from `PostingAllocation` constructor.
   - Add unit test in `backend/tests/test_csv_import.py` verifying error-free Spiir CSV import.
3. **Fix Runtime Crash in `backend/app/services/transfer_service.py`:**
   - *Reference:* [Phase 2 Review (§2.2)](docs/code_review/phase2_backend_services_security.md#22-transfer_servicepy-internal-transfer-auto-detection) & [Backlog Story 1.3](docs/code_review/refactoring_backlog.md#story-13-fix-category-constructor-crash-in-transfer_servicepy).
   - In `backend/app/services/transfer_service.py:51`, replace `name="Kontooverførsel"` with `sub_name="Kontooverførsel"` in `Category` constructor.
   - Add unit test verifying transfer auto-detection works when the transfer category does not pre-exist.

### Phase 2: Minor-Unit Money Arithmetic, Migrations & Storage Integrity (P1)
*See [Phase 1 Review (§1.2 & §1.5)](docs/code_review/phase1_architecture_data_models.md#12-strict-minor-unit-integer-money-handling-7-compliance), [Phase 2 Review (§2.5 & §2.6)](docs/code_review/phase2_backend_services_security.md#25-budget_servicepy-budget-crud-bills--suggestions), and [Backlog Epic 2](docs/code_review/refactoring_backlog.md#epic-2-minor-unit-money-arithmetic-migrations--data-integrity-p1).*

4. **Eliminate Float Arithmetic in Financial Services:**
   - *Reference:* [Phase 1 Review (§1.2)](docs/code_review/phase1_architecture_data_models.md#12-strict-minor-unit-integer-money-handling-7-compliance) & [Backlog Story 2.1](docs/code_review/refactoring_backlog.md#story-21-enforce-strict-minor-unit-integer-arithmetic-across-all-services).
   - In `backend/app/services/transaction_service.py:77`: replace `int(amount_value * 100)` with `to_minor(str(amount_value))`.
   - In `backend/app/services/insights_service.py:295-311`: refactor `get_averages()` to calculate averages natively on integer minor units before formatting, eliminating `sum(float(item["income"]))`.
   - In `backend/app/services/csv_service.py:36`: refactor `_parse_amount()` to use `to_minor(Decimal(clean))`.
5. **Prevent Side-Effect Database Mutation in Read/Suggestion API:**
   - *Reference:* [Phase 2 Review (§2.5)](docs/code_review/phase2_backend_services_security.md#25-budget_servicepy-budget-crud-bills--suggestions) & [Backlog Story 2.3](docs/code_review/refactoring_backlog.md#story-23-prevent-side-effect-db-mutations-in-budget-suggestion-read-api).
   - In `backend/app/services/budget_service.py:359-376`: remove automatic `db.add(Budget(...))` and `db.commit()` inside `generate_budget_suggestion()`.
6. **Implement Backup Rotation & Storage Retention:**
   - *Reference:* [Phase 1 Review (§1.5)](docs/code_review/phase1_architecture_data_models.md#15-database-backup-retention--disk-space-exhaustion) & [Backlog Story 2.2](docs/code_review/refactoring_backlog.md#story-22-implement-automated-backup-rotation--retention-policy).
   - In `backend/app/core/storage.py` and `kvitteringer_service.py`: implement `prune_backups()` to keep only the latest 5 `.bak` snapshots.
   - Clean up existing orphaned `.bak` files in `backend/data/backups/`.

### Phase 3: Backend Performance, Query Optimization & Security (P1)
*See [Phase 2 Review (§2.3, §2.4, §2.7 & §2.9)](docs/code_review/phase2_backend_services_security.md#23-sync_servicepy-enable-banking-retrieval--normalization), [Phase 3 Review (§2 & §3)](docs/code_review/phase3_backend_api_schemas_testing.md), and [Backlog Epic 3](docs/code_review/refactoring_backlog.md#epic-3-backend-performance-query-optimization--security-p1).*

7. **Batch SQLite Commits in Sync Service:**
   - *Reference:* [Phase 2 Review (§2.3)](docs/code_review/phase2_backend_services_security.md#23-sync_servicepy-enable-banking-retrieval--normalization) & [Backlog Story 3.1](docs/code_review/refactoring_backlog.md#story-31-batch-db-commits-in-sync-service).
   - In `backend/app/services/sync_service.py:331`: replace per-transaction `db.commit()` inside the sync loop with `db.flush()` and a single batch `db.commit()`.
8. **Eliminate $N+1$ Query Bottlenecks in Rules Engine:**
   - *Reference:* [Phase 2 Review (§2.7)](docs/code_review/phase2_backend_services_security.md#27-rules_servicepy-auto-categorization-rules-engine) & [Backlog Story 3.2](docs/code_review/refactoring_backlog.md#story-32-eliminate-n1-queries-in-categorization-rules-engine).
   - In `backend/app/services/rules_service.py:706-709`: use `selectinload(Posting.allocations)` in `apply_rules_to_uncategorized()` instead of querying `PostingAllocation` in a loop.
9. **Remove Sensitive Plaintext Logging & Standardize Logger:**
   - *Reference:* [Phase 2 Review (§2.4 & §2.8)](docs/code_review/phase2_backend_services_security.md#24-bank_servicepy-bank-connections--psd2-consent) & [Backlog Story 3.3](docs/code_review/refactoring_backlog.md#story-33-remove-plaintext-sensitive-logging--standardize-logger).
   - In `backend/app/services/bank_service.py` and `household_service.py`: remove `print()` statements dumping session payloads/tokens, and migrate all services to standard `logging.getLogger("peng.<service>")`.
10. **Add Inbound Webhook Secret Authentication:**
    - *Reference:* [Phase 2 Review (§2.9)](docs/code_review/phase2_backend_services_security.md#29-inbound_email_servicepy--imap_workerpy-receipt-ingestion) & [Backlog Story 3.4](docs/code_review/refactoring_backlog.md#story-34-add-inbound-webhook-secret-authentication).
    - In `backend/app/api/routers/inbound.py` and `deploy/cloudflare/email-worker.js`: add `INBOUND_EMAIL_WEBHOOK_SECRET` header validation.

### Phase 4: Frontend Modularity, i18n Compliance & Testing (P2)
*See [Phase 4 Review (§2, §3 & §5)](docs/code_review/phase4_frontend_state_ui.md), [Phase 3 Review (§4)](docs/code_review/phase3_backend_api_schemas_testing.md#4-test-suite-audit--quality-assessment), and [Backlog Epic 4](docs/code_review/refactoring_backlog.md#epic-4-frontend-modularity-i18n--testing-p2).*

11. **Decompose Monolithic `frontend/src/api/client.ts` (1,050+ lines):**
    - *Reference:* [Phase 4 Review (§2.1)](docs/code_review/phase4_frontend_state_ui.md#21-monolithic-api-client-frontendsrcapiclientts) & [Backlog Story 4.1](docs/code_review/refactoring_backlog.md#story-41-decompose-monolithic-frontendsrcapiclientts).
    - Split into `frontend/src/api/http.ts` (base fetch wrapper with auth/household headers), `frontend/src/api/types/` (domain interfaces), and `frontend/src/features/<domain>/api/` (domain React Query hooks).
12. **Fix All Hardcoded Strings & Missing Translations:**
    - *Reference:* [Phase 4 Review (§3)](docs/code_review/phase4_frontend_state_ui.md#3-i18n--localization-compliance) & [Backlog Story 4.2](docs/code_review/refactoring_backlog.md#story-42-resolve-all-hardcoded-strings--translation-inconsistencies).
    - Update `TransactionsPage.tsx`, `BudgetsPage.tsx`, and sidebar components to replace hardcoded Danish text (`"Vælg alle"`, `"poster valgt"`, `"Husk denne fremover?"`, `"Nej tak"`, `"kr. / md"`) and `isDa ? ... : ...` checks with proper `t(...)` keys in `da.json` and `en.json`.
13. **Add Frontend Vitest Component Tests:**
    - *Reference:* [Phase 4 Review (§5)](docs/code_review/phase4_frontend_state_ui.md#5-frontend-automated-testing) & [Backlog Story 4.3](docs/code_review/refactoring_backlog.md#story-43-add-frontend-vitest--playwright-test-suite).
    - Add unit tests for key UI components (`CategoryPicker`, `TransactionFilters`, `MonthGrid`) so `npm test` runs and passes.

### Phase 5: Container Hardening & Documentation (P3)
*See [Phase 5 Review (§2 & §5)](docs/code_review/phase5_devops_deployment_docs.md) and [Backlog Epic 5](docs/code_review/refactoring_backlog.md#epic-5-container-hardening--architecture-documentation-p3).*

14. **Harden Production `Dockerfile`:**
    - *Reference:* [Phase 5 Review (§2.1)](docs/code_review/phase5_devops_deployment_docs.md#21-multi-stage-dockerfile-dockerfile) & [Backlog Story 5.1](docs/code_review/refactoring_backlog.md#story-51-harden-production-docker-container).
    - Create a non-root system user (`peng`) in Stage 2 runtime.
15. **Add Missing Architecture Decision Records (ADRs):**
    - *Reference:* [Phase 5 Review (§5.1)](docs/code_review/phase5_devops_deployment_docs.md#51-architecture-decision-records-docsarchitecturedecisions) & [Backlog Story 5.2](docs/code_review/refactoring_backlog.md#story-52-document-missing-adrs).
    - Create ADR-0004 (Posting vs PostingAllocation Split Architecture) and ADR-0005 (Dual-Database Storage Boundary).

---

## 🚦 Verification Commands
After making changes, verify that the entire stack passes checks:
- **Backend Tests & Linting:**
  ```bash
  source .venv/bin/activate && ruff check backend/app backend/tests && pytest backend/tests/ -v
  ```
- **Frontend Build & Tests:**
  ```bash
  cd frontend && npm test && npm run build
  ```
- **Full Deployment Check:**
  ```bash
  ./scripts/check.sh
  ```
```
