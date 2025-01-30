import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Check if all required environment variables are set"

    # List of required environment variables (excluding DB-related ones initially)
    REQUIRED_ENV_VARS = [
        "DJANGO_SECRET_KEY",
        "PPS_ENCRYPTION_KEY",
        "ALLOWED_HOSTS",
        "ADDITIONAL_CORS_ORIGINS",
        "CSRF_TRUSTED_ORIGINS",
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
        "AZURE_POSTGRESQL_CONNECTIONSTRING",  # This is the main DB connection variable
    ]

    # If `AZURE_POSTGRESQL_CONNECTIONSTRING` is not set, check these as well
    FALLBACK_DB_VARS = [
        "DB_HOST",
        "DB_NAME",
        "DB_USER",
        "DB_PASS",
    ]

    def handle(self, *args, **kwargs):
        missing_vars = []

        self.stdout.write("\n🚀 **Checking Environment Variables Before Deployment**\n")

        # Check required variables
        for var in self.REQUIRED_ENV_VARS:
            value = os.getenv(var, None)
            if not value:
                missing_vars.append(var)
                self.stdout.write(self.style.ERROR(f"❌ MISSING: {var}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"✅ {var}: {value}"))

        # Check individual DB credentials only if `AZURE_POSTGRESQL_CONNECTIONSTRING` is NOT set
        if not os.getenv("AZURE_POSTGRESQL_CONNECTIONSTRING"):
            self.stdout.write(
                "\n🔍 `AZURE_POSTGRESQL_CONNECTIONSTRING` is missing! Checking individual DB credentials...\n")
            for var in self.FALLBACK_DB_VARS:
                value = os.getenv(var, None)
                if not value:
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
