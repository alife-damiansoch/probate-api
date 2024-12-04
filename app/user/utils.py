from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


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
