from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlmodel import Session, col, select

from app.models import Account, Category, Posting, PostingAllocation, engine
from app.services.category_service import make_category_id

logger = logging.getLogger(__name__)


def detect_internal_transfers() -> dict[str, Any]:
    """Find and auto-categorize transfers between the user's own accounts.

    If one account is an 'Opsparing' account, the outgoing transaction is
    categorized as 'Pension & Opsparing -> [Account Name]' and the incoming
    is categorized as 'Kontooverførsel'. If both are normal accounts, both are
    categorized as 'Kontooverførsel'.
    """
    with Session(engine) as db:
        # We need to fetch all accounts to know their types
        accounts = db.exec(select(Account)).all()
        account_dict = {a.uid: a for a in accounts}

        postings = db.exec(select(Posting).order_by(col(Posting.booking_date).asc())).all()

        # Pre-fetch allocations
        allocations = db.exec(select(PostingAllocation)).all()
        alloc_by_posting = {a.posting_id: a for a in allocations}

        matched_posting_ids: set[str] = set()
        matches_found = 0

        # Group by absolute amount to speed up matching
        postings_by_abs_amount: dict[int, list[Posting]] = {}
        for p in postings:
            abs_amt = abs(p.amount_minor)
            if abs_amt not in postings_by_abs_amount:
                postings_by_abs_amount[abs_amt] = []
            postings_by_abs_amount[abs_amt].append(p)

        # Ensure category "Vis ikke -> Kontooverførsel" exists
        transfer_cat_id = make_category_id("Vis ikke", "Kontooverførsel")
        transfer_cat = db.get(Category, transfer_cat_id)
        if not transfer_cat:
            transfer_cat = Category(
                id=transfer_cat_id,
                main_name="Vis ikke",
                sub_name="Kontooverførsel",
                expense_type="Variable",
            )
            db.add(transfer_cat)
            db.commit()

        for _abs_amt, group in postings_by_abs_amount.items():
            if len(group) < 2:
                continue

            for i, p1 in enumerate(group):
                if p1.id in matched_posting_ids:
                    continue

                for j in range(i + 1, len(group)):
                    p2 = group[j]
                    if p2.id in matched_posting_ids:
                        continue

                    if p1.account_uid == p2.account_uid:
                        continue

                    if p1.amount_minor == p2.amount_minor:
                        continue

                    try:
                        a1 = account_dict.get(p1.account_uid)
                        a2 = account_dict.get(p2.account_uid)

                        max_diff = 0
                        if a1 and a2 and a1.bank_connection_id != a2.bank_connection_id:
                            max_diff = 3  # Allow up to 3 days for inter-bank transfers (weekends)

                        d1 = datetime.fromisoformat(p1.booking_date[:10])
                        d2 = datetime.fromisoformat(p2.booking_date[:10])
                        diff = abs((d1 - d2).days)

                        if diff <= max_diff:
                            matched_posting_ids.add(p1.id)
                            matched_posting_ids.add(p2.id)
                            matches_found += 1

                            type1 = a1.account_type if a1 else "Indlån"
                            type2 = a2.account_type if a2 else "Indlån"

                            if p1.amount_minor < 0:
                                p_out, p_in = p1, p2
                                a_out, a_in = a1, a2
                                type_out, type_in = type1, type2
                            else:
                                p_out, p_in = p2, p1
                                a_out, a_in = a2, a1
                                type_out, type_in = type2, type1

                            alloc_out = alloc_by_posting.get(p_out.id)
                            alloc_in = alloc_by_posting.get(p_in.id)

                            if not alloc_out:
                                alloc_out = PostingAllocation(
                                    posting_id=p_out.id, amount_minor=p_out.amount_minor
                                )
                                db.add(alloc_out)
                            if not alloc_in:
                                alloc_in = PostingAllocation(
                                    posting_id=p_in.id, amount_minor=p_in.amount_minor
                                )
                                db.add(alloc_in)

                            def can_overwrite(alloc: PostingAllocation) -> bool:
                                if not alloc.category_id:
                                    return True
                                return (
                                    alloc.category_id.startswith("diverse|")
                                    or alloc.category_id.startswith("vis-ikke|")
                                    or alloc.category_id.startswith("pension-opsparing|")
                                )

                            def get_savings_category_id(account: Account | None) -> str:
                                if account and account.savings_category_id:
                                    return account.savings_category_id
                                return make_category_id("Pension & Opsparing", "Anden opsparing")

                            if type_in == "Opsparing" and type_out != "Opsparing":
                                if can_overwrite(alloc_out):
                                    alloc_out.category_id = get_savings_category_id(a_in)
                                if can_overwrite(alloc_in):
                                    alloc_in.category_id = transfer_cat.id

                            elif type_out == "Opsparing" and type_in != "Opsparing":
                                if can_overwrite(alloc_out):
                                    alloc_out.category_id = transfer_cat.id
                                if can_overwrite(alloc_in):
                                    alloc_in.category_id = get_savings_category_id(a_out)

                            else:
                                if can_overwrite(alloc_out):
                                    alloc_out.category_id = transfer_cat.id
                                if can_overwrite(alloc_in):
                                    alloc_in.category_id = transfer_cat.id

                            break
                    except ValueError:
                        pass

        db.commit()
        return {"matched_pairs": matches_found, "total_transfers_processed": matches_found * 2}
