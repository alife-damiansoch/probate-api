from rest_framework.throttling import ScopedRateThrottle
from django.core.cache import cache
from django.utils.timezone import now
from rest_framework.exceptions import Throttled, APIException
from app.settings import ADMIN_EMAILS
from communications.utils import send_email_f
import logging
import math

logger = logging.getLogger(__name__)


class TooManyRequestsException(APIException):
    """
    Custom Exception to return 429 Too Many Requests.
    """
    status_code = 429
    default_detail = "Too many requests. Please try again later."
    default_code = "too_many_requests"


class CombinedThrottle(ScopedRateThrottle):
    """
    A combined short-term and sustained throttling mechanism.
    - Short-term: Limits burst requests.
    - Sustained: Blocks repeated offenders for a long period (e.g., 24 hours).
    """

    sustained_scope = "sustained"
    sustained_block_time = 60 * 60 * 24  # Block for 24 hours
    sustained_limit = 50  # Number of violations before permanent block

    def allow_request(self, request, view):
        """
        Check both short-term and sustained limits.
        """
        self.request = request
        ip_address = self.get_ident(request)
        user = getattr(request, "user", None)
        user_email = getattr(user, "email", "Unauthenticated User")

        # Cache key for sustained violations
        sustained_cache_key = f"throttle_sustained_{ip_address}"

        # Check if the IP is already blocked for 24 hours
        if cache.get(sustained_cache_key) is True:
            logger.error(f"🚨 [SustainedThrottle] Permanent block: {ip_address} exceeded sustained limit!")

            remaining_time = self.get_remaining_time(sustained_cache_key)
            raise TooManyRequestsException(
                detail=f"Your IP has been temporarily blocked due to excessive failed requests. "
                       f"Try again in {remaining_time}."
            )

        # Check short-term burst throttle
        burst_throttled = not super().allow_request(request, view)
        wait_time = self.get_remaining_time(self.get_cache_key(request, view))

        # If short-term throttle is exceeded
        if burst_throttled:
            # Track sustained violations
            sustained_attempts = cache.get(sustained_cache_key, 0) + 1
            cache.set(sustained_cache_key, sustained_attempts, timeout=self.sustained_block_time)

            logger.warning(
                f"⚠️ [SustainedThrottle] {ip_address} failed {sustained_attempts}/{self.sustained_limit} sustained attempts.")

            # If sustained attempts reach the limit, permanently block
            if sustained_attempts >= self.sustained_limit:
                cache.set(sustained_cache_key, True, timeout=self.sustained_block_time)
                logger.error(
                    f"🚨 [SustainedThrottle] {ip_address} permanently blocked for {self.sustained_block_time // 3600} hours.")

                # Send email alert 🚨
                subject = "🚨 API Permanent Block Alert: Repeated Violations Detected"
                message = f"""
                <h2>⚠️ Sustained Throttle Alert ⚠️</h2>
                <p><strong>Permanent block triggered</strong> for <b>{user_email}</b></p>
                <p>🌐 <strong>IP Address:</strong> {ip_address}</p>
                <p>⏳ <strong>Blocked Until:</strong> {now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <hr>
                <p>This is an automated security alert.</p>
                """

                # Notify admins
                for admin_email in ADMIN_EMAILS:
                    send_email_f(
                        sender="noreply@alife.ie",
                        recipient=admin_email,
                        subject=subject,
                        message=message,
                        save_in_email_log=False,
                    )

                raise TooManyRequestsException(
                    detail=f"Your IP has been temporarily blocked due to excessive failed requests. "
                           f"Try again in {self.sustained_block_time // 3600} hours."
                )

                # If short-term throttle is exceeded, return the remaining wait time
            raise TooManyRequestsException(
                detail=f"Too many requests. Please wait {wait_time} before trying again."
            )

        return True  # Allow request if below threshold

    def get_remaining_time(self, cache_key):
        """
        Calculate the remaining wait time for a blocked request.
        """
        cached_data = cache.get(cache_key)
        # print(cached_data)
        if not cached_data or not isinstance(cached_data, dict) or "expires_at" not in cached_data:
            return "a while"  # Fallback if cache is missing or invalid

        expiry_time = cached_data["expires_at"]
        remaining_time = (expiry_time - now()).total_seconds()

        if remaining_time >= 3600:
            return f"{math.ceil(remaining_time / 3600)} hours"
        if remaining_time >= 60:
            return f"{math.ceil(remaining_time / 60)} minutes"
        return f"{int(remaining_time)} seconds"
