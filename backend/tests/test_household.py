import pytest
from sqlmodel import Session, select
from fastapi import HTTPException

from app.database import Household, HouseholdMember, User, engine
from app.household_service import invite_member, get_household_members
from app.auth import _sync_user_and_household
from unittest.mock import MagicMock

def test_invite_member_and_pending_sync():
    with Session(engine) as db:
        # 1. Setup owner user and household
        owner = User(logto_id="owner_logto_123", email="owner@example.com", name="Owner")
        db.add(owner)
        db.commit()
        db.refresh(owner)

        hh = Household(name="Familien Hansen")
        db.add(hh)
        db.commit()
        db.refresh(hh)

        owner_member = HouseholdMember(household_id=hh.id, user_id=owner.id, role="owner")
        db.add(owner_member)
        db.commit()

        # 2. Invite a brand new email (user does not exist yet)
        res = invite_member(hh.id, owner.id, "partner@example.com")
        assert res["success"] is True
        assert res["email"] == "partner@example.com"
        assert res["role"] == "member"

        # Verify pending user was created in DB
        invited_user = db.exec(select(User).where(User.email == "partner@example.com")).first()
        assert invited_user is not None
        assert invited_user.logto_id == "pending:partner@example.com"

        # Verify membership was created
        membership = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == hh.id,
                HouseholdMember.user_id == invited_user.id
            )
        ).first()
        assert membership is not None
        assert membership.role == "member"

        # 3. Test duplicate invite raises error
        with pytest.raises(HTTPException) as exc_info:
            invite_member(hh.id, owner.id, "partner@example.com")
        assert exc_info.value.status_code == 400
        assert "already a member" in exc_info.value.detail

        # 4. Test auth sync when invited user logs in for first time via Logto
        req = MagicMock()
        req.headers = {}
        auth_data = _sync_user_and_household(req, "logto_partner_456", "partner@example.com")
        assert auth_data["user_id"] == invited_user.id
        assert auth_data["household_id"] == hh.id

        # Verify logto_id updated
        db.refresh(invited_user)
        assert invited_user.logto_id == "logto_partner_456"

def test_update_household():
    from app.household_service import update_household

    with Session(engine) as db:
        owner = User(logto_id="owner_rename_1", email="owner_rename@example.com", name="Owner")
        db.add(owner)
        db.commit()
        db.refresh(owner)

        hh = Household(name="Gammelt Husstandsnavn")
        db.add(hh)
        db.commit()
        db.refresh(hh)

        owner_member = HouseholdMember(household_id=hh.id, user_id=owner.id, role="owner")
        db.add(owner_member)
        db.commit()

        updated = update_household(hh.id, owner.id, "Nyt Husstandsnavn")
        assert updated["name"] == "Nyt Husstandsnavn"

        db.refresh(hh)
        assert hh.name == "Nyt Husstandsnavn"
