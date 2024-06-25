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
