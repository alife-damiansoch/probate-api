from django.core.management.base import BaseCommand
from core.models import EmailLog  # Update this import based on where your model is


class Command(BaseCommand):
    """
       Django management command to update all sent EmailLogs to mark them as seen.

       This command:
       1. Retrieves all `EmailLog` entries where `is_sent=True` and `seen=False`.
       2. Updates the `seen` field to `True` for each matching entry, indicating the emails have been viewed.

       If no matching entries are found, a warning message is displayed.

       Attributes:
       - help (str): A brief description of the command.

       Methods:
       - handle: Main method that performs the update, displaying the number of records updated or a warning if none are found.

       Usage:
       Run this command from the command line with `python manage.py <command_name>`.
       """
    help = "Update all EmailLogs where is_sent=True to set seen=True"

    def handle(self, *args, **kwargs):
        # Fetch all EmailLog entries where is_sent is True and seen is False
        email_logs = EmailLog.objects.filter(is_sent=True, seen=False)

        if not email_logs.exists():
            self.stdout.write(self.style.WARNING('No EmailLogs to update.'))
            return

        # Update seen status to True for each email log
        updated_count = email_logs.update(seen=True)

        self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} EmailLogs to seen=True.'))
