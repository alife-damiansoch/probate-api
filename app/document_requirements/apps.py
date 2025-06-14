from django.apps import AppConfig


class DocumentRequirementsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'document_requirements'
    verbose_name = 'Document Requirements'

    def ready(self):
        # Import signals if you need them
        pass
