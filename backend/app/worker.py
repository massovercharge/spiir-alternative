import asyncio
import datetime
from sqlmodel import Session, select
from app.database import engine, Household, HouseholdMember

async def purge_deleted_households_worker():
    """Background task to permanently delete households soft-deleted more than 2 hours ago."""
    while True:
        try:
            with Session(engine) as db:
                now = datetime.datetime.now(datetime.timezone.utc)
                cutoff = now - datetime.timedelta(hours=2)
                
                # We need to find households where deleted_at is not None and is older than cutoff
                households = db.exec(
                    select(Household).where(Household.deleted_at != None)
                ).all()
                
                for hh in households:
                    if hh.deleted_at:
                        try:
                            # Safely parse ISO format with Z
                            dt_str = hh.deleted_at.replace("Z", "+00:00")
                            deleted_time = datetime.datetime.fromisoformat(dt_str)
                            
                            # If timezone unaware, assume UTC
                            if deleted_time.tzinfo is None:
                                deleted_time = deleted_time.replace(tzinfo=datetime.timezone.utc)
                                
                            if deleted_time < cutoff:
                                print(f"[WORKER] Purging household {hh.id} ({hh.name}) as it was deleted > 2 hours ago", flush=True)
                                
                                # Since this is a simple implementation, if PRAGMA foreign_keys=ON, this might fail unless cascaded.
                                # Let's import all models to manually delete dependent records
                                from app.database import Account, Transaction, Posting, PostingAllocation, Budget, Rule, RecurringTransaction, BankConnection
                                
                                # Delete dependent rows in reverse dependency order
                                for model in [PostingAllocation, Posting, Transaction, Account, Budget, Rule, RecurringTransaction, BankConnection]:
                                    if hasattr(model, "household_id"):
                                        rows = db.exec(select(model).where(model.household_id == hh.id)).all()
                                        for row in rows:
                                            db.delete(row)
                                            
                                # Delete members
                                members = db.exec(select(HouseholdMember).where(HouseholdMember.household_id == hh.id)).all()
                                for m in members:
                                    db.delete(m)
                                    
                                # Delete household
                                db.delete(hh)
                                db.commit()
                        except Exception as e:
                            print(f"[WORKER] Error purging household {hh.id}: {e}", flush=True)
                            db.rollback()
        except Exception as e:
            print(f"[WORKER] Global error: {e}", flush=True)
            
        await asyncio.sleep(60 * 10)  # Check every 10 minutes
