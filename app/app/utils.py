import json
import uuid

from django.core.files.uploadedfile import InMemoryUploadedFile

from core.models import Event  # Import your event model


def log_event(request, request_body, application=None, response_status=None, response=None, is_error=False):
    # print(f"Log event request: {request}")
    # print(f"Log event application: {application}")
    # print(f"Log event body: {request_body}")

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
