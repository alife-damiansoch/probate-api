from django.utils.deprecation import MiddlewareMixin
from json import JSONDecodeError
import json

from app.utils import log_event


class LogEventOnErrorMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
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
            "/api/user/token/"
        ]

        restricted_origins_paths = [
            "/api/applications/agent_applications/",
            "/api/loans/"
        ]

        # adds Access-Control-Allow-Headers to preflight requests,
        # allowing content-type and authorization headers in the actual requests.
        if request.method == 'OPTIONS':
            response['Access-Control-Allow-Headers'] = 'content-type, authorization'

        if any(path in request.path for path in allow_all_origins_paths):
            response['Access-Control-Allow-Origin'] = '*'
        elif any(path in request.path for path in restricted_origins_paths):
            origin = request.META.get('HTTP_ORIGIN')
            if origin in restricted_origins:
                response['Access-Control-Allow-Origin'] = origin
        return response
