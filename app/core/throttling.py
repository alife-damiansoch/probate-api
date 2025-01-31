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
