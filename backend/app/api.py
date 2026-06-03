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

    return app


app = create_app()
