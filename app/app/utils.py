import json
import uuid
from core.models import Event  # Import your event model


def log_event(request, request_body, application=None):
    # print(f"Log event request: {request}")
    # print(f"Log event application: {application}")
    # print(f"Log event body: {request_body}")
    default_response_status = None
    default_response = ""
    default_is_error = False
    log_data = {
        'request_id': getattr(request, 'id', uuid.uuid4()),
        'method': request.method,
        'path': request.path,
        'body': json.dumps(request_body) if request_body else None,
        'response_status': default_response_status,
        'response': default_response,
        'is_error': default_is_error,
        'is_notification': True,
        'user': str(request.user) if request.user is not None else '',
        'is_staff': request.user.is_staff if request.user else False,
        'application': application if application else None
    }
    # print(f"log_data: {log_data}")
    event = Event.objects.create(**log_data)
