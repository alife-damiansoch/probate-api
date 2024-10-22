from django.apps import AppConfig
from django.conf import settings


class CommunicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communications'

    def ready(self):
        # Only start the scheduler if not in test mode
        if not settings.TESTING:
            from .scheduler import start_scheduler
            print("Starting the scheduler from ready method.")
            start_scheduler()
