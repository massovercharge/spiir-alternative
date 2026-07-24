from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.auth import get_auth_dependency
from app.sync_service import get_sync_status, start_sync_job
from app.bank_service import complete_auth_session, list_bank_connections, start_auth_session
from app.storebox_service import process_storebox_link, process_storebox_file
from app.transaction_service import auto_link_receipts
from app.csv_service import import_spiir_csv
from app.schemas.requests import BankConnectRequest, BankCallbackRequest, StoreboxImportLinkRequest

router = APIRouter(prefix="/api", tags=["sync"])

# Sync
@router.post("/sync/start")
def sync_start() -> dict[str, Any]:
    """Start a background bank transaction retrieval job."""
    return start_sync_job()

@router.get("/sync/status")
def sync_status() -> dict[str, Any]:
    """Check the status of the latest sync job."""
    return get_sync_status()

# Bank
@router.post("/bank/connect")
def bank_connect(payload: BankConnectRequest) -> dict[str, Any]:
    """Start the PSD2 authorization flow."""
    try:
        return start_auth_session(payload.redirect_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/bank/callback")
def bank_callback(payload: BankCallbackRequest) -> dict[str, Any]:
    """Complete the PSD2 authorization flow."""
    try:
        return complete_auth_session(payload.code)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/bank/connections")
def bank_connections() -> list[dict[str, Any]]:
    """List active bank connections."""
    return list_bank_connections()

# Storebox
@router.post("/storebox/import-link")
def storebox_import_link(payload: StoreboxImportLinkRequest) -> dict[str, Any]:
    """Download and import Storebox receipts from a URL."""
    try:
        result = process_storebox_link(payload.url)
        linked = auto_link_receipts()
        result["auto_linked"] = linked
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/storebox/import-file")
async def storebox_import_file(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload and import a Storebox ZIP or JSON file."""
    try:
        content = await file.read()
        result = process_storebox_file(content, file.filename or "")
        linked = auto_link_receipts()
        result["auto_linked"] = linked
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

# Import
@router.post("/import/spiir")
async def import_spiir_endpoint(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload and import a Spiir CSV export."""
    content = await file.read()
    try:
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            text_content = content.decode("latin-1")
        stats = import_spiir_csv(text_content)
        return stats
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process CSV: {e!s}") from e
