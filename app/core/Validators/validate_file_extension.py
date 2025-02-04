import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def is_valid_file_extension(filename):
    """
    Check if the uploaded file has a valid extension.
    """
    ext = os.path.splitext(filename)[1].lower()

    # Ensure ALLOWED_FILE_EXTENSIONS is correctly loaded
    allowed_extensions = getattr(settings, "ALLOWED_FILE_EXTENSIONS", [])

    if ext not in allowed_extensions:
        logger.warning(f"Blocked file upload: {filename} (Invalid extension: {ext})")
        return False
    return True
