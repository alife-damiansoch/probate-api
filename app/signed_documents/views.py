from hashlib import sha256

from PyPDF2.errors import PdfReadError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, OpenApiExample
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404

from agents_loan.permissions import IsStaff
from core.models import Application, Document, SignedDocumentLog
from .serializers import SignedDocumentSerializer, SignedDocumentLogSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.forms.models import model_to_dict

import requests
import os

from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
from datetime import datetime
from django.core.files.base import File
import base64
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


# def get_client_ip(request):
#     """Retrieve the client's IP address from the request."""
#     x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#     if x_forwarded_for:
#         ip = x_forwarded_for.split(',')[0]
#     else:
#         ip = request.META.get('REMOTE_ADDR')
#     return ip
def get_client_ip(request):
    """Retrieve the public IP address of the client using an external API."""
    try:
        # Use a service like ipify to get the public IP address
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx, 5xx)
        public_ip = response.json().get('ip')
        return public_ip
    except (requests.RequestException, ValueError) as e:
        # Fallback to the default REMOTE_ADDR if the public IP lookup fails
        print(f"Public IP lookup failed: {e}")
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


@extend_schema_view(
    post=extend_schema(
        summary='Upload a signed document',
        description='Allows an authenticated user to upload a signed PDF document and a signature image for a specific application. Both the document and the image must be provided as file uploads.',
        tags=['signed_documents'],
        request={
            'multipart/form-data': {
                'document': OpenApiTypes.BINARY,  # File upload for PDF
                'signature_image': OpenApiTypes.BINARY  # File upload for image
            }
        },

        responses={
            201: SignedDocumentSerializer,
            400: OpenApiTypes.OBJECT,  # Expect error response with message key
        }
    )
)
class SignedDocumentUploadView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = SignedDocumentSerializer

    def decode_signature_image(self, signature_base64):
        """Decode a base64 string to a PIL image."""
        format, imgstr = signature_base64.split(';base64,')
        image_data = base64.b64decode(imgstr)
        return Image.open(BytesIO(image_data))

    def post(self, request, application_id):
        try:
            application = Application.objects.get(id=application_id)
        except Application.DoesNotExist:
            raise Http404("Application not found")

        # Retrieve the uploaded PDF and signature image from request
        pdf_file = request.FILES.get('document')
        signature_base64 = request.data.get('signature_image')  # Get signature image base64 string
        solicitor_full_name = request.data.get('solicitor_full_name')  # Extract solicitor's full name
        # Retrieve and convert the confirmation value to a boolean
        confirmation_str = request.data.get('confirmation')
        confirmation = confirmation_str.lower() == 'true' if confirmation_str else False
        confirmation_message = request.data.get('confirmation_message')  # Extract the confirmation message

        if not pdf_file:
            return Response({"error": "PDF file is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not pdf_file.name.lower().endswith('.pdf'):
            return Response({"error": "Uploaded file must be a PDF."}, status=status.HTTP_400_BAD_REQUEST)

        if not signature_base64:
            return Response({"error": "Signature image is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate the signature hash (SHA-256 hash of file content)
        file_content = pdf_file.read()
        # Retrieve the current timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

        # Combine file content and timestamp, then calculate the hash
        combined_content = file_content + timestamp.encode()
        signature_hash = sha256(combined_content).hexdigest()
        pdf_file.seek(0)  # Reset file pointer after reading

        # Validate the PDF file by attempting to read it
        try:
            pdf_reader = PdfReader(pdf_file)
        except Exception:
            return Response({"error": "The uploaded file is not a valid PDF."}, status=status.HTTP_400_BAD_REQUEST)

        # Rewind the file pointer again after PdfReader attempt
        pdf_file.seek(0)

        # Create a PdfWriter to modify the PDF and add metadata
        pdf_writer = PdfWriter()  # Initialize the PdfWriter
        for page_num, page in enumerate(pdf_reader.pages):
            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=A4)

            # Decode and place the signature image onto the PDF
            signature_image = self.decode_signature_image(signature_base64)
            image_width, image_height = signature_image.size

            # Save the decoded image to a temporary file
            signature_filename = f'tmp_signature_{datetime.now().strftime("%Y%m%d%H%M%S")}.png'
            signature_image.save(signature_filename)

            try:
                # Calculate the position for the bottom-left of the page (A4 size: 595.27 x 841.89 points)
                x_position = 50  # 50 points from the left side
                y_position = 50  # 50 points above the bottom edge

                # Draw the signature image on the PDF (adjust size and position as needed)
                can.drawImage(signature_filename, x=x_position, y=y_position, width=image_width / 4,
                              height=image_height / 4)
                can.save()
                packet.seek(0)

                # Overlay the signature on each page
                overlay_pdf = PdfReader(packet)
                page.merge_page(overlay_pdf.pages[0])

                # Add the modified page to the writer
                pdf_writer.add_page(page)
            finally:
                # Remove the temporary file after processing
                if os.path.exists(signature_filename):
                    os.remove(signature_filename)

        # Define metadata to be embedded into the PDF
        metadata = {
            '/Title': f'Signed Document for Application {application.id}',
            '/Author': request.user.email,
            '/Subject': f"Signed by {request.user.email}",
            '/Keywords': f"Application ID: {application.id}, "
                         f"User: {request.user.email}, "
                         f"IP: {get_client_ip(request)}, "
                         f"Hash: {signature_hash}, "
                         f"Solicitor Full Name: {solicitor_full_name}, "
                         f"Confirmation_checked_by_user: {confirmation}, "
                         f"Confirmation Message: {confirmation_message}",
            '/CreationDate': datetime.now().strftime("D:%Y%m%d%H%M%S"),
            '/ModDate': datetime.now().strftime("D:%Y%m%d%H%M%S"),
        }
        pdf_writer.add_metadata(metadata)

        # Save the modified PDF to an in-memory file
        signed_pdf_buffer = BytesIO()
        pdf_writer.write(signed_pdf_buffer)
        signed_pdf_buffer.seek(0)

        # Wrap the BytesIO in a Django File object and assign a name
        pdf_file_to_save = File(signed_pdf_buffer, name=pdf_file.name)

        # Save the modified PDF file in the Document model
        signed_document = Document.objects.create(
            application=application,
            document=pdf_file_to_save,  # Use the File object with a name attribute
            is_signed=True,
            original_name=pdf_file.name,
        )

        print(f"Created Document: {model_to_dict(signed_document)}")  # Debug: Full object details

        # Capture metadata for logging
        user = request.user
        ip_address = get_client_ip(request)

        # Create a log entry for the signed document
        signed_document_log = SignedDocumentLog.objects.create(
            user=user,
            application=application,
            ip_address=ip_address,
            signature_hash=signature_hash,
            file_path=signed_document.document.name,
            signing_user_email=user.email,
            confirmation_message=confirmation_message,  # Add the confirmation message to the log
            solicitor_full_name=solicitor_full_name,  # Store the solicitor's full name
            confirmation_checked_by_user=confirmation,  # Include the confirmation status in the log
        )

        print(f"Created SignedDocumentLog: {model_to_dict(signed_document_log)}")  # Debug: Full log details

        # Return serialized document data
        serializer = self.serializer_class(signed_document)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        summary='List all Signed Document Logs',
        description='Retrieve a list of all signed document logs available in the system. The logs include information such as the user, application ID, IP address, signature hash, and other metadata.',
        tags=['signed_documents'],
        responses={
            200: SignedDocumentLogSerializer(many=True),
            404: OpenApiTypes.OBJECT,
        },
    )
)
class SignedDocumentLogListView(ListAPIView):
    """List all signed document logs."""
    queryset = SignedDocumentLog.objects.all()
    serializer_class = SignedDocumentLogSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]


@extend_schema_view(
    get=extend_schema(
        summary='List Signed Document Logs by Application ID',
        description='Retrieve a list of signed document logs filtered by a specific application ID. Useful for tracking all logs associated with a given application.',
        tags=['signed_documents'],

        responses={
            200: SignedDocumentLogSerializer(many=True),
            404: OpenApiTypes.OBJECT,
        },
    )
)
class SignedDocumentLogByApplicationView(ListAPIView):
    """List signed document logs filtered by application ID."""
    serializer_class = SignedDocumentLogSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]

    def get_queryset(self):
        """Filter logs based on the provided application ID."""
        application_id = self.kwargs['application_id']
        return SignedDocumentLog.objects.filter(application_id=application_id)
