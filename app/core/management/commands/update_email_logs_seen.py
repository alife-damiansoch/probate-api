from django.core.management.base import BaseCommand
from core.models import EmailLog  # Update this import based on where your model is


class Command(BaseCommand):
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
