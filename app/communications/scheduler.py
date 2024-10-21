from apscheduler.schedulers.background import BackgroundScheduler
from communications.utils import fetch_emails


def start_scheduler():
    # Create a scheduler instance
    scheduler = BackgroundScheduler()

    # Add the fetch_emails task to run every minute
    scheduler.add_job(fetch_emails, 'interval', minutes=1)  # No need for self

    # Start the scheduler
    scheduler.start()

    print("Scheduler started: Email fetch job will run every minute.")
