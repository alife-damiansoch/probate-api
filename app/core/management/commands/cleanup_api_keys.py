from django.core.management.base import BaseCommand
from core.models import FrontendAPIKey


class Command(BaseCommand):
    help = "Delete expired API keys from the database"

    def handle(self, *args, **kwargs):
        print("Deleting Expired API keys Cronjob started")
        FrontendAPIKey.cleanup_expired_keys()
        self.stdout.write(self.style.SUCCESS("✅ Expired API keys deleted"))
