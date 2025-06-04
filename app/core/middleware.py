import logging
import json
from json import JSONDecodeError

from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied


class LogEventOnErrorMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if request.path == '/favicon.ico':
            return response
        if 400 <= response.status_code < 600:
            try:
                response_body = json.loads(response.content.decode())
            except (JSONDecodeError, ValueError):
                response_body = response.status_code
            # Import log_event INSIDE the function
            from app.utils import log_event
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


def get_excluded_paths():
    from app import settings
    return [
        f'/{settings.ADMIN_URL}/',
        '/api/docs/',
        '/api/schema/',
        '/api/user/activate/',
        '/api/user/reset-password/',
        '/csp-report/',
        '/favicon.ico',
    ]


class CountryMiddleware(MiddlewareMixin):
    def __call__(self, request):
        from app import settings
        EXCLUDED_PATHS = get_excluded_paths()
        if any(request.path.startswith(path) for path in EXCLUDED_PATHS):
            return self.get_response(request)
        referer = request.headers.get('Referer', '')
        is_swagger_request = '/api/docs/' in referer
        country = request.headers.get('Country')
        if not country:
            if is_swagger_request or getattr(settings, 'TESTING', False):
                request.META['HTTP_COUNTRY'] = 'IE'
                country = 'IE'
            else:
                return JsonResponse(
                    {'error': 'Country header is required.'},
                    status=400,
                )
        request.country = country
        response = self.get_response(request)
        return response


class ValidateAPIKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from app import settings
        if settings.TESTING:
            return self.get_response(request)
        EXCLUDED_PATHS = get_excluded_paths() + [
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
        ]
        if any(request.path.startswith(path) for path in EXCLUDED_PATHS):
            return self.get_response(request)
        # JWT authentication
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken
        jwt_authenticator = JWTAuthentication()
        try:
            auth_result = jwt_authenticator.authenticate(request)
            if auth_result:
                request.user, _ = auth_result
            else:
                return JsonResponse(
                    {"detail": "Given token not valid for any token type", "code": "token_not_valid"},
                    status=401
                )
        except InvalidToken:
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
        # Retrieve API key from cookies
        api_key = request.COOKIES.get(
            'X-Frontend-API-Key' if not request.user.is_staff else "X-Frontend-API-Key-Agents")
        if not api_key:
            return JsonResponse({"error": "Forbidden: Missing API key in request"}, status=403)
        from core.models import FrontendAPIKey
        try:
            key_obj = FrontendAPIKey.objects.get(user=request.user)
            if key_obj.is_expired():
                key_obj.delete()
                return JsonResponse({"error": "Forbidden: API key expired"}, status=403)
            if api_key != key_obj.key:
                return JsonResponse({"error": "Forbidden: Invalid API key"}, status=403)
            if request.path != "/api/communications/count-unseen_info_email/":
                key_obj.refresh_expiration()
            response = self.get_response(request)
            response[
                "X-API-Key-Expiration" if not request.user.is_staff else "X-API-Key-Expiration-Agents"] = key_obj.expires_at.isoformat()
            return response
        except FrontendAPIKey.DoesNotExist:
            return JsonResponse({"error": "Forbidden: API key not found in storage"}, status=403)


class LogHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # print("Request Headers:", dict(request.headers))
        response = self.get_response(request)
        return response


class AdminIPRestrictionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        from app import settings
        from app.settings import ALLOWED_ADMIN_IPS
        if settings.TESTING:
            return None
        client_ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
        if "," in client_ip:
            client_ip = client_ip.split(",")[0].strip()
        restricted_paths = [
            f"/{settings.ADMIN_URL}/",
            "/api/schema/",
            "/api/docs/",
        ]
        if any(request.path.startswith(path) for path in restricted_paths) and client_ip not in ALLOWED_ADMIN_IPS:
            raise PermissionDenied("Unauthorized IP - Access Denied")
        return None


class CSPReportOnlyMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        from app import settings
        django_env = getattr(settings, "ENV", "production").lower()
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
        if request.path.startswith("/api/docs/"):
            if django_env == "development":
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
        response["Content-Security-Policy"] = csp_policy
        return response
