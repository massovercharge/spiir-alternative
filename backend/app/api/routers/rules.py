from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_auth_dependency
from app.services.rules_service import (
    apply_rules_to_uncategorized,
    create_rule,
    delete_rule,
    list_rules,
    update_rule,
    preprocess_description,
)
from app.services.transaction_service import apply_rule_retroactively
from app.schemas.requests import RuleCreateRequest, RuleUpdateRequest

router = APIRouter(prefix="/api/rules", tags=["rules"])

@router.get("")
def rules_list(source: Optional[str] = None, category_id: Optional[str] = None) -> list[dict[str, Any]]:
    """List categorization rules, optionally filtered by source or category."""
    return list_rules(source=source, category_id=category_id)

@router.post("")
def rules_create(payload: RuleCreateRequest) -> dict[str, Any]:
    """Create a new user-defined categorization rule."""
    return create_rule(
        category_id=payload.category_id,
        match_pattern=payload.match_pattern,
        is_regex=payload.is_regex,
        partial_match=payload.partial_match,
        priority=payload.priority,
    )

@router.put("/{rule_id}")
def rules_update(rule_id: str, payload: RuleUpdateRequest) -> dict[str, Any]:
    """Update an existing categorization rule."""
    result = update_rule(rule_id, payload.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result

@router.delete("/{rule_id}")
def rules_delete(rule_id: str) -> dict[str, str]:
    """Delete a categorization rule."""
    if not delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted"}

@router.post("/apply")
def rules_apply() -> dict[str, Any]:
    """Retroactively apply rules to uncategorized postings."""
    return apply_rules_to_uncategorized()

@router.post("/custom")
def create_custom_rule(payload: RuleCreateRequest) -> dict[str, Any]:
    """Create a custom rule for the user and apply retroactively."""
    match_pattern = payload.match_pattern
    is_regex = payload.is_regex

    if not is_regex:
        cleaned = preprocess_description(match_pattern)
        if cleaned:
            match_pattern = cleaned

    rule = create_rule(
        match_pattern=match_pattern,
        category_id=payload.category_id,
        is_regex=is_regex,
        partial_match=payload.partial_match,
        priority=payload.priority
    )

    updated_count = apply_rule_retroactively(rule["id"])
    return {"rule": rule, "updated_count": updated_count}
