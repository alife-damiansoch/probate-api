# communications/management/commands/fetch_emails.py
from django.core.management.base import BaseCommand
from communications.utils import fetch_emails


class Command(BaseCommand):
    help = 'Fetch new emails from the IMAP server'

    def handle(self, *args, **kwargs):
        fetch_emails()
