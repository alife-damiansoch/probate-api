import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check if all required environment variables are set"

    REQUIRED_ENV_VARS = [
        "DB_HOST",
        "DB_NAME",
        "DB_USER",
        "DB_PASS",
        "DJANGO_SECRET_KEY",
        "PPS_ENCRYPTION_KEY",
        "ALLOWED_HOSTS",
        "SECRET_KEY",
        "DEBUG",
        "AZURE_STORAGE_CONNECTION_STRING",
        "AZURE_ACCOUNT_NAME",
        "AZURE_CONTAINER",
        "COMPANY_NAME",
        "COMPANY_ADDRESS",
        "COMPANY_REGISTRATION_NUMBER",
        "COMPANY_WEBSITE",
        "COMPANY_PHONE_NUMBER",
        "COMPANY_CEO",
        "EMAIL_HOST",
        "EMAIL_HOST_USER",
        "EMAIL_HOST_PASSWORD",
        "DEFAULT_FROM_EMAIL",
        "IMAP_SERVER",
        "IMAP_PORT",
        "IMAP_USER",
        "IMAP_PASSWORD",
        "ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL",
        "COMMITTEE_MEMBERS_COUNT_REQUIRED_FOR_APPROVAL",
    ]

    def handle(self, *args, **kwargs):
        missing_vars = []

        self.stdout.write("\n🚀 **Checking Environment Variables Before Deployment**\n")

        for var in self.REQUIRED_ENV_VARS:
            value = os.getenv(var, None)
            if value is None or value == "":
                missing_vars.append(var)
                self.stdout.write(self.style.ERROR(f"❌ MISSING: {var}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"✅ {var}: {value}"))

        if missing_vars:
            self.stdout.write("\n⚠️ **Warning: The following environment variables are missing:**\n")
            for var in missing_vars:
                self.stdout.write(self.style.WARNING(f"⚠️ {var}"))
            self.stdout.write("\nEnsure they are set in Azure App Service → Configuration.\n")

        else:
            self.stdout.write(self.style.SUCCESS("\n✅ All environment variables are set!\n"))
