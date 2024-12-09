import pyotp
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.exceptions import APIException

from core.models import OTP, AuthenticatorSecret


def validate_user_password(password, user=None):
    """
    Validate a password using all Django validators defined in AUTH_PASSWORD_VALIDATORS.

    Args:
        password (str): The password to validate.
        user (User, optional): The user instance (required for some validators like similarity).

    Raises:
        ValidationError: If the password fails validation.
    """
    try:
        # Validate the password against all validators
        validate_password(password, user=user)
    except ValidationError as e:
        # Raise all validation error messages as a single error
        raise ValidationError({"password": e.messages})


def validate_otp(email, otp):
    """
    Validate the OTP for the given email and remove it if successfully validated.
    """
    try:
        otp_record = OTP.objects.get(email=email)
        if otp_record.code == otp:
            # Optional: Check if OTP is still valid
            if not otp_record.is_valid():
                raise APIException("Verification code has expired.")

            # OTP is valid, remove the record
            otp_record.delete()
            return True
        else:
            return False
    except OTP.DoesNotExist:
        raise APIException("No verification code found for the provided email.")


def validate_authenticator_code(user, code):
    """
    Validate the code from the Authenticator app.
    """
    try:
        # Fetch the authenticator secret for the user
        authenticator = AuthenticatorSecret.objects.get(user=user)
        totp = pyotp.TOTP(authenticator.secret)
        return totp.verify(code)  # Verify the code with the secret
    except AuthenticatorSecret.DoesNotExist:
        raise APIException("Authenticator is not set up for this user.")
