from django.test import TestCase, Client
from core.models import Event  # Update the import as per your project structure
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
