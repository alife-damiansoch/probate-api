"""
Test solicitors_application api
"""
import json

from django.contrib.auth import get_user_model

from django.urls import reverse

from rest_framework import status

from rest_framework.test import APIClient, APITestCase

from core.models import (Application, Deceased, Dispute, RejectionReason, Event, )

from solicitors_loan import serializers

from decimal import Decimal

from django.utils import timezone


def get_detail_url(application_id):
    """create the detail url"""
    return reverse('solicitors_loan:solicitor_application-detail', args=[application_id])


def get_document_upload_url(application_id):
    return reverse('solicitors_loan:solicitor_application-upload-document', args=[application_id])


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


class PublicTestApplicationAPI(APITestCase):
    """Unauthenticated API tests"""

    def setUp(self):
        self.client = APIClient()
        self.APPLICATIONS_URL = reverse('solicitors_loan:solicitor_application-list')

    def test_authentication_required(self):
        """Test that authentication is required"""
        response = self.client.get(self.APPLICATIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateTestApplicationAPI(APITestCase):
    """Unauthenticated API tests"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.APPLICATIONS_URL = reverse('solicitors_loan:solicitor_application-list')

    def test_retrieve_applications(self):
        """Test retrieving all applications"""
        create_application(user=self.user)
        create_application(user=self.user)
        response = self.client.get(self.APPLICATIONS_URL)
        applications = Application.objects.all().order_by('-id')
        serializer = serializers.SolicitorApplicationSerializer(applications, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_retrieve_self_applications(self):
        """Test retrieving applications created by self.user"""
        # Create some applications for `self.user`
        create_application(user=self.user)
        create_application(user=self.user)

        # Create an application for a different user
        other_user = get_user_model().objects.create_user(
            email="other_user@example.com",
            password="otherpass123",
        )  # Create a new method to generate another user or use existing one
        create_application(user=other_user)

        response = self.client.get(self.APPLICATIONS_URL)
        # Change the query to filter applications by `self.user`
        user_applications = Application.objects.filter(user=self.user).order_by('-id')
        serializer = serializers.SolicitorApplicationSerializer(user_applications, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data, serializer.data)

    def test_receive_application_details(self):
        """test recieving details of an application"""
        application = create_application(user=self.user)
        url = get_detail_url(application.id)
        response = self.client.get(url)
        serializer = serializers.SolicitorApplicationDetailSerializer(application)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)
        self.assertEqual(response.data['id'], application.id)

    def test_create_application_requires_all_fields(self):
        """Test that an application requires all fields"""
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

        for key in ['amount', 'term', 'deceased', 'dispute', 'applicants', 'estates']:
            modified_data = {k: v for k, v in data.items() if k != key}
            response = self.client.post(self.APPLICATIONS_URL, modified_data, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, msg=f"{key} not provided in data")

    def test_create_all_fields_application(self):
        """Test creating a new application with all fields"""
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

        response = self.client.post(self.APPLICATIONS_URL, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, msg=response.data)

        application = Application.objects.get(id=response.data['id'])

        self.assertEqual(application.amount, Decimal(data['amount']))
        self.assertEqual(application.term, data['term'])
        self.assertEqual(application.user, self.user)
        self.assertEqual(application.deceased.first_name, data['deceased']['first_name'])
        self.assertEqual(application.deceased.last_name, data['deceased']['last_name'])
        self.assertEqual(application.dispute.details, data['dispute']['details'])

        # Check that the correct number of applicants and estates were created
        self.assertEqual(application.applicants.count(), len(data['applicants']))
        self.assertEqual(application.estates.count(), len(data['estates']))

        # Check all applicants
        for i in range(len(data['applicants'])):
            applicant = application.applicants.all()[i]
            applicant_data = data['applicants'][i]
            self.assertEqual(applicant.title, applicant_data['title'])
            self.assertEqual(applicant.first_name, applicant_data['first_name'])
            self.assertEqual(applicant.last_name, applicant_data['last_name'])
            self.assertEqual(applicant.pps_number, applicant_data['pps_number'])

        # Check all estates
        for i in range(len(data['estates'])):
            estate = application.estates.all()[i]
            estate_data = data['estates'][i]
            self.assertEqual(estate.description, estate_data['description'])
            self.assertEqual(estate.value, Decimal(estate_data['value']))

            # Check event created
        events = Event.objects.all()
        event = events[0]
        self.assertEqual(events.count(), 1)
        self.assertEqual(event.application, application)
        self.assertEqual(event.user, str(self.user))
        self.assertIsNotNone(event.request_id)
        self.assertEqual(event.method, 'POST')
        self.assertEqual(event.path, self.APPLICATIONS_URL)
        self.assertEqual(event.body, json.dumps(data))
        self.assertFalse(event.is_error)
        self.assertTrue(event.is_notification)
        self.assertFalse(event.is_staff)

    def test_update_put_application_requires_all_fields(self):
        """Test that updating an application requires all fields"""
        # Create a test application with all necessary fields filled
        application = Application.objects.create(
            amount=2000.00,
            term=24,
            deceased=Deceased.objects.create(first_name='John', last_name='Doe'),

            user=self.user,
        )

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

        for key in ['amount', 'term', 'deceased', 'dispute', 'applicants', 'estates']:
            modified_data = {k: v for k, v in data.items() if k != key}
            url = get_detail_url(application_id=application.id)
            response = self.client.put(url, modified_data, format='json')

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, msg=f"{key} not provided in data")

    def test_update_patch_application_(self):
        """Test that updating an application requires all fields"""
        # Create a test application with all necessary fields filled
        application = Application.objects.create(
            amount=2000.00,
            term=24,
            deceased=Deceased.objects.create(first_name='John', last_name='Doe'),

            user=self.user,
        )

        data = {
            'amount': '2001.00'}

        url = get_detail_url(application_id=application.id)
        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

    def test_update_application_success(self):
        """Test that updating an application succeeds"""
        # Create a test application with all necessary fields filled
        application = Application.objects.create(
            amount=2000.00,
            term=24,
            deceased=Deceased.objects.create(
                first_name='John',
                last_name='Doe'
            ),
            user=self.user,
        )

        new_data = {
            'amount': '3000.00',
            'term': 36,
            'deceased': {
                'first_name': 'Jane',
                'last_name': 'Doe'
            },
            'dispute': {
                'details': 'Updated details'
            },
            'applicants': [
                {
                    'title': 'Mrs',
                    'first_name': 'Jane',
                    'last_name': 'Doe',
                    'pps_number': '7654321AG'
                }
            ],
            'estates': [
                {
                    'description': 'Updated estate',
                    'value': '30000.00'
                }
            ],
        }

        url = get_detail_url(application_id=application.id)
        response = self.client.put(url, new_data, format='json')

        # Check that status of the response is 200
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Fetch the updated application from the database
        application.refresh_from_db()

        # Check if fields have been updated
        self.assertEqual(application.amount, Decimal(new_data['amount']))
        self.assertEqual(application.term, new_data['term'])
        self.assertEqual(application.deceased.first_name, new_data['deceased']['first_name'])

        # Check event created
        events = Event.objects.all()
        event = events[0]
        self.assertEqual(events.count(), 1)
        self.assertEqual(event.application, application)
        self.assertEqual(event.user, str(self.user))
        self.assertIsNotNone(event.request_id)
        self.assertEqual(event.method, 'PUT')
        self.assertEqual(event.path, get_detail_url(application_id=application.id))
        self.assertEqual(event.body, json.dumps(new_data))
        self.assertFalse(event.is_error)
        self.assertTrue(event.is_notification)
        self.assertFalse(event.is_staff)

    def test_delete_application(self):
        """Test that application deletion works"""
        # Create a test application with all necessary fields filled
        application = Application.objects.create(
            amount=2000.00,
            term=24,
            deceased=Deceased.objects.create(first_name='John', last_name='Doe'),
            user=self.user,
        )

        url = get_detail_url(application_id=application.id)

        # Check that the application exists before deletion
        self.assertTrue(Application.objects.filter(id=application.id).exists())

        response = self.client.delete(url)

        # Check response status code
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Check that the application no longer exists after deletion
        self.assertFalse(Application.objects.filter(id=application.id).exists())

        # Check event created
        events = Event.objects.all()
        event = events[0]
        self.assertEqual(events.count(), 1)
        self.assertEqual(event.application, None)
        self.assertEqual(event.user, str(self.user))
        self.assertIsNotNone(event.request_id)
        self.assertEqual(event.method, 'DELETE')
        self.assertEqual(event.path, get_detail_url(application_id=application.id))
        self.assertFalse(event.is_error)
        self.assertTrue(event.is_notification)
        self.assertFalse(event.is_staff)


from copy import deepcopy


class ApplicationUpdateTests(APITestCase):
    """Testing individual field update for Applications"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(email='test@example.com', password='testpassword')
        self.client.force_authenticate(self.user)

        self.deceased = Deceased.objects.create(first_name='John', last_name='Doe')
        self.dispute = Dispute.objects.create(details='Some details')
        self.rejection_reason = RejectionReason.objects.create(reason_text='Some reason')

        self.application = Application.objects.create(
            amount=2000.00,
            term=24,
            deceased=self.deceased,
            dispute=self.dispute,
            approved=False,
            last_updated_by=None,
            undertaking_ready=False,
            loan_agreement_ready=False,
            assigned_to=None,
            is_rejected=False,
            rejected_reason=None,
            rejected_date=None,
            user=self.user
        )

        self.url = get_detail_url(application_id=self.application.id)

    def refresh_application(self):
        """Refresh the application instance to get updated values from DB"""
        self.application.refresh_from_db()

    def assertOtherFieldsUnchanged(self, old_instance, updated_field_names):
        new_instance = deepcopy(self.application)
        self.refresh_application()

        for field in old_instance._meta.fields:
            if field.name not in updated_field_names:
                self.assertEqual(getattr(old_instance, field.name), getattr(new_instance, field.name))

    # Test 'amount' field
    def test_update_amount(self):
        data = {'amount': '3000.00'}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()
        self.assertEqual(str(self.application.amount), data['amount'])

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['amount', 'last_updated_by'])

    # Test 'term' field
    def test_update_term(self):
        data = {'term': 30}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()
        self.assertEqual(self.application.term, data['term'])

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['term', 'last_updated_by'])

    # Test 'approved' field
    def test_update_approved_doesnt_work(self):
        data = {'approved': True}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['last_updated_by'])

    # Test 'undertaking_ready' field
    def test_update_undertaking_ready_not_changed(self):
        data = {'undertaking_ready': True}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['last_updated_by'])

    # Test 'loan_agreement_ready' field
    def test_update_loan_agreement_ready_not_changed(self):
        data = {'loan_agreement_ready': True}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')

        # Check the field has been updated.
        self.refresh_application()

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['last_updated_by'])

    # Test 'is_rejected' field
    def test_update_is_rejected(self):
        data = {'is_rejected': True}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['last_updated_by'])

    # Test 'rejected_reason' field
    def test_update_rejected_reason_not_working(self):
        data = {'rejected_reason': self.rejection_reason.id}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['last_updated_by'])

    # Test 'rejected_date' field
    def test_update_rejected_date(self):
        data = {'rejected_date': "2024-01-01"}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['last_updated_by'])

    #
    def test_update_deceased(self):
        data = {
            "deceased": {
                "first_name": "Jane",
                "last_name": "Doe",
            }
        }

        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()
        self.assertEqual(self.application.deceased.first_name, data["deceased"]['first_name'])
        self.assertEqual(self.application.deceased.last_name, data["deceased"]['last_name'])

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['deceased', 'last_updated_by'])

        # Checking if deceased is updated not created new one and assigned
        self.assertEqual(self.application.deceased.id, self.deceased.id)
        dec = Deceased.objects.all()
        self.assertEqual(dec.count(), 1)

    # Test 'dispute' field
    def test_update_dispute(self):
        data = {
            "dispute": {
                "details": "New dispute"
            }
        }

        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()
        self.assertEqual(self.application.dispute.details, data["dispute"]['details'])

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['dispute', 'last_updated_by'])

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['deceased', 'last_updated_by'])

        # Checking if dispute is updated not created new one and assigned
        self.assertEqual(self.application.dispute.id, self.dispute.id)
        dis = Dispute.objects.all()
        self.assertEqual(dis.count(), 1)
