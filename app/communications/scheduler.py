import asyncio
from apscheduler.schedulers.background import BackgroundScheduler

from communications.utils import fetch_emails


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_emails_sync, 'interval', minutes=1)  # Adjust interval as needed
    scheduler.start()


def fetch_emails_sync():
    # Running the async function in a synchronous context
    asyncio.run(fetch_emails())

    print("Scheduler started: Email fetch job will run every minute.")
