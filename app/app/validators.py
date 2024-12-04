from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import (
    UserAttributeSimilarityValidator,
    MinimumLengthValidator,
    CommonPasswordValidator,
    NumericPasswordValidator,
)


class MixedCharacterValidator:
    """
    Validate that a password:
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character
    - Passes all default Django password validations
    """

    def validate(self, password, user=None):
        errors = []

        # Default Django validators
        default_validators = [
            UserAttributeSimilarityValidator(user_attributes=['email', 'name']),
            MinimumLengthValidator(min_length=8),
            CommonPasswordValidator(),
            NumericPasswordValidator(),
        ]

        # Validate using default validators
        for validator in default_validators:
            try:
                validator.validate(password, user)
            except ValidationError as e:
                errors.extend(e.messages)

        # Custom mixed character validations
        if not any(char.islower() for char in password):
            errors.append(
                "The password must contain at least one lowercase letter."
            )
        if not any(char.isupper() for char in password):
            errors.append(
                "The password must contain at least one uppercase letter."
            )
        if not any(char.isdigit() for char in password):
            errors.append(
                "The password must contain at least one digit."
            )
        if not any(char in "!@#$%^&*()-_+=~`[]{}|;:'\",.<>?/\\|€£¥" for char in password):
            errors.append(
                "The password must contain at least one special character."
            )

        if errors:
            # Raise all collected errors in one go
            raise ValidationError(errors)

    def get_help_text(self):
        return (
            "Your password must meet the following criteria:\n"
            "- At least one lowercase letter\n"
            "- At least one uppercase letter\n"
            "- At least one digit\n"
            "- At least one special character\n"
            "- Not too similar to your email or name\n"
            "- At least 8 characters long\n"
            "- Not a common password\n"
            "- Not entirely numeric"
        )
