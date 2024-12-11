import re
from rest_framework.exceptions import ValidationError as DRFValidationError


class ApplicantsValidator:
    """Class-based validator for applicants."""

    # Country-specific validation regex patterns and error messages
    validation_rules = {
        'IE': {
            'regex': re.compile(r'^\d{7}[A-Z]{1,2}$'),
            'error_message': 'PPS Number must be 7 digits followed by 1 or 2 letters.'
        },
        'UK': {
            'regex': re.compile(
                r'^(?!BG|GB|KN|NK|NT|TN|ZZ)'  # Exclude specific invalid prefixes
                r'(?![DFIQUV])'  # Exclude invalid first letters
                r'[A-CEGHJ-NOPRT-Z]'  # Valid first letter
                r'(?![DFIOQUV])'  # Exclude invalid second letters
                r'[A-CEGHJ-NOPRT-Z]'  # Valid second letter
                r'\d{6}'  # Six digits
                r'[A-D]$'  # Suffix letter A, B, C, or D
            ),
            'error_message': 'NI Number must start with two valid letters, '
                             'followed by six digits, and end with A, B, C, or D.'
        }
        # Add more countries here as needed
    }

    @staticmethod
    def validate(applicants_data, user):
        """Validate the identification numbers of applicants."""
        for applicant in applicants_data:
            # Fetch the application and user to determine the country
            # print(applicant)

            if not user.country:
                raise DRFValidationError({
                    'country': 'Could not determine the country for validation.'
                })

            user_country = user.country
            if user_country not in ApplicantsValidator.validation_rules:
                raise DRFValidationError({
                    'country': f'Validation rules for country {user_country} are not defined.'
                })

            # Fetch country-specific validation rules
            rules = ApplicantsValidator.validation_rules[user_country]

            # Use the decrypted PPS property for validation
            identifier = (
                applicant.get('pps_number')

            )
            if not identifier:
                raise DRFValidationError({
                    'identifier': f'{user_country} identifier is required.'
                })

            identifier = identifier.upper()
            if not rules['regex'].match(identifier):
                raise DRFValidationError({
                    'identifier': rules['error_message']
                })
