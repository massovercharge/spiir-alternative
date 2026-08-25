# Phase 1 Code Review: Architecture, Data Models & Data Integrity

## 1. Executive Summary

Phase 1 investigates the core architectural layer of Peng: database schemas, SQLModel/SQLAlchemy ORM models, multi-tenancy isolation hooks, strict minor-unit integer money handling, dual-database boundaries, and persistence lifecycle.

The foundation follows the V3 architecture ([ADR-0001](file:///home/debian/spiir-alternative/docs/architecture/decisions/0001-integer-money-storage.md) & [ADR-0002](file:///home/debian/spiir-alternative/docs/architecture/decisions/0002-household-management-and-invitations.md)), separating immutable bank postings (`Posting`) from user categorization and split records (`PostingAllocation`). However, key defects exist in database migration practices, tenant filter bypasses in background threads, float math leaks in services, and unbounded database backup file accumulation.

---

## 2. Detailed Findings & Analysis

### 1.1 Multi-Tenant Isolation via ContextVars & ORM Events

#### Mechanism:
Multi-tenancy isolation is implemented in `backend/app/models/all_models.py` via SQLAlchemy event listeners:
- `current_household_id: ContextVar[str]` (line 30)
- `_add_tenant_filter` on `SASession, "do_orm_execute"` (lines 152–168)
- `_receive_before_insert` on `Mapper, "before_insert"` (lines 170–179)

#### Issues Identified:
1. **System vs. Household Categorization Rules:**
   - `CategorizationRule` has `household_id: Optional[str] = None` (for system-seeded rules) and `household_id: str` (for user-created rules).
   - In `_add_tenant_filter` (lines 161–167):
     ```python
     with_loader_criteria(
         SQLModel,
         lambda cls: cls.household_id == bindparam("hh_id", callable_=lambda: current_household_id.get()) if hasattr(cls, "household_id") and cls.__name__ != "HouseholdMember" else True,
         include_aliases=True
     )
     ```
   - When querying `CategorizationRule`, this filter injects `WHERE categorizationrule.household_id = :hh_id`.
   - **Impact:** System rules (`household_id IS NULL`) are filtered out whenever `current_household_id` is active, unless queries explicitly bypass the tenant filter or rules are loaded in a detached session!
2. **Background Thread ContextVar Loss:**
   - Background tasks spawned via `threading.Thread` or `asyncio.create_task` (e.g. `purge_deleted_households_worker`, `run_imap_poller_loop`) run with empty context variables unless explicitly propagated.
   - When a service runs inside a background worker, `current_household_id.get()` raises `LookupError`, resulting in no tenant filter being applied.
3. **Raw SQL Bypasses Tenant Filtering:**
   - Queries executed via `session.exec(text(...))` bypass `with_loader_criteria` completely. Multiple places (like database migrations and category data fixes in `all_models.py`) execute raw SQL.

---

### 1.2 Strict Minor-Unit Integer Money Handling (§7 Compliance)

#### Mandate:
Per project rules in `.agents/AGENTS.md` and [ADR-0001](file:///home/debian/spiir-alternative/docs/architecture/decisions/0001-integer-money-storage.md):
> 🔴 **Pengebeløb:** All monetary values MUST be stored and handled as `INTEGER` representing the minor unit (e.g. øre for DKK, cents for EUR or USD). Do NOT use `float` or `DECIMAL` in the database.

#### Evaluation:
- Database columns in `all_models.py` (`amount_minor`, `balance_minor`, `balance_after_transaction_minor`) are strictly `INTEGER`.
- `app.core.money` provides `to_minor()`, `from_minor()`, and `format_amount()`.

#### Violations & Inconsistencies:
1. **Float Multiplication in `transaction_service.py` (Line 77):**
   ```python
   if amount_op and amount_value is not None:
       amount_minor = int(amount_value * 100) # ⚠️ Float arithmetic bug
   ```
   *Issue:* For float `19.99`, `19.99 * 100` evaluates to `1998.9999999999998` in IEEE 754 float, and `int()` truncates it to `1998` instead of `1999`. Must use `to_minor(str(amount_value))` or `to_minor(Decimal(str(amount_value)))`.
2. **Float Parsing & Averaging in `insights_service.py` (Lines 295–311):**
   ```python
   total_income = sum(float(item["income"]) for item in series)
   total_fixed = sum(float(item["expense_fixed"]) for item in series)
   ...
   "income_avg": format_amount(int((total_income / months_counted) * 100)),
   "income_total": format_amount(int(total_income * 100)),
   ```
   *Issue:* `series` already had formatted strings derived from exact minor integers. The service parses these strings to floats, sums them as floats, multiplies by 100, and truncates to int. This discards integer precision.
3. **Float Parsing in `csv_service.py` (Line 36):**
   ```python
   def _parse_amount(amount_str: str) -> int:
       clean = amount_str.replace('.', '').replace(',', '.')
       return int(round(float(clean) * 100)) # ⚠️ Should use Decimal
   ```
4. **Minor Unit Sign Conventions in Budget Rollover:**
   - In `budget_service.py` (line 454): `carryover = effective_budgeted - actual`.
   - Expenses in `PostingAllocation.amount_minor` are stored as negative integers (e.g. `-50000` for 500 DKK expense).
   - In `Budget.amount_minor`, budgets are stored as positive integers (e.g. `50000` for 500 DKK budget).
   - Combining positive budgeted amount and negative actual amount leads to inverted rollover calculations if signs are not normalized consistently across all budget types.

---

### 1.3 Database Architecture: Dual-Database Isolation & Purge Risks

#### Structure:
The application uses two separate SQLite databases:
1. `backend/data/peng.sqlite`: Main application database (Users, Households, Accounts, Postings, Allocations, Budgets, Rules).
2. `backend/data/kvitteringer.db`: Storebox receipt warehouse (raw receipt dumps, receipt line occurrences, item clusters, price tracker index).

#### Issues Identified:
1. **Destructive Schema Reset in `kvitteringer_service.py` (Lines 775–788):**
   ```python
   def _purge_outdated_database_file() -> bool:
       if version == SCHEMA_VERSION:
           return False
       _delete_database_files() # ⚠️ Deletes entire kvitteringer.db file!
       return True
   ```
   *Risk:* Whenever `SCHEMA_VERSION` is updated or modified, the service deletes `kvitteringer.db`, `kvitteringer.db-shm`, and `kvitteringer.db-wal` from disk. If the raw upload files in `data/storebox-downloads` are missing or corrupted, all receipt history is permanently lost.
2. **Cross-Database Foreign Keys Are Impossible:**
   - `PostingAllocation` contains `item_cluster_id: Optional[str]`, referencing an item cluster in `kvitteringer.db`.
   - Because these are separate SQLite files, foreign key constraints cannot be enforced by the SQLite engine (`PRAGMA foreign_keys=ON` only applies per-database). Orphaned cluster IDs or desynced receipt links cannot be caught at the DB layer.

---

### 1.4 Database Migrations & Schema Evolution

#### Current State:
- Table creation and schema updates are executed inside `create_db_and_tables()` in `backend/app/models/all_models.py` (lines 55–140).
- Ad-hoc `ALTER TABLE` statements are wrapped in `with contextlib.suppress(Exception):`.
- There is no versioned migration tool (such as Alembic).

#### Deficiencies:
- **Silent Failures:** If an `ALTER TABLE` fails due to syntax or SQLite lock contention, `contextlib.suppress(Exception)` silences the error without logging, leaving tables in an inconsistent state.
- **No Down Migrations / Rollbacks:** No mechanism to revert schema changes.
- **No Migration History Table:** Impossible to ascertain which schema revisions have been applied to a production instance.

---

### 1.5 Database Backup Retention & Disk Space Exhaustion

#### Finding:
In `backend/app/core/storage.py` (lines 28–35) and `kvitteringer_service.py` (line 22):
```python
def create_backup(path: Path) -> Path | None:
    backup_dir = get_data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.name}.{_timestamp()}.bak"
    shutil.copy2(path, backup_path)
    return backup_path
```
- Every time receipts are re-indexed or imported, a new `.bak` file is created in `data/backups/`.
- There is **no retention policy, TTL, or max-backup pruning**.
- The workspace currently contains **over 50 backup files** in `backend/data/backups/`. Over time in production, this leads to storage exhaustion on VPS/self-hosted servers.

---

## 3. Phase 1 Refactoring Action Plan

1. **Refactor `_add_tenant_filter`:**
   - Update criteria to allow `CategorizationRule.household_id.is_(None)` alongside the active household ID so system rules are never excluded.
2. **Standardize Money Arithmetic:**
   - Replace all `int(val * 100)` and `float` sums in `transaction_service.py`, `insights_service.py`, and `csv_service.py` with `app.core.money` functions (`to_minor`, `from_minor`).
3. **Implement Backup Retention:**
   - Add automated backup rotation keeping the last $N$ (e.g. 5) backups and deleting older `.bak` files.
4. **Prepare Alembic Migrations:**
   - Replace inline `ALTER TABLE` calls with version-controlled Alembic migrations.
5. **Protect `kvitteringer.db` Lifecycle:**
   - Replace the destructive `_delete_database_files()` with table-level migrations or safe table rebuilds.
