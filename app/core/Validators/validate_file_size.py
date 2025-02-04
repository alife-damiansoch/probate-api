from django.conf import settings

# Default max size for unknown file types (20MB)
DEFAULT_MAX_SIZE = 20 * 1024 * 1024  # 20MB

# Define max file size limits per category
MAX_FILE_SIZES = {
    "image": 10 * 1024 * 1024,  # 10MB
    "document": 50 * 1024 * 1024,  # 50MB
    "sheet": 30 * 1024 * 1024,  # 30MB
}

# Get allowed extensions from .env
ALLOWED_FILE_EXTENSIONS = settings.ALLOWED_FILE_EXTENSIONS

# Define known categories based on common file extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".ppt", ".pptx", ".odp"}
SHEET_EXTENSIONS = {".xls", ".xlsx", ".ods", ".csv"}


def is_valid_file_size(file):
    """
    Checks if the file size is within allowed limits.
    Returns True if valid, False otherwise.
    """
    file_extension = f".{file.name.lower().split('.')[-1]}"

    # Ensure the file extension is allowed
    if file_extension not in ALLOWED_FILE_EXTENSIONS:
        return False  # File extension is not allowed

    # Dynamically determine max file size
    if file_extension in IMAGE_EXTENSIONS:
        max_size = MAX_FILE_SIZES["image"]
    elif file_extension in DOCUMENT_EXTENSIONS:
        max_size = MAX_FILE_SIZES["document"]
    elif file_extension in SHEET_EXTENSIONS:
        max_size = MAX_FILE_SIZES["sheet"]
    else:
        max_size = DEFAULT_MAX_SIZE  # Fallback for unknown file types

    return file.size <= max_size  # ✅ Return True if within size limit, False otherwise
