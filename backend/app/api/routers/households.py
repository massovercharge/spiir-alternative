from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_auth_dependency
from app.services.household_service import (
    create_household,
    get_household_members,
    invite_member,
    list_households,
    remove_member,
    update_household,
    delete_household,
    restore_household,
    update_member_role,
)
from app.schemas.requests import (
    HouseholdCreateRequest,
    HouseholdUpdateRequest,
    HouseholdInviteRequest,
    HouseholdMemberRoleUpdateRequest,
)

router = APIRouter(prefix="/api/households", tags=["households"])

@router.get("")
def households_list(auth: dict[str, Any] = Depends(get_auth_dependency())) -> list[dict[str, Any]]:
    """List all households the user is a member of."""
    return list_households(auth["user_id"])

@router.post("")
def household_create(payload: HouseholdCreateRequest, auth: dict[str, Any] = Depends(get_auth_dependency())) -> dict[str, Any]:
    """Create a new household."""
    return create_household(auth["user_id"], payload.name)

@router.patch("/{household_id}")
def household_update(household_id: str, payload: HouseholdUpdateRequest, auth: dict[str, Any] = Depends(get_auth_dependency())) -> dict[str, Any]:
    """Rename a household."""
    return update_household(household_id, auth["user_id"], payload.name)

@router.get("/{household_id}/members")
def household_members(household_id: str, auth: dict[str, Any] = Depends(get_auth_dependency())) -> list[dict[str, Any]]:
    """List members of a household."""
    return get_household_members(household_id, auth["user_id"])

@router.post("/{household_id}/members")
def households_invite_member(
    household_id: str,
    payload: HouseholdInviteRequest,
    auth: dict[str, Any] = Depends(get_auth_dependency())
) -> dict[str, Any]:
    """Invite a member to a household."""
    return invite_member(household_id, auth["user_id"], payload.email)

@router.delete("/{household_id}/members/{user_id}")
def households_remove_member(
    household_id: str,
    user_id: str,
    auth: dict[str, Any] = Depends(get_auth_dependency())
) -> dict[str, Any]:
    """Remove a member from a household (requires owner role)."""
    return remove_member(household_id, auth["user_id"], user_id)

@router.patch("/{household_id}/members/{user_id}/role")
def households_update_member_role(
    household_id: str,
    user_id: str,
    payload: HouseholdMemberRoleUpdateRequest,
    auth: dict[str, Any] = Depends(get_auth_dependency())
) -> dict[str, Any]:
    """Update a household member's role (requires owner role)."""
    return update_member_role(household_id, auth["user_id"], user_id, payload.role)

@router.delete("/{household_id}")
def households_delete(
    household_id: str,
    auth: dict[str, Any] = Depends(get_auth_dependency())
) -> dict[str, Any]:
    """Delete a household (soft delete)."""
    return delete_household(household_id, auth["user_id"])

@router.post("/{household_id}/restore")
def households_restore(
    household_id: str,
    auth: dict[str, Any] = Depends(get_auth_dependency())
) -> dict[str, Any]:
    """Restore a soft-deleted household."""
    return restore_household(household_id, auth["user_id"])
