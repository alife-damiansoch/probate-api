"""
Test agents_application api
"""
import json
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.forms import model_to_dict
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST
from rest_framework.test import APIClient, APITestCase
from rest_framework.authtoken.models import Token

from agents_loan.serializers import AgentApplicationSerializer
from core.models import (Application, Deceased, Document, User, Event, Dispute, Estate, Applicant, Team)

from agents_loan import serializers

from decimal import Decimal

from reportlab.pdfgen import canvas

import tempfile
import os


def get_detail_url(application_id):
    """create the detail url"""
    return reverse('agents_loan:agent_application-detail', args=[application_id])


def get_document_upload_url(application_id):
    return reverse('agents_loan:agent_application-upload-document', args=[application_id])


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
    """Unauthenticated and non_staff API tests"""

    def setUp(self):
        self.client = APIClient()
        self.APPLICATIONS_URL = reverse('agents_loan:agent_application-list')

    def test_authentication_required(self):
        """Test that authentication is required"""
        response = self.client.get(self.APPLICATIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_non_staff_requests_returns_error(self):
        """Test that authentication is required for non-staff users"""
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.APPLICATIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PrivateTestApplicationAPI(APITestCase):
    """Unauthenticated API tests"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
            is_staff=True,
            country="IE",
            phone_number="+353861111111",
        )
        self.user.teams.add(Team.objects.create(name="ie_team"))
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.APPLICATIONS_URL = reverse('agents_loan:agent_application-list')

    def create_applicant(self, application, first_name, last_name, pps_number):
        """Helper function to create an applicant"""
        return Applicant.objects.create(
            application=application,
            first_name=first_name,
            last_name=last_name,
            pps_number=pps_number
        )

    def test_retrieve_applications(self):
        """Test retrieving all applications"""

        user1 = get_user_model().objects.create_user(
            email='test1@example.com',
            password='testpass123',
            country="IE"
        )
        user2 = get_user_model().objects.create_user(
            email='test2@example.com',
            password='testpass123',
            country="IE"
        )

        app1 = create_application(user=self.user)
        app2 = create_application(user=self.user)

        app3 = create_application(user=user1)  # Create application with 'user1'
        app4 = create_application(user=user2)  # Create application with 'user2'

        app5 = create_application(self.user)

        response = self.client.get(self.APPLICATIONS_URL)

        applications = Application.objects.all().order_by('-id')

        self.assertIn(app1, applications)

        self.assertIn(app2, applications)
        self.assertIn(app3, applications)
        self.assertIn(app4, applications)
        self.assertIn(app5, applications)

        serializer = serializers.AgentApplicationSerializer(applications, many=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], serializer.data)

    def test_receive_application_details(self):
        """test recieving details of an application"""
        application = create_application(user=self.user)
        url = get_detail_url(application.id)
        response = self.client.get(url)
        serializer = serializers.AgentApplicationDetailSerializer(application)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)
        self.assertEqual(response.data['id'], application.id)

    # def test_create_application_requires_all_fields(self):
    #     """Test that an application requires all fields"""
    #     data = {
    #         'amount': '2000.00',
    #         'term': 24,
    #         'deceased': {
    #             'first_name': 'John',
    #             'last_name': 'Doe'
    #         },
    #         'dispute': {
    #             'details': 'Some details'
    #         },
    #         'applicants': [
    #             {
    #                 'title': 'Mr',
    #                 'first_name': 'John',
    #                 'last_name': 'Doe',
    #                 'pps_number': '1234567AG'
    #             }
    #         ],
    #         'estates': [
    #             {
    #                 'description': 'Some estate',
    #                 'value': '20000.00'
    #             }
    #         ],
    #     }
    #
    #     for key in ['amount', 'term', 'deceased', 'dispute', 'applicants', 'estates']:
    #         modified_data = {k: v for k, v in data.items() if k != key}
    #         response = self.client.post(self.APPLICATIONS_URL, modified_data, format='json')
    #         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, msg=f"{key} not provided in data")
    #
    # def test_create_all_fields_application(self):
    #     """Test creating a new application with all fields"""
    #     data = {
    #         'amount': '2000.00',
    #         'term': 24,
    #         'deceased': {
    #             'first_name': 'John',
    #             'last_name': 'Doe'
    #         },
    #         'dispute': {
    #             'details': 'Some details'
    #         },
    #         'applicants': [
    #             {
    #                 'title': 'Mr',
    #                 'first_name': 'John',
    #                 'last_name': 'Doe',
    #                 'pps_number': '1234567AG'
    #             }
    #         ],
    #         'estates': [
    #             {
    #                 'description': 'Some estate',
    #                 'value': '20000.00'
    #             }
    #         ],
    #     }
    #
    #     response = self.client.post(self.APPLICATIONS_URL, data, format='json')
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED, msg=response.data)
    #
    #     application = Application.objects.get(id=response.data['id'])
    #
    #     self.assertEqual(application.amount, Decimal(data['amount']))
    #     self.assertEqual(application.term, data['term'])
    #     self.assertEqual(application.user, self.user)
    #     self.assertEqual(application.deceased.first_name, data['deceased']['first_name'])
    #     self.assertEqual(application.deceased.last_name, data['deceased']['last_name'])
    #     self.assertEqual(application.dispute.details, data['dispute']['details'])
    #
    #     # Check that the correct number of applicants and estates were created
    #     self.assertEqual(application.applicants.count(), len(data['applicants']))
    #     self.assertEqual(application.estates.count(), len(data['estates']))
    #
    #     # Check all applicants
    #     for i in range(len(data['applicants'])):
    #         applicant = application.applicants.all()[i]
    #         applicant_data = data['applicants'][i]
    #         self.assertEqual(applicant.title, applicant_data['title'])
    #         self.assertEqual(applicant.first_name, applicant_data['first_name'])
    #         self.assertEqual(applicant.last_name, applicant_data['last_name'])
    #         self.assertEqual(applicant.decrypted_pps, applicant_data['pps_number'])
    #
    #     # Check all estates
    #     for i in range(len(data['estates'])):
    #         estate = application.estates.all()[i]
    #         estate_data = data['estates'][i]
    #         self.assertEqual(estate.description, estate_data['description'])
    #         self.assertEqual(estate.value, Decimal(estate_data['value']))
    #
    #     # Check event created
    #     events = Event.objects.all()
    #     event = events[0]
    #     self.assertEqual(events.count(), 1)
    #     self.assertEqual(event.application, application)
    #     self.assertEqual(event.user, str(self.user))
    #     self.assertIsNotNone(event.request_id)
    #     self.assertEqual(event.method, 'POST')
    #     self.assertEqual(event.path, self.APPLICATIONS_URL)
    #     self.assertEqual(event.body, json.dumps(data))
    #     self.assertFalse(event.is_error)
    #     self.assertTrue(event.is_notification)
    #     self.assertTrue(event.is_staff)

    def test_update_application_requires_all_fields(self):
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
        # Clear all existing events
        Event.objects.all().delete()

        for key in ['amount', 'term', 'deceased', 'dispute', 'applicants', 'estates']:
            modified_data = {k: v for k, v in data.items() if k != key}
            url = get_detail_url(application_id=application.id)
            response = self.client.put(url, modified_data, format='json')

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, msg=f"{key} not provided in data")

    def test_update_put_application_success(self):
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
        self.assertTrue(event.is_staff)

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
        if response.status_code != status.HTTP_204_NO_CONTENT:
            print(f"Response status code: {response.status_code}")
            print(f"Response data: {response.data}")

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
        self.assertTrue(event.is_staff)

    def test_rejecting_the_application(self):
        """test rejecting the application"""
        app = Application.objects.create(
            amount=2000.00,
            term=24,
            deceased=Deceased.objects.create(first_name='John', last_name='Doe'),
            dispute=Dispute.objects.create(details='Some details'),
            user=self.user,
        )

        application = self.client.get(get_detail_url(application_id=app.id))
        original_data = application.data.copy()

        # Update the fields
        updated_data = application.data.copy()
        updated_data['is_rejected'] = True
        updated_data['rejected_date'] = timezone.now().date().isoformat()
        updated_data['rejected_reason'] = "test rejection"

        response = self.client.put(get_detail_url(application_id=app.id), updated_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK, f"error: {response.data}")

        app.refresh_from_db()

        self.assertEqual(app.is_rejected, True)
        self.assertEqual(app.rejected_reason, "test rejection")
        self.assertEqual(app.rejected_date, timezone.now().date())

        # Check that all other fields have not changed
        response = self.client.get(get_detail_url(application_id=app.id))
        final_data = response.data
        for field in original_data:
            if field not in ['is_rejected', 'rejected_date', 'rejected_reason', 'last_updated_by',
                             'last_updated_by_email']:
                self.assertEqual(final_data[field], original_data[field], f"Failed on field: {field}")


class ApplicationUpdateTests(APITestCase):
    """Testing individual field update for Applications"""

    def setUp(self):
        self.team = Team.objects.create(name='ie_team')
        self.user = get_user_model().objects.create_user(email='test@example.com', password='testpassword',
                                                         is_staff=True, country="IE")
        self.user.teams.add(self.team)
        self.client.force_authenticate(self.user)

        self.deceased = Deceased.objects.create(first_name='John', last_name='Doe')
        self.dispute = Dispute.objects.create(details='Some details')
        self.rejection_reason = 'Some reason'

        self.application = Application.objects.create(
            amount=2000.00,
            term=24,
            deceased=self.deceased,
            dispute=self.dispute,
            approved=False,
            last_updated_by=None,
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
    def test_update_approved(self):
        data = {'approved': True}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()
        self.assertEqual(self.application.approved, data['approved'])

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['approved', 'last_updated_by'])

    # Test 'is_rejected' field
    def test_update_is_rejected(self):
        data = {'is_rejected': True}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()
        self.assertEqual(self.application.is_rejected, data['is_rejected'])

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['is_rejected', 'last_updated_by'])

    # Test 'rejected_reason' field
    def test_update_rejected_reason(self):
        data = {'rejected_reason': self.rejection_reason}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()
        self.assertEqual(self.application.rejected_reason, data['rejected_reason'])
        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['rejected_reason', 'last_updated_by'])

    # Test 'rejected_date' field
    def test_update_rejected_date(self):
        data = {'rejected_date': "2024-01-01"}
        old_instance = deepcopy(self.application)

        response = self.client.patch(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, msg=f"error: {response.data}")

        # Check the field has been updated.
        self.refresh_application()
        self.assertEqual(str(self.application.rejected_date), data['rejected_date'])

        # Check that no other fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['rejected_date', 'last_updated_by'])

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

    def test_update_assigned_to(self):
        # Let's create a new User to assign the application to
        new_user = get_user_model().objects.create_user(
            email='newuser@example.com', password='newpassword', is_staff=True)

        # Prepare the data for the patch request
        data = {'assigned_to': new_user.id}
        old_instance = deepcopy(self.application)

        # Send the patch request
        response = self.client.patch(self.url, data, format='json')

        # Check that the request was successful.
        self.assertEqual(response.status_code, status.HTTP_200_OK,
                         msg=f"Error: {response.data}")

        # Check the user.id is updated.
        self.refresh_application()
        self.assertEqual(self.application.assigned_to.id, new_user.id)

        # Check that only the 'assigned_to' and 'last_updated_by' fields have changed.
        self.assertOtherFieldsUnchanged(old_instance, ['assigned_to', 'last_updated_by'])
