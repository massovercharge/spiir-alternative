import sys
from pathlib import Path

# Add the project root to sys.path so we can import 'app'
sys.path.append(str(Path(__file__).parent.parent))

from sqlmodel import Session, select, or_
from app.database import PostingAllocation, engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_uncategorized():
    """Migrate all None and diverse|ukategoriseret to diverse|ikke-kategoriseret."""
    logger.info("Starting migration of uncategorized allocations...")
    
    with Session(engine) as session:
        allocations = session.exec(
            select(PostingAllocation).where(
                or_(
                    PostingAllocation.category_id.is_(None),
                    PostingAllocation.category_id == "diverse|ukategoriseret"
                )
            )
        ).all()
        
        count = 0
        for alloc in allocations:
            alloc.category_id = "diverse|ikke-kategoriseret"
            count += 1
            
        if count > 0:
            session.commit()
            logger.info(f"Successfully migrated {count} allocations to 'diverse|ikke-kategoriseret'.")
        else:
            logger.info("No allocations needed migration.")

if __name__ == "__main__":
    migrate_uncategorized()
