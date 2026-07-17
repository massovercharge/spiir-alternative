import sys
from pathlib import Path

# Add the project root to sys.path so we can import 'app'
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime
from sqlmodel import Session, col, select
from app.category_service import make_category_id
from app.database import Account, Category, Posting, PostingAllocation, engine

def detect_internal_transfers_dry_run():
    with Session(engine) as db:
        accounts = db.exec(select(Account)).all()
        account_dict = {a.uid: a for a in accounts}

        postings = db.exec(
            select(Posting).order_by(col(Posting.booking_date).asc())
        ).all()

        allocations = db.exec(select(PostingAllocation)).all()
        alloc_by_posting = {a.posting_id: a for a in allocations}

        matched_posting_ids = set()
        matches_found = 0

        postings_by_abs_amount = {}
        for p in postings:
            abs_amt = abs(p.amount_minor)
            if abs_amt not in postings_by_abs_amount:
                postings_by_abs_amount[abs_amt] = []
            postings_by_abs_amount[abs_amt].append(p)

        transfer_cat_id = make_category_id("Vis ikke", "Kontooverførsel")

        print("--- DRY RUN SAVINGS TRANSFERS ---")
        
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
                            max_diff = 3

                        d1 = datetime.fromisoformat(p1.booking_date[:10])
                        d2 = datetime.fromisoformat(p2.booking_date[:10])
                        diff = abs((d1 - d2).days)
                        if diff <= max_diff:
                            matched_posting_ids.add(p1.id)
                            matched_posting_ids.add(p2.id)
                            matches_found += 1

                            a1 = account_dict.get(p1.account_uid)
                            a2 = account_dict.get(p2.account_uid)

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

                            def can_overwrite(alloc) -> bool:
                                if not alloc or not alloc.category_id:
                                    return True
                                return alloc.category_id.startswith("diverse|") or alloc.category_id.startswith("vis-ikke|") or alloc.category_id.startswith("pension-opsparing|")

                            def get_savings_category_id(account) -> str:
                                if account and account.savings_category_id:
                                    return account.savings_category_id
                                return make_category_id("Pension & Opsparing", "Anden opsparing")

                            # Determine what the new category would be
                            out_new_cat = None
                            in_new_cat = None
                            
                            if type_in == "Opsparing" and type_out != "Opsparing":
                                if can_overwrite(alloc_out):
                                    out_new_cat = get_savings_category_id(a_in)
                                if can_overwrite(alloc_in):
                                    in_new_cat = transfer_cat_id
                            elif type_out == "Opsparing" and type_in != "Opsparing":
                                if can_overwrite(alloc_out):
                                    out_new_cat = transfer_cat_id
                                if can_overwrite(alloc_in):
                                    in_new_cat = get_savings_category_id(a_out)
                            else:
                                if can_overwrite(alloc_out):
                                    out_new_cat = transfer_cat_id
                                if can_overwrite(alloc_in):
                                    in_new_cat = transfer_cat_id

                            out_current = alloc_out.category_id if alloc_out else 'None'
                            in_current = alloc_in.category_id if alloc_in else 'None'
                            
                            # Only print if something actually changes and involves an Opsparing account
                            is_savings_transfer = (type_out == "Opsparing" or type_in == "Opsparing")
                            
                            a_out_name = a_out.name if a_out else 'Unknown'
                            a_in_name = a_in.name if a_in else 'Unknown'
                            is_spiir = "(Spiir)" in a_out_name or "(Spiir)" in a_in_name

                            if is_savings_transfer and not is_spiir and (out_new_cat or in_new_cat):
                                # Also filter out if there is no actual category change
                                if out_new_cat != out_current or in_new_cat != in_current:
                                    print(f"\nMatch {_abs_amt/100} DKK ({d1.date()} - {d2.date()}):")
                                    print(f"  OUT: {a_out_name} ({type_out}) - {p_out.original_description}")
                                    print(f"       Current Cat: {out_current} -> New Cat: {out_new_cat or out_current}")
                                    print(f"  IN : {a_in_name} ({type_in}) - {p_in.original_description}")
                                    print(f"       Current Cat: {in_current} -> New Cat: {in_new_cat or in_current}")

                            break
                    except ValueError:
                        pass
        print(f"\nTotal matches found: {matches_found}")

if __name__ == "__main__":
    detect_internal_transfers_dry_run()
