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
    # Create a blank image with white background
    image = Image.new('RGB', (300, 100), color='white')
    draw = ImageDraw.Draw(image)

    # Set up the font (system-dependent, check the available fonts or use a generic one)
    try:
        # If you have a specific TTF font file, you can use it like this:
        font = ImageFont.truetype("arial.ttf", 36)
    except IOError:
        # Fallback if the TTF file is not found
        font = ImageFont.load_default()

    # Draw a sample signature text
    draw.text((50, 30), "John Doe", fill='black', font=font)

    # Save the image to a BytesIO stream
    image_stream = BytesIO()
    image.save(image_stream, format='PNG')
    image_stream.seek(0)

    # Encode the image in base64
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

    def tearDown(self):
        """Clean up any created files."""
        # print("Skipping document cleanup for debugging.")
        for document in self.application.documents.all():
            if os.path.exists(document.document.path):
                os.remove(document.document.path)
        self.application.documents.all().delete()

    def test_upload_signed_document(self):
        """Test uploading a signed document successfully."""
        url = get_signed_document_upload_url(application_id=self.application.id)

        # Create a valid PDF file using the reportlab library
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        c = canvas.Canvas(temp_file.name)
        c.drawString(100, 750, "This is a test PDF for signed document upload.")
        c.showPage()
        c.save()

        # Create a fake signature hash for the test
        with open(temp_file.name, 'rb') as f:
            file_content = f.read()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # Combine file content and timestamp, then calculate the hash
            combined_content = file_content + timestamp.encode()
        signature_hash = sha256(combined_content).hexdigest()

        # Generate a sample base64-encoded signature image
        sample_signature = generate_sample_signature()

        # Prepare extra data
        confirmation_message = "Test confirmation message."
        solicitor_full_name = "John Doe"

        # Make a POST request to upload the document
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
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                         f"Unexpected status code: {response.status_code}, Response content: {response.content}")

        self.assertTrue(Document.objects.filter(application=self.application, is_signed=True).exists())

        # Validate document metadata
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
        self.assertTrue(log_entry.confirmation_message)  # Check that confirmation message exists and is non-empty
        self.assertTrue(os.path.exists(document.document.path))

        # Clean up temporary file
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

        # Create a temporary PDF file for the test using reportlab
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        c = canvas.Canvas(temp_file.name)
        c.drawString(100, 750, "This is a test PDF for signed document upload.")
        c.showPage()
        c.save()

        # Create a fake signature hash for the test
        with open(temp_file.name, 'rb') as f:
            file_content = f.read()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # Combine file content and timestamp, then calculate the hash
            combined_content = file_content + timestamp.encode()
        signature_hash = sha256(combined_content).hexdigest()

        # Generate a sample base64-encoded signature image
        sample_signature = generate_sample_signature()

        # Prepare extra data
        confirmation_message = "Test confirmation message."
        solicitor_full_name = "John Doe"

        # Make a POST request to upload the document
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
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                         f"Unexpected status code: {response.status_code}, Response content: {response.content}")

        # Check that a log entry has been created
        log_entry = SignedDocumentLog.objects.filter(application=self.application,
                                                     signature_hash=signature_hash).first()
        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.user, self.user)
        self.assertEqual(log_entry.application, self.application)
        self.assertEqual(log_entry.signature_hash, signature_hash)
        self.assertEqual(log_entry.solicitor_full_name, solicitor_full_name)
        self.assertEqual(log_entry.confirmation_checked_by_user, True)
        self.assertTrue(log_entry.confirmation_message)  # Check that confirmation message exists and is non-empty

        # Clean up temporary file
        temp_file.close()
        os.remove(temp_file.name)
