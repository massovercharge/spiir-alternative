# Spiir-Alternative V2 Rewrite — Agent Handoff Prompt

## Project Location
`/home/danielw/Documents/projects/spiir-alternative`

## Deployment
- Server: `192.168.50.5` via `./scripts/deploy.sh` (rsync + docker compose)
- Public URL: `https://spiir.seame.click`
- Auth: **Logto** (keep as-is — `backend/app/auth.py` + frontend Logto SDK)

## Architecture Plan
See: `~/.gemini/antigravity/brain/184bbfcc-61d8-4d60-8996-7dd6abfe3c0a/artifacts/v2_rewrite_plan.md`

---

## What Has Been Done (Phase 1 — Backend)

### ✅ New V2 Database Schema (`backend/app/database.py`)
Completely rewritten with SQLModel. **No more `payload_json` blobs.** Models:
- `Account` — bank accounts linked via Enable Banking
- `Category` — taxonomy rows (e.g. `"bolig|boliglån-husleje"`)
- `Transaction` — flat columns for amount, description, category_id, custom_note, is_extraordinary, is_excluded, etc. Category overrides are **directly on the Transaction row** (no separate BankOverride table)
- `SyncJob` — tracks Enable Banking retrieval jobs in SQLite (replaces JSON status file)

Database file: `data/database.sqlite` (was `data/v2_database.sqlite`, updated to just `database.sqlite`)

### ✅ New Category Service (`backend/app/category_service.py`)
- `DEFAULT_TAXONOMY` dict with all Spiir categories
- `seed_categories()` — idempotent seeding into `Category` table
- `list_categories()` / `get_taxonomy_response()` — query taxonomy from DB
- `make_category_id(main, sub)` — slugified composite key

### ✅ New Transaction Service (`backend/app/transaction_service.py`)
- `list_transactions(limit, offset, account_uid, search)` — paginated with filtering
- `get_transaction(id)` — single lookup
- `update_transactions(ids, patch)` — apply category/note/flag changes directly to rows
- `income_expense_series()` — monthly income/expense aggregates (respects `is_excluded`)
- `sunburst_data()` — hierarchical Plotly sunburst data grouped by category

### ✅ New Sync Service (`backend/app/sync_service.py`)
- Preserves all Enable Banking JWT auth, pagination, raw JSON archiving
- `_normalize_and_persist()` — upserts directly into `Account` + `Transaction` tables
- `retrieve_transactions()` — orchestrates the full sync flow
- `start_sync_job()` / `get_sync_status()` — background thread with SyncJob table tracking
- **Bank-agnostic**: all "Nordea" references have been removed from the entire codebase

### ✅ New V2 API (`backend/app/api.py`)
Clean REST endpoints:
- `GET /api/status`
- `GET /api/transactions` (paginated, filterable)
- `GET /api/transactions/{id}`
- `PATCH /api/transactions` (override category/note/flags)
- `GET /api/categories`
- `GET /api/insights/income-expense-series`
- `GET /api/insights/sunburst`
- `POST /api/sync/start`
- `GET /api/sync/status`

**Plus backward-compatibility aliases** so the old frontend still works:
- `GET /api/bank/taxonomy` → categories
- `GET /api/bank/retrieve/start` → sync start
- `GET /api/bank/retrieve/status` → sync status
- `GET /api/spiir/local-ledger/transactions` → transactions
- `POST /api/spiir/local-ledger/overrides` → update (with old category format mapping)
- `GET /api/spiir/local-ledger/income-expense-series` → insights
- `GET /api/spiir/status` → status
- `GET /api/bank/transactions` → transactions
- `POST /api/bank/overrides` → update

### ✅ Dockerfile Updated
`backend/Dockerfile` CMD now points to `app.api:app` instead of `app.reference_api:app`

### ✅ Tests (`backend/tests/test_database.py`)
16 passing tests (0.5s) covering:
- All 4 database models (CRUD, defaults, updates)
- Category seeding + idempotency
- Transaction listing, pagination, search, updates
- Income/expense series (including `is_excluded` filtering)
- All tests use in-memory SQLite — no file pollution

### ✅ Dev Environment
- Python venv at `.venv/` with `pytest`, `pytest-asyncio`, `ruff`
- `ruff check` passes clean on all new files
- Run tests: `source .venv/bin/activate && PYTHONPATH=backend pytest backend/tests/ -v`

### ✅ Deployed to Server
The V2 API is running on `192.168.50.5`. It starts up cleanly and seeds categories on boot.

### ✅ Migration Script (`scripts/migrate_v1_to_v2.py`)
Written but **NOT YET EXECUTED on server**. It reads old `BankTransaction`/`BankAccount`/`BankOverride` tables from the old `data/database.sqlite` and inserts into the new V2 schema. The script needs to be copied into the container and run:
```bash
ssh root@192.168.50.5 "docker cp /opt/spiir-alternative/scripts/migrate_v1_to_v2.py spiir-alternative-spiir-api-1:/app/migrate_v1_to_v2.py && docker exec -e PYTHONPATH=/app spiir-alternative-spiir-api-1 python /app/migrate_v1_to_v2.py"
```

**IMPORTANT**: The old and new schemas both write to `data/database.sqlite` now. The migration script defines V1 models with explicit `__tablename__` to read from the old tables (`bankaccount`, `banktransaction`, `bankoverride`). The new V2 tables are `account`, `category`, `transaction`, `syncjob`. They can coexist in the same file.

---

## What Remains

### Phase 1 — Remaining Backend Work
1. **Run the migration script** on the server (see command above). Verify data migrated correctly.
2. **Delete legacy service files** once migration is confirmed:
   - `backend/app/bank_service.py` (replaced by `sync_service.py` + `transaction_service.py` + `category_service.py`)
   - `backend/app/spiir_service.py` (replaced by `transaction_service.py`)
   - `backend/app/spiir_local_ledger_service.py` (replaced by `transaction_service.py`)
   - `backend/app/local_ledger_overrides.py` (no longer needed)
   - `backend/app/reference_api.py` (replaced by `api.py`)
   - `backend/app/scheduler.py` (rewrite if periodic sync is desired)
3. **Clean up `config.py`** — remove all the `get_spiir_*` path helpers that point to JSON files. Only `get_data_dir()` and `get_storebox_source_dir()` / `get_kvitteringer_*` are needed.

### Phase 2 — Frontend Rewrite
The frontend is currently a monolithic React app. The old files still call old API endpoints — the backward-compat aliases in `api.py` bridge this gap for now.

TODO:
1. **Modularize `BankDashboard.tsx`** (3600+ lines) into:
   - `pages/Dashboard.tsx`
   - `components/charts/SunburstChart.tsx`
   - `components/transactions/TransactionTable.tsx`
   - `components/filters/FilterBar.tsx`
   - `components/sync/SyncManager.tsx`
2. **Update `frontend/src/api.ts`** to call the new clean endpoints (`/api/transactions`, `/api/categories`, `/api/sync/*`, `/api/insights/*`) instead of the old Spiir/bank paths.
3. **Keep Logto auth** — `frontend/src/Auth.tsx` is working and should remain unchanged.
4. **Preserve Plotly sunburst** — the new `/api/insights/sunburst` endpoint already returns the exact `{labels, parents, values}` format Plotly expects.

### Phase 3 — Testing & CI/CD
1. **Add `vitest`** to frontend for component tests.
2. **Expand `deploy.sh`** to run `pytest` + `vitest` before deploying (fail-fast CI).
3. **Pre-commit hooks** with `ruff` + `vitest`.

### Phase 4 — Final Cleanup
1. Remove all backward-compat aliases from `api.py` once frontend is updated.
2. Update `README.md` and `docs/` to reflect V2 architecture.
3. Clean up the orphan `spiir-alternative-api-1` container on the server: `docker compose up -d --remove-orphans`

---

## Key Files Summary

| File | Status | Purpose |
|------|--------|---------|
| `backend/app/database.py` | ✅ NEW | V2 SQLModel schema |
| `backend/app/category_service.py` | ✅ NEW | Taxonomy CRUD |
| `backend/app/transaction_service.py` | ✅ NEW | Transaction CRUD + insights |
| `backend/app/sync_service.py` | ✅ NEW | Enable Banking sync |
| `backend/app/api.py` | ✅ NEW | V2 FastAPI endpoints |
| `backend/app/auth.py` | ✅ KEPT | Logto JWT verification |
| `backend/tests/test_database.py` | ✅ NEW | 16 passing tests |
| `scripts/migrate_v1_to_v2.py` | ⏳ NOT RUN | V1→V2 data migration |
| `backend/app/bank_service.py` | 🗑️ DELETE | Old V1 service |
| `backend/app/spiir_service.py` | 🗑️ DELETE | Old V1 service |
| `backend/app/spiir_local_ledger_service.py` | 🗑️ DELETE | Old V1 service |
| `backend/app/reference_api.py` | 🗑️ DELETE | Old V1 API |
| `frontend/src/BankDashboard.tsx` | 🔄 REWRITE | Monolithic → components |
| `frontend/src/api.ts` | 🔄 UPDATE | Point to V2 endpoints |
