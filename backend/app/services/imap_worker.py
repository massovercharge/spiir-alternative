"""IMAP poller worker for inbound Storebox/Nexi receipt emails."""
from __future__ import annotations

import asyncio
import imaplib
import logging

from app.core.config import get_imap_config
from app.services.inbound_email_service import process_inbound_email

logger = logging.getLogger("peng.imap_worker")


async def run_imap_poller_loop():
    """Background loop that polls configured IMAP mailbox for new receipt emails."""
    config = get_imap_config()
    if not config["enabled"] or not config["host"] or not config["user"]:
        logger.info("[IMAP] IMAP polling is disabled or not configured.")
        return

    logger.info(
        "[IMAP] Starting IMAP polling worker for %s@%s (interval: %ss)",
        config["user"],
        config["host"],
        config["poll_interval"],
    )

    while True:
        try:
            # Run blocking IMAP operations in a worker thread
            await asyncio.to_thread(_poll_imap_once, config)
        except Exception as exc:
            logger.warning("[IMAP] Error during IMAP poll: %s", exc)

        await asyncio.sleep(int(config["poll_interval"]))


def _poll_imap_once(config: dict[str, object]):
    """Connect to IMAP server, fetch unseen emails, and process them."""
    host = str(config["host"])
    port = int(config["port"])
    user = str(config["user"])
    password = str(config["password"])
    use_ssl = bool(config["ssl"])
    folder = str(config["folder"])

    if not host or not user or not password:
        return

    client = None
    try:
        client = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
        client.login(user, password)
        res, _ = client.select(folder)
        if res != "OK":
            logger.warning("[IMAP] Failed to select folder '%s'", folder)
            return

        status, message_ids = client.search(None, "UNSEEN")
        if status != "OK" or not message_ids or not message_ids[0]:
            return

        ids = message_ids[0].split()
        logger.info("[IMAP] Found %d unseen messages to process", len(ids))

        for msg_id in ids:
            try:
                fetch_status, data = client.fetch(msg_id, "(RFC822)")
                if fetch_status != "OK" or not data:
                    continue

                raw_email = None
                for response_part in data:
                    if isinstance(response_part, tuple) and len(response_part) > 1:
                        raw_email = response_part[1]
                        break

                if raw_email and isinstance(raw_email, bytes):
                    result = process_inbound_email(raw_email, source_type="imap")
                    logger.info("[IMAP] Processed email msg_id=%s -> result: %s", msg_id.decode(), result.get("status"))

                # Mark as seen
                client.store(msg_id, "+FLAGS", "\\Seen")
            except Exception as e:
                logger.error("[IMAP] Failed to process message %s: %s", msg_id, e)

    finally:
        if client:
            import contextlib
            with contextlib.suppress(Exception):
                client.close()
            with contextlib.suppress(Exception):
                client.logout()
