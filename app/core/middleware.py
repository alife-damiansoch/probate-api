from django.utils.deprecation import MiddlewareMixin
from json import JSONDecodeError
import json
from django.http import JsonResponse

from app import settings
from app.utils import log_event


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


class CountryMiddleware(MiddlewareMixin):
    """
    Middleware to enforce the presence of a 'Country' header in all requests.
    """

    def __call__(self, request):
        # Skip validation for admin and API documentation endpoints
        if (
                request.path.startswith('/admin/')
                or request.path.startswith('/api/docs/')
                or request.path.startswith('/api/schema/')
                or request.path.startswith('/api/user/activate/')
        ):
            return self.get_response(request)

        # Check if the 'Country' header is provided
        country = request.headers.get('Country')
        if not country:
            if getattr(settings, 'TESTING', False):
                # Automatically add the Country header during tests
                request.META['HTTP_COUNTRY'] = 'IE'  # Add the header in the request.META
                country = 'IE'  # Ensure country is set for further processing
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
