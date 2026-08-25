# Phase 2 Code Review: Backend Services, Business Logic & Security

## 1. Executive Summary

Phase 2 provides an exhaustive, function-by-function audit of all 16 backend domain services located in `backend/app/services/`, alongside security mechanisms (`auth.py`), external integrations (Enable Banking, Cloudflare Email, Storebox), background workers (`worker.py`, `imap_worker.py`), and thread-safety invariants.

While domain features (such as the 324-keyword Spiir Danish market categorization engine and Storebox receipt split linker) are conceptually robust, several critical runtime bugs, performance bottlenecks ($O(N)$ full-table memory loads, commit-per-row loops), and security gaps (unauthenticated webhooks, plaintext sensitive data logging) were discovered.

---

## 2. Service-by-Service Audit & Critical Defects

### 2.1 `csv_service.py` (Spiir CSV Import Service)
- **[CRITICAL ERROR] Runtime Crash on Insert (Line 193):**
  ```python
  alloc = PostingAllocation(
      posting_id=posting_id,
      amount_minor=amount_minor,
      category_id=cat_id,
      description=description, # 💥 ERROR: PostingAllocation has no 'description' field
      note=row.get("Comment", ""),
      is_extraordinary=(row.get("Extraordinary", "No").lower() == "yes")
  )
  ```
  `PostingAllocation` defines `note`, `item_name`, and `item_cluster_id`. Passing `description=description` causes a Python `TypeError` immediately upon importing any non-merged CSV posting.
- **[HIGH] Dangerous Fuzzy Match on Date & Amount Only (Lines 102–106):**
  ```python
  existing_postings = db.exec(
      select(Posting)
      .where(Posting.booking_date == date_str)
      .where(Posting.amount_minor == amount_minor)
  ).all()
  ```
  If a user has two distinct 100 DKK transactions on the same date (e.g. Netto and 7-Eleven), this query matches *both* and overwrites the category and tags of *all* matching postings with the CSV row's attributes.

---

### 2.2 `transfer_service.py` (Internal Transfer Auto-Detection)
- **[HIGH ERROR] Runtime Crash on Missing Category (Line 51):**
  ```python
  transfer_cat = Category(
      id=transfer_cat_id, 
      main_name="Vis ikke", 
      name="Kontooverførsel", # 💥 ERROR: Category model field is 'sub_name', not 'name'
      expense_type="Variable"
  )
  ```
  If `Vis ikke|Kontooverførsel` is missing in the database, this throws `TypeError: Category.__init__() got an unexpected keyword argument 'name'`.
- **[PERFORMANCE] $O(N)$ Full Table In-Memory Load & $O(K^2)$ Matching Loop (Lines 28–34):**
  ```python
  postings = db.exec(select(Posting).order_by(col(Posting.booking_date).asc())).all()
  allocations = db.exec(select(PostingAllocation)).all()
  ```
  Loads all postings and allocations in the entire household into Python memory on every transfer detection run (triggered on every account update and sync completion). As transaction history grows, this causes memory pressure and CPU spikes.
- **[LOGIC] Corruption of Split Transactions (Line 34):**
  `alloc_by_posting = {a.posting_id: a for a in allocations}` assumes a 1:1 mapping between posting and allocation. For split transactions with multiple allocations, it overwrites with the last allocation and corrupts allocation amounts.

---

### 2.3 `sync_service.py` (Enable Banking Retrieval & Normalization)
- **[HIGH] Commit-Per-Row I/O Bottleneck (Line 331):**
  ```python
  for raw_dict in raw_txs:
      ...
      db.add(posting)
      db.add(alloc)
      db.commit()  # ⚠️ Disk commit for EVERY single transaction
  ```
  A sync job with 500 transactions executes 500 synchronous SQLite disk writes and lock acquisitions. This should be batched via `db.flush()` with a single `db.commit()` per account or batch.
- **[CONCURRENCY] Global Mutex Blocks Multi-Tenancy (Lines 30–31, 631–650):**
  ```python
  _RETRIEVE_STATE: dict[str, Any] = {"thread": None}
  _RETRIEVE_LOCK = threading.Lock()
  ```
  A single global lock and thread variable prevents concurrent syncs across households. If Household A starts a bank sync, Household B is blocked from syncing until Household A completes.

---

### 2.4 `bank_service.py` (Bank Connections & PSD2 Consent)
- **[SECURITY] Sensitive Raw Bank Session Dumps Logged to Stdout (Lines 66–69):**
  ```python
  print("=== RAW SESSION RESPONSE ===")
  import json
  print(json.dumps(session_response, indent=2))
  print("============================")
  ```
  Prints raw API responses containing user account IBANs, session tokens, and personal account holder names to standard output in production containers.
- **[CODE QUALITY] Print statements used throughout instead of standard Python logging:**
  Lines 66, 82, 141, 186 use `print(...)` instead of `logging.getLogger(__name__)`.

---

### 2.5 `budget_service.py` (Budget CRUD, Bills & Suggestions)
- **[SIDE-EFFECT] Unintended Database Mutation in Read/Suggestion API (Lines 359–376):**
  In `generate_budget_suggestion()`:
  ```python
  for m in target_months:
      existing = db.exec(...).first()
      if not existing:
          db.add(Budget(category_id=cat_id, year=target_year, month=m, ...))
  db.commit()
  ```
  A frontend query requesting suggestions mutates the database and inserts permanent `Budget` rows without explicit user confirmation.
- **[CODE QUALITY] Dead Code Statement (Line 248):**
  `now.year - (1 if now.month >= 1 else 2) # simplified 1 year back` is evaluated without variable assignment.

---

### 2.6 `insights_service.py` (Analytics, Time Series & Sunburst)
- **[PRECISION] Precision Loss via Float Roundtrips (Lines 295–311):**
  `sum(float(item["income"]) for item in series)` converts formatted strings back to float, performs float arithmetic, and scales by 100, violating integer money rules.
- **[PERFORMANCE] Full-Table Scan on Trends (Line 328):**
  `get_category_trends()` joins all allocations and postings across all historical time without date or limit bounding.

---

### 2.7 `rules_service.py` (Auto-Categorization Rules Engine)
- **[PERFORMANCE] $N+1$ Query Pattern in `apply_rules_to_uncategorized` (Lines 706–709):**
  ```python
  for posting in postings:
      allocs = db.exec(
          select(PostingAllocation).where(PostingAllocation.posting_id == posting.id)
      ).all()
  ```
  Executes $N$ separate SQL queries for $N$ postings instead of eager-loading allocations via `selectinload(Posting.allocations)`.
- **[LOGIC] Dynamic Attribute Attachment for Regex (Lines 472–491):**
  `rule._compiled_regex = compiled` dynamically attaches compiled regexes to ephemeral SQLModel objects. An in-memory LRU cache keyed by `(pattern, is_regex, partial_match)` provides true reusability across requests.

---

### 2.8 `household_service.py` (Multi-Tenancy & Access Control)
- **[ARCHITECTURE] HTTP Exceptions Raised Inside Domain Service Layer:**
  Lines 61, 65, 91, 123, 134, 156, 175, 183, 193, 204, 221, 227, 254, 258, 269, 280, 290, 302 raise FastAPI `HTTPException` directly from `household_service.py`. Domain services should raise domain exceptions (e.g. `AccessDeniedError`, `NotFoundError`), with FastAPI routers translating them to HTTP status codes.
- **[DEBUG LEAK] Leftover Debug Print (Line 28):**
  `print(f"[DEBUG] list_households for user_id={user_id} ...", flush=True)` outputs user ID and household names to stdout on every request.

---

### 2.9 `inbound_email_service.py` & `imap_worker.py` (Receipt Ingestion)
- **[SECURITY] Webhook Lacks Shared Secret / Signature Verification:**
  `backend/app/api/routers/inbound.py` allows unauthenticated POST requests to `/api/inbound/email`. While token matching is performed on recipient addresses, there is no webhook secret validation (`X-Webhook-Secret` or HMAC signature) from Cloudflare Workers, allowing potential denial-of-service or fake email submission if the endpoint is discovered.
- **[ROBUSTNESS] IMAP Poller Error Resilience (Lines 31–34 in `imap_worker.py`):**
  Uses `asyncio.to_thread(_poll_imap_once)` correctly for blocking IMAP I/O. However, unhandled socket timeouts in `client.login()` or `client.search()` can hang threads indefinitely without connection timeout parameters.

---

## 3. Security & Authentication Architecture

### 3.1 Logto JWT Verification (`backend/app/core/auth.py`)
- **Strengths:** Validates JWT against JWKS (`PyJWKClient`), verifies audience (`LOGTO_API_RESOURCE`), issuer (`LOGTO_ENDPOINT/oidc`), and signature algorithm (`RS256`, `ES384`).
- **User Provisioning:** Automatically syncs Logto user profile and creates default household on first login. Handles pending invite resolution smoothly.
- **Recommendations:** Cache user DB lookups for the duration of the request to prevent redundant user queries across middleware and route handlers.

---

## 4. Phase 2 Refactoring Action Plan

1. **Fix Critical Bugs Immediately:**
   - Remove `description=description` from `PostingAllocation` in `csv_service.py`.
   - Fix `name` -> `sub_name` in `Category` constructor in `transfer_service.py`.
   - Prevent side-effect insertions in `budget_service.py` (`generate_budget_suggestion`).
2. **Optimize Query & Commit Performance:**
   - Batch database commits in `sync_service.py` (commit per account/batch rather than per transaction).
   - Eliminate $N+1$ queries in `rules_service.py` using `selectinload(Posting.allocations)`.
   - Optimize `transfer_service.py` and `insights_service.py` to query only relevant date windows rather than full table loads.
3. **Enhance Security & Logging:**
   - Remove sensitive `print(...)` statements logging session tokens and payload dumps in `bank_service.py` and `household_service.py`.
   - Add webhook secret validation (`INBOUND_EMAIL_WEBHOOK_SECRET`) to `/api/inbound/email`.
   - Transition all services to Python `logging.getLogger("peng.<service>")`.
