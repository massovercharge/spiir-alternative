from app.database import engine, Posting, PostingAllocation, CategorizationRule
from sqlmodel import Session, select, col
from app.rules_service import evaluate_posting

def run_fix():
    print("Starter fuld re-kategorisering af alle transaktioner med den nye word-boundary motor...")
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
        
        allocations = db.exec(select(PostingAllocation)).all()
        
        print(f"Fandt {len(allocations)} transaktioner i alt. Tjekker alle...")
        
        for alloc in allocations:
            posting = db.get(Posting, alloc.posting_id)
            if not posting:
                continue
            
            matched = evaluate_posting(posting, rules=active_rules)
            fallback = "diverse|ikke-kategoriseret"
            new_cat = matched or fallback
            
            if alloc.category_id != new_cat:
                alloc.category_id = new_cat
                db.add(alloc)
                updated += 1
                
        db.commit()
    print(f"Færdig! Opdaterede {updated} transaktioner til nye, mere præcise kategorier.")

if __name__ == "__main__":
    run_fix()
