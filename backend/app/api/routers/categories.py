from typing import Any
from fastapi import APIRouter, Depends

from app.auth import get_auth_dependency
from app.category_service import get_taxonomy_response

router = APIRouter(prefix="/api/categories", tags=["categories"])

@router.get("")
def categories_list() -> dict[str, Any]:
    """Return the full category taxonomy with usage counts."""
    return get_taxonomy_response()
