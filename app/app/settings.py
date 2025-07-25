"""
Django settings for app project.

Generated by 'django-admin startproject' using Django 3.2.25.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""
import sys

from dotenv import load_dotenv
import os
from datetime import timedelta
from pathlib import Path
import dj_database_url

from corsheaders.defaults import default_headers

TESTING = 'test' in sys.argv

# Load environment variables from the .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'changeme')
COMPANY_NAME = os.getenv('COMPANY_NAME', 'Default Company Name')
COMPANY_ADDRESS = os.getenv('COMPANY_ADDRESS', 'Default Company Address')
# Get ADMIN_EMAILS as a list
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "").split(",")
# Remove empty strings if the env variable is not set
ADMIN_EMAILS = [email.strip() for email in ADMIN_EMAILS if email.strip()]

# for PEP check
DILISENSE_API_KEY = os.getenv('DILISENSE_API_KEY', '')

# CCR Configuration
CCR_PROVIDER_CODE = os.getenv('CCR_PROVIDER_CODE', 'TEST001')  # Your temporary code
CCR_TEST_MODE = os.getenv('CCR_TEST_MODE', 'True').lower() == 'true'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(int(os.getenv('DEBUG', 0)))
# Enable these only in production
ENV = os.getenv('DJANGO_ENV', 'development')
IS_PRODUCTION = ENV == 'production'

SOLICITORS_WEBSITE = os.getenv('SOLICITORS_WEBSITE', '')

# custom url to access admin
ADMIN_URL = os.getenv('ADMIN_URL', '/')
ALLOWED_ADMIN_IPS = os.getenv('ALLOWED_ADMIN_IPS', '')

if IS_PRODUCTION:
    SECURE_SSL_REDIRECT = True  # Force HTTPS
    SESSION_COOKIE_SECURE = True  # Secure cookies over HTTPS
    CSRF_COOKIE_SECURE = True  # Secure CSRF cookies
    SECURE_HSTS_SECONDS = 31536000  # Enforce HTTPS for 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'DENY'  # Prevent iframe clickjacking
    SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME sniffing
    SECURE_BROWSER_XSS_FILTER = True  # Enable XSS filtering
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"  # Secure referrer policy
else:
    SECURE_SSL_REDIRECT = False  # Allow HTTP in development
    SESSION_COOKIE_SECURE = False  # Allow insecure cookies in dev
    CSRF_COOKIE_SECURE = False  # Allow CSRF cookies over HTTP
    SECURE_HSTS_SECONDS = 0  # No HSTS enforcement in dev
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Get Azure's auto-generated hostname (if running in Azure)
website_hostname = os.getenv('WEBSITE_HOSTNAME')

# Load allowed hosts from .env
ALLOWED_HOSTS = list(filter(None, os.getenv('ALLOWED_HOSTS', '').split(',')))

# If running in Azure, add `website_hostname` to ALLOWED_HOSTS
if website_hostname:
    ALLOWED_HOSTS.append(website_hostname)

# Load CSRF trusted origins from .env
CSRF_TRUSTED_ORIGINS = list(filter(None, os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')))

# Prepare the ALLOWED_FILE_EXTENSIONS variable so the files can be validated when uploaded
# Get allowed file extensions from the .env file and convert it into a list
ALLOWED_FILE_EXTENSIONS = os.getenv("ALLOWED_FILE_EXTENSIONS", "").split(",")

# Ensure all extensions start with a dot (e.g., ".pdf" instead of "pdf")
ALLOWED_FILE_EXTENSIONS = [ext.strip().lower() if ext.startswith('.') else f".{ext.strip().lower()}"
                           for ext in ALLOWED_FILE_EXTENSIONS]

# If running in Azure, add `website_hostname` to CSRF_TRUSTED_ORIGINS
if website_hostname:
    CSRF_TRUSTED_ORIGINS.append(f"https://{website_hostname}")

# CORS Configuration
if DEBUG:
    CORS_ORIGIN_ALLOW_ALL = True
    CORS_ALLOWED_ORIGINS = []
else:
    ADDITIONAL_CORS_ORIGINS = list(filter(None, os.getenv('ADDITIONAL_CORS_ORIGINS', '').split(',')))
    CORS_ALLOWED_ORIGINS = ADDITIONAL_CORS_ORIGINS.copy()

    # If running in Azure, add `website_hostname` to CORS_ALLOWED_ORIGINS
    if website_hostname:
        CORS_ALLOWED_ORIGINS.append(f"https://{website_hostname}")

    CORS_ORIGIN_ALLOW_ALL = False

# LOAN
ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL = float(os.getenv("ADVANCEMENT_THRESHOLD_FOR_COMMITTEE_APPROVAL", 1000000))
COMMITTEE_MEMBERS_COUNT_REQUIRED_FOR_APPROVAL = int(os.getenv("COMMITTEE_MEMBERS_COUNT_REQUIRED_FOR_APPROVAL", 1))
if TESTING:
    COMMITTEE_MEMBERS_COUNT_REQUIRED_FOR_APPROVAL = 1

# Encryption key for PPS number
PPS_ENCRYPTION_KEY = os.getenv("PPS_ENCRYPTION_KEY")
if not PPS_ENCRYPTION_KEY:
    raise ValueError("PPS_ENCRYPTION_KEY must be set in the environment.")

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    # 'rest_framework.authtoken',
    'drf_spectacular',
    'rangefilter',
    'auditlog',
    'storages',
    'channels',
    'core',
    'user',
    'solicitors_loan',
    'agents_loan',
    'event',
    'comment',
    'expense',
    'loan',
    'notifications',
    'assigned_solicitor',
    'undertaking',
    'downloadableFiles',
    'signed_documents',
    'agents_default_assignments',
    'communications',
    "estates",
    'document_requirements',
    'internal_files',
    'finance_checklist',
    "loanbook",
    'document_emails',
    'ccr_reporting'
]

MIDDLEWARE = [
    'core.middleware.CSPReportOnlyMiddleware',
    'django.middleware.security.SecurityMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
    'django.contrib.sessions.middleware.SessionMiddleware',
    # 'core.middleware.CorsMiddleware',  # Add this
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',

    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.ValidateAPIKeyMiddleware',
    'core.middleware.CountryMiddleware',
    'core.middleware.LogEventOnErrorMiddleware',
    'core.middleware.LogHeadersMiddleware',
    'core.middleware.AdminIPRestrictionMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

# Retrieve the connection string from Azure environment variables
CONNECTION = os.getenv('AZURE_POSTGRESQL_CONNECTIONSTRING', '')
# Retrieve the connection string from Render environment variables
DATABASE_URL = os.getenv('DATABASE_URL', '')

if DATABASE_URL:
    print("🟢 Using Render DATABASE_URL for PostgreSQL connection:")
    print(f"DATABASE_URL = {DATABASE_URL}")
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
    }
elif os.getenv('AZURE_POSTGRESQL_CONNECTIONSTRING', ''):
    CONNECTION = os.getenv('AZURE_POSTGRESQL_CONNECTIONSTRING', '')
    print("🔵 Using AZURE_POSTGRESQL_CONNECTIONSTRING for PostgreSQL connection:")
    print(f"AZURE_POSTGRESQL_CONNECTIONSTRING = {CONNECTION}")
    CONNECTION_STR = {pair.split('=')[0]: pair.split('=')[1] for pair in CONNECTION.split(' ')}
    print(f"Parsed Azure connection: {CONNECTION_STR}")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": CONNECTION_STR.get("dbname"),
            "HOST": CONNECTION_STR.get("host"),
            "USER": CONNECTION_STR.get("user"),
            "PASSWORD": CONNECTION_STR.get("password"),
            "PORT": CONNECTION_STR.get("port", "5432"),
            "OPTIONS": {
                "sslmode": CONNECTION_STR.get("sslmode", "require"),
            },
        }
    }
else:
    print("🟡 WARNING: DATABASE_URL and AZURE_POSTGRESQL_CONNECTIONSTRING are not set!")
    print("Fallback to manual local DB settings:")
    print(
        f"DB_HOST={os.environ.get('DB_HOST', 'localhost')}, DB_NAME={os.environ.get('DB_NAME', 'your_local_db')}, DB_USER={os.environ.get('DB_USER', 'postgres')}")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'NAME': os.environ.get('DB_NAME', 'your_local_db'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASS', ''),
            'PORT': '5432',
        }
    }

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [

    {
        'NAME': 'app.validators.MixedCharacterValidator',  # Replace with the actual path
    },
]

# Password Reset Token Expiry
PASSWORD_RESET_TIMEOUT = 3600  # 1 hour (time in seconds)

# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Dublin'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

if not DEBUG:  # in production

    # Azure settings
    AZURE_ACCOUNT_NAME = os.getenv('AZURE_ACCOUNT_NAME', 'your-default-account-name')
    AZURE_CUSTOM_DOMAIN = f'{AZURE_ACCOUNT_NAME}.blob.core.windows.net'
    AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING', 'your-default-connection-string')
    AZURE_CONTAINER = os.getenv('AZURE_CONTAINER', 'your-default-container-name')

    # Configure storage using Django 4.2+ STORAGES setting
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.azure_storage.AzureBlobStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

    MEDIA_URL = f"https://{AZURE_CUSTOM_DOMAIN}/{AZURE_CONTAINER}/"
    STATIC_URL = "/static/"  # Required for Django to generate correct URLs for static files
    STATIC_ROOT = BASE_DIR / "staticfiles"  # WhiteNoise serves files from here

    # Ensure `staticfiles/` directory exists before starting the server
    os.makedirs(STATIC_ROOT, exist_ok=True)  # ✅ Automatically create it if missing

    # Set ATTACHMENTS_DIR to point to Azure Blob Storage container path
    ATTACHMENTS_DIR = f"https://{AZURE_CUSTOM_DOMAIN}/{AZURE_CONTAINER}/attachments/"
    DOC_DOWNLOAD_DIR = f"{MEDIA_URL}DocDownload/"

    # Outgoing Email Settings (SMTP)
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST')
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 26))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False").lower() in ["true", "1", "yes"]
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ["true", "1", "yes"]
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')

    # Incoming Email Settings (IMAP)
    IMAP_SERVER = os.getenv('IMAP_SERVER')
    IMAP_PORT = int(os.getenv('IMAP_PORT', 993))  # Convert to int
    IMAP_USER = os.getenv('IMAP_USER')
    IMAP_PASSWORD = os.getenv('IMAP_PASSWORD')
    IMAP_USE_TLS = os.getenv("IMAP_USE_TLS", "False").lower() in ["true", "1", "yes"]
    IMAP_USE_SSL = os.getenv("IMAP_USE_SSL", "True").lower() in ["true", "1", "yes"]  # Defaulting to True for IMAP SSL

else:  # in development
    MEDIA_URL = '/media/'
    STATIC_URL = '/static/'
    STATICFILES_DIRS = [BASE_DIR / "static"]
    STATIC_ROOT = BASE_DIR / "staticfiles"
    MEDIA_ROOT = BASE_DIR / "media"
    DOC_DOWNLOAD_DIR = os.path.join(MEDIA_ROOT, 'DocDownload')
    # Set default attachment directory to a subfolder within media
    ATTACHMENTS_DIR = os.path.join(MEDIA_ROOT, 'email_attachments')
    # Your Non-SSL settings
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False").lower() in ["true", "1", "yes"]
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ["true", "1", "yes"]
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 26))
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')

    # Incoming Email Settings (IMAP)
    IMAP_SERVER = os.getenv('IMAP_SERVER')
    IMAP_PORT = int(os.getenv('IMAP_PORT', 993))  # Convert to int
    IMAP_USER = os.getenv('IMAP_USER')
    IMAP_PASSWORD = os.getenv('IMAP_PASSWORD')
    IMAP_USE_TLS = os.getenv("IMAP_USE_TLS", "False").lower() in ["true", "1", "yes"]
    IMAP_USE_SSL = os.getenv("IMAP_USE_SSL", "True").lower() in ["true", "1", "yes"]  # Defaulting to True for IMAP SSL

# Ensure the local attachments directory exists if in development
if DEBUG:
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'core.User'

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": 'drf_spectacular.openapi.AutoSchema',

    "DEFAULT_AUTHENTICATION_CLASSES": (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),

    "DEFAULT_THROTTLE_CLASSES": [
        "core.throttling.CombinedThrottle",  # Your merged short + long throttle
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],

    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/minute" if TESTING else "200/minute",
        "user": "100000/hour" if TESTING else "10000/hour",  # Allows high activity without blocking real users
        "login": "10000/minute" if TESTING else "10/minute",  # Prevent brute-force attacks
        "password_reset": "10000/minute" if TESTING else "10/minute",
        "activation": "10000/minute" if TESTING else "10/minute",
        "otp_verification": "10000/minute" if TESTING else "15/minute",  # OTP needs a bit more
        "authenticator_verification": "10000/minute" if TESTING else "15/minute",
        "registration": "10000/minute" if TESTING else "100/minute",  # Increased to handle form validation retries
        "password_change": "10000/minute" if TESTING else "10/minute",
        "sustained": "10000/day" if TESTING else "500/day",  # Increased but still blocks abusers
    }
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=10),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    "COMPONENT_SPLIT_REQUEST": True,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayRequestDuration': True,
        'docExpansion': 'list'
    },

}

ASGI_APPLICATION = 'app.routing.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    },
}

# Specify the headers that are allowed, including the custom 'Country' header


CORS_ALLOW_CREDENTIALS = True  # Allow sending cookies & authentication headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    'Country', 'Frontend-Host', "x-frontend-api-key", "x-frontend-api-key-agents", "x-api-key-expiration",
    "x-api-key-expiration-agents"
]
CORS_EXPOSE_HEADERS = [
    "x-api-key-expiration",
    "x-api-key-expiration-agents",
    # CCR headers
    'Content-Disposition',
    'X-CCR-Record-Count',
    'X-CCR-Reference-Date',
    'X-CCR-Test-Mode',
    'X-CCR-Summary',
    'X-CCR-Filename'
]

# Enable JSON serialization for audit logs (fills the "Serialized data" field)
AUDITLOG_INCLUDE_ALL_MODELS = False  # We're registering models manually
AUDITLOG_SERIALIZATION = 'json'  # This enables the serialized_data field

# Optional: Configure what gets logged
AUDITLOG_USE_TEXT_CHANGES_IF_JSON_IS_NOT_PRESENT = True  # Fallback for serialization
AUDITLOG_ACTOR_FIELD = 'email'
