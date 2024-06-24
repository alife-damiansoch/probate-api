import json
import uuid
from django.utils.deprecation import MiddlewareMixin
from core.models import Events

from django.urls import reverse


class LoggingMiddleware(MiddlewareMixin):

    def process_request(self, request):
        exclude_paths = ['/api/user/', '/favicon.ico']
        if any(request.path.startswith(path) for path in exclude_paths):
            # If the current URL starts with any of our excluded paths, do nothing and return None so that
            # Django can process the request normally:
            return None

        request.id = uuid.uuid4()
        if request.method in ['PUT', 'POST', 'DELETE']:
            # Check for file upload
            if request.META.get('CONTENT_TYPE', '') == 'multipart/form-data':
                body = 'File uploaded'
            else:
                try:
                    body = json.loads(request.body.decode('utf-8'))
                except (UnicodeDecodeError, json.decoder.JSONDecodeError):
                    body = 'Non-JSON request body'

            is_notification = True
            log_data = {
                'request_id': request.id,
                'method': request.method,  # Request method
                'path': request.path,  # Request path
                'body': body,  # Request body
                'is_notification': is_notification,  # If the event was a notification
                'user': str(request.user),
                'is_staff': request.user.is_staff,

            }
            Events.objects.create(**log_data)
        return None

    def process_response(self, request, response):
        if response.status_code >= 400:
            if response.get('Content-Type') == 'application/json':
                response_data = json.loads(response.content.decode('utf-8'))
                if "non_field_errors" in response_data and \
                        "Unable to authenticate with provided credentials" in response_data["non_field_errors"]:
                    # Skip logging for bad username/password errors
                    return response
            else:
                response_data = str(response.content)

            log_data = {
                'request_id': request.id if hasattr(request, 'id') else uuid.uuid4(),
                'user': str(request.user if request.user.is_authenticated else 'AnonymousUser'),
                'method': request.method,
                'path': request.path,
                'response_status': response.status_code,
                'response': json.dumps(response_data),
                'is_error': True,
            }
            if 'applications' in request.path:
                # Split the path components
                parts = request.path.split('/')
                # Try to find the application id if possible
                application_id = None
                if 'applications' in parts:
                    try:
                        app_index = parts.index('applications') + 1
                        application_id = parts[app_index]
                    except IndexError:
                        pass
                    except ValueError:  # 'applications' not in list
                        pass
                # Include the application_id in log_data
                log_data['application_id'] = application_id
            Events.objects.create(**log_data)

        return response
