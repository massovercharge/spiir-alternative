import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .bank_service import start_bank_retrieve_job

logger = logging.getLogger(__name__)

# Start the background scheduler
scheduler = BackgroundScheduler()

def sync_bank_accounts():
    logger.info("Starting automated bank sync job...")
    try:
        start_bank_retrieve_job(sync_local_ledger=True)
        logger.info("Automated bank sync job dispatched successfully.")
    except Exception as e:
        logger.error(f"Error starting automated bank sync: {e}")

# Run daily at 2:00 AM
scheduler.add_job(
    sync_bank_accounts,
    trigger=CronTrigger(hour=2, minute=0),
    id="daily_bank_sync",
    name="Daily Bank Sync",
    replace_existing=True,
)

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started. Next bank sync scheduled.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler shut down.")
