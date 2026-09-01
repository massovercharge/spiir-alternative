from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.core.auth import get_auth_dependency
from app.models import Household, current_household_id, engine
from app.schemas.widget import (
    ReorderWidgetRequest,
    ToggleWidgetRequest,
    WidgetListItem,
)
from app.services.widget_service import (
    clear_widget_cache,
    execute_widget,
    get_active_widgets_data,
    list_widgets,
    reorder_widget,
    toggle_widget,
)

router = APIRouter(prefix="/api/widgets", tags=["widgets"])


def _resolve_household_id(request: Request, household_id: Optional[str] = None) -> str:
    """Resolve effective household ID from parameter, header, contextvar or first DB entry."""
    if household_id:
        return household_id

    header_id = request.headers.get("X-Household-Id")
    if header_id:
        return header_id

    ctx_id = current_household_id.get()
    if ctx_id:
        return ctx_id

    # Fallback to first available household in database
    try:
        with Session(engine) as session:
            h = session.exec(select(Household)).first()
            if h:
                return str(h.id)
    except Exception:
        pass

    return "default_household"


@router.get("", response_model=list[WidgetListItem])
def get_widgets(
    request: Request,
    household_id: Optional[str] = Query(None),
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> list[WidgetListItem]:
    """List all discovered widgets with enabled status and order for the household."""
    effective_h_id = _resolve_household_id(request, household_id)
    return list_widgets(effective_h_id)


@router.post("/{widget_id}/toggle")
def toggle_widget_status(
    widget_id: str,
    payload: ToggleWidgetRequest,
    request: Request,
    household_id: Optional[str] = Query(None),
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Enable or disable a widget for the current household."""
    effective_h_id = _resolve_household_id(request, household_id)
    is_enabled = toggle_widget(effective_h_id, widget_id, payload.enabled)
    return {"widget_id": widget_id, "is_enabled": is_enabled}


@router.post("/{widget_id}/reorder")
def reorder_widget_position(
    widget_id: str,
    payload: ReorderWidgetRequest,
    request: Request,
    household_id: Optional[str] = Query(None),
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Move a widget up or down in presentation order."""
    effective_h_id = _resolve_household_id(request, household_id)
    new_order = reorder_widget(effective_h_id, widget_id, payload.direction)
    return {"order": new_order}


@router.get("/{widget_id}/data")
def get_single_widget_data(
    widget_id: str,
    request: Request,
    force_refresh: bool = Query(False),
    household_id: Optional[str] = Query(None),
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Execute and return data for a single widget."""
    effective_h_id = _resolve_household_id(request, household_id)
    try:
        manifest, output = execute_widget(
            widget_id, effective_h_id, force_refresh=force_refresh
        )
        return {
            "manifest": manifest.model_dump(),
            "output": output.model_dump(),
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve)) from ve
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Fejl under eksekvering af widget: {e!s}"
        ) from e


@router.get("/active/data")
def get_active_widgets(
    request: Request,
    force_refresh: bool = Query(False),
    household_id: Optional[str] = Query(None),
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> list[dict[str, Any]]:
    """Execute and return data for all active widgets for the dashboard."""
    effective_h_id = _resolve_household_id(request, household_id)
    return get_active_widgets_data(effective_h_id, force_refresh=force_refresh)


@router.post("/reload")
def reload_widgets(
    auth: dict[str, Any] = Depends(get_auth_dependency()),
) -> dict[str, Any]:
    """Clear memory cache and refresh discovered widgets."""
    clear_widget_cache()
    return {"status": "ok", "message": "Cache ryddet og widgets genindlæst."}
