from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)

from auditlog.registry import auditlog
from django.db.models import ForeignKey
from django.conf import settings

import uuid
import os


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


class Document(models.Model):
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='documents')
    document = models.FileField(upload_to=get_application_document_file_path)
    original_name = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        if self.document:
            self.original_name = self.document.name
        super().save(*args, **kwargs)

    # this overwrites makes sure that file is deleted when instance is deleted from the database
    def delete(self, *args, **kwargs):
        self.document.delete()
        super().delete(*args, **kwargs)


auditlog.register(User)
auditlog.register(Application)
