from rest_framework.throttling import ScopedRateThrottle
from django.core.cache import cache
from django.utils.timezone import now
from communications.utils import send_email_f  # Import your existing email function
from app.settings import ADMIN_EMAILS
import logging

logger = logging.getLogger(__name__)


class AlertScopedRateThrottle(ScopedRateThrottle):
    """
    Custom Scoped Rate Throttle that sends an email alert when a user exceeds the limit.
    """

    def allow_request(self, request, view):
        """
        Override `allow_request` to check the throttle limit and trigger an alert.
        """
        self.request = request  # Store the request temporarily for use in `wait()`
        return super().allow_request(request, view)

    def wait(self):
        """
        Check if the request is throttled, and if so, send an alert email.
        """
        wait_time = super().wait()  # Get the normal wait time from DRF

        # Ensure request is available
        if not hasattr(self, "request"):
            return wait_time  # Prevent errors if request is missing

        # Get user info (IP, user ID, etc.)
        request = self.request
        user = getattr(request, "user", None)
        ip_address = self.get_ident(request)
        user_email = getattr(user, "email", "Unauthenticated User")

        # Generate a cache key to prevent duplicate alerts
        cache_key = f"throttle_alert_{ip_address}_{self.scope}"

        if not cache.get(cache_key):  # Only send one alert per block period
            logger.warning(f"Throttle limit exceeded for {user_email} (IP: {ip_address}) on {self.scope}")

            # Create the alert email message
            subject = "🚨 API Throttling Alert: Excessive Requests Detected"
            message = f"""
            <h2>⚠️ API Throttling Alert ⚠️</h2>
            <p><strong>Throttle Limit Exceeded</strong> for <b>{user_email}</b></p>
            <p>🌐 <strong>IP Address:</strong> {ip_address}</p>
            <p>🔄 <strong>Endpoint Scope:</strong> {self.scope}</p>
            <p>⏳ <strong>Blocked Until:</strong> {now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr>
            <p>This is an automated alert from the authentication system.</p>
            """

            # Send the alert to all admin emails
            for admin_email in ADMIN_EMAILS:
                send_email_f(
                    sender="noreply@alife.ie",
                    recipient=admin_email,
                    subject=subject,
                    message=message,
                    save_in_email_log=False,  # No need to log internal alerts
                )

            # Store in cache to avoid repeated alerts
            cache.set(cache_key, True, timeout=60 * 10)  # Prevent duplicate alerts for 10 minutes

        return wait_time  # Return the normal wait time for DRF throttling


class SustainedThrottle(ScopedRateThrottle):
    """
    Custom Sustained Throttle that:
    - Limits short-term bursts.
    - Blocks repeated offenders for a long period (e.g., 24 hours).
    """

    sustained_scope = "sustained"  # Separate scope for long-term throttling
    sustained_block_time = 60 * 60 * 24  # Block for 24 hours (86400 seconds)

    def allow_request(self, request, view):
        """
        Override `allow_request` to check both burst and sustained limits.
        """
        self.request = request
        user = getattr(request, "user", None)
        ip_address = self.get_ident(request)

        # Cache keys to track violations
        burst_cache_key = f"throttle_burst_{ip_address}_{self.scope}"
        sustained_cache_key = f"throttle_sustained_{ip_address}"

        # Check if the IP is already blocked for 24 hours
        if cache.get(sustained_cache_key):
            logger.warning(f"🚨 Permanent block: {ip_address} exceeded sustained limit!")
            return False  # Permanently block

        # Check normal short-term (burst) throttle
        if not super().allow_request(request, view):
            # Increase sustained counter if burst limit is exceeded
            sustained_attempts = cache.get(sustained_cache_key, 0) + 1
            cache.set(sustained_cache_key, sustained_attempts, timeout=self.sustained_block_time)

            # If the user exceeded the sustained limit, block for 24 hours
            if sustained_attempts >= 50:  # Example: Block if 50 violations occur in a day
                cache.set(sustained_cache_key, True, timeout=self.sustained_block_time)
                logger.error(f"🚨 {ip_address} permanently blocked for 24 hours due to repeated violations.")

                # Send email alert
                subject = "🚨 API Permanent Block Alert: Repeated Violations Detected"
                message = f"""
                <h2>⚠️ Sustained Throttle Alert ⚠️</h2>
                <p><strong>Permanent block triggered</strong> for <b>{user.email if user else 'Unauthenticated User'}</b></p>
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

                return False  # Block request

        return True  # Allow request if below threshold
