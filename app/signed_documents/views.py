import json
from hashlib import sha256

from PyPDF2.errors import PdfReadError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, OpenApiExample
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404

from agents_loan.permissions import IsStaff
from core.models import Application, Document, SignedDocumentLog, Notification
from .helpers import get_geolocation, get_proxy_info
from .serializers import SignedDocumentSerializer, SignedDocumentLogSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.forms.models import model_to_dict
from django.db import transaction

import requests
import os

from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.constants import UserAccessPermissions
from io import BytesIO
from datetime import datetime
from django.core.files.base import File
import base64
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


def get_client_ip(request):
    """Retrieve the client's public IP address."""
    # If the frontend passes the IP directly, use that
    client_ip = request.data.get('ip_address')  # Check if IP is sent by the frontend

    if not client_ip:  # Fallback to server-side detection
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.META.get('REMOTE_ADDR')
    return client_ip


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

    @transaction.atomic
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
        # Retrieve document type info
        is_undertaking = request.data.get('is_undertaking', False)
        is_loan_agreement = request.data.get('is_loan_agreement', False)
        # Retrieve the device information (sent from frontend)
        device_info_str = request.data.get('device_info', '{}')  # Get the device info JSON string
        # Parse the device information JSON string into a dictionary
        try:
            device_info = json.loads(device_info_str)
        except json.JSONDecodeError:
            return Response({"error": "Invalid device info format."}, status=status.HTTP_400_BAD_REQUEST)
        user_agent = device_info.get('user_agent', 'Unknown')
        browser_name = device_info.get('browser_name', 'Unknown')
        browser_version = device_info.get('browser_version', 'Unknown')
        os_name = device_info.get('os_name', 'Unknown')
        os_version = device_info.get('os_version', 'Unknown')
        cpu_architecture = device_info.get('cpu_architecture', 'Unknown')
        device_type = device_info.get('device_type', 'Unknown')
        device_model = device_info.get('device_model', 'Unknown')
        device_vendor = device_info.get('device_vendor', 'Unknown')
        screen_resolution = device_info.get('screen_resolution', 'Unknown')

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
        total_pages = len(pdf_reader.pages)

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

                # Define the position for the text below the signature image
                text_x = x_position  # Same X position as the image
                text_y = y_position - 15  # Position text 15 points below the image

                # Add "Signed on" text below the image
                can.setFont("Helvetica", 10)  # Set font and size
                can.drawString(text_x, text_y, f"Signed on: {datetime.now().strftime('%d/%m/%Y')}")  # Display date

                can.save()
                packet.seek(0)

                # Overlay the signature on last page
                if page_num == total_pages - 1:  # Check if it's the last page
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
            '/Title': f'Signed Document for Application ',
            '/Author': request.user.email,
            '/Subject': f"Application id: {application.id}",
            '/Keywords': f"User: {request.user.email}, "
                         f"IP: {get_client_ip(request)}, "
                         f"Hash: {signature_hash}, "
                         f"Solicitor Full Name: {solicitor_full_name}, "
                         f"Confirmation_checked_by_user: {confirmation}, "
                         f"Confirmation Message: {confirmation_message}",
            '/CreationDate': datetime.now().strftime("D:%Y%m%d%H%M%S"),
            '/ModDate': datetime.now().strftime("D:%Y%m%d%H%M%S"),
        }
        pdf_writer.add_metadata(metadata)

        pdf_writer.encrypt(user_password="", owner_pwd=None, permissions_flag=UserAccessPermissions.PRINT,
                           use_128bit=True)

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
            is_undertaking=True if is_undertaking == "true" else False,
            is_loan_agreement=True if is_loan_agreement == "true" else False,
        )

        # print(f"Created Document: {model_to_dict(signed_document)}")  # Debug: Full object details

        # Capture metadata for logging
        user = request.user
        ip_address = get_client_ip(request)
        geolocation_data = get_geolocation(ip_address)
        proxy_data = get_proxy_info(ip_address)

        # Create a log entry for the signed document with geolocation data
        signed_document_log = SignedDocumentLog.objects.create(
            user=request.user,
            application=application,
            ip_address=ip_address,
            signature_hash=signature_hash,
            file_path=signed_document.document.name,
            signing_user_email=request.user.email,
            confirmation_message=confirmation_message,
            solicitor_full_name=solicitor_full_name,
            confirmation_checked_by_user=confirmation,
            signature_image_base64=signature_base64,
            # geo_data_info
            country=geolocation_data.get("country") if geolocation_data else None,
            country_code=geolocation_data.get("country_code") if geolocation_data else None,  # Correct reference
            region=geolocation_data.get("region") if geolocation_data else None,
            region_name=geolocation_data.get("region_name") if geolocation_data else None,  # Correct reference
            city=geolocation_data.get("city") if geolocation_data else None,
            zip=geolocation_data.get("zip") if geolocation_data else None,  # Correct reference
            latitude=geolocation_data.get("latitude") if geolocation_data else None,  # Correct reference
            longitude=geolocation_data.get("longitude") if geolocation_data else None,  # Correct reference
            timezone=geolocation_data.get("timezone") if geolocation_data else None,
            isp=geolocation_data.get("isp") if geolocation_data else None,
            org=geolocation_data.get("org") if geolocation_data else None,
            as_number=geolocation_data.get("as_number") if geolocation_data else None,  # Correct reference
            # Proxy/VPN details
            is_proxy=proxy_data.get("is_proxy") if proxy_data else False,
            type=proxy_data.get("proxy_type") if proxy_data else None,
            proxy_provider=proxy_data.get("proxy_provider") if proxy_data else None,
            # Device Info
            device_user_agent=user_agent,
            device_browser_name=browser_name,
            device_browser_version=browser_version,
            device_os_name=os_name,
            device_os_version=os_version,
            device_cpu_architecture=cpu_architecture,
            device_type=device_type,
            device_model=device_model,
            device_vendor=device_vendor,
            device_screen_resolution=screen_resolution,
        )

        # print(f"Created SignedDocumentLog: {model_to_dict(signed_document_log)}")  # Debug: Full log details

        # send notification to users
        notification = Notification.objects.create(
            recipient=application.assigned_to,
            text='Signed document uploaded',
            seen=False,
            created_by=self.request.user,
            application=application
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'broadcast',
            {
                'type': 'notification',
                'message': notification.text,
                'recipient': notification.recipient.email if notification.recipient else None,
                'notification_id': notification.id,
                'application_id': application.id,
                'seen': notification.seen,
                'country': application.user.country,
            }
        )

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
    queryset = SignedDocumentLog.objects.all().order_by('-timestamp')
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
        return SignedDocumentLog.objects.filter(application_id=application_id).order_by("-timestamp")


@extend_schema_view(
    get=extend_schema(
        summary='Retrieve Signed Document Log by File Path',
        description='Retrieve a single signed document log based on the last part of the file path (guid.pdf).',
        tags=['signed_documents'],

        responses={200: SignedDocumentLogSerializer, 404: OpenApiTypes.OBJECT},
    )
)
class SignedDocumentLogByFilePathView(RetrieveAPIView):
    """Retrieve a SignedDocumentLog entry by file name."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]
    queryset = SignedDocumentLog.objects.all()
    serializer_class = SignedDocumentLogSerializer
    lookup_field = 'file_path'  # Set the field to match with the file_name from the URL

    def get_object(self):
        """Override to fetch the object based on the file name in the URL."""
        file_name = self.kwargs['file_name']  # Capture the file_name from the URL
        # Filter to find the SignedDocumentLog by file path using just the file name
        return SignedDocumentLog.objects.get(file_path__endswith=file_name)
