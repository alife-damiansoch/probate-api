# document_emails/views.py
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
import os

from core.models import Application  # Adjust import path as needed
from .models import EmailCommunication, EmailDocument
from .serializers import (
    EmailCommunicationListSerializer,
    EmailCommunicationDetailSerializer,
    EmailCommunicationCreateSerializer,
    SendEmailSerializer
)
from .services import EmailService, EmailTemplateService


class EmailCommunicationListView(APIView):
    """List and create email communications for an application"""

    permission_classes = [IsAuthenticated]

    def get_application(self, application_id):
        return get_object_or_404(Application, id=application_id)

    @extend_schema(
        summary="List email communications for an application",
        description="Retrieve all email communications for a specific application",
        responses={200: EmailCommunicationListSerializer(many=True)},
        tags=["email_communications"],
    )
    def get(self, request, application_id):
        application = self.get_application(application_id)

        # Check permissions - staff or application owner
        if not request.user.is_staff and application.user != request.user:
            return Response(
                {"detail": "You don't have permission to view these emails"},
                status=status.HTTP_403_FORBIDDEN
            )

        emails = EmailCommunication.objects.filter(application=application)
        serializer = EmailCommunicationListSerializer(emails, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new email communication",
        description="Create a new email communication with documents for an application",
        request=EmailCommunicationCreateSerializer,
        responses={201: EmailCommunicationDetailSerializer},
        tags=["email_communications"],
    )
    def post(self, request, application_id):
        application = self.get_application(application_id)

        # Check permissions - only staff can create emails
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can create email communications"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Add application to request data
        data = request.data.copy()
        data['application'] = application.id

        serializer = EmailCommunicationCreateSerializer(data=data)
        if serializer.is_valid():
            email_communication = serializer.save(sent_by=request.user)

            # Return detailed view of created email
            detail_serializer = EmailCommunicationDetailSerializer(email_communication)
            return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EmailCommunicationDetailView(APIView):
    """Retrieve, update, or delete a specific email communication"""

    permission_classes = [IsAuthenticated]

    def get_email_communication(self, email_id):
        return get_object_or_404(EmailCommunication, id=email_id)

    @extend_schema(
        summary="Retrieve email communication details",
        description="Get detailed information about a specific email communication",
        responses={200: EmailCommunicationDetailSerializer},
        tags=["email_communications"],
    )
    def get(self, request, email_id):
        email_communication = self.get_email_communication(email_id)

        # Check permissions
        if not request.user.is_staff and email_communication.application.user != request.user:
            return Response(
                {"detail": "You don't have permission to view this email"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = EmailCommunicationDetailSerializer(email_communication)
        return Response(serializer.data)

    @extend_schema(
        summary="Update email communication",
        description="Update an email communication (only if not sent yet)",
        request=EmailCommunicationCreateSerializer,
        responses={200: EmailCommunicationDetailSerializer},
        tags=["email_communications"],
    )
    def patch(self, request, email_id):
        email_communication = self.get_email_communication(email_id)

        # Check permissions - only staff
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can update email communications"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Prevent updating sent emails
        if email_communication.status == 'sent':
            return Response(
                {"detail": "Cannot update already sent emails"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = EmailCommunicationCreateSerializer(
            email_communication,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            email_communication = serializer.save()
            detail_serializer = EmailCommunicationDetailSerializer(email_communication)
            return Response(detail_serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Delete email communication",
        description="Delete an email communication (only if not sent yet)",
        responses={204: None},
        tags=["email_communications"],
    )
    def delete(self, request, email_id):
        email_communication = self.get_email_communication(email_id)

        # Check permissions - only staff
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can delete email communications"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Prevent deleting sent emails
        if email_communication.status == 'sent':
            return Response(
                {"detail": "Cannot delete already sent emails"},
                status=status.HTTP_400_BAD_REQUEST
            )

        email_communication.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SendEmailView(APIView):
    """Send an email communication"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Send email communication",
        description="Send an email communication to the recipient",
        request=SendEmailSerializer,
        responses={200: {"description": "Email sent successfully"}},
        tags=["email_communications"],
    )
    def post(self, request, email_id):
        email_communication = get_object_or_404(EmailCommunication, id=email_id)

        # Check permissions - only staff
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can send emails"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if already sent
        if email_communication.status == 'sent':
            return Response(
                {"detail": "Email has already been sent"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SendEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Use email service to send
            email_service = EmailService()
            result = email_service.send_email_communication(
                email_communication,
                send_immediately=serializer.validated_data.get('send_immediately', True),
                schedule_for=serializer.validated_data.get('schedule_for')
            )

            if result['success']:
                # Update email status
                email_communication.status = 'sent'
                email_communication.sent_at = timezone.now()
                email_communication.email_service_id = result.get('message_id')
                email_communication.save()

                return Response({
                    "detail": "Email sent successfully",
                    "message_id": result.get('message_id')
                })
            else:
                email_communication.status = 'failed'
                email_communication.save()

                return Response(
                    {"detail": f"Failed to send email: {result.get('error')}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            email_communication.status = 'failed'
            email_communication.save()

            return Response(
                {"detail": f"Error sending email: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmailDocumentDownloadView(APIView):
    """Download email document attachments"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Download email document",
        description="Download a document attached to an email communication",
        responses={
            200: {"content": {"application/octet-stream": {}}},
            403: {"description": "Forbidden"},
            404: {"description": "Document not found"}
        },
        tags=["email_communications"],
    )
    def get(self, request, document_id):
        email_document = get_object_or_404(EmailDocument, id=document_id)

        # Check permissions
        if not request.user.is_staff and email_document.email_communication.application.user != request.user:
            return Response(
                {"detail": "You don't have permission to download this document"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            if not email_document.document or not os.path.exists(email_document.document.path):
                return Response(
                    {"detail": "Document file not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            with open(email_document.document.path, 'rb') as file:
                response = HttpResponse(
                    file.read(),
                    content_type=email_document.mime_type or 'application/octet-stream'
                )
                response['Content-Disposition'] = f'attachment; filename="{email_document.original_name}"'
                return response

        except Exception as e:
            return Response(
                {"detail": f"Error downloading document: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmailTemplateListView(APIView):
    """List available email templates"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List available email templates",
        description="Get a list of all available email templates",
        responses={200: {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"}
                }
            }
        }},
        tags=["email_templates"],
    )
    def get(self, request):
        # Only staff can view templates
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can view email templates"},
                status=status.HTTP_403_FORBIDDEN
            )

        templates = EmailTemplateService.get_available_templates()
        return Response(templates)
