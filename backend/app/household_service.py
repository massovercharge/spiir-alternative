"""Household service — manages households and members."""
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.database import Household, HouseholdMember, User, engine


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
            select(HouseholdMember).where(HouseholdMember.household_id == household_id)
        ).all()

        result = []
        for m in memberships:
            user = db.get(User, m.user_id)
            if user:
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
                    "email": display_email,
                    "name": display_name,
                    "role": m.role,
                    "is_me": (m.user_id == requesting_user_id),
                })
        return result

def invite_member(household_id: str, requesting_user_id: str, email: str) -> dict[str, Any]:
    """Add a member to the household by email."""
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
        user = db.exec(select(User).where(User.email == email)).first()
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

        new_member = HouseholdMember(household_id=household_id, user_id=user.id, role="member")
        db.add(new_member)
        db.commit()

        return {"success": True, "email": user.email, "role": "member"}
