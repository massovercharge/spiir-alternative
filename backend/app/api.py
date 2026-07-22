"""Peng API — REST endpoints for personal finance management.

Provides transaction listing, categorization, insights, and bank
synchronization backed by a local SQLite database.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .account_service import list_accounts_with_balances
from .auth import get_auth_dependency
from .bank_service import complete_auth_session, list_bank_connections, start_auth_session
from .budget_service import (
    generate_budget_suggestion,
    get_annual_summary,
    get_budget_bills,
    list_budgets,
    upsert_budget,
    upsert_budget_bills,
)
from .category_service import get_taxonomy_response, seed_categories
from .database import create_db_and_tables
from .household_service import (
    create_household,
    get_household_members,
    invite_member,
    list_households,
    update_household,
)
from .insights_service import get_category_trends, income_expense_series, sunburst_data
from .recurring_service import (
    create_recurring,
    delete_recurring,
    detect_recurring,
    list_recurring,
)
from .rules_service import (
    apply_rules_to_uncategorized,
    create_rule,
    delete_rule,
    list_rules,
    seed_spiir_rules,
    update_rule,
)
from .sync_service import get_sync_status, start_sync_job
from .transaction_service import (
    get_transaction,
    list_transactions,
    split_allocation,
    update_transactions,
)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database, seed categories, and seed Spiir rules on startup."""
    create_db_and_tables()
    seed_categories()
    seed_spiir_rules()
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure the Peng FastAPI application."""
    app = FastAPI(
        title="Peng API",
        description="Self-hostable personal finance — categorization, budgeting & accounting.",
        version="0.1.0",
        lifespan=lifespan,
    )

    api_router = APIRouter(dependencies=[Depends(get_auth_dependency())])

    # ----- Health -----

    @app.get("/api/health")
    def health_check() -> dict[str, str]:
        """Health check endpoint for Docker and monitoring."""
        return {"status": "ok", "version": "0.1.0"}

    # ----- Households -----

    @api_router.get("/api/households")
    def households_list(auth: dict[str, Any] = Depends(get_auth_dependency())) -> list[dict[str, Any]]:
        """List all households the user is a member of."""
        return list_households(auth["user_id"])

    @api_router.post("/api/households")
    def household_create(payload: dict[str, Any], auth: dict[str, Any] = Depends(get_auth_dependency())) -> dict[str, Any]:
        """Create a new household."""
        name = payload.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        return create_household(auth["user_id"], name)

    @api_router.patch("/api/households/{household_id}")
    def household_update(household_id: str, payload: dict[str, Any], auth: dict[str, Any] = Depends(get_auth_dependency())) -> dict[str, Any]:
        """Rename a household."""
        name = payload.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        return update_household(household_id, auth["user_id"], name)

    @api_router.get("/api/households/{household_id}/members")
    def household_members(household_id: str, auth: dict[str, Any] = Depends(get_auth_dependency())) -> list[dict[str, Any]]:
        """List members of a household."""
        return get_household_members(household_id, auth["user_id"])

    @api_router.post("/api/households/{household_id}/members")
    def household_member_invite(household_id: str, payload: dict[str, Any], auth: dict[str, Any] = Depends(get_auth_dependency())) -> dict[str, Any]:
        """Invite a member by email."""
        email = payload.get("email")
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
        return invite_member(household_id, auth["user_id"], email)

    # ----- Accounts -----

    @api_router.get("/api/accounts")
    def accounts_list() -> list[dict[str, Any]]:
        """List accounts with their real-time calculated balances."""
        return list_accounts_with_balances()

    @api_router.patch("/api/accounts/{account_uid}")
    def account_update(account_uid: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an account."""
        try:
            from .account_service import update_account
            name = payload.get("name")
            account_type = payload.get("account_type")
            savings_category_id = payload.get("savings_category_id")
            if not name:
                raise ValueError("Name is required")
            result = update_account(account_uid, name, account_type, savings_category_id)
            if not result:
                raise HTTPException(status_code=404, detail="Account not found")
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api_router.get("/api/accounts/{account_uid}/balance_history")
    def account_balance_history(account_uid: str, days: int = 365) -> list[dict[str, Any]]:
        """Get the daily balance history for an account."""
        from .account_service import get_account_balance_history
        return get_account_balance_history(account_uid, days)

    # ----- Transactions -----

    @api_router.get("/api/transactions")
    def transactions_list(
        limit: Annotated[int | None, Query(ge=1)] = None,
        offset: Annotated[int, Query(ge=0)] = 0,
        account_uid: str | None = None,
        search: str | None = None,
        filter_type: str | None = None,
        tag: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        amount_op: str | None = None,
        amount_value: float | None = None,
        category_id: str | None = None,
    ) -> dict[str, object]:
        """List transactions with optional filtering and pagination."""
        return list_transactions(
            limit=limit, offset=offset, account_uid=account_uid, search=search,
            filter_type=filter_type, tag=tag, start_date=start_date, end_date=end_date,
            amount_op=amount_op, amount_value=amount_value, category_id=category_id
        )

    @api_router.get("/api/transactions/{transaction_id}")
    def transaction_detail(transaction_id: str) -> dict[str, object]:
        """Get a single transaction by ID."""
        result = get_transaction(transaction_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return result

    @api_router.patch("/api/transactions")
    def transactions_update(payload: dict[str, Any]) -> dict[str, object]:
        """Apply overrides (category, note, flags) to one or more transactions."""
        try:
            ids = [str(x) for x in payload.get("transaction_ids", []) if str(x).strip()]
            patch = payload.get("patch", {})
            if not isinstance(patch, dict):
                raise ValueError("Invalid patch")
            return update_transactions(ids, patch)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api_router.put("/api/transactions/{transaction_id}/category")
    def update_single_transaction_category(transaction_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update category for a single transaction."""
        from app.transaction_service import update_transaction_category
        category_id = payload.get("category_id")
        if not category_id:
            raise HTTPException(status_code=400, detail="Missing category_id")
        success = update_transaction_category(transaction_id, category_id)
        if not success:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return {"success": True}

    @api_router.post("/api/transactions/{transaction_id}/split")
    def transaction_split(transaction_id: str, payload: dict[str, Any]) -> dict[str, object]:
        """Split a transaction into multiple allocations."""
        try:
            splits = payload.get("splits", [])
            if not isinstance(splits, list):
                raise ValueError("Splits must be a list")
            return split_allocation(transaction_id, splits)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api_router.post("/api/transactions/{transaction_id}/link-receipt")
    def transaction_link_receipt(transaction_id: str, payload: dict[str, Any]) -> dict[str, object]:
        """Link a receipt to a transaction and automatically split it into items."""
        try:
            from app.transaction_service import link_receipt_to_transaction
            receipt_id = payload.get("receipt_id")
            if not receipt_id:
                raise ValueError("receipt_id is required")
            return link_receipt_to_transaction(transaction_id, receipt_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api_router.get("/api/tags")
    def tags_list() -> dict[str, list[dict[str, str]]]:
        """Get all tags created by the user."""
        from app.transaction_service import list_tags
        tags = list_tags()
        return {"tags": [{"id": t.id, "name": t.name} for t in tags]}

    @api_router.post("/api/rules/custom")
    def create_custom_rule(payload: dict[str, Any]) -> dict[str, Any]:
        """Create a custom rule for the user and apply retroactively."""
        from app.rules_service import create_rule
        from app.transaction_service import apply_rule_retroactively

        match_pattern = payload.get("match_pattern")
        category_id = payload.get("category_id")

        if not match_pattern or not category_id:
            raise HTTPException(status_code=400, detail="Missing match_pattern or category_id")

        rule = create_rule(
            match_pattern=match_pattern,
            category_id=category_id,
            is_regex=False,
            partial_match=bool(payload.get("partial_match", False)),
            priority=500
        )

        updated_count = apply_rule_retroactively(rule["id"])
        return {"rule": rule, "updated_count": updated_count}

    # ----- Categories / Taxonomy -----

    @api_router.get("/api/categories")
    def categories_list() -> dict[str, object]:
        """Return the full category taxonomy with usage counts."""
        return get_taxonomy_response()

    # ----- Insights -----

    @api_router.get("/api/insights/income-expense-series")
    def insights_income_expense(year: int | None = None) -> dict[str, object]:
        """Monthly income/expense aggregates for bar charts."""
        return income_expense_series(year)

    @api_router.get("/api/insights/sunburst")
    def insights_sunburst(year: int | None = None, month: int | None = None, filter_type: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict[str, object]:
        """Hierarchical category data for sunburst/drilldown charts."""
        return sunburst_data(year=year, month=month, filter_type=filter_type, start_date=start_date, end_date=end_date)

    @api_router.get("/api/insights/averages")
    def insights_averages(year: int) -> dict[str, Any]:
        """Get monthly averages for a year."""
        from app.insights_service import get_averages
        return get_averages(year)

    @api_router.get("/api/insights/category-drilldown")
    def insights_category_drilldown(category_name: str, year: int) -> dict[str, Any]:
        """Get monthly drill-down data for a category."""
        from app.insights_service import category_drilldown
        return category_drilldown(category_name, year)

    @api_router.get("/api/insights/trends")
    def insights_trends() -> list[dict[str, Any]]:
        """Trend data for income/expenses over time."""
        return get_category_trends()

    @api_router.post("/api/import/spiir")
    async def import_spiir_endpoint(file: UploadFile = File(...)) -> dict[str, Any]:
        """Upload and import a Spiir CSV export."""
        from app.csv_service import import_spiir_csv
        content = await file.read()
        try:
            # Decode using utf-8 first, fallback to latin-1
            try:
                text_content = content.decode("utf-8")
            except UnicodeDecodeError:
                text_content = content.decode("latin-1")

            stats = import_spiir_csv(text_content)
            return stats
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to process CSV: {e!s}") from e

    # ----- Budgets -----

    @api_router.get("/api/budgets")
    def budgets_list(year: int, month: int | None = None, category_id: str | None = None) -> list[dict[str, Any]]:
        """List budgets for a given year and optional month/category."""
        return list_budgets(year, month, category_id)

    @api_router.post("/api/budgets")
    def budgets_upsert(payload: dict[str, Any]) -> dict[str, Any]:
        """Create or update a budget."""
        try:
            return upsert_budget(
                category_id=payload["category_id"],
                year=payload["year"],
                month=payload["month"],
                amount_minor=int(payload["amount_minor"]),
                budget_type=payload.get("budget_type", "limit"),
                rollover=bool(payload.get("rollover", False)),
            )
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Missing required field: {exc}") from exc

    @api_router.post("/api/budgets/generate")
    def budgets_generate(months: int = 12, year: int | None = None) -> list[dict[str, Any]]:
        """Auto-generate budget suggestions based on historical spending."""
        return generate_budget_suggestion(months, year)

    @api_router.get("/api/budgets/bills/{category_id}/{year}")
    def budgets_get_bills(category_id: str, year: int) -> list[dict[str, Any]]:
        """Get all specific bills for a budget category."""
        return get_budget_bills(category_id, year)

    @api_router.post("/api/budgets/bills")
    def budgets_upsert_bills(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Replace all specific bills for a category and recalculate its monthly budget."""
        try:
            return upsert_budget_bills(
                category_id=payload["category_id"],
                year=payload["year"],
                bills_data=payload.get("bills", []),
            )
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Missing required field: {exc}") from exc

    @api_router.get("/api/budgets/summary/{year}")
    def budgets_summary(year: int) -> dict[str, Any]:
        """Get the annual summary of budgeted vs actual spending."""
        return get_annual_summary(year)

    # ----- Sync (Enable Banking) -----

    @api_router.post("/api/sync/start")
    def sync_start() -> dict[str, object]:
        """Start a background bank transaction retrieval job."""
        return start_sync_job()

    @api_router.get("/api/sync/status")
    def sync_status() -> dict[str, object]:
        """Check the status of the latest sync job."""
        return get_sync_status()

    @api_router.post("/api/bank/connect")
    def bank_connect(payload: dict[str, Any]) -> dict[str, Any]:
        """Start the PSD2 authorization flow."""
        redirect_url = payload.get("redirect_url")
        if not redirect_url:
            raise HTTPException(status_code=400, detail="redirect_url is required")
        try:
            return start_auth_session(redirect_url)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            print(f"ERROR in bank_connect: {exc}")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @api_router.post("/api/bank/callback")
    def bank_callback(payload: dict[str, Any]) -> dict[str, Any]:
        """Complete the PSD2 authorization flow."""
        code = payload.get("code")
        if not code:
            raise HTTPException(status_code=400, detail="code is required")
        try:
            return complete_auth_session(code)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @api_router.get("/api/bank/connections")
    def bank_connections() -> list[dict[str, Any]]:
        """List active bank connections."""
        return list_bank_connections()

    # ----- Import (Storebox) -----

    @api_router.post("/api/storebox/import-link")
    def storebox_import_link(payload: dict[str, Any]) -> dict[str, object]:
        """Download and import Storebox receipts from a URL."""
        from .storebox_service import process_storebox_link
        from .transaction_service import auto_link_receipts
        url = payload.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL is required")
        try:
            result = process_storebox_link(url)
            linked = auto_link_receipts()
            result["auto_linked"] = linked
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api_router.post("/api/storebox/import-file")
    async def storebox_import_file(file: UploadFile = File(...)) -> dict[str, object]:
        """Upload and import a Storebox ZIP or JSON file."""
        from .storebox_service import process_storebox_file
        from .transaction_service import auto_link_receipts
        try:
            content = await file.read()
            result = process_storebox_file(content, file.filename or "")
            linked = auto_link_receipts()
            result["auto_linked"] = linked
            return result
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ----- Rules (Auto-categorization) -----

    @api_router.get("/api/rules")
    def rules_list(
        source: str | None = None,
        category_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List categorization rules, optionally filtered by source or category."""
        return list_rules(source=source, category_id=category_id)

    @api_router.post("/api/rules")
    def rules_create(payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new user-defined categorization rule."""
        try:
            return create_rule(
                category_id=payload["category_id"],
                match_pattern=payload["match_pattern"],
                is_regex=bool(payload.get("is_regex", False)),
                partial_match=bool(payload.get("partial_match", False)),
                priority=int(payload.get("priority", 500)),
            )
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Missing required field: {exc}") from exc

    @api_router.put("/api/rules/{rule_id}")
    def rules_update(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an existing categorization rule."""
        result = update_rule(rule_id, payload)
        if result is None:
            raise HTTPException(status_code=404, detail="Rule not found")
        return result

    @api_router.delete("/api/rules/{rule_id}")
    def rules_delete(rule_id: str) -> dict[str, str]:
        """Delete a categorization rule."""
        if not delete_rule(rule_id):
            raise HTTPException(status_code=404, detail="Rule not found")
        return {"status": "deleted"}

    @api_router.post("/api/rules/apply")
    def rules_apply() -> dict[str, Any]:
        """Retroactively apply rules to uncategorized postings."""
        return apply_rules_to_uncategorized()

    # ----- Recurring Transactions (Faste Udgifter) -----

    @api_router.get("/api/recurring")
    def recurring_list() -> list[dict[str, Any]]:
        """List all recurring transactions."""
        return list_recurring()

    @api_router.post("/api/recurring")
    def recurring_create(payload: dict[str, Any]) -> dict[str, Any]:
        """Create a manual recurring transaction."""
        try:
            return create_recurring(payload)
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Missing required field: {exc}") from exc

    @api_router.delete("/api/recurring/{rtx_id}")
    def recurring_delete(rtx_id: str) -> dict[str, str]:
        """Delete/deactivate a recurring transaction."""
        if not delete_recurring(rtx_id):
            raise HTTPException(status_code=404, detail="Recurring transaction not found")
        return {"status": "deleted"}

    @api_router.post("/api/recurring/detect")
    def recurring_detect() -> list[dict[str, Any]]:
        """Detect and propose recurring transactions based on history."""
        return detect_recurring()

    app.include_router(api_router)

    # ----- Serve Frontend (Static) -----

    # Check if the frontend dist folder exists (e.g. built via Docker)
    # Local dev structure: spiir-alternative/backend/app/api.py -> spiir-alternative/frontend/dist
    frontend_dist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")

    # Docker structure: /app/app/api.py -> /app/frontend/dist
    if not os.path.isdir(frontend_dist_path):
        frontend_dist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

    if os.path.isdir(frontend_dist_path):
        # Serve static assets (js, css, images) from /assets
        assets_path = os.path.join(frontend_dist_path, "assets")
        if os.path.isdir(assets_path):
            app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

        # Catch-all route for SPA routing (React Router)
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            # If the file exists, serve it (e.g. favicon.ico)
            file_path = os.path.join(frontend_dist_path, full_path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            # Otherwise, fall back to index.html for client-side routing
            return FileResponse(os.path.join(frontend_dist_path, "index.html"))

    return app


app = create_app()
