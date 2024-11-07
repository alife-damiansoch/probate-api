from django.core.management.base import BaseCommand
from core.models import User, Solicitor, AssociatedEmail
from django.db import transaction


class Command(BaseCommand):
    """
      Django management command to add emails to the AssociatedEmail model for all users and solicitors.

      This command:
      1. Finds the first superuser in the database to assign as the `added_by` field in AssociatedEmail entries.
      2. Adds emails for users who are not staff (is_staff=False) to the AssociatedEmail model, if they aren’t already associated.
      3. Adds solicitors' emails (if they exist) to the AssociatedEmail model, ensuring there are no duplicate entries.

      If no superuser is found, the command outputs an error and terminates.

      Methods:
      - handle: Main method that orchestrates the email addition process, including error handling.
      - add_users_to_associated_email: Adds emails of non-staff users to AssociatedEmail, marking the superuser as `added_by`.
      - add_solicitors_to_associated_email: Adds emails of solicitors to AssociatedEmail, with the superuser as `added_by`.

      Parameters:
      - None directly, but the command utilizes the User and Solicitor models, and the AssociatedEmail model for logging emails.

      Returns:
      None. This command logs information to the console and updates the database.

      Exceptions:
      - If an error occurs, it outputs an error message and raises the exception.

      Usage:
      Run this command from the command line with `python manage.py <command_name>`.
      """
    help = 'Add emails to AssociatedEmail for all users and solicitors'

    def handle(self, *args, **kwargs):
        try:
            # Find the first superuser to assign as 'added_by'
            superuser = User.objects.filter(is_superuser=True).first()
            if not superuser:
                self.stdout.write(self.style.ERROR('No superuser found. Please create a superuser first.'))
                return

            # Add users to AssociatedEmail where is_staff is False
            user_count = self.add_users_to_associated_email(superuser)
            if user_count == 0:
                self.stdout.write(self.style.WARNING('No new users were added to AssociatedEmail'))

            # Add solicitors to AssociatedEmail
            solicitor_count = self.add_solicitors_to_associated_email(superuser)
            if solicitor_count == 0:
                self.stdout.write(self.style.WARNING('No new solicitors were added to AssociatedEmail'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))
            raise e

    @transaction.atomic
    def add_users_to_associated_email(self, superuser):
        users = User.objects.filter(is_staff=False)
        added_count = 0

        for user in users:
            if not AssociatedEmail.objects.filter(user=user, email=user.email).exists():
                AssociatedEmail.objects.create(
                    user=user,
                    email=user.email,
                    added_by=superuser
                )
                self.stdout.write(self.style.SUCCESS(f'Added {user.email} to AssociatedEmail'))
                added_count += 1

        return added_count

    @transaction.atomic
    def add_solicitors_to_associated_email(self, superuser):
        solicitors = Solicitor.objects.exclude(own_email__isnull=True).exclude(own_email='')
        added_count = 0

        for solicitor in solicitors:
            if not AssociatedEmail.objects.filter(user=solicitor.user, email=solicitor.own_email).exists():
                AssociatedEmail.objects.create(
                    user=solicitor.user,
                    email=solicitor.own_email,
                    added_by=superuser
                )
                self.stdout.write(self.style.SUCCESS(f'Added {solicitor.own_email} to AssociatedEmail'))
                added_count += 1

        return added_count
