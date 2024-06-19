from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin
)

from auditlog.registry import auditlog


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


# endregion

auditlog.register(User)
