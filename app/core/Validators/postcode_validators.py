import re
from rest_framework.exceptions import ValidationError as DRFValidationError


class PostcodeValidator:
    """Class-based postcode validator for multiple countries."""

    validation_rules = {
        'IE': {
            'pattern': r'^[ACDEFHKNPRTVWXY][0-9][0-9W][A-Z0-9]{4}$',
            'error_message': "Eircode must be in the format 'D02X285'. Routing key: 3 characters, followed by 4 alphanumeric characters.",
        },
        'UK': {
            # Using Postcode.js approach for format validation
            'pattern': r'^[a-z]{1,2}\d[a-z\d]?\s*\d[a-z]{2}$',
            'error_message': "Postcode must be in a valid UK format, e.g., 'SW1A 1AA' or 'EC1A 1BB'.",
        }
    }

    @staticmethod
    def validate(postcode, country_code):
        """
        Validate the postcode based on the country code.

        Parameters:
        - postcode (str): The postcode to validate.
        - country_code (str): The 2-letter ISO country code (e.g., 'IE', 'UK').

        Raises:
        - ValidationError: If the postcode does not match the required format for the country.
        """
        if country_code not in PostcodeValidator.validation_rules:
            raise DRFValidationError(
                f"Postcode validation rules for country '{country_code}' are not defined."
            )

        # Fetch the validation rule for the country
        rules = PostcodeValidator.validation_rules[country_code]
        pattern = rules['pattern']
        error_message = rules['error_message']

        # Perform validation
        if not re.match(pattern, postcode.strip(), re.IGNORECASE):  # Ignore case
            raise DRFValidationError(error_message)
