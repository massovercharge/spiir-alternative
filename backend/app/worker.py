import asyncio
import datetime
from sqlmodel import Session, select
from app.models import engine, Household, HouseholdMember

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
                                
                                # Since SQLite does not automatically handle ON DELETE CASCADE if the schema 
                                # was created before ondelete="CASCADE" was added, we must manually delete dependent records.
                                from app.models import (
                                    Account, Posting, PostingAllocation, Budget, BudgetBill,
                                    CategorizationRule, RecurringTransaction, BankConnection,
                                    Document, CategoryOverrideLog, SyncJob, Tag, Payee
                                )
                                
                                # Delete dependent rows in reverse dependency order
                                models_to_purge = [
                                    Document, PostingAllocation, Posting, 
                                    RecurringTransaction, Account, BankConnection, Payee,
                                    BudgetBill, Budget, CategorizationRule, 
                                    CategoryOverrideLog, SyncJob, Tag, HouseholdMember
                                ]
                                
                                # Manually delete link tables that don't have household_id
                                from app.models import PostingAllocationTagLink
                                allocations = db.exec(select(PostingAllocation).where(PostingAllocation.household_id == hh.id)).all()
                                for alloc in allocations:
                                    links = db.exec(select(PostingAllocationTagLink).where(PostingAllocationTagLink.allocation_id == alloc.id)).all()
                                    for link in links:
                                        db.delete(link)
                                        
                                for model in models_to_purge:
                                    if hasattr(model, "household_id"):
                                        rows = db.exec(select(model).where(model.household_id == hh.id)).all()
                                        for row in rows:
                                            db.delete(row)
                                        try:
                                            db.flush()
                                        except Exception as e:
                                            print(f"[WORKER] Failed when flushing {model.__name__}: {e}", flush=True)
                                            raise
                                            
                                # Check if household was restored during purge processing
                                db.refresh(hh)
                                if not hh.deleted_at:
                                    print(f"[WORKER] Household {hh.id} was restored during purge, aborting deletion", flush=True)
                                    db.rollback()
                                    continue

                                # Delete household
                                db.delete(hh)
                                try:
                                    db.commit()
                                except Exception as e:
                                    print(f"[WORKER] Failed when committing household {hh.id}: {e}", flush=True)
                                    raise
                        except Exception as e:
                            print(f"[WORKER] Error purging household {hh.id}: {e}", flush=True)
                            db.rollback()
        except Exception as e:
            print(f"[WORKER] Global error: {e}", flush=True)
            
        await asyncio.sleep(60 * 10)  # Check every 10 minutes
