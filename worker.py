"""
Background worker for email polling and processing using Dramatiq.
Can also run as async tasks in the FastAPI app.
"""

import logging
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from config import get_settings
from classification_service import ClassificationService

logger = logging.getLogger(__name__)

settings = get_settings()
classification_service = ClassificationService()

# For now, using APScheduler instead of Dramatiq to keep setup simple
scheduler = BackgroundScheduler()


def poll_and_process_emails():
    """Poll Gmail inbox and process unread emails"""
    try:
        logger.info("Starting email polling...")
        result = classification_service.process_unread_emails()
        logger.info(f"Polling complete: {result}")
    except Exception as e:
        logger.error(f"Error in poll_and_process_emails: {e}")


def start_scheduler():
    """Start the background scheduler"""
    if not scheduler.running:
        poll_interval = settings.poll_interval_seconds
        scheduler.add_job(
            poll_and_process_emails,
            'interval',
            seconds=poll_interval,
            id='email_poller',
            name='Email Poller'
        )
        scheduler.start()
        logger.info(f"Started email poller (interval: {poll_interval}s)")


def stop_scheduler():
    """Stop the background scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Stopped email poller")
