from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.auth import get_auth_dependency
from app.schemas.requests import BankCallbackRequest, BankConnectRequest, StoreboxImportLinkRequest
from app.services.bank_service import (
    complete_auth_session,
    delete_bank_connection,
    list_bank_connections,
    start_auth_session,
)
from app.services.coop_service import process_coop_file
from app.services.csv_service import import_spiir_csv
from app.services.storebox_service import process_storebox_file, process_storebox_link
from app.services.sync_service import get_sync_status, start_sync_job
from app.services.transaction_service import auto_link_receipts

router = APIRouter(prefix="/api", tags=["sync"])


# Sync
@router.post("/sync/start")
def sync_start(auth: dict[str, Any] = Depends(get_auth_dependency())) -> dict[str, Any]:
    """Start a background bank transaction retrieval job."""
    return start_sync_job()


@router.get("/sync/status")
def sync_status(auth: dict[str, Any] = Depends(get_auth_dependency())) -> dict[str, Any]:
    """Check the status of the latest sync job."""
    return get_sync_status()


# Bank
@router.post("/bank/connect")
def bank_connect(
    payload: BankConnectRequest, auth: dict[str, Any] = Depends(get_auth_dependency())
) -> dict[str, Any]:
    """Start the PSD2 authorization flow."""
    try:
        return start_auth_session(payload.redirect_url, payload.bank_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/bank/callback")
def bank_callback(
    payload: BankCallbackRequest, auth: dict[str, Any] = Depends(get_auth_dependency())
) -> dict[str, Any]:
    """Complete the PSD2 authorization flow."""
    import logging

    try:
        return complete_auth_session(payload.code)
    except Exception as exc:
        logging.exception("Failed in bank_callback: %s", str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/bank/connections")
def bank_connections(auth: dict[str, Any] = Depends(get_auth_dependency())) -> list[dict[str, Any]]:
    """List active bank connections."""
    return list_bank_connections()


@router.delete("/bank/connections/{connection_id}")
def bank_connection_delete(
    connection_id: str, auth: dict[str, Any] = Depends(get_auth_dependency())
) -> dict[str, Any]:
    """Delete a bank connection and revoke consent."""
    try:
        return delete_bank_connection(connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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


# Coop
@router.post("/coop/import-file")
async def coop_import_file(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload and import a Coop JSON receipt export."""
    try:
        content = await file.read()
        result = process_coop_file(content, file.filename or "receipts-coop.json")
        linked = auto_link_receipts()
        result["auto_linked"] = linked
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# Receipt Status & Sync Overview
@router.get("/receipts/status")
@router.get("/kvitteringer/status")
def receipts_status(auth: dict[str, Any] = Depends(get_auth_dependency())) -> dict[str, Any]:
    """Get status, counts, matched transaction counts, and recent import runs for receipts."""
    from app.services.kvitteringer_service import get_kvitteringer_status

    return get_kvitteringer_status()


@router.post("/receipts/auto-link")
def receipts_auto_link(auth: dict[str, Any] = Depends(get_auth_dependency())) -> dict[str, Any]:
    """Scan transactions and automatically link matching receipts."""
    from app.services.kvitteringer_service import get_kvitteringer_status
    from app.services.transaction_service import auto_link_receipts

    linked_count = auto_link_receipts()
    status = get_kvitteringer_status()
    return {
        "auto_linked_count": linked_count,
        "status": status,
    }




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
