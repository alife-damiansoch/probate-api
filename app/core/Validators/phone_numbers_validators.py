import re
from rest_framework.exceptions import ValidationError


class PhoneNumberValidator:
    """Class-based phone number validator for multiple countries."""

    # Validation rules for different countries
    validation_rules = {
        'IE': {
            'pattern': r'^\+353\d{8,9}$',
            'error_message': "Phone number must start with '+353' followed by 7-9 digits."
        },
        'UK': {
            'pattern': r'^\+447\d{9}$',
            'error_message': "Phone number must start with '+44' followed by 10 digits."
        }
        # Add more countries here as needed
    }

    @staticmethod
    def validate(phone_number, country_code):
        """
        Validate the phone number based on the country code.

        Parameters:
        - phone_number (str): The phone number to validate.
        - country_code (str): The 2-letter ISO country code (e.g., 'IE', 'UK').

        Raises:
        - ValidationError: If the phone number does not match the required format for the country.
        """
      
        if country_code not in PhoneNumberValidator.validation_rules:
            raise ValidationError({
                "phone_number": f"Phone number validation rules for country '{country_code}' are not defined."
            })

        # Fetch the validation rule for the country
        rules = PhoneNumberValidator.validation_rules[country_code]
        pattern = rules['pattern']
        error_message = rules['error_message']

        # Perform validation
        if not re.match(pattern, phone_number):
            raise ValidationError({"phone_number": error_message})  # Structured error
