# Peng Full-Stack Code Review — Executive Summary & Roadmap

## 1. Overview & Context

This comprehensive code review evaluates the complete **Peng** codebase—a bank-agnostic, self-hostable personal finance application built with **FastAPI**, **SQLite** (SQLModel/SQLAlchemy), and **React 18** (**Vite**, **TypeScript**, **TailwindCSS**).

The review assesses architecture, data integrity, security, domain service logic, multi-tenancy isolation, API design, frontend state management, test coverage, i18n compliance, and DevOps infrastructure against the project rules and standards defined in `.agents/AGENTS.md`.

---

## 2. Overall Stack Scorecard

| Domain | Rating | Summary |
| :--- | :---: | :--- |
| **Architecture & Separation of Concerns** | **B+** | Clean separation of backend `api/`, `core/`, `models/`, `services/` and frontend `components/`, `pages/`, `context/`. Minor leakage of HTTP concerns into services and monolithic `api/client.ts`. |
| **Data Integrity & Minor Units (§7)** | **B-** | The core rule of integer minor units (`amount_minor`) is followed across the main database schema, but several critical arithmetic leaks exist in `insights_service.py`, `transaction_service.py`, and `csv_service.py` where floats are multiplied and truncated. |
| **Multi-Tenancy & Tenant Isolation** | **B** | ContextVar + SQLAlchemy event listener (`_add_tenant_filter`) provides transparent household isolation for ORM queries. However, background workers, raw SQL, and global single-threaded locks bypass or clash with multi-tenant contexts. |
| **Security & Auth** | **B** | Logto OIDC token validation and HTTP Basic auth are well-implemented. Inbound webhooks lack signature verification/secret tokens, and raw bank payloads with sensitive identifiers are logged to stdout in some services. |
| **Backend Services & Business Logic** | **C+** | Rich domain logic (Spiir rules engine, Storebox receipt matching, transfer auto-detection). However, several services suffer from $O(N)$ full-table in-memory loads, $N+1$ query loops, per-row commit bottlenecks, and a bug in `csv_service.py` causing runtime exceptions. |
| **Frontend Architecture & UX** | **B+** | Modern React 18, React Query v5, virtualized transaction lists (`@tanstack/react-virtual`), animated state transitions (`framer-motion`), and full dark/light theme support. `api/client.ts` is an oversized monolith (1,050+ lines). |
| **i18n & Localization** | **B-** | `react-i18next` configured for `da` and `en`. Most text is translated, but multiple hardcoded Danish strings and manual `i18n.language === 'da'` conditionals exist in pages and sidebars. |
| **Testing & Quality Assurance** | **B** | Backend has 143 passing pytest integration tests with in-memory SQLite fixtures. Frontend has zero Vitest or Playwright test files (`npm test` currently exits with error code 1). |
| **CI/CD, DevOps & Automation** | **C** | Docker multi-stage build is well structured. However, `scripts/check.sh` suppresses test and lint failures with `|| true`, allowing failing builds to deploy. Automatic database backups in `data/backups/` have no retention limit, causing storage bloat. |

---

## 3. Top 10 Critical & High Severity Findings

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 KEY DEFECT MATRIX BY SEVERITY                                     │
├────┬──────────┬─────────────────────────────────────┬────────────────────────────────────────────┤
│ #  │ Severity │ Module / File                       │ Issue Summary                              │
├────┼──────────┼─────────────────────────────────────┼────────────────────────────────────────────┤
│ 1  │ CRITICAL │ scripts/check.sh                    │ `|| true` suppresses test & lint failures   │
│ 2  │ CRITICAL │ services/csv_service.py             │ Invalid kwarg crashes Spiir CSV import     │
│ 3  │ HIGH     │ services/transfer_service.py        │ Crashes when creating Category ('name')    │
│ 4  │ HIGH     │ core/money.py / services            │ Float math conversions leak rounding error │
│ 5  │ HIGH     │ models/all_models.py / migrations   │ Lack of migration tool / suppressed ALTERs │
│ 6  │ HIGH     │ services/sync_service.py            │ Global mutex blocks multi-household sync   │
│ 7  │ HIGH     │ services/sync_service.py            │ Per-transaction DB commits bottleneck I/O  │
│ 8  │ HIGH     │ core/storage.py / kvitteringer      │ Unbounded database backups leak disk space │
│ 9  │ MEDIUM   │ frontend/api/client.ts              │ 1,050-line monolith couples API & queries  │
│ 10 │ MEDIUM   │ frontend/src/pages/                 │ Hardcoded strings violate i18n mandate     │
└────┴──────────┴─────────────────────────────────────┴────────────────────────────────────────────┘
```

1. **[CRITICAL] `scripts/check.sh` suppresses test and lint failures:** Lines 17 and 20 pipe errors to `/dev/null` and append `|| true`. Deployment succeeds even if tests fail completely.
2. **[CRITICAL] Runtime Crash in `csv_service.py`:** Line 193 instantiates `PostingAllocation(..., description=description)` which throws `TypeError: unexpected keyword argument 'description'` as `description` does not exist on `PostingAllocation`.
3. **[HIGH] Runtime Crash in `transfer_service.py`:** Line 51 creates `Category(id=..., name="Kontooverførsel")` using `name` instead of `sub_name`, throwing `TypeError` when the default transfer category is missing.
4. **[HIGH] Floating-Point Arithmetic Inaccuracies in Minor Units:** `int(amount_value * 100)` in `transaction_service.py`, `sum(float(...))` in `insights_service.py`, and `round(float(clean) * 100)` in `csv_service.py` bypass `app.core.money` Decimal conversions and risk penny-off rounding bugs.
5. **[HIGH] Migration Fragility & Schema Drift:** Database schema relies on inline `ALTER TABLE` statements inside `contextlib.suppress(Exception)` on startup. Column type modifications, index additions, and rollback support are impossible without a formal Alembic migration pipeline.
6. **[HIGH] Global Mutex in Sync Service Blocks Multi-Tenancy:** In-memory `_RETRIEVE_LOCK` and `_RETRIEVE_STATE` allow only one sync job across the entire backend process. Syncing Household A blocks Household B.
7. **[HIGH] SQLite Commit-Per-Row I/O Bottleneck:** `sync_service.py` executes `db.commit()` on every single normalized transaction inside the sync loop. A 500-transaction sync performs 500 disk syncs rather than batching in a transaction.
8. **[HIGH] Backup Storage Leak:** `create_backup` in `core/storage.py` and `kvitteringer_service.py` creates a timestamped copy of `.db` files without retention limits, resulting in unbounded disk usage.
9. **[MEDIUM] Monolithic Frontend API Client:** `frontend/src/api/client.ts` exceeds 1,050 lines, combining raw fetch calls, TypeScript types, and React Query custom hooks into a single tightly-coupled file.
10. **[MEDIUM] i18n Gaps & Hardcoded Strings:** Multiple pages (`TransactionsPage.tsx`, `BudgetsPage.tsx`, `SettingsPage.tsx`) contain hardcoded Danish strings and direct locale checks (`i18n.language === 'da'`) instead of react-i18next translation keys.

---

## 4. Documentation Structure

This review is organized into 5 domain-specific documents plus an actionable refactoring backlog:

- **[Phase 1: Architecture, Data Models & Data Integrity](phase1_architecture_data_models.md)**  
  *Schema normalization, SQLModel models, multi-tenancy isolation, integer money compliance, dual-database architecture, and backup management.*
- **[Phase 2: Backend Services, Business Logic & Security](phase2_backend_services_security.md)**  
  *Detailed analysis of all 16 backend services, rules engine, sync orchestration, Storebox ingestion, token security, and thread safety.*
- **[Phase 3: Backend API Layer, Schemas & Testing](phase3_backend_api_schemas_testing.md)**  
  *FastAPI routers, Pydantic v2 schemas, REST consistency, domain error handling, and test suite evaluation.*
- **[Phase 4: Frontend Architecture, State, Components & UI/UX](phase4_frontend_state_ui.md)**  
  *React 18 patterns, React Query cache architecture, design system, theme consistency, virtual list performance, and i18n.*
- **[Phase 5: DevOps, Deployment, CI/CD & Documentation](phase5_devops_deployment_docs.md)**  
  *Docker containerization, Cloudflare email worker, deployment script robustness, ADR alignment, and release note workflows.*
- **[Refactoring Backlog & Execution Plan](refactoring_backlog.md)**  
  *Prioritized Epics, user stories, acceptance criteria, and step-by-step implementation phases.*
