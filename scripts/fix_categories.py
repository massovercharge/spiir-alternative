from app.database import engine, Posting, PostingAllocation, CategorizationRule
from sqlmodel import Session, select, col
from app.rules_service import evaluate_posting

def run_fix():
    print("Starter re-kategorisering af fejl-kategoriserede transaktioner...")
    updated = 0
    with Session(engine) as db:
        active_rules = db.exec(
            select(CategorizationRule)
            .where(CategorizationRule.is_active == True)
            .order_by(
                col(CategorizationRule.source).desc(),
                col(CategorizationRule.priority).asc(),
            )
        ).all()
        
        # Find alle posteringer i 'diverse|ikke-kategoriseret'
        allocations = db.exec(
            select(PostingAllocation)
            .where(PostingAllocation.category_id == "diverse|ikke-kategoriseret")
        ).all()
        
        print(f"Fandt {len(allocations)} transaktioner i ukendt kategori. Tjekker...")
        
        for alloc in allocations:
            posting = db.get(Posting, alloc.posting_id)
            if not posting:
                continue
            
            matched = evaluate_posting(posting, rules=active_rules)
            if matched and matched != "diverse|ikke-kategoriseret":
                alloc.category_id = matched
                db.add(alloc)
                updated += 1
                
        db.commit()
    print(f"Færdig! Opdaterede {updated} transaktioner til korrekte kategorier.")

if __name__ == "__main__":
    run_fix()
