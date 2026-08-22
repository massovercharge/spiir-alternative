"""Household service — manages households and members."""
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import Household, HouseholdMember, User, engine


def list_households(user_id: str) -> list[dict[str, Any]]:
    """List all households that the user is a member of."""
    with Session(engine) as db:
        memberships = db.exec(
            select(HouseholdMember).where(HouseholdMember.user_id == user_id)
        ).all()

        result = []
        for m in memberships:
            hh = db.get(Household, m.household_id)
            if hh:
                result.append({
                    "id": hh.id,
                    "name": hh.name,
                    "role": m.role,
                    "created_at": hh.created_at,
                    "deleted_at": hh.deleted_at,
                })
        print(f"[DEBUG] list_households for user_id={user_id} -> returning {len(result)} households: {[r['name'] for r in result]}", flush=True)
        return result

def create_household(user_id: str, name: str) -> dict[str, Any]:
    """Create a new household and assign the user as owner."""
    with Session(engine) as db:
        hh = Household(name=name)
        db.add(hh)
        db.commit()
        db.refresh(hh)

        member = HouseholdMember(household_id=hh.id, user_id=user_id, role="owner")
        db.add(member)
        db.commit()

        return {
            "id": hh.id,
            "name": hh.name,
            "role": "owner",
            "created_at": hh.created_at,
        }

def update_household(household_id: str, user_id: str, name: str) -> dict[str, Any]:
    """Rename an existing household (requires owner role)."""
    with Session(engine) as db:
        membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == user_id
            )
        ).first()

        if not membership or membership.role != "owner":
            raise HTTPException(status_code=403, detail="Only owners can rename the household")

        hh = db.get(Household, household_id)
        if not hh:
            raise HTTPException(status_code=404, detail="Household not found")

        hh.name = name.strip()
        db.add(hh)
        db.commit()
        db.refresh(hh)

        return {
            "id": hh.id,
            "name": hh.name,
            "role": membership.role,
            "created_at": hh.created_at,
        }

def get_household_members(household_id: str, requesting_user_id: str) -> list[dict[str, Any]]:
    """List all members of a household."""
    with Session(engine) as db:
        # Validate access
        membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == requesting_user_id
            )
        ).first()

        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")

        memberships = db.exec(
            select(HouseholdMember, User)
            .join(User, User.id == HouseholdMember.user_id)
            .where(HouseholdMember.household_id == household_id)
        ).all()

        result = []
        for m, user in memberships:
            display_email = user.email or ""
            if not display_email and user.logto_id:
                if user.logto_id.startswith("pending:"):
                    display_email = user.logto_id.replace("pending:", "")
                elif user.logto_id == "local_user":
                    display_email = "local@example.com"
                else:
                    display_email = ""

            display_name = user.name or (display_email.split("@")[0] if "@" in display_email else "")
            result.append({
                "id": user.id,
                "email": display_email,
                "name": display_name,
                "role": m.role,
                "is_me": (m.user_id == requesting_user_id),
            })
        return result

def invite_member(household_id: str, requesting_user_id: str, email: str, role: str = "member") -> dict[str, Any]:
    """Add a member to the household by email."""
    if role not in ("owner", "member"):
        raise HTTPException(status_code=400, detail="Invalid role")

    with Session(engine) as db:
        # Validate that requesting user is owner
        membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == requesting_user_id
            )
        ).first()

        if not membership or membership.role != "owner":
            raise HTTPException(status_code=403, detail="Only owners can invite members")

        # Find user by email
        from sqlmodel import func
        email = email.lower().strip()
        user = db.exec(select(User).where(func.lower(User.email) == email)).first()
        if not user:
            user = User(logto_id=f"pending:{email}", email=email, name=email.split("@")[0])
            db.add(user)
            db.commit()
            db.refresh(user)

        # Check if already member
        existing = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == user.id
            )
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="User is already a member")

        new_member = HouseholdMember(household_id=household_id, user_id=user.id, role=role)
        db.add(new_member)
        db.commit()

        return {"success": True, "email": user.email, "role": role}

def remove_member(household_id: str, requesting_user_id: str, target_user_id: str) -> dict[str, Any]:
    """Remove a member from the household (or leave household if requesting_user_id == target_user_id)."""
    with Session(engine) as db:
        req_membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == requesting_user_id
            )
        ).first()

        if not req_membership:
            raise HTTPException(status_code=403, detail="Access denied")

        is_self_removal = (requesting_user_id == target_user_id)
        if not is_self_removal and req_membership.role != "owner":
            raise HTTPException(status_code=403, detail="Only owners can remove other members")

        user_to_remove = db.exec(select(User).where(User.id == target_user_id)).first()
        if not user_to_remove:
            raise HTTPException(status_code=404, detail="User not found")

        target_membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == user_to_remove.id
            )
        ).first()

        if not target_membership:
            raise HTTPException(status_code=404, detail="Membership not found")

        # Check if removing the last owner
        if target_membership.role == "owner":
            owner_count = len(db.exec(
                select(HouseholdMember).where(
                    HouseholdMember.household_id == household_id,
                    HouseholdMember.role == "owner"
                )
            ).all())
            if owner_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot leave or remove the last owner of the household")

        db.delete(target_membership)
        db.commit()

        return {"success": True}

def delete_household(household_id: str, requesting_user_id: str) -> dict[str, Any]:
    """Mark a household as deleted (soft delete)."""
    from app.models import _utcnow_iso
    with Session(engine) as db:
        req_membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == requesting_user_id
            )
        ).first()

        if not req_membership or req_membership.role != "owner":
            raise HTTPException(status_code=403, detail="Only owners can delete the household")

        hh = db.get(Household, household_id)
        if not hh:
            raise HTTPException(status_code=404, detail="Household not found")

        hh.deleted_at = _utcnow_iso()
        db.add(hh)
        db.commit()

        return {"success": True, "deleted": True}

def restore_household(household_id: str, requesting_user_id: str) -> dict[str, Any]:
    """Restore a soft-deleted household."""
    import datetime
    with Session(engine) as db:
        req_membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == requesting_user_id
            )
        ).first()

        if not req_membership or req_membership.role != "owner":
            raise HTTPException(status_code=403, detail="Only owners can restore the household")

        hh = db.get(Household, household_id)
        if not hh:
            raise HTTPException(status_code=404, detail="Household not found")

        if not hh.deleted_at:
            raise HTTPException(status_code=400, detail="Household is not deleted")

        deleted_time = datetime.datetime.fromisoformat(hh.deleted_at.replace("Z", "+00:00"))
        if (datetime.datetime.now(datetime.timezone.utc) - deleted_time).total_seconds() > 7200:
            raise HTTPException(status_code=400, detail="Cannot restore household after 2 hours")

        hh.deleted_at = None
        db.add(hh)
        db.commit()

        return {"success": True}

def update_member_role(household_id: str, requesting_user_id: str, target_user_id: str, role: str) -> dict[str, Any]:
    """Update a household member's role (requires owner role)."""
    if role not in ("owner", "member"):
        raise HTTPException(status_code=400, detail="Invalid role")

    with Session(engine) as db:
        req_membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == requesting_user_id
            )
        ).first()

        if not req_membership or req_membership.role != "owner":
            raise HTTPException(status_code=403, detail="Only owners can change roles")

        target_membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == target_user_id
            )
        ).first()

        if not target_membership:
            raise HTTPException(status_code=404, detail="Member not found in household")

        if role == "member" and target_membership.role == "owner":
            # Ensure there's at least one other owner
            other_owners = db.exec(
                select(HouseholdMember).where(
                    HouseholdMember.household_id == household_id,
                    HouseholdMember.role == "owner",
                    HouseholdMember.user_id != target_user_id
                )
            ).all()
            if not other_owners:
                raise HTTPException(status_code=400, detail="Cannot change role: household must have at least one owner")

        target_membership.role = role
        db.add(target_membership)
        db.commit()

        return {"success": True, "role": role}
