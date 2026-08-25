from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.auth import _sync_user_and_household
from app.models import Household, HouseholdMember, User, all_models
from app.services.household_service import invite_member


def test_invite_member_and_pending_sync():
    with Session(all_models.engine) as db:
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
    from app.services.household_service import update_household

    with Session(all_models.engine) as db:
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

def test_list_households_bypasses_tenant_filter():
    from app.models import current_household_id
    from app.services.household_service import list_households

    with Session(all_models.engine) as db:
        # Create user
        u = User(logto_id="test_list_123", email="list@example.com")
        db.add(u)
        db.commit()

        # Create two households
        hh1 = Household(name="HH1")
        hh2 = Household(name="HH2")
        db.add(hh1)
        db.add(hh2)
        db.commit()

        # Add user to both
        m1 = HouseholdMember(household_id=hh1.id, user_id=u.id)
        m2 = HouseholdMember(household_id=hh2.id, user_id=u.id)
        db.add(m1)
        db.add(m2)
        db.commit()

        # Set active tenant context to ONLY hh1
        token = current_household_id.set(hh1.id)
        try:
            # Bug: list_households used to only return hh1 because HouseholdMember was filtered
            households = list_households(u.id)
            assert len(households) == 2
            names = [h["name"] for h in households]
            assert "HH1" in names
            assert "HH2" in names
        finally:
            current_household_id.reset(token)

def test_remove_member_self_removal_and_last_owner_protection():
    from app.services.household_service import remove_member

    with Session(all_models.engine) as db:
        owner = User(logto_id="owner_rm_1", email="owner_rm@example.com")
        member = User(logto_id="member_rm_2", email="member_rm@example.com")
        db.add(owner)
        db.add(member)
        db.commit()

        hh = Household(name="Fælles Husstand")
        db.add(hh)
        db.commit()

        m_owner = HouseholdMember(household_id=hh.id, user_id=owner.id, role="owner")
        m_member = HouseholdMember(household_id=hh.id, user_id=member.id, role="member")
        db.add(m_owner)
        db.add(m_member)
        db.commit()

        # 1. Non-owner member can leave (self-removal)
        res = remove_member(hh.id, member.id, member.id)
        assert res["success"] is True

        # Verify member is removed
        remaining = db.exec(
            select(HouseholdMember).where(
                HouseholdMember.household_id == hh.id,
                HouseholdMember.user_id == member.id
            )
        ).first()
        assert remaining is None

        # 2. Last owner cannot leave or be removed
        with pytest.raises(HTTPException) as exc_info:
            remove_member(hh.id, owner.id, owner.id)
        assert exc_info.value.status_code == 400
        assert "last owner" in exc_info.value.detail

def test_invite_member_email_normalization():
    from app.schemas.requests import HouseholdInviteRequest

    req = HouseholdInviteRequest(email="  MixedCase.User@Example.COM  ")
    assert req.email == "mixedcase.user@example.com"
    assert req.role == "member"

def test_update_member_role_and_last_owner_protection():
    from app.services.household_service import update_member_role

    with Session(all_models.engine) as db:
        owner = User(logto_id="owner_role_1", email="owner_role@example.com")
        member = User(logto_id="member_role_2", email="member_role@example.com")
        db.add(owner)
        db.add(member)
        db.commit()

        hh = Household(name="Husstand Roller")
        db.add(hh)
        db.commit()

        m_owner = HouseholdMember(household_id=hh.id, user_id=owner.id, role="owner")
        m_member = HouseholdMember(household_id=hh.id, user_id=member.id, role="member")
        db.add(m_owner)
        db.add(m_member)
        db.commit()

        # 1. Non-owner cannot change roles (HTTP 403)
        with pytest.raises(HTTPException) as exc:
            update_member_role(hh.id, member.id, member.id, "owner")
        assert exc.value.status_code == 403

        # 2. Owner promotes member to owner
        res = update_member_role(hh.id, owner.id, member.id, "owner")
        assert res["success"] is True
        assert res["role"] == "owner"

        db.refresh(m_member)
        assert m_member.role == "owner"

        # 3. Demote original owner to member (allowed since member is now also an owner)
        res2 = update_member_role(hh.id, member.id, owner.id, "member")
        assert res2["success"] is True
        assert res2["role"] == "member"

        # 4. Try to demote the now last owner (should fail with HTTP 400)
        with pytest.raises(HTTPException) as exc:
            update_member_role(hh.id, member.id, member.id, "member")
        assert exc.value.status_code == 400
        assert "at least one owner" in exc.value.detail

def test_update_transaction_category_creates_missing_allocation():
    from app.models import Account, BankConnection, Posting, PostingAllocation
    from app.services.transaction_service import update_transaction_category

    with Session(all_models.engine) as db:
        hh = Household(name="Tx Category Test HH")
        db.add(hh)
        db.commit()
        db.refresh(hh)
        all_models.current_household_id.set(hh.id)

        bc = BankConnection(household_id=hh.id, bank_name="Test Bank", external_id="ext123")
        db.add(bc)
        db.commit()

        acc = Account(household_id=hh.id, bank_connection_id=bc.id, account_number="1234", name="NemKonto")
        db.add(acc)
        db.commit()

        posting = Posting(
            id="tx_test_alloc_1",
            household_id=hh.id,
            account_uid=acc.uid,
            booking_date="2026-08-01",
            original_description="Netto",
            cleaned_description="Netto",
            amount_minor=-15000,
        )
        db.add(posting)
        db.commit()

        # Ensure NO PostingAllocation exists yet
        alloc = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == posting.id)).first()
        assert alloc is None

        # Update category
        success = update_transaction_category(posting.id, "dagligvarer|supermarked")
        assert success is True

        # Verify allocation was automatically created with correct household_id and category
        alloc = db.exec(select(PostingAllocation).where(PostingAllocation.posting_id == posting.id)).first()
        assert alloc is not None
        assert alloc.category_id == "dagligvarer|supermarked"
        assert alloc.amount_minor == -15000
        assert alloc.household_id == hh.id

