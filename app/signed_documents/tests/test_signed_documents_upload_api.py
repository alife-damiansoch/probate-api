from io import BytesIO

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from core.models import Application, Document, SignedDocumentLog

import tempfile
import os
from hashlib import sha256

from reportlab.pdfgen import canvas

import base64
from PIL import Image, ImageDraw, ImageFont

from datetime import datetime


# Helper function to create test data
def create_application(user, **params):
    """Create and return a new application object."""
    defaults = {
        'amount': 1000.00,
        'term': 12,
    }
    defaults.update(params)
    application = Application.objects.create(user=user, **defaults)
    return application


def get_signed_document_upload_url(application_id):
    """Return the URL for signed document upload."""
    return reverse('signed_documents:signed_document_upload', args=[application_id])


def generate_sample_signature():
    """Generate a more realistic signature-like image with some text."""
    image = Image.new('RGB', (300, 100), color='white')
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except IOError:
        font = ImageFont.load_default()

    draw.text((50, 30), "John Doe", fill='black', font=font)

    image_stream = BytesIO()
    image.save(image_stream, format='PNG')
    image_stream.seek(0)

    image_base64 = base64.b64encode(image_stream.read()).decode('utf-8')
    return f"data:image/png;base64,{image_base64}"


class SignedDocumentUploadTest(TestCase):
    """Test suite for signed document upload functionality."""

    def setUp(self):
        """Set up the test environment."""
        self.user = get_user_model().objects.create_user(
            email='testuser@example.com',
            password='testpass123'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.application = create_application(user=self.user)
        self.mock_client_ip = "192.168.1.1"  # Define a mock IP for the client
        self.server_ip = "127.0.0.1"  # Fallback IP if no `HTTP_X_FORWARDED_FOR` is provided

    def tearDown(self):
        """Clean up any created files."""
        for document in self.application.documents.all():
            if os.path.exists(document.document.path):
                os.remove(document.document.path)
        self.application.documents.all().delete()

    def test_upload_signed_document(self):
        """Test uploading a signed document successfully."""
        url = get_signed_document_upload_url(application_id=self.application.id)

        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        c = canvas.Canvas(temp_file.name)
        c.drawString(100, 750, "This is a test PDF for signed document upload.")
        c.showPage()
        c.save()

        with open(temp_file.name, 'rb') as f:
            file_content = f.read()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            combined_content = file_content + timestamp.encode()
        signature_hash = sha256(combined_content).hexdigest()

        sample_signature = generate_sample_signature()
        confirmation_message = "Test confirmation message."
        solicitor_full_name = "John Doe"

        temp_file.seek(0)  # Reset the file pointer for uploading
        response = self.client.post(
            url,
            {
                'document': temp_file,
                'signature': signature_hash,
                'signature_image': sample_signature,
                'solicitor_full_name': solicitor_full_name,
                'confirmation': 'true',
                'confirmation_message': confirmation_message,
            },
            format='multipart',
            HTTP_X_FORWARDED_FOR=self.mock_client_ip  # Mock the client IP header
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                         f"Unexpected status code: {response.status_code}, Response content: {response.content}")

        self.assertTrue(Document.objects.filter(application=self.application, is_signed=True).exists())

        document = Document.objects.filter(application=self.application, is_signed=True).first()
        self.assertEqual(document.original_name, os.path.basename(temp_file.name))
        self.assertTrue(document.is_signed)

        # Validate log entry creation
        log_entry = SignedDocumentLog.objects.filter(application=self.application,
                                                     signature_hash=signature_hash).first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.application, self.application)
        self.assertEqual(log_entry.signature_hash, signature_hash)
        self.assertEqual(log_entry.solicitor_full_name, solicitor_full_name)
        self.assertEqual(log_entry.confirmation_checked_by_user, True)
        self.assertTrue(log_entry.confirmation_message)
        self.assertEqual(log_entry.ip_address, self.mock_client_ip)  # Check the logged IP address
        self.assertTrue(os.path.exists(document.document.path))

        temp_file.close()
        os.remove(temp_file.name)

    def test_upload_missing_signed_document(self):
        """Test uploading a signed document without providing a file."""
        url = get_signed_document_upload_url(application_id=self.application.id)
        response = self.client.post(url, {'signature': 'test-signature-hash'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('PDF file is required.', response.data['error'])

    def test_upload_signed_document_with_invalid_file(self):
        """Test uploading a non-PDF file as a signed document."""
        url = get_signed_document_upload_url(application_id=self.application.id)

        # Create a temporary non-PDF file for the test
        temp_file = tempfile.NamedTemporaryFile(suffix='.txt', delete=False)
        temp_file.write(b"This is a test text file, not a PDF.")
        temp_file.seek(0)

        response = self.client.post(url, {'document': temp_file, 'signature': 'test-signature-hash'},
                                    format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Uploaded file must be a PDF', response.data['error'])

        temp_file.close()
        os.remove(temp_file.name)

    from reportlab.pdfgen import canvas

    def test_log_created_for_signed_document(self):
        """Test that a SignedDocumentLog entry is created when a signed document is uploaded."""
        url = get_signed_document_upload_url(application_id=self.application.id)

        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        c = canvas.Canvas(temp_file.name)
        c.drawString(100, 750, "This is a test PDF for signed document upload.")
        c.showPage()
        c.save()

        with open(temp_file.name, 'rb') as f:
            file_content = f.read()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            combined_content = file_content + timestamp.encode()
        signature_hash = sha256(combined_content).hexdigest()

        sample_signature = generate_sample_signature()
        confirmation_message = "Test confirmation message."
        solicitor_full_name = "John Doe"

        temp_file.seek(0)
        response = self.client.post(
            url,
            {
                'document': temp_file,
                'signature': signature_hash,
                'signature_image': sample_signature,
                'solicitor_full_name': solicitor_full_name,
                'confirmation': 'true',
                'confirmation_message': confirmation_message,
            },
            format='multipart',
            HTTP_X_FORWARDED_FOR=self.mock_client_ip
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        log_entry = SignedDocumentLog.objects.filter(application=self.application,
                                                     signature_hash=signature_hash).first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.application, self.application)
        self.assertEqual(log_entry.signature_hash, signature_hash)
        self.assertEqual(log_entry.solicitor_full_name, solicitor_full_name)
        self.assertEqual(log_entry.confirmation_checked_by_user, True)
        self.assertEqual(log_entry.ip_address, self.mock_client_ip)  # Check the correct IP address

        temp_file.close()
        os.remove(temp_file.name)

    def test_upload_signed_document_with_forwarded_for_header(self):
        """Test uploading a signed document with `HTTP_X_FORWARDED_FOR` header set."""
        url = get_signed_document_upload_url(application_id=self.application.id)

        temp_file = self._create_test_pdf()
        signature_hash = self._generate_signature_hash(temp_file)
        sample_signature = generate_sample_signature()
        confirmation_message = "Test confirmation message."
        solicitor_full_name = "John Doe"

        temp_file.seek(0)
        response = self.client.post(
            url,
            {
                'document': temp_file,
                'signature': signature_hash,
                'signature_image': sample_signature,
                'solicitor_full_name': solicitor_full_name,
                'confirmation': 'true',
                'confirmation_message': confirmation_message,
            },
            format='multipart',
            HTTP_X_FORWARDED_FOR=self.mock_client_ip  # Mock the client IP header
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        log_entry = SignedDocumentLog.objects.filter(application=self.application,
                                                     signature_hash=signature_hash).first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.ip_address, self.mock_client_ip)

        temp_file.close()
        os.remove(temp_file.name)

    def test_upload_signed_document_without_forwarded_for_header(self):
        """Test uploading a signed document without `HTTP_X_FORWARDED_FOR` header."""
        url = get_signed_document_upload_url(application_id=self.application.id)

        temp_file = self._create_test_pdf()
        signature_hash = self._generate_signature_hash(temp_file)
        sample_signature = generate_sample_signature()
        confirmation_message = "Test confirmation message."
        solicitor_full_name = "John Doe"

        temp_file.seek(0)
        response = self.client.post(
            url,
            {
                'document': temp_file,
                'signature': signature_hash,
                'signature_image': sample_signature,
                'solicitor_full_name': solicitor_full_name,
                'confirmation': 'true',
                'confirmation_message': confirmation_message,
            },
            format='multipart',
            REMOTE_ADDR=self.server_ip  # Set the fallback server IP address
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        log_entry = SignedDocumentLog.objects.filter(application=self.application,
                                                     signature_hash=signature_hash).first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.ip_address, self.server_ip)

        temp_file.close()
        os.remove(temp_file.name)

    def _create_test_pdf(self):
        """Helper method to create a temporary test PDF."""
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        c = canvas.Canvas(temp_file.name)
        c.drawString(100, 750, "This is a test PDF for signed document upload.")
        c.showPage()
        c.save()
        return temp_file

    def _generate_signature_hash(self, temp_file):
        """Helper method to generate a signature hash for a given file."""
        with open(temp_file.name, 'rb') as f:
            file_content = f.read()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            combined_content = file_content + timestamp.encode()
        return sha256(combined_content).hexdigest()
