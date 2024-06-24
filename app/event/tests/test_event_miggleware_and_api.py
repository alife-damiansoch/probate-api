import json

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import Events, Deceased, Application  # Update with your app name


def create_application(user, **params):
    """create and return a new application object"""
    # Create a new Deceased instance without parameters
    deceased = Deceased.objects.create(first_name="John", last_name="Doe")
    defaults = {
        'amount': 1000.00,  # Default amount
        'term': 12,  # Default term
        # 'user': None,  # Since this can be null
        # 'approved': False,  # Default status
        # 'last_updated_by': None,  # Since this can be null
        'deceased': deceased,  # Assign the new deceased instance
        # 'dispute': None,
        # 'undertaking_ready': False,  # Default status
        # 'loan_agreement_ready': False,  # Default status
        # 'assigned_to': None,  # Since this can be null
    }
    defaults.update(params)
    application = Application.objects.create(user=user, **defaults)
    return application


def get_detail_url(application_id):
    """create the detail url"""
    return reverse('solicitors_loan:solicitor_application-detail', args=[application_id])


class LoggingMiddlewareTest(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.client.login(email='test@example.com', password='testpass123')
        self.GET_ROUTE = reverse('solicitors_loan:solicitor_application-list')
        self.default_application = create_application(self.user)
        self.PUT_URL = get_detail_url(self.default_application.id)

    def test_post_request(self):
        data = {
            'amount': '2000.00',
            'term': 24,
            'deceased': {
                'first_name': 'John',
                'last_name': 'Doe'
            },
            'dispute': {
                'details': 'Some details'
            },
            'applicants': [
                {
                    'title': 'Mr',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'pps_number': '1234567AG'
                }
            ],
            'estates': [
                {
                    'description': 'Some estate',
                    'value': '20000.00'
                }
            ],
        }

        response = self.client.post(self.GET_ROUTE, data, format='json')
        self.assertEqual(response.status_code, 201)
        logged_event = Events.objects.latest('created_at')
        self.assertNotEqual(logged_event, None)
        self.assertEqual(logged_event.method, 'POST')
        self.assertEqual(logged_event.path, self.GET_ROUTE)
        self.assertEqual(logged_event.user, str(self.user))

    def test_put_request(self):
        data = {
            'amount': '2000.00',
            'term': 24,
            'deceased': {
                'first_name': 'John',
                'last_name': 'Doe'
            },
            'dispute': {
                'details': 'Some details'
            },
            'applicants': [
                {
                    'title': 'Mr',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'pps_number': '1234567AG'
                }
            ],
            'estates': [
                {
                    'description': 'Some estate',
                    'value': '20000.00'
                }
            ],
        }
        response = self.client.put(self.PUT_URL, json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 200, f"error: {response.data}")
        logged_event = Events.objects.latest('created_at')
        self.assertNotEqual(logged_event, None)
        self.assertEqual(logged_event.method, 'PUT')

    def test_error_response(self):
        other_user = get_user_model().objects.create_user(
            email='test1@example.com',
            password='testpass123',
        )
        client = APIClient()
        client.force_authenticate(user=other_user)

        response = client.get(self.PUT_URL)  # replace with route that results in error
        self.assertTrue(response.status_code >= 400)
        logged_event = Events.objects.latest('created_at')
        self.assertNotEqual(logged_event, None)
        self.assertEqual(logged_event.is_error, True)
