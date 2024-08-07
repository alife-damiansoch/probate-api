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
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import (Application, Deceased, Document, User, Event, )

from reportlab.pdfgen import canvas

import tempfile
import os

import shutil


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

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()  # Call the super class method first
        shutil.rmtree('media/uploads/application')

    def test_upload_document_file(self):
        """Test uploading a new document"""
        url = get_document_upload_url(application_id=self.application.id)

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as document_file:
            document_file_name = document_file.name  # We store the name to reopen it later

        c = canvas.Canvas(document_file_name)
        c.drawString(100, 750, "Hello, this is a test PDF document")
        c.showPage()
        c.save()

        with open(document_file_name, 'rb') as document_file:
            payload = {"document": document_file}
            response = self.client.post(url, data=payload, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        os.remove(document_file_name)  # Delete the pdf after the test

        self.assertTrue(Document.objects.filter(application=self.application).exists())
        application = Application.objects.get(id=self.application.id)
        self.assertEqual(application.documents.count(), 1)
        document = Document.objects.first()
        self.assertTrue(bool(document.document), "File is not present in document field")
        self.assertTrue(os.path.exists(document.document.path))

        # Check event created
        events = Event.objects.all()
        event = events[0]
        self.assertEqual(events.count(), 1)
        self.assertEqual(event.application, application)
        self.assertEqual(event.user, str(self.user))
        self.assertIsNotNone(event.request_id)
        self.assertEqual(event.method, 'POST')
        self.assertEqual(event.path, get_document_upload_url(application_id=application.id))
        self.assertFalse(event.is_error)
        self.assertTrue(event.is_notification)
        self.assertFalse(event.is_staff)

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

        # Replaced the token creation
        refresh = RefreshToken.for_user(user2)  # Create a new Refresh Token for user2
        token2 = str(refresh.access_token)  # Here is the string representation of the access token

        delete_url = reverse('solicitors_loan:solicitor-document-delete-view', args=[document1.id])

        client2.credentials(HTTP_AUTHORIZATION='Bearer ' + token2)  # Login as user2
        response = client2.delete(delete_url)

        # Confirm that the response status is HTTP 403 Forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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

        # Check event created
        events = Event.objects.all()
        event = events[0]
        self.assertEqual(events.count(), 1)
        self.assertEqual(event.application, None)
        self.assertEqual(event.user, str(self.user))
        self.assertIsNotNone(event.request_id)
        self.assertEqual(event.method, 'DELETE')
        self.assertEqual(event.path, delete_url)
        self.assertFalse(event.is_error)
        self.assertTrue(event.is_notification)
        self.assertFalse(event.is_staff)
        self.assertEqual(json.loads(event.body), {'message': 'A document was deleted.'})

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
