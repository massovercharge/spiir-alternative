"""Peng API — REST endpoints for personal finance management.

Provides transaction listing, categorization, insights, and bank
synchronization backed by a local SQLite database.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import Routers
from app.api.routers import (
    accounts,
    budgets,
    categories,
    households,
    inbound,
    insights,
    recurring,
    rules,
    sync,
    transactions,
)
from app.core.auth import get_auth_dependency
from app.models import create_db_and_tables
from app.services.category_service import seed_categories
from app.services.rules_service import seed_spiir_rules

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database, seed categories, and seed Spiir rules on startup."""
    create_db_and_tables()
    seed_categories()
    new_rules_count = seed_spiir_rules()

    if new_rules_count > 0:
        from app.services.rules_service import apply_rules_to_uncategorized
        apply_rules_to_uncategorized()

    try:
        from app.services.transaction_service import auto_link_receipts
        auto_link_receipts()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Error running startup auto-link receipts: %s", e)

    # Start background workers
    import asyncio

    from app.services.imap_worker import run_imap_poller_loop
    from app.worker import purge_deleted_households_worker
    task = asyncio.create_task(purge_deleted_households_worker())
    imap_task = asyncio.create_task(run_imap_poller_loop())

    yield

    task.cancel()
    imap_task.cancel()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure the Peng FastAPI application."""
    app = FastAPI(
        title="Peng API",
        description="Self-hostable personal finance — categorization, budgeting & accounting.",
        version="1.3.0",
        lifespan=lifespan,
    )

    from fastapi import Request
    from fastapi.responses import JSONResponse

    # All API routes require auth
    dependencies = [Depends(get_auth_dependency())]

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    # Health check
    @app.get("/api/health")
    def health_check() -> dict[str, str]:
        """Health check endpoint for Docker and monitoring."""
        return {"status": "ok", "version": "0.1.0"}

    # Include routers
    app.include_router(households.router, dependencies=dependencies)
    app.include_router(accounts.router, dependencies=dependencies)
    app.include_router(transactions.router, dependencies=dependencies)
    app.include_router(categories.router, dependencies=dependencies)
    app.include_router(insights.router, dependencies=dependencies)
    app.include_router(budgets.router, dependencies=dependencies)
    app.include_router(rules.router, dependencies=dependencies)
    app.include_router(recurring.router, dependencies=dependencies)
    app.include_router(sync.router, dependencies=dependencies)
    app.include_router(inbound.router)

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
