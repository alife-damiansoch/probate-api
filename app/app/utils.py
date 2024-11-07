import json
import uuid

from django.core.files.uploadedfile import InMemoryUploadedFile

from core.models import Event  # Import your event model


def log_event(request, request_body, application=None, response_status=None, response=None, is_error=False):
    """
       Logs an event in the application, capturing relevant request and response details, and stores it in the Event model.

       This function records information from an HTTP request, including metadata like request method, path, and body,
       as well as response details if provided. It can also specify if the log entry is an error or a notification and associates
       it with an application or user if available.

       Parameters:
       - request (HttpRequest): The HTTP request object containing details about the request.
       - request_body (dict or str): The body of the request, typically a dictionary (will be JSON-encoded).
       - application (Application, optional): An associated application instance, if applicable. Default is None.
       - response_status (int, optional): The HTTP status code of the response, if available. Default is None.
       - response (HttpResponse, optional): The HTTP response object, from which the response content is extracted. Default is None.
       - is_error (bool, optional): A flag indicating if the log entry represents an error. Default is False.

       Returns:
       None. The function creates an entry in the Event model.
       """

    log_data = {
        'request_id': getattr(request, 'id', uuid.uuid4()),
        'method': request.method,
        'path': request.path,
        'body': json.dumps(request_body) if isinstance(request_body, dict) else None,
        'response_status': response_status,
        'response': json.dumps(response.content.decode()) if response is not None else None,
        'is_error': is_error,
        'is_notification': True,
        'user': str(request.user) if request.user is not None else '',
        'is_staff': request.user.is_staff if request.user else False,
        'application': application if application else None
    }
    # print(f"log_data: {log_data}")
    event = Event.objects.create(**log_data)
