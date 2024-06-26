from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
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

from django.utils.functional import cached_property


# helper function to get file name for the documents uploaded
def get_application_document_file_path(instance, filename):
    """Generate a file path for an application document."""
    ext = os.path.splitext(filename)[1]
    filename = f"{uuid.uuid4()}{ext}"

    return os.path.join('uploads', 'application', filename)


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
    eircode = models.CharField(max_length=7)

    def __str__(self):
        return f'{self.line1}, {self.town_city}, {self.county}, {self.eircode}'


class User(AbstractBaseUser, PermissionsMixin):
    """User in the system"""
    email = models.EmailField(unique=True, max_length=255)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, default=None)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=255, default=None, null=True, blank=True, )
    address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True, default=None)

    objects = UserManager()

    USERNAME_FIELD = 'email'

    def __str__(self):
        return f"{self.name}  -  {self.email}"


# endregion
class Deceased(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class Dispute(models.Model):
    details = models.TextField()

    def __str__(self):
        return self.details


class Application(models.Model):
    """Application model"""
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    term = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(36)])
    user = ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                      related_name='solicitor_applications_set')
    approved = models.BooleanField(default=False)
    last_updated_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                 default=None,
                                 related_name='updated_applications_set')
    date_submitted = models.DateTimeField(auto_now_add=True)
    deceased = models.ForeignKey(
        Deceased, on_delete=models.PROTECT, null=True, blank=True, )  # Each application has one deceased
    dispute = models.OneToOneField(
        Dispute, on_delete=models.SET_NULL, null=True, blank=True, related_name='application')
    undertaking_ready = models.BooleanField(default=False)
    loan_agreement_ready = models.BooleanField(default=False)
    assigned_to = ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, default=None,
                             related_name='assigned_applications_set')

    def value_of_the_estate_after_expenses(self):
        estates_sum = self.estates.aggregate(total_estate_value=Sum('value'))['total_estate_value'] or 0
        expenses_sum = self.expenses.aggregate(total_expense_value=Sum('value'))['total_expense_value'] or 0
        return estates_sum - expenses_sum


class Comment(models.Model):
    text = models.TextField(default=None, null=True, blank=True)
    created_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                            related_name='comment_user_created')
    is_completed = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, blank=True, default=None)
    updated_by = ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                            related_name='comment_user_updated')


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
    pps_number = models.CharField(max_length=9)
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
    approved_date = models.DateField(default=timezone.now)
    is_settled = models.BooleanField(default=False)
    settled_date = models.DateField(default=None, null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='loans_approved_by')
    last_updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        default=None, related_name='loans_updated_by')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

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
        return self.amount_agreed - transactions_sum + extensions_fee_sum

    @property
    def amount_paid(self):
        return self.amount_agreed - self.current_balance


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


auditlog.register(User)
auditlog.register(Application)
auditlog.register(Document)
