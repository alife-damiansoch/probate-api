from django.core.management.base import BaseCommand
from core.models import User, Solicitor, AssociatedEmail
from django.db import transaction


class Command(BaseCommand):
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
