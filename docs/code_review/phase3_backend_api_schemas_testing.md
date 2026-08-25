# Phase 3 Code Review: Backend API Layer, Schemas & Testing

## 1. Executive Summary

Phase 3 evaluates the FastAPI REST interface (`backend/app/api/routers/`), request/response data contracts (`backend/app/schemas/`), input validation mechanisms, and backend automated testing (`backend/tests/`).

The backend features 143 passing pytest integration tests against an in-memory SQLite database, demonstrating good baseline test coverage for CRUD operations. However, significant architectural gaps exist in the schema layer: lack of Pydantic response models, missing OpenAPI typing contracts, loose error handling, and untested edge cases in multi-tenancy and CSV parsing.

---

## 2. API Design & Routing Architecture

### 2.1 Router Structure & Organization
Routers are grouped by domain in `backend/app/api/routers/`:
- `accounts.py`: Bank account listing, metadata updates, balance history.
- `admin.py`: Administrative operations.
- `bank.py`: Enable Banking connection flow and OAuth callbacks.
- `budgets.py`: Annual summaries, monthly limits, and bill CRUD.
- `categories.py`: Taxonomy listing and category metadata.
- `csv_import.py`: Spiir CSV file upload endpoint.
- `health.py`: Health check and version reporting.
- `households.py`: Household CRUD, member invites, role updates, and inbound email management.
- `inbound.py`: Unauthenticated inbound email receipt webhook.
- `insights.py`: Income/expense time series, sunburst charts, category trends.
- `recurring.py`: Recurring fixed expense tracking and proposals.
- `rules.py`: Keyword and regex categorization rule management.
- `sync.py`: Enable Banking transaction sync trigger and progress polling.
- `transactions.py`: Paginated posting list, categorization patches, splits, and receipt links.

### 2.2 Routing Inconsistencies & Issues
1. **Health Check Version Drift:**
   - In `backend/app/main.py` (line 101): `health_check()` hardcodes `{"status": "ok", "version": "0.1.0"}` while `FastAPI(..., version="1.3.0")` and `package.json` specifies `"1.5.3"`. Version numbers should be dynamically sourced from `app.__version__` or package metadata.
2. **Missing Response Schemas (`response_model`):**
   - The majority of router endpoints omit `response_model=...` in their decorator definitions (e.g. `@router.get("/transactions")`, `@router.get("/insights/income-expense-series")`, `@router.post("/budgets")`).
   - **Impact:** FastAPI cannot generate accurate OpenAPI/Swagger documentation, and API outputs are not validated or sanitized through Pydantic response filters before serialization.
3. **Inconsistent REST Verb Usage:**
   - `PUT /api/transactions/{id}/category` updates a single field of a transaction (should conventionally be `PATCH`).
   - `POST /api/budgets/bills` is used for replacing bills rather than `PUT` or `POST /api/budgets/bills/batch`.

---

## 3. Pydantic Schemas & Data Validation

### 3.1 Schema Completeness (`backend/app/schemas/requests.py`)
- Request models are defined cleanly in `requests.py` with Pydantic v2 validators (`@field_validator`).
- **Deficiency:** There is no corresponding `schemas/responses.py`. All responses return raw Python dictionaries (`dict[str, Any]`), bypassing schema validation.

### 3.2 Key Validation Gaps:
- **`TransactionPatch`:** Allows arbitrary string values for `category_id` without verifying format (`main|sub` slug) or existence against the database taxonomy.
- **`BudgetUpsertRequest`:** `month` lacks bounds validation (`Field(..., ge=1, le=12)`).
- **`RuleCreateRequest`:** `match_pattern` is validated for `min_length=1`, but when `is_regex=True`, regex syntax validity is not verified at schema validation time, allowing invalid regexes (`re.error`) to be saved.

---

## 4. Test Suite Audit & Quality Assessment

### 4.1 Pytest Suite Execution
- **Collected:** 143 test cases across 8 test modules.
- **Result:** 143 passed in 10.01 seconds.
- **Configuration:** `pyproject.toml` configures in-memory SQLite database fixtures (`sqlite:///:memory:`) via `conftest.py`.

```
backend/tests/test_categorization.py    [  1%]
backend/tests/test_database.py          [ 18%]
backend/tests/test_household.py         [ 23%]
backend/tests/test_inbound_email.py     [ 28%]
backend/tests/test_money.py             [ 46%]
backend/tests/test_recurring.py         [ 49%]
backend/tests/test_rules.py             [ 77%]
backend/tests/test_sync_integration.py  [ 79%]
backend/tests/test_sync_service.py      [100%]
```

### 4.2 Test Coverage Gaps & Blind Spots:
1. **Missing Tests for `csv_service.py`:**
   - There are zero tests covering Spiir CSV parsing and import in `backend/tests/`. This allowed the critical `description=description` runtime crash to remain undetected.
2. **Missing Tests for `transfer_service.py`:**
   - Internal transfer auto-detection and category generation have no dedicated test module.
3. **Multi-Tenant Leakage Edge Cases:**
   - Existing tests in `test_household.py` verify membership creation, but do not test whether a query executed under Household A can accidentally access transactions or rules belonging to Household B.
4. **Mock Quality in Inbound Email Tests:**
   - Tests in `test_inbound_email.py` test regex parsing and token resolution well, but mock the Storebox download step without testing corrupted or malicious ZIP payloads.

---

## 5. Phase 3 Refactoring Action Plan

1. **Create Pydantic Response Schemas (`backend/app/schemas/responses.py`):**
   - Define typed response schemas for `TransactionResponse`, `AccountResponse`, `BudgetSummaryResponse`, `InsightsSeriesResponse`, `RuleResponse`, and `HouseholdResponse`.
   - Add `response_model` annotations to all FastAPI route handlers.
2. **Standardize Error Handling & Exception Middleware:**
   - Create domain exceptions (`NotFoundError`, `ValidationError`, `TenantAccessError`, `SyncError`) in `backend/app/core/exceptions.py`.
   - Map domain exceptions to standardized JSON error responses via FastAPI exception handlers.
3. **Expand Test Suite:**
   - Add `test_csv_import.py` with valid and malformed Spiir CSV fixtures.
   - Add `test_transfers.py` covering inter-account transfers, savings account routing, and split integrity.
   - Add multi-tenant isolation integration tests ensuring strict query segregation across multiple active households.
