from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communications'

    def ready(self):
        # Import and start the scheduler only once apps are loaded
        from .scheduler import start_scheduler
        print("Starting the scheduler from ready method.")
        start_scheduler()
