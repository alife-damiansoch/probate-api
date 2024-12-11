import os
import re
import uuid
from django.core.exceptions import ValidationError


def get_application_document_file_path(instance, filename):
    """
      Generates a unique file path for saving an application document.

      This function creates a unique filename by appending a UUID to the original file’s extension and places it
      within the `uploads/application/` directory. This ensures each document has a unique file path, avoiding
      naming conflicts and maintaining organized file storage.

      Parameters:
      - instance: The model instance associated with the document being saved.
      - filename (str): The original filename of the document, including its extension.

      Returns:
      - str: A string representing the file path where the document will be saved.

      Example:
      - Input: filename="document.pdf"
      - Output: "uploads/application/<unique_uuid>.pdf"
      """
    ext = os.path.splitext(filename)[1]
    filename = f"{uuid.uuid4()}{ext}"

    return os.path.join('uploads', 'application', filename)


def validate_eircode(value):
    """
     Validates an Irish Eircode format by checking its routing key and unique identifier.

     This function ensures that the given Eircode meets the standard Irish format, which includes:
     1. A routing key (first 3 characters) matching the pattern `[ACDEFHKNPRTVWXY][0-9][0-9W]`.
     2. A unique identifier (last 4 characters) that consists of alphanumeric characters.

     Parameters:
     - value (str): The Eircode to validate. This value is automatically converted to uppercase for standardization.

     Raises:
     - ValidationError: If the Eircode does not match the required format for either the routing key or unique identifier.

     Example:
     - Input: "D02X285"
     - Valid Eircode passes without error; invalid format raises a ValidationError.

     Notes:
     - The function splits the Eircode into a routing key and a unique identifier, using regular expressions to validate each part.
     - If the routing key or unique identifier is invalid, an error message indicating the issue is raised.
     """
    value = value.strip().upper()  # Trim whitespace and convert to uppercase

    # Check length
    if len(value) != 7:
        raise ValidationError(
            f'{value} must be exactly 7 characters long.',
            params={'value': value},
        )

    # Regular expression for the routing key
    rk_regex = r'^[ACDEFHKNPRTVWXY][0-9][0-9W]$'
    # Regular expression for unique identifier
    ui_regex = r'^[A-Z0-9]{4}$'

    routing_key = value[:3]
    unique_identifier = value[3:]

    if not re.match(rk_regex, routing_key):
        raise ValidationError(
            f'{value} is not a valid Eircode. Invalid routing key: {routing_key}.',
            params={'value': value},
        )

    if not re.match(ui_regex, unique_identifier):
        raise ValidationError(
            f'{value} is not a valid Eircode. Invalid unique identifier: {unique_identifier}.',
            params={'value': value},
        )

# def validate_irish_phone_number(value):
#     """
#        Validates an Irish phone number format.
#
#        This function checks if the given phone number matches the standard Irish phone number format, which allows:
#        1. A leading `+353` country code or a leading `0` for domestic numbers.
#        2. Irish phone numbers beginning with area codes `1`, `2`, `4`, `6`, `7`, or `9`.
#        3. Between 7 and 9 additional digits following the area code.
#
#        Parameters:
#        - value (str): The phone number to validate, provided as a string.
#
#        Raises:
#        - ValidationError: If the phone number does not match the required Irish format.
#
#        Example:
#        - Valid inputs: "+353123456789", "012345678"
#        - Invalid input: Raises a ValidationError with a message prompting correct format.
#
#        Notes:
#        - Irish phone numbers should be in the format `+353999999999` or `0999999999`.
#        """
#     pattern = r'^(?:\+353|0)[124679]?\d{7,9}$'
#     if not re.match(pattern, value):
#         raise ValidationError(
#             f"{value} is not a valid Irish phone number. Please enter phone number in the format: '+353999999999' or '0999999999'",
#         )
