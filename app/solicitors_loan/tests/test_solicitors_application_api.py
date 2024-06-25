"""
Test solicitors_application api
"""
import json

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST
from rest_framework.test import APIClient, APITestCase
from rest_framework.authtoken.models import Token

from core.models import (Application, Deceased, Document, User, Event, )

from solicitors_loan import serializers

from decimal import Decimal

from reportlab.pdfgen import canvas

import tempfile
import os


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
        serializer = serializers.ApplicationSerializer(applications, many=True)
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
        serializer = serializers.ApplicationSerializer(user_applications, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data, serializer.data)

    def test_receive_application_details(self):
        """test recieving details of an application"""
        application = create_application(user=self.user)
        url = get_detail_url(application.id)
        response = self.client.get(url)
        serializer = serializers.ApplicationDetailSerializer(application)
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

        for key in ['amount', 'term', 'deceased', 'dispute', 'applicants', 'estates']:
            modified_data = {k: v for k, v in data.items() if k != key}
            url = get_detail_url(application_id=application.id)
            response = self.client.put(url, modified_data, format='json')

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, msg=f"{key} not provided in data")

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


class DocumentUploadTest(TestCase):
    """Test uploading documents"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.application = create_application(
            user=self.user,
        )

    def tearDown(self):
        self.application.documents.all().delete()

    def test_upload_document_file(self):
        """Test uploading a new document"""
        url = get_document_upload_url(application_id=self.application.id)
        with tempfile.NamedTemporaryFile(suffix='.pdf') as document_file:
            # creating empty pdf
            c = canvas.Canvas(document_file.name)
            c.drawString(100, 750, "Hello, this is a test PDF document")
            c.showPage()
            c.save()

            document_file.seek(0)
            payload = {"document": document_file}
            response = self.client.post(url, data=payload, format='multipart')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertTrue(Document.objects.filter(application=self.application).exists())
        application = Application.objects.get(id=self.application.id)
        self.assertEqual(application.documents.count(), 1)
        document = Document.objects.first()
        self.assertTrue(bool(document.document), "File is not present in document field")
        self.assertTrue(os.path.exists(document.document.path))

    def test_upload_document_file_with_invalid_file(self):
        """Test uploading a new document return error when not document file"""
        url = get_document_upload_url(application_id=self.application.id)
        payload = {"document": "not_a_file"}
        response = self.client.post(url, data=payload, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_document_different_user_returns_error(self):
        """Test deleting a document with different user"""

        user2 = User.objects.create_user(email='test2@example.com', password='testpassword')
        client2 = APIClient()
        client2.force_authenticate(user=user2)
        application1 = Application.objects.create(amount=2000.00,
                                                  term=24,
                                                  deceased=Deceased.objects.create(first_name='John', last_name='Doe'),
                                                  user=self.user, )
        document1 = Document.objects.create(application=application1)
        token2 = Token.objects.create(user=user2)
        delete_url = reverse('solicitors_loan:solicitor-document-delete-view', args=[document1.id])

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token2.key)  # Login as user2
        response = client2.delete(delete_url)

        # Confirm that the response status is HTTP 403 Forbidden
        self.assertEqual(response.status_code, HTTP_403_FORBIDDEN)

        # Confirm that the document still exists.
        self.assertTrue(Document.objects.filter(id=document1.id).exists())

    def test_document_and_file_successfully_deleted(self):
        """
        Test if document and associated file is successfully deleted.
        """

        application1 = Application.objects.create(
            amount=2000.00,
            term=24,
            deceased=Deceased.objects.create(first_name='John', last_name='Doe'),
            user=self.user,
        )
        document1 = Document.objects.create(application=application1)
        document1.document.save('myfile1.txt', ContentFile('hello world'))  # Add this line
        document1.refresh_from_db()

        delete_url = reverse('solicitors_loan:solicitor-document-delete-view', args=[document1.id])

        file_path = document1.document.path
        response = self.client.delete(delete_url)

        self.assertEqual(response.status_code, HTTP_204_NO_CONTENT, f"{response}")
        self.assertFalse(Document.objects.filter(id=document1.id).exists())
        self.assertFalse(os.path.exists(file_path))

    def test_delete_document_approved_application_returns_error(self):
        """
        Test deleting a document associated with an approved application returns a ValidationError.
        """

        application1 = Application.objects.create(
            amount=2000.00,
            term=24,
            deceased=Deceased.objects.create(first_name='John', last_name='Doe'),
            user=self.user,
            approved=True,  # Application is approved
        )

        document1 = Document.objects.create(application=application1)
        document1.document.save('myfile.txt', ContentFile('hello world'))
        document1.refresh_from_db()

        delete_url = reverse('solicitors_loan:solicitor-document-delete-view', args=[document1.id])

        response = self.client.delete(delete_url)

        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)

        # Access the response content
        response_content = json.loads(response.content)

        # Check for your specific error message
        self.assertEqual(response_content[0], "This operation is not allowed on approved applications")

        # Confirm that the document still exists in the database and the file still exists
        self.assertTrue(Document.objects.filter(id=document1.id).exists())
        self.assertTrue(os.path.exists(document1.document.path))
