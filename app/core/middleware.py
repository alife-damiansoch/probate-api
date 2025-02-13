import logging

from django.utils.deprecation import MiddlewareMixin
from json import JSONDecodeError
import json
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from rest_framework_simplejwt.exceptions import InvalidToken

from app import settings
from app.utils import log_event
from app.settings import ADMIN_URL, MIDDLEWARE
from app.settings import ALLOWED_ADMIN_IPS
from django.core.cache import cache

from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth import get_user_model

from core.models import FrontendAPIKey

User = get_user_model()


class LogEventOnErrorMiddleware(MiddlewareMixin):
    """
       Middleware to log events for error responses in Django requests.

       This middleware intercepts responses with status codes in the 400–599 range, indicating client or server errors,
       and logs the details of the failed request using the `log_event` function. The log entry includes request metadata,
       response status, and any additional error information, to assist with tracking and diagnosing errors.

       Methods:
       - process_response: Intercepts the response, checks for error status codes, and logs relevant details.

       Parameters:
       - request (HttpRequest): The current request object.
       - response (HttpResponse): The response object returned by the view.

       Process:
       1. Ignores requests to the '/favicon.ico' endpoint.
       2. Checks if the response status code indicates an error (400–599).
       3. Attempts to parse the response body as JSON; if not JSON, only logs the status code.
       4. Calls the `log_event` function with request and response details, marking the log entry as an error.

       Returns:
       - HttpResponse: The original response is returned after logging, ensuring the response cycle proceeds normally.

       Notes:
       - Requires the `log_event` function to be defined and accessible.
       """

    def process_response(self, request, response):
        # Ignore '/favicon.ico' endpoint.
        if request.path == '/favicon.ico':
            return response
        if 400 <= response.status_code < 600:

            # Attempt to parse body JSON
            response_body = response.content.decode()
            try:
                response_body = json.loads(response_body)
            except (JSONDecodeError, ValueError):
                # If content is not JSON, then only log the status code.
                response_body = response.status_code

            # Log details about the failed request
            event = log_event(
                request=request,
                request_body={
                    "message": "Error response detected",
                },
                application=None,
                response_status=response.status_code,
                response=response,
                is_error=True

            )

        return response


class CorsMiddleware(object):
    """
       Custom middleware to manage Cross-Origin Resource Sharing (CORS) for specified endpoints in a Django application.

       This middleware allows or restricts CORS access based on the request path and origin. Specific paths can allow
       access from any origin, while others are restricted to a defined set of origins. It also sets necessary headers
       for preflight requests to enable cross-origin communication.

       Attributes:
       - get_response: Callable that takes a request and returns a response.

       Methods:
       - __call__: Processes each request and response to set CORS headers based on predefined rules.

       Parameters:
       - request (HttpRequest): The incoming HTTP request to process.

       Process:
       1. Checks if the request is a preflight (OPTIONS) request and, if so, sets headers to allow content-type and authorization headers.
       2. Allows all origins (`*`) for requests to paths in `allow_all_origins_paths`.
       3. For requests to paths in `restricted_origins_paths`, allows access only if the request's origin is in the `restricted_origins` list.
       4. Returns the modified response with the appropriate CORS headers.

       Returns:
       - HttpResponse: The response with updated CORS headers.

       Configuration:
       - `restricted_origins` (list): A list of origins allowed for restricted paths.
       - `allow_all_origins_paths` (list): Paths open to all origins.
       - `restricted_origins_paths` (list): Paths restricted to origins in `restricted_origins`.
       """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        restricted_origins = [
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://localhost:3000",
            "https://af3a-79-97-102-189.ngrok-free.app"
        ]

        allow_all_origins_paths = [
            "/api/applications/comments/",
            "/api/applications/events/",
            "/api/applications/expenses/",
            "/api/applications/solicitor_applications/",
            "/api/download/",
            "/api/user/",
            "/api/user/token/",
            "/api/user/token/refresh/",
            "api/use/activate/"
        ]

        restricted_origins_paths = [
            "/api/applications/agent_applications/",
            "/api/loans/"
        ]

        # adds Access-Control-Allow-Headers and Access-Control-Allow-Methods to preflight requests,
        # allowing content-type and authorization headers in the actual requests.
        if request.method == 'OPTIONS':
            response['Access-Control-Allow-Headers'] = 'content-type, authorization'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, PUT, DELETE, OPTIONS'

        if any(path in request.path for path in allow_all_origins_paths):
            response['Access-Control-Allow-Origin'] = '*'
        elif any(path in request.path for path in restricted_origins_paths):
            origin = request.META.get('HTTP_ORIGIN')
            if origin in restricted_origins:
                response['Access-Control-Allow-Origin'] = origin

        return response


EXCLUDED_PATHS = [
    f'/{settings.ADMIN_URL}/',
    '/api/docs/',
    '/api/schema/',
    '/api/user/activate/',
    '/api/user/reset-password/',
    '/csp-report/'
]


class CountryMiddleware(MiddlewareMixin):
    """
    Middleware to enforce the presence of a 'Country' header in all requests,
    while automatically adding it for Swagger requests based on the Referer.
    """

    def __call__(self, request):
        # Skip validation for admin and API documentation endpoints
        if any(request.path.startswith(path) for path in EXCLUDED_PATHS):
            return self.get_response(request)

        # Check if the request originates from Swagger (Referer contains '/api/docs/')
        referer = request.headers.get('Referer', '')
        is_swagger_request = '/api/docs/' in referer

        # Check if the 'Country' header is provided
        country = request.headers.get('Country')
        if not country:
            if is_swagger_request:
                # Automatically add 'Country: IE' for Swagger requests
                request.META['HTTP_COUNTRY'] = 'IE'
                country = 'IE'  # Ensure country is set for further processing
            elif getattr(settings, 'TESTING', False):
                # Automatically add 'Country: IE' during tests
                request.META['HTTP_COUNTRY'] = 'IE'
                country = 'IE'
            else:
                # Return a 400 Bad Request response if the 'Country' header is missing
                return JsonResponse(
                    {'error': 'Country header is required.'},
                    status=400,
                )

        # Set the country on the request object for further processing
        request.country = country

        response = self.get_response(request)
        return response


class ValidateAPIKeyMiddleware:
    """
    Middleware to validate the X-Frontend-API-Key for all incoming requests
    except the excluded paths or when running tests.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ✅ Skip check if running tests
        if settings.TESTING:
            return self.get_response(request)

        # ✅ Extend EXCLUDED_PATHS for this middleware
        EXCLUDED_PATHS.extend([
            "/api/user/check-credentials/",
            "/api/user/validate-otp/",
            "/api/user/verify-authenticator-code/",
            "/api/user/update-auth-method/",
            "/api/user/token/",
            "/api/user/me/",
            "/api/user/create/",
            "/api/user/activate/",
            "/api/user/forgot-password/",
            "/api/user/reset-password/",
        ])

        # ✅ Skip validation for excluded paths
        if any(request.path.startswith(path) for path in EXCLUDED_PATHS):
            return self.get_response(request)

            # ✅ Manually authenticate JWT token before checking API key
        jwt_authenticator = JWTAuthentication()
        try:
            auth_result = jwt_authenticator.authenticate(request)

            if auth_result:
                request.user, _ = auth_result  # ✅ Set authenticated user
            else:
                # ✅ Return the same response as DRF when token is missing or expired
                return JsonResponse(
                    {"detail": "Given token not valid for any token type", "code": "token_not_valid"},
                    status=401
                )

        except InvalidToken:
            # ✅ Handle explicitly invalid token cases
            return JsonResponse(
                {"detail": "Given token not valid for any token type", "code": "token_not_valid"},
                status=401
            )
        except Exception as e:
            print("JWT Authentication failed:", str(e))
            return JsonResponse(
                {"detail": "Unauthorized: Token validation failed", "code": "token_not_valid"},
                status=401
            )
        # ✅ Retrieve the API key from cookies
        api_key = request.COOKIES.get(
            'X-Frontend-API-Key' if not request.user.is_staff else "X-Frontend-API-Key-Agents")
        print("API KEY FROM REQUEST:", api_key)
        print("USER In Request:", request.user.__dict__)
        print("WHOLE REQUEST", request.__dict__)
        # Do this check only for the Solicitor users
        # if request.user.is_staff:
        #     return self.get_response(request)
        if not api_key:
            return JsonResponse({"error": "Forbidden: Missing API key in request"}, status=403)

            # ✅ Retrieve the API key from the database
        try:
            key_obj = FrontendAPIKey.objects.get(user=request.user)
            if key_obj.is_expired():
                key_obj.delete()  # Delete expired key
                return JsonResponse({"error": "Forbidden: API key expired"}, status=403)

            # ✅ check the key
            if api_key != key_obj.key:
                return JsonResponse({"error": "Forbidden: Invalid API key"}, status=403)

                # ✅ Refresh the expiration time to 15 minutes from now
            if request.path != "/api/communications/count-unseen_info_email/":
                key_obj.refresh_expiration()

            # ✅ Add expiration time to response headers
            response = self.get_response(request)
            response[
                "X-API-Key-Expiration" if not request.user.is_staff else "X-API-Key-Expiration-Agents"] = key_obj.expires_at.isoformat()  # Send as ISO timestamp
            return response

        except FrontendAPIKey.DoesNotExist:
            return JsonResponse({"error": "Forbidden: API key not found in storage"}, status=403)


class LogHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log all incoming headers
        print("Request Headers:", dict(request.headers))

        # Continue processing the request
        response = self.get_response(request)
        return response


class AdminIPRestrictionMiddleware(MiddlewareMixin):
    """
    Middleware to restrict access to the Django Admin panel
    and API Docs based on a whitelist of allowed IP addresses.
    """

    def process_request(self, request):
        # Skip IP restriction if running tests
        if settings.TESTING:
            return None

        # Get client IP address (supports proxies)
        client_ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
        if "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()  # Extract real client IP if behind a proxy

        # Define restricted paths
        restricted_paths = [
            f"/{settings.ADMIN_URL}/",  # Admin Panel
            "/api/schema/",  # API Schema
            "/api/docs/",  # API Docs
        ]

        # If request path matches and IP is not allowed, deny access
        if any(request.path.startswith(path) for path in restricted_paths) and client_ip not in ALLOWED_ADMIN_IPS:
            raise PermissionDenied("Unauthorized IP - Access Denied")

        return None  # Continue processing the request


class CSPReportOnlyMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Get the environment setting from .env (defaults to "production")
        django_env = getattr(settings, "ENV", "production").lower()

        # Default strict CSP for production (no inline scripts)
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' https://apis.google.com https://unpkg.com; "
            "script-src-elem 'self' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
            "style-src-elem 'self' https://unpkg.com; "
            "img-src 'self' data: https://res.cloudinary.com https://unpkg.com; "
            "connect-src 'self' https://api.alife.ie; "
            "font-src 'self' https://fonts.gstatic.com; "
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "report-uri /csp-report/; "
        )

        # Allow inline scripts ONLY for /api/docs/
        if request.path.startswith("/api/docs/"):
            if django_env == "development":
                # ✅ DEVELOPMENT: Allow both HTTP & HTTPS, inline scripts
                csp_policy = (
                    "default-src 'self' http: https:; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' http: https: https://apis.google.com https://unpkg.com; "
                    "script-src-elem 'self' 'unsafe-inline' http: https: https://unpkg.com; "
                    "style-src 'self' 'unsafe-inline' http: https: https://fonts.googleapis.com https://unpkg.com; "
                    "style-src-elem 'self' http: https: https://unpkg.com; "
                    "img-src 'self' data: http: https: https://res.cloudinary.com https://unpkg.com; "
                    "connect-src 'self' http: https: https://api.alife.ie; "
                    "font-src 'self' http: https: https://fonts.gstatic.com; "
                    "frame-ancestors 'none'; "
                    "form-action 'self'; "
                    "report-uri /csp-report/; "
                )
            else:
                # ✅ PRODUCTION: HTTPS only, but allows inline scripts for /api/docs/
                csp_policy = (
                    "default-src 'self' https:; "
                    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com https://unpkg.com; "
                    "script-src-elem 'self' 'unsafe-inline' https://unpkg.com; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
                    "style-src-elem 'self' https://unpkg.com; "
                    "img-src 'self' data: https://res.cloudinary.com https://unpkg.com; "
                    "connect-src 'self' https://api.alife.ie; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    "frame-ancestors 'none'; "
                    "form-action 'self'; "
                    "report-uri /csp-report/; "
                )

        # Apply the policy to the response
        response["Content-Security-Policy"] = csp_policy
        return response
