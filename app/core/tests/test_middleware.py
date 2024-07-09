from django.http import HttpResponse
from django.test import TestCase, Client, RequestFactory
from core.models import Event  # Update the import as per your project structure
from core.middleware import CorsMiddleware
import json


class LogEventOnErrorMiddlewareTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_log_404_error(self):
        response = self.client.get('/path/that/does/no/exist/')
        self.assertEqual(response.status_code, 404)

        event = Event.objects.last()
        self.assertIsNotNone(event)
        self.assertEqual(event.method, 'GET')
        self.assertEqual(event.path, '/path/that/does/no/exist/')

        expected_body = {
            "message": "Error response detected",
        }
        self.assertEqual(json.loads(event.body), expected_body)
        self.assertTrue(event.is_error)
        self.assertEqual(event.response_status, 404)
        # Add your further asserts here

    def test_log_500_error(self):
        response = self.client.get('/test/500/')
        self.assertEqual(response.status_code, 500)

        event = Event.objects.last()

        self.assertIsNotNone(event)
        self.assertEqual(event.method, 'GET')
        self.assertEqual(event.path, '/test/500/')
        expected_body = {
            "message": "Error response detected",
        }
        self.assertEqual(json.loads(event.body), expected_body)
        self.assertTrue(event.is_error)
        self.assertEqual(event.response_status, 500)
        # Add your further asserts here


class CorsMiddlewareTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = CorsMiddleware(self.get_response)

    def get_response(self, request):
        return HttpResponse()

    def test_allows_all_origins_for_allow_all_paths(self):
        for path in ['/api/applications/comments/', '/api/applications/events/', '/api/applications/expenses/']:
            request = self.factory.get(path)
            request.META['HTTP_ORIGIN'] = 'http://test.com'
            response = self.middleware(request)
            self.assertEqual(response['Access-Control-Allow-Origin'], '*')

    def test_allows_restricted_origins_for_restricted_paths(self):
        restricted_origins = [
            "http://127.0.0.1",
            "http://127.0.0.1:3000",
            "http://localhost:3000"
        ]
        for path in ['/api/applications/agent_applications/', '/api/loans/']:
            for origin in restricted_origins:
                request = self.factory.get(path)
                request.META['HTTP_ORIGIN'] = origin
                response = self.middleware(request)
                self.assertEqual(response['Access-Control-Allow-Origin'], origin)

    def test_does_not_allow_unrestricted_origins_for_restricted_paths(self):
        for path in ['/api/applications/agent_applications/', '/api/loans/']:
            request = self.factory.get(path)
            request.META['HTTP_ORIGIN'] = 'http://unrestricted.com'
            response = self.middleware(request)
            self.assertFalse('Access-Control-Allow-Origin' in response.headers)

    def test_no_effect_on_other_paths(self):
        request = self.factory.get('/some_other_path/')
        request.META['HTTP_ORIGIN'] = 'http://unrestricted.com'
        response = self.middleware(request)
        old_response = self.get_response(request)
        self.assertEqual(old_response.headers.get('Access-Control-Allow-Origin'),
                         response.headers.get('Access-Control-Allow-Origin'))

    def test_preflight_request(self):
        # Add other paths that need to be tested
        all_paths = ["/api/applications/comments/", "/api/applications/events/", "/api/applications/expenses/",
                     "/api/applications/solicitor_applications/", "/api/download/", "/api/user/", "/api/user/token/",
                     "/api/applications/agent_applications/", "/api/loans/"]

        for path in all_paths:
            request = self.factory.options(path)
            response = self.middleware(request)

            # check if 'content-type' and 'authorization' are in the value of 'Access-Control-Allow-Headers'
            allow_headers = response.get('Access-Control-Allow-Headers', '')
            self.assertIn('content-type', allow_headers.split(', '))
            self.assertIn('authorization', allow_headers.split(', '))

    def test_actual_request(self):
        for path in ["/api/applications/comments/",
                     "/api/applications/events/",
                     "/api/applications/expenses/"]:
            request = self.factory.get(path)
            request.META['HTTP_ORIGIN'] = "http://unrestricted.com"
            response = self.middleware(request)

            # check if 'Access-Control-Allow-Headers' is not in the headers of actual requests
            self.assertNotIn('Access-Control-Allow-Headers', response)
