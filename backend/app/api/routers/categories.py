from typing import Any

from fastapi import APIRouter

from app.services.category_service import get_taxonomy_response

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
def categories_list() -> dict[str, Any]:
    """Return the full category taxonomy with usage counts."""
    return get_taxonomy_response()
