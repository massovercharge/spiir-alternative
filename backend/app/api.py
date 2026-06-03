"""V2 API — Clean REST endpoints backed by SQLite."""
from __future__ import annotations

from typing import Annotated, Any

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Query

from .auth import verify_token
from .database import create_db_and_tables
from .category_service import seed_categories, get_taxonomy_response
from .transaction_service import (
    list_transactions,
    get_transaction,
    update_transactions,
    income_expense_series,
    sunburst_data,
)
from .sync_service import get_sync_status, start_sync_job


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    seed_categories()
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="Spiir Alternative API",
        version="2.0.0",
        lifespan=lifespan,
        dependencies=[Depends(verify_token)],
    )

    # ----- Status -----

    @app.get("/api/status")
    def api_status() -> dict[str, object]:
        return {"status": "ok", "version": "2.0.0"}

    # ----- Transactions -----

    @app.get("/api/transactions")
    def transactions_list(
        limit: Annotated[int | None, Query(ge=1)] = None,
        offset: Annotated[int, Query(ge=0)] = 0,
        account_uid: str | None = None,
        search: str | None = None,
    ) -> dict[str, object]:
        return list_transactions(
            limit=limit, offset=offset, account_uid=account_uid, search=search
        )

    @app.get("/api/transactions/{transaction_id}")
    def transaction_detail(transaction_id: str) -> dict[str, object]:
        result = get_transaction(transaction_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return result

    @app.patch("/api/transactions")
    def transactions_update(payload: dict[str, Any]) -> dict[str, object]:
        try:
            ids = [str(x) for x in payload.get("transaction_ids", []) if str(x).strip()]
            patch = payload.get("patch", {})
            if not isinstance(patch, dict):
                raise ValueError("Invalid patch")
            return update_transactions(ids, patch)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ----- Categories / Taxonomy -----

    @app.get("/api/categories")
    def categories_list() -> dict[str, object]:
        return get_taxonomy_response()

    # Backward compatibility alias
    @app.get("/api/bank/taxonomy")
    def bank_taxonomy_compat() -> dict[str, object]:
        return get_taxonomy_response()

    # ----- Insights -----

    @app.get("/api/insights/income-expense-series")
    def insights_income_expense() -> dict[str, object]:
        return income_expense_series()

    @app.get("/api/insights/sunburst")
    def insights_sunburst() -> dict[str, object]:
        return sunburst_data()

    # ----- Sync (Enable Banking) -----

    @app.post("/api/sync/start")
    def sync_start() -> dict[str, object]:
        return start_sync_job()

    @app.get("/api/sync/status")
    def sync_status() -> dict[str, object]:
        return get_sync_status()

    # Backward compatibility aliases for frontend
    @app.post("/api/bank/retrieve/start")
    def bank_retrieve_start_compat() -> dict[str, object]:
        return start_sync_job()

    @app.get("/api/bank/retrieve/status")
    def bank_retrieve_status_compat() -> dict[str, object]:
        return get_sync_status()

    # ----- Backward compatibility: local-ledger endpoints -----
    # These map the old Spiir endpoints to the new transaction service

    @app.get("/api/spiir/local-ledger/transactions")
    def local_ledger_transactions_compat(
        limit: Annotated[int | None, Query(ge=1)] = None,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, object]:
        return list_transactions(limit=limit, offset=offset)

    @app.post("/api/spiir/local-ledger/overrides")
    def local_ledger_overrides_compat(payload: dict[str, Any]) -> dict[str, object]:
        try:
            ids = [str(x) for x in payload.get("transaction_ids", []) if str(x).strip()]
            patch = payload.get("patch", {})
            if not isinstance(patch, dict):
                raise ValueError("Invalid patch")

            # Map old category format to new category_id
            if "category" in patch:
                cat = patch.get("category")
                if isinstance(cat, dict) and cat.get("categoryId"):
                    from .category_service import make_category_id
                    main = cat.get("mainCategoryName", "Diverse")
                    sub = cat.get("categoryName", "Ukendt")
                    patch["category_id"] = make_category_id(main, sub)

            if "note" in patch:
                patch["custom_note"] = patch.pop("note")

            return update_transactions(ids, patch)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/spiir/local-ledger/income-expense-series")
    def local_ledger_income_expense_compat() -> dict[str, object]:
        return income_expense_series()

    @app.get("/api/spiir/status")
    def spiir_status_compat() -> dict[str, object]:
        """Compatibility endpoint that returns status in the old format."""
        result = list_transactions(limit=1)
        return {
            "raw_exists": True,
            "processed_exists": True,
            "transaction_count": result.get("transaction_count", 0),
            "generated_at": result.get("generated_at"),
            "rebuild_required": False,
        }

    @app.get("/api/bank/transactions")
    def bank_transactions_compat() -> dict[str, object]:
        return list_transactions()

    @app.post("/api/bank/overrides")
    def bank_overrides_compat(payload: dict[str, Any]) -> dict[str, object]:
        return local_ledger_overrides_compat(payload)

    return app


app = create_app()
