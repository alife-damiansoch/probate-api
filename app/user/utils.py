import pyotp
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.exceptions import APIException, AuthenticationFailed

from core.models import OTP, AuthenticatorSecret

from django.contrib.auth import authenticate
from django.core.cache import cache
from communications.utils import send_email_f
from app.settings import ADMIN_EMAILS
from django.utils.timezone import now, timedelta
import logging

logger = logging.getLogger(__name__)


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


# Configuration
FAILED_LOGIN_LIMIT = 5  # Max failed attempts before blocking
BLOCK_TIME_MINUTES = 15  # Time (in minutes) for blocking users


def custom_authenticate(request, email=None, password=None):
    """
    Custom authentication function that tracks failed login attempts by IP and email,
    blocking users after repeated failures and sending an email alert to the admin list.
    """

    client_ip = get_client_ip(request)
    ip_cache_key = f"failed_login_attempts_{client_ip}"
    email_cache_key = f"failed_login_attempts_{email}"

    # Check if IP or email is already blocked
    if cache.get(f"blocked_ip_{client_ip}") or cache.get(f"blocked_email_{email}"):
        logger.warning(f"Blocked login attempt for {email} from {client_ip} (Too many failed attempts)")

        raise AuthenticationFailed({
            "error": "Your account has been temporarily locked due to multiple failed login attempts.",
            "message": f"Please try again after {BLOCK_TIME_MINUTES} minutes or contact support if you need assistance."
        })

    # Authenticate the user
    user = authenticate(request=request, username=email, password=password)

    if user is None:
        # Increase failed login count for IP and email
        ip_attempts = cache.get(ip_cache_key, 0) + 1
        email_attempts = cache.get(email_cache_key, 0) + 1

        cache.set(ip_cache_key, ip_attempts, timeout=BLOCK_TIME_MINUTES * 60)
        cache.set(email_cache_key, email_attempts, timeout=BLOCK_TIME_MINUTES * 60)

        logger.warning(f"Failed login attempt {ip_attempts}/{FAILED_LOGIN_LIMIT} from IP {client_ip} for email {email}")

        # Block IP or email if attempts exceed the limit
        if ip_attempts >= FAILED_LOGIN_LIMIT or email_attempts >= FAILED_LOGIN_LIMIT:
            cache.set(f"blocked_ip_{client_ip}", True, timeout=BLOCK_TIME_MINUTES * 60)
            cache.set(f"blocked_email_{email}", True, timeout=BLOCK_TIME_MINUTES * 60)

            unblock_time = now() + timedelta(minutes=BLOCK_TIME_MINUTES)
            logger.error(f"Blocked {email} (IP: {client_ip}) for {BLOCK_TIME_MINUTES} minutes due to failed logins")

            # Send email alert to all admins
            send_block_alert(email, client_ip, ip_attempts, email_attempts, unblock_time)

        raise AuthenticationFailed({
            "error": "Incorrect email or password. Please check your credentials.",
            "message": f"You have {FAILED_LOGIN_LIMIT - max(ip_attempts, email_attempts)} attempts remaining before your account is temporarily locked."
        })

    # Reset failed attempts for IP and email on successful login
    cache.delete(ip_cache_key)
    cache.delete(email_cache_key)
    return user  # Return authenticated user


def send_block_alert(email, ip, ip_attempts, email_attempts, unblock_time):
    """
    Sends an email alert when a user is blocked due to excessive failed login attempts.
    """

    subject = "⚠️ User Blocked Due to Multiple Failed Login Attempts"
    message = f"""
    <h2>🚨 Brute Force Protection Alert 🚨</h2>
    <p><strong>A user has been blocked due to too many failed login attempts.</strong></p>
    <p>🔒 <strong>Blocked Email:</strong> {email}</p>
    <p>🌐 <strong>Blocked IP:</strong> {ip}</p>
    <p>🔄 <strong>Failed Login Attempts (IP):</strong> {ip_attempts}</p>
    <p>🔄 <strong>Failed Login Attempts (Email):</strong> {email_attempts}</p>
    <p>⏳ <strong>Block Duration:</strong> {BLOCK_TIME_MINUTES} minutes</p>
    <p>🕒 <strong>Unblock Time:</strong> {unblock_time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <hr>
    <p>This is an automated alert from the authentication system.</p>
    """

    # Send the email to all admin recipients
    for admin_email in ADMIN_EMAILS:
        send_email_f(
            sender="noreply@alife.ie",
            recipient=admin_email,
            subject=subject,
            message=message,
            save_in_email_log=False  # No need to log this email in the email log
        )


def get_client_ip(request):
    """ Extracts the real IP address of the client, even if behind a proxy """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()  # Get first IP in list
    return request.META.get("REMOTE_ADDR", "")
