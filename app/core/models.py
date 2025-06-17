import secrets
from datetime import datetime
from decimal import Decimal

from cryptography.fernet import Fernet, InvalidToken
from dateutil.relativedelta import relativedelta
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import JSONField
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)
from django.template.loader import render_to_string
from django.utils import timezone

from auditlog.registry import auditlog
from django.db.models import ForeignKey, Sum
from django.conf import settings
from django.db import models

import uuid

from django.core.exceptions import ValidationError

from django.utils.timezone import now
from datetime import timedelta

from core.utils import get_application_document_file_path


# helper function to get file name for the documents uploaded


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
        user.is_active = True
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
    county = models.CharField(max_length=50, blank=True, null=True)
    eircode = models.CharField(max_length=12)

    def __str__(self):
        return f'{self.line1}, {self.town_city}, {self.county}, {self.eircode}'


COUNTRY_CHOICES = [
    ('IE', 'Ireland (Euro)', '€'),
    ('UK', 'United Kingdom (Pound)', '£'),
]


class User(AbstractBaseUser, PermissionsMixin):
    """User in the system"""
    AUTH_METHOD_CHOICES = [
        ('otp', 'OTP via Email'),
        ('authenticator', 'Authenticator App'),
    ]
    email = models.EmailField(unique=True, max_length=255)
    teams = models.ManyToManyField(Team, blank=True, related_name='users')  # Changed to ManyToManyField
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=255, default=None, null=True,
                                    blank=True, )
    address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True, default=None)
    country = models.CharField(
        max_length=2,
        choices=[(code, name) for code, name, _ in COUNTRY_CHOICES],  # Map choices for Django display
        null=True,
        blank=True
    )
    activation_token = models.UUIDField(default=None, unique=True, null=True, blank=True)
    preferred_auth_method = models.CharField(
        max_length=20,
        choices=AUTH_METHOD_CHOICES,
        default='otp',
        verbose_name='Preferred Authentication Method',
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'

    def __str__(self):
        return f"{self.name}  -  {self.email}"

    def get_currency(self):
        for code, name, currency in COUNTRY_CHOICES:
            if self.country == code:
                return currency
        return None

    def save(self, *args, **kwargs):
        # Automatically generate activation token for non-staff and inactive users if not set
        if not self.is_staff and not self.is_active and not self.activation_token:
            self.activation_token = uuid.uuid4()
        super().save(*args, **kwargs)


# this is for One Time password email verification
class OTP(models.Model):
    email = models.EmailField(unique=True)  # Ensure one OTP per email
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        """Check if the OTP is still valid (e.g., expires in 5 minutes)."""
        return now() < self.created_at + timedelta(minutes=5)


#     This is for Authenticator app verification
class AuthenticatorSecret(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='authenticator_secret'
    )
    secret = models.CharField(max_length=32)  # Base32 secret for TOTP
    is_active = models.BooleanField(default=False)  # Track if the secret is active
    created_at = models.DateTimeField(auto_now_add=True)


class Solicitor(models.Model):
    """Assigned Solicitor for a particular task or application"""

    # ForeignKey to the User model
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solicitors')

    # Additional fields
    title = models.CharField(max_length=50)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    own_email = models.EmailField(max_length=255, null=True, blank=True, unique=True)  # Optional email field
    own_phone_number = models.CharField(max_length=20, null=True,
                                        blank=True)  # Optional phone number field

    def __str__(self):
        return f"{self.title} {self.first_name} {self.last_name} "


class AssociatedEmail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='associated_emails')
    email = models.EmailField()
    date_added = models.DateTimeField(default=timezone.now)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='added_emails')

    def __str__(self):
        return self.email


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
    is_new = models.BooleanField(default=True)  # Indicates if this is a new application

    was_will_prepared_by_solicitor = models.BooleanField(
        default=False,
        help_text="Was this will professionally prepared by a solicitor?"
    )

    class Meta:
        indexes = [
            models.Index(fields=['date_submitted']),
            models.Index(fields=['term']),
            models.Index(fields=['amount']),
            models.Index(fields=['user']),
            models.Index(fields=['solicitor']),
            models.Index(fields=['assigned_to']),
        ]

    def value_of_the_estate_after_expenses(self):
        total_assets = Decimal(0)
        total_debts = Decimal(0)

        related_fields = [
            self.real_and_leasehold.all(),
            self.household_contents.all(),
            self.cars_boats.all(),
            self.business_farming.all(),
            self.business_other.all(),
            self.unpaid_purchase_money.all(),
            self.financial_assets.all(),
            self.life_insurance.all(),
            self.debts_owing.all(),
            self.securities_quoted.all(),
            self.securities_unquoted.all(),
            self.other_property.all(),
            self.irish_debts.all(),
        ]

        for related in related_fields:
            assets_sum = related.filter(is_asset=True).aggregate(sum=Sum('value'))['sum'] or Decimal(0)
            debts_sum = related.filter(is_asset=False).aggregate(sum=Sum('value'))['sum'] or Decimal(0)
            total_assets += assets_sum
            total_debts += debts_sum

        return total_assets - total_debts

    @property
    def undertaking_ready(self) -> bool:
        return Document.objects.filter(application=self, is_undertaking=True).exists()

    @property
    def loan_agreement_ready(self) -> bool:
        applicants = Applicant.objects.filter(application=self)
        applicants_count = len(applicants)
        return len(Document.objects.filter(application=self,
                                           is_loan_agreement=True)) >= applicants_count > 0

    def delete(self, *args, **kwargs):
        if self.deceased is not None:
            self.deceased.delete()
        if self.dispute is not None:
            self.dispute.delete()
        super().delete(*args, **kwargs)


class ApplicationProcessingStatus(models.Model):
    """Application processing status and solicitor preferences"""

    AML_METHOD_CHOICES = [
        ('KYC', 'KYC'),
        ('AML', 'AML'),
    ]

    application = models.OneToOneField(
        'Application',
        on_delete=models.CASCADE,
        related_name='processing_status'
    )

    application_details_completed_confirmed = models.BooleanField(default=False)

    solicitor_preferred_aml_method = models.CharField(
        max_length=3,
        choices=AML_METHOD_CHOICES,
        null=True,
        blank=True
    )

    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='updated_processing_status_set'
    )

    date_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Processing Status for Application {self.application.id}"


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

    # Existing fields
    title = models.CharField(max_length=5, choices=TITLE_CHOICES)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    pps_number = models.BinaryField(null=True, blank=True)
    application = models.ForeignKey(
        'Application', on_delete=models.CASCADE, related_name='applicants')

    # New fields with default values for compatibility
    address_line_1 = models.CharField(max_length=255, default='', blank=True)
    address_line_2 = models.CharField(max_length=255, default='', blank=True)
    city = models.CharField(max_length=100, default='', blank=True)
    county = models.CharField(max_length=100, default='', blank=True)
    postal_code = models.CharField(max_length=20, default='', blank=True)
    country = models.CharField(max_length=100, default='Ireland', blank=True)

    date_of_birth = models.DateField(null=True, blank=True)

    email = models.EmailField(max_length=254, default='', blank=True)

    phone_number = models.CharField(max_length=17, default='', blank=True)

    # Timestamps for auditing
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def full_name(self):
        """Return the full name of the applicant."""
        return f"{self.first_name} {self.last_name}"

    @property
    def full_address(self):
        """Return the full formatted address."""
        address_parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.county,
            self.postal_code,
            self.country
        ]
        return ', '.join([part for part in address_parts if part.strip()])

    @property
    def decrypted_pps(self):
        """Decrypt and return the PPS number."""
        if not self.pps_number:
            return None
        cipher = Fernet(settings.PPS_ENCRYPTION_KEY)
        encrypted_pps = (
            self.pps_number.tobytes()
            if isinstance(self.pps_number, memoryview)
            else self.pps_number
        )
        return cipher.decrypt(encrypted_pps).decode()

    def encrypt_pps(self, pps):
        """Encrypt the given PPS number."""
        cipher = Fernet(settings.PPS_ENCRYPTION_KEY)
        return cipher.encrypt(pps.encode())

    def save(self, *args, **kwargs):
        """Ensure encryption happens before saving."""
        if self.pps_number and isinstance(self.pps_number, str):  # Encrypt if it's plain text
            self.pps_number = self.encrypt_pps(self.pps_number)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Applicant'
        verbose_name_plural = 'Applicants'


class RealAndLeaseholdProperty(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="real_and_leasehold")
    address = models.TextField(blank=True)
    county = models.CharField(max_length=128, blank=True)
    nature = models.CharField(max_length=128, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class HouseholdContents(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="household_contents")
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class CarsBoats(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="cars_boats")
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class BusinessFarming(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="business_farming")
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class BusinessOther(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="business_other")
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class UnpaidPurchaseMoney(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="unpaid_purchase_money")
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class FinancialAsset(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="financial_assets")
    institution = models.CharField(max_length=128, blank=True)
    account_number = models.CharField(max_length=128, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class LifeInsurance(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="life_insurance")
    insurer = models.CharField(max_length=128, blank=True)
    policy_number = models.CharField(max_length=128, blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class DebtOwed(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="debts_owing")
    debtor = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=False)
    is_asset = models.BooleanField(default=True)


class SecuritiesQuoted(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="securities_quoted")
    description = models.TextField(blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class SecuritiesUnquoted(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="securities_unquoted")
    description = models.TextField(blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=False)
    is_asset = models.BooleanField(default=True)


class OtherProperty(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="other_property")
    description = models.TextField(blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    lendable = models.BooleanField(default=True)
    is_asset = models.BooleanField(default=True)


class IrishDebt(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="irish_debts")
    creditor = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    lendable = models.BooleanField(default=False)
    # NOT an asset
    is_asset = models.BooleanField(default=False)


class Expense(models.Model):
    description = models.CharField(max_length=255)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='expenses')

    def __str__(self):
        return f'{self.description} - {self.value}'


class Document(models.Model):
    SIGNER_CHOICES = [
        ('solicitor', 'Solicitor'),
        ('applicant', 'Applicant'),
    ]

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(upload_to=get_application_document_file_path)
    original_name = models.CharField(max_length=255, blank=True)
    is_signed = models.BooleanField(default=False)
    is_undertaking = models.BooleanField(default=False)
    is_loan_agreement = models.BooleanField(default=False)
    signature_required = models.BooleanField(default=False)
    who_needs_to_sign = models.CharField(
        max_length=20,
        choices=SIGNER_CHOICES,
        default='solicitor',
        help_text="Who needs to sign this document"
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    # NEW FIELD: Link to document requirement (for user-uploaded docs)
    document_type_requirement = models.ForeignKey(
        'document_requirements.ApplicationDocumentRequirement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="The requirement this document fulfills"
    )

    def save(self, *args, **kwargs):
        # Only auto-set original_name when creating the instance AND it's empty
        if self.document and not self.id and not self.original_name:
            # Generate meaningful name based on document type and application
            if self.is_undertaking:
                self.original_name = f"Solicitor_Undertaking_{self.application.id}"
            elif self.is_loan_agreement:
                # For loan agreements, fallback to basic name if not set in view
                self.original_name = f"Advancement_Agreement_{self.application.id}"
            else:
                # Fallback to filename without extension
                filename = self.document.name
                if filename:
                    self.original_name = filename.rsplit('.', 1)[0] if '.' in filename else filename

        # Auto-set signature requirements based on document type
        if self.is_undertaking:
            self.signature_required = True
            self.who_needs_to_sign = 'solicitor'
        elif self.is_loan_agreement:
            self.signature_required = True
            self.who_needs_to_sign = 'applicant'

        super().save(*args, **kwargs)

    # this overwrites makes sure that file is deleted when instance is deleted from the database
    def delete(self, *args, **kwargs):
        self.document.delete()
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.original_name} - {self.application.id}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Document"
        verbose_name_plural = "Documents"


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
    # Fields for CommitteeApproval functionality
    needs_committee_approval = models.BooleanField(default=False)
    is_committee_approved = models.BooleanField(null=True, default=None)

    # New fields for paid out status
    is_paid_out = models.BooleanField(default=False)
    paid_out_date = models.DateField(null=True, blank=True)
    pay_out_reference_number = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['amount_agreed']),
            models.Index(fields=['fee_agreed']),
            models.Index(fields=['term_agreed']),
            models.Index(fields=['settled_date']),
            models.Index(fields=['paid_out_date']),
            models.Index(fields=['is_settled']),
            models.Index(fields=['is_paid_out']),
            models.Index(fields=['is_committee_approved']),
            models.Index(fields=['needs_committee_approval']),
            models.Index(fields=["pay_out_reference_number"])
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            is_new = self.pk is None  # Check if the instance is new

            if is_new:
                # Set approved_date for new objects
                self.approved_date = timezone.now().date()

                # Determine if committee approval is needed
                self.needs_committee_approval = self.amount_agreed >= settings.ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL

            # Set or clear paid_out_date based on is_paid_out
            if self.is_paid_out and not self.paid_out_date:
                self.paid_out_date = timezone.now().date()
            elif not self.is_paid_out:
                self.paid_out_date = None

            # Save the instance to ensure self.id is assigned
            super().save(*args, **kwargs)

            # Notify committee members if approval is needed and this is a new instance
            if is_new and self.needs_committee_approval:
                self.notify_committee_members(
                    message=f'Advancement: {self.id}, application:{self.application.id} needs committee approval',
                    subject="Committee Approval Required")

            # Auto-approve the related application if not already approved
            if self.application and not self.application.approved:
                self.application.approved = True
                self.application.save(update_fields=['approved'])

    @property
    def maturity_date(self):
        """
        Calculate the maturity date based on the paid_out_date if present, otherwise, return None.
        """
        # If the loan has not been paid out, return None
        if not self.paid_out_date:
            return None

        # Sum the total extension term
        extensions_term_sum = self.extensions.aggregate(total_extension_term=Sum('extension_term_months'))[
                                  'total_extension_term'] or 0

        # Calculate maturity date based on paid_out_date
        return self.paid_out_date + relativedelta(months=self.term_agreed + extensions_term_sum)

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

    @property
    def committee_approvements_status(self):
        """
            Generates a summary of the committee approval status, detailing approvals, rejections, and pending responses.

            This property method:
            1. Checks if there are any recorded approvals or rejections by committee members for a particular item.
            2. Collects emails of committee members who have approved, rejected (including rejection reasons), or have not yet responded.
            3. Builds a formatted HTML string that outlines the approval status, listing members who approved, members who rejected (with reasons), and members with no response.

            Returns:
            - str: An HTML-formatted status message with sections for approved, rejected, and pending members.

            Example:
            - Output:
              ```
              <h5>Committee Approval Status:</h5>
              <strong>Approved by:</strong> member1@example.com, member2@example.com<hr />
              <strong>Rejected by:</strong> member3@example.com <strong>Reason:</strong> Reason for rejection<hr />
              <strong>No response from:</strong> member4@example.com, member5@example.com<hr />
              ```

            Notes:
            - If there are no recorded interactions, returns "No interactions recorded".
            - Committee members are identified as users in the "committee_members" team.
            """
        # Check if there are any recorded approvals or rejections
        approvals = self.committee_approvals.filter(approved=True)
        rejections = self.committee_approvals.filter(approved=False)
        total_interactions = approvals.count() + rejections.count()

        if total_interactions == 0:
            return "No interactions recorded"

        # Get lists of emails for each status
        approved_emails = [approval.member.email for approval in approvals]
        rejected_emails = [rejection.member.email for rejection in rejections]  # Emails only for pending check
        rejected_emails_with_reasons = [
            f"{rejection.member.email} \n<strong >Reason:</strong> {rejection.rejection_reason or 'No reason provided'}"
            for rejection in rejections
        ]
        all_committee_members = User.objects.filter(teams__name="committee_members")

        # Exclude members who have already responded
        pending_emails = [
            member.email for member in all_committee_members
            if member.email not in approved_emails and member.email not in rejected_emails
        ]

        # Build the status message
        status_message = "<h5>Committee Approval Status:</h5>\n"
        if approved_emails:
            status_message += f"<strong>Approved by:\n</strong> {', '.join(approved_emails)}<hr />"
        if rejected_emails_with_reasons:
            status_message += f"<strong>Rejected by:\n</strong> {', '.join(rejected_emails_with_reasons)}<hr />"
        if pending_emails:
            status_message += f"<strong>No response from:\n</strong> {', '.join(pending_emails)}<hr />"

        return status_message

    def first_applicant(self):
        applicant = self.application.applicants.first()
        return str(applicant) if applicant else 'No applicants'

    def notify_committee_members(self, message, subject):

        from communications.utils import send_email_f  # importing it here because of the circular import
        committee_members = User.objects.filter(teams__name='committee_members')

        notification_message = ""
        for member in committee_members:
            # Render the HTML email template
            email_content = render_to_string("emails/committee_notification.html", {
                "member": member.name.strip() if member.name and member.name.strip() else member.email,
                "application": self.application,
                "subject": subject,
                "message": message,

            })

            res = send_email_f(
                sender=settings.DEFAULT_FROM_EMAIL,
                recipient=member.email,
                subject=f'Committee Approval notification',
                message=email_content,
                application=self.application,
                solicitor_firm=self.application.user,
                save_in_email_log=False
            )
            notification_message += f'Advancement committee approval {res}. Send to {member.email}\n'
        try:
            # print("Creating notification object...")
            notification = Notification.objects.create(
                recipient=None,
                text=notification_message,
                seen=False,
                created_by=None,
                application=self.application,
            )
            return True  # Return True if all emails are sent successfully
        except Exception as e:
            print(f"Error creating notification: {e}")
            return False  # Return False if any error occurs


class CommitteeApproval(models.Model):
    loan = models.ForeignKey(
        Loan,
        on_delete=models.SET_NULL,
        related_name="committee_approvals",
        null=True,
        blank=True
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="committee_approvals",
        null=True,
        blank=True
    )
    member = models.ForeignKey(User, on_delete=models.CASCADE)
    approved = models.BooleanField(default=False)
    rejection_reason = models.TextField(null=True, blank=True)  # Required when rejected
    decision_date = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('loan', 'member')

    def clean(self):
        # Ensure rejection_reason is provided when approved is False
        if not self.approved and not self.rejection_reason:
            raise ValidationError("Rejection reason is required when rejecting a loan.")

    def save(self, *args, **kwargs):
        # Automatically set application from the loan's application
        if self.loan and not self.application:
            self.application = self.loan.application
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.loan} - {self.member} - {'Approved' if self.approved else 'Rejected'}"


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
        recipient_email = self.recipient.email if self.recipient else 'No recipient'
        application = self.application.id if self.application else 'No application'
        return f"Recipient: {recipient_email}, Text: {self.text[:20]}..., Application ID: {application}"


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


class Assignment(models.Model):
    """Model to assign agencies to staff users."""
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_staff': True},
        related_name='assigned_agencies',

    )
    agency_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_staff': False},
        related_name='assigned_staff_user',

    )
    assigned_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        verbose_name = 'Assignment'
        verbose_name_plural = 'Assignments'

    def __str__(self):
        return f"{self.agency_user.name if self.agency_user else 'Unassigned'} assigned to {self.staff_user.name}"


class BaseEmailLog(models.Model):
    sender = models.EmailField()
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_sent = models.BooleanField(default=False)
    attachments = models.JSONField(null=True, blank=True)  # Store file paths as a JSON object
    original_filenames = models.JSONField(null=True, blank=True)  # Store original file names
    message_id = models.CharField(max_length=255, null=True, blank=True)
    application = models.ForeignKey('Application', on_delete=models.CASCADE, null=True, blank=True)
    solicitor_firm = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    seen = models.BooleanField(default=False)
    send_from = models.EmailField(null=True, blank=True)

    class Meta:
        abstract = True  # This makes the model abstract so it won't create a database table

    def __str__(self):
        return f"Email from {self.sender} to {self.recipient} - {self.subject}"


# Extend BaseEmailLog for default info@ emails
class EmailLog(BaseEmailLog):
    # You can add any specific fields or methods if needed, but it's empty here
    pass


# Extend BaseEmailLog for user-specific emails
class UserEmailLog(BaseEmailLog):
    # Similarly, you can add specific fields or methods here if needed
    pass


class FrontendAPIKey(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="frontend_api_key")
    key = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe(32))
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        """Set expiration time dynamically on save (15 minutes from now)."""
        self.expires_at = now() + timedelta(minutes=15)
        super().save(*args, **kwargs)

    def is_expired(self):
        """Check if the key is expired."""
        return now() > self.expires_at

    def refresh_expiration(self):
        """Extend the expiration time to 15 minutes from now."""
        self.expires_at = now() + timedelta(minutes=15)
        self.save(update_fields=["expires_at"])  # Save only the expires_at field

    @staticmethod
    def cleanup_expired_keys():
        """Delete expired API keys periodically (can be run as a cron job)."""
        FrontendAPIKey.objects.filter(expires_at__lt=now()).delete()
        FrontendAPIKey.objects.filter(expires_at__lt=now()).delete()


auditlog.register(User)
auditlog.register(Application)
auditlog.register(Document)
auditlog.register(Loan)
auditlog.register(SignedDocumentLog)
auditlog.register(EmailLog)
auditlog.register(CommitteeApproval)
# auditlog.register(FrontendAPIKey)
