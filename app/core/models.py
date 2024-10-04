from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)
from django.utils import timezone

from auditlog.registry import auditlog
from django.db.models import ForeignKey, Sum
from django.conf import settings

import uuid
import os
import re
from django.core.exceptions import ValidationError

from django.utils.functional import cached_property


# helper function to get file name for the documents uploaded
def get_application_document_file_path(instance, filename):
    """Generate a file path for an application document."""
    ext = os.path.splitext(filename)[1]
    filename = f"{uuid.uuid4()}{ext}"

    return os.path.join('uploads', 'application', filename)


def validate_eircode(value):
    value = value.upper()  # Convert to uppercase
    """Check if the given value is a valid Eircode"""
    # Regular expression for the routing key (general rule)
    rk_regex = r'^[ACDEFHKNPRTVWXY][0-9][0-9W]$'
    # Regular expression for unique identifier
    ui_regex = r'^[ACDEFHKNPRTVWXY0-9]{4}$'

    routing_key = value[:3]  # First 3 characters
    unique_identifier = value[3:]  # Last 4 characters

    if not re.match(rk_regex, routing_key):
        raise ValidationError(
            f'{value} is not a valid Eircode, invalid routing key',
            params={'value': value},
        )

    if not re.match(ui_regex, unique_identifier):
        raise ValidationError(
            f'{value} is not a valid Eircode, invalid unique identifier',
            params={'value': value},
        )


def validate_irish_phone_number(value):
    """ Check if the value is a valid Irish phone number """
    pattern = r'^(?:\+353|0)[124679]?\d{7,9}$'
    if not re.match(pattern, value):
        raise ValidationError(
            f"{value} is not a valid Irish phone number. Please enter phone number in the format: '+353999999999' or '0999999999'",
        )


# region <Creating custom user model in django with extra fields name and team>
class UserManager(BaseUserManager):
    """Manager for users"""

    def create_user(self, email, password=None, **extra_fields):
        """Creates and saves a new user"""
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password):
        """Creates and saves a superuser with the given email and password."""
        user = self.create_user(email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class Team(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Address(models.Model):
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    town_city = models.CharField(max_length=50)
    county = models.CharField(max_length=50)
    eircode = models.CharField(max_length=7, validators=[validate_eircode])

    def __str__(self):
        return f'{self.line1}, {self.town_city}, {self.county}, {self.eircode}'


class User(AbstractBaseUser, PermissionsMixin):
    """User in the system"""
    email = models.EmailField(unique=True, max_length=255)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, default=None)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(validators=[validate_irish_phone_number], max_length=255, default=None, null=True,
                                    blank=True, )
    address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True, default=None)

    objects = UserManager()

    USERNAME_FIELD = 'email'

    def __str__(self):
        return f"{self.name}  -  {self.email}"


from django.db import models


class Solicitor(models.Model):
    """Assigned Solicitor for a particular task or application"""

    # ForeignKey to the User model
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitors')

    # Additional fields
    title = models.CharField(max_length=50)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    own_email = models.EmailField(max_length=255, null=True, blank=True)  # Optional email field
    own_phone_number = models.CharField(validators=[validate_irish_phone_number], max_length=20, null=True,
                                        blank=True)  # Optional phone number field

    def __str__(self):
        return f"{self.title} {self.first_name} {self.last_name} "


# endregion
class Deceased(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    # def delete(self, *args, **kwargs):
    #     if hasattr(self, 'application'):
    #         raise ValidationError("Cannot delete Deceased because an Application exists.")
    #     super().delete(*args, **kwargs)


class Dispute(models.Model):
    details = models.TextField()

    def __str__(self):
        return self.details

    # def delete(self, *args, **kwargs):
    #     if hasattr(self, 'application'):
    #         raise ValidationError("Cannot delete Dispute because an Application exists.")
    #     super().delete(*args, **kwargs)


class Application(models.Model):
    """Application model"""
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    term = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(36)])
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='solicitor_applications_set'
    )
    approved = models.BooleanField(default=False)
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        default=None, related_name='updated_applications_set'
    )
    date_submitted = models.DateTimeField(auto_now_add=True)
    deceased = models.ForeignKey(
        Deceased, on_delete=models.CASCADE, null=True, blank=True,
        related_name='applications'  # Renamed related name to reflect the one-to-many relationship
    )
    dispute = models.ForeignKey(
        Dispute, on_delete=models.CASCADE, null=True, blank=True,
        related_name='applications'  # Renamed related name to reflect the one-to-many relationship
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, default=None,
        related_name='assigned_applications_set'
    )
    is_rejected = models.BooleanField(default=False)
    rejected_reason = models.TextField(null=True, blank=True, default=None)
    rejected_date = models.DateField(null=True, blank=True, default=None)
    solicitor = models.ForeignKey(
        Solicitor, on_delete=models.PROTECT, null=True, blank=True, related_name='applications'
    )

    def value_of_the_estate_after_expenses(self):
        estates_sum = self.estates.aggregate(total_estate_value=Sum('value'))['total_estate_value'] or 0
        expenses_sum = self.expenses.aggregate(total_expense_value=Sum('value'))['total_expense_value'] or 0
        return estates_sum - expenses_sum

    @property
    def undertaking_ready(self) -> bool:
        return Document.objects.filter(application=self, is_undertaking=True).exists()

    @property
    def loan_agreement_ready(self) -> bool:
        return Document.objects.filter(application=self, is_loan_agreement=True).exists()

    def delete(self, *args, **kwargs):
        if self.deceased is not None:
            self.deceased.delete()
        if self.dispute is not None:
            self.dispute.delete()
        super().delete(*args, **kwargs)


class Comment(models.Model):
    text = models.TextField(default=None, null=True, blank=True)
    created_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                            related_name='comment_user_created')
    is_completed = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, blank=True, default=None)
    updated_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                            related_name='comment_user_updated')
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)


class Applicant(models.Model):
    TITLE_CHOICES = (
        ('Mr', 'Mr'),
        ('Ms', 'Ms'),
        ('Mrs', 'Mrs'),
        ('Dr', 'Dr'),
        ('Prof', 'Prof'),
    )

    title = models.CharField(max_length=5, choices=TITLE_CHOICES)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    pps_number = models.CharField(max_length=13, error_messages={
        'max_length': 'Ensure that PPS field has no more than 9 characters',
    })
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='applicants')

    # Each applicant can be associated with at most one application

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class Estate(models.Model):
    description = models.CharField(max_length=255)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='estates')

    def __str__(self):
        return f'{self.description} - {self.value}'


class Expense(models.Model):
    description = models.CharField(max_length=255)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='expenses')

    def __str__(self):
        return f'{self.description} - {self.value}'


class Document(models.Model):
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(upload_to=get_application_document_file_path)
    original_name = models.CharField(max_length=255, blank=True)
    is_signed = models.BooleanField(default=False)
    is_undertaking = models.BooleanField(default=False)
    is_loan_agreement = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def save(self, *args, **kwargs):
        if self.document and not self.id:  # Only set original_name when creating the instance
            self.original_name = self.document.name
        super().save(*args, **kwargs)

    # this overwrites makes sure that file is deleted when instance is deleted from the database
    def delete(self, *args, **kwargs):
        self.document.delete()
        super().delete(*args, **kwargs)


class Event(models.Model):
    request_id = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    body = models.TextField(null=True)
    response_status = models.PositiveIntegerField(null=True)
    response = models.TextField(null=True)
    is_error = models.BooleanField(default=False)
    is_notification = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    application = ForeignKey(Application, on_delete=models.CASCADE, blank=True, null=True, default=None,
                             related_name='events')


class Loan(models.Model):
    application = models.OneToOneField(Application, on_delete=models.PROTECT, related_name='loan')
    amount_agreed = models.DecimalField(max_digits=12, decimal_places=2)
    fee_agreed = models.DecimalField(max_digits=12, decimal_places=2)
    term_agreed = models.IntegerField(null=False, default=12, validators=[MinValueValidator(1), MaxValueValidator(36)])
    approved_date = models.DateField(null=True, blank=True)
    is_settled = models.BooleanField(default=False)
    settled_date = models.DateField(default=None, null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='loans_approved_by')
    last_updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        default=None, related_name='loans_updated_by')

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.pk:  # pk is None for new objects
                self.approved_date = timezone.now().date()
            super().save(*args, **kwargs)
            if self.application and not self.application.approved:
                self.application.approved = True
                self.application.save(update_fields=['approved'])

    @property
    def maturity_date(self):
        extensions_term_sum = self.extensions.aggregate(total_extension_term=Sum('extension_term_months'))[
                                  'total_extension_term'] or 0
        return self.approved_date + relativedelta(months=self.term_agreed + extensions_term_sum)

    @property
    def current_balance(self):
        transactions_sum = self.transactions.aggregate(total_paid=Sum('amount'))['total_paid'] or 0
        extensions_fee_sum = self.extensions.aggregate(total_extension_fee=Sum('extension_fee'))[
                                 'total_extension_fee'] or 0
        return self.amount_agreed + self.fee_agreed - transactions_sum + extensions_fee_sum

    @property
    def amount_paid(self):
        transactions_sum = self.transactions.aggregate(total_paid=Sum('amount'))['total_paid'] or 0
        return transactions_sum

    @property
    def extension_fees_total(self):
        return self.extensions.aggregate(total_extension_fee=Sum('extension_fee'))['total_extension_fee'] or 0

    def first_applicant(self):
        applicant = self.application.applicants.first()
        return str(applicant) if applicant else 'No applicants'


class Transaction(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_date = models.DateTimeField(
        default=timezone.now)  # Changed to DateTimeField for timezone-aware datetime
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='loan_transactions_created', default=None)
    description = models.TextField(blank=True, null=True)


class LoanExtension(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='extensions')
    extension_term_months = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(36)])
    extension_fee = models.DecimalField(max_digits=12, decimal_places=2)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name='loan_extensions_created')
    description = models.TextField(blank=True, null=True)
    created_date = models.DateTimeField(default=timezone.now)


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    text = models.CharField(max_length=500)
    seen = models.BooleanField(default=False)
    timestamp = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name='created_notifications'
    )
    application = models.ForeignKey(
        'Application', on_delete=models.CASCADE, null=True, blank=True, related_name='notifications_application'
    )

    def __str__(self):
        recipient_email = self.recipient.email if self.recipient else 'Application not assigned'
        return f'{recipient_email}: {self.text}'


class SignedDocumentLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='signed_documents'
    )
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE,
        related_name='signed_documents'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    signature_hash = models.CharField(max_length=64)  # SHA-256 hash length
    file_path = models.FileField(upload_to='signed_documents/')
    signing_user_email = models.EmailField(null=True, blank=True)  # Store the signing user email
    confirmation_message = models.TextField(null=True, blank=True)  # Store the confirmation message
    solicitor_full_name = models.CharField(max_length=255, null=True, blank=True)  # Store solicitor's full name
    confirmation_checked_by_user = models.BooleanField(default=False, null=True)
    signature_image_base64 = models.TextField(null=True, blank=True)  # New field for storing signature image

    # Geolocation fields
    country = models.CharField(max_length=100, null=True, blank=True)
    country_code = models.CharField(max_length=10, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    region_name = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    zip = models.CharField(max_length=20, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    timezone = models.CharField(max_length=50, null=True, blank=True)
    isp = models.CharField(max_length=200, null=True, blank=True)
    org = models.CharField(max_length=200, null=True, blank=True)
    as_number = models.CharField(max_length=100, null=True, blank=True)  # Store the AS number

    # New fields for proxy/VPN detection
    is_proxy = models.BooleanField(default=False, null=True)
    type = models.CharField(max_length=50, null=True, blank=True)  # Could be 'VPN', 'Proxy', etc.
    proxy_provider = models.CharField(max_length=255, null=True, blank=True)

    # New device information fields
    device_user_agent = models.TextField(null=True, blank=True)  # Complete User-Agent string
    device_browser_name = models.CharField(max_length=100, null=True, blank=True)  # e.g., 'Chrome'
    device_browser_version = models.CharField(max_length=100, null=True, blank=True)  # e.g., '89.0.4389.82'
    device_os_name = models.CharField(max_length=100, null=True, blank=True)  # e.g., 'Windows'
    device_os_version = models.CharField(max_length=100, null=True, blank=True)  # e.g., '10'
    device_cpu_architecture = models.CharField(max_length=50, null=True, blank=True)  # e.g., 'x64'
    device_type = models.CharField(max_length=50, null=True, blank=True)  # e.g., 'mobile', 'desktop'
    device_model = models.CharField(max_length=100, null=True, blank=True)  # e.g., 'iPhone'
    device_vendor = models.CharField(max_length=100, null=True, blank=True)  # e.g., 'Apple'
    device_screen_resolution = models.CharField(max_length=50, null=True, blank=True)  # e.g., '1920x1080'

    def __str__(self):
        return f'Signed Document for Application ID {self.application.id} by {self.user}'


auditlog.register(User)
auditlog.register(Application)
auditlog.register(Document)
auditlog.register(Loan)
