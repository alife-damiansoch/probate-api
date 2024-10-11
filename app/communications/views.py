# communications/views.py
import os
import uuid

from django.conf import settings
from rest_framework import viewsets
from rest_framework import viewsets, mixins
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes
from rest_framework.views import APIView
from django.http import FileResponse, Http404

from agents_loan.permissions import IsStaff
from core.models import EmailLog, Application
from .serializers import SendEmailSerializerByApplicationId, EmailLogSerializer, SendEmailToRecipientsSerializer, \
    ReplyEmailSerializer
from .utils import send_email_f, fetch_emails


# Custom ViewSet with only the 'list' and 'send_email' actions
@extend_schema_view(
    list=extend_schema(
        summary='List all Emails',
        description='Returns a list of all sent and received emails, including metadata like sender, recipient, subject, and message content.',
        tags=['communications'],
    ),
    send_email_with_application=extend_schema(
        summary='Send an Email',
        description='Sends an email using the provided sender, applicationId, subject, and message. Returns a confirmation message on success.',
        tags=['communications'],
        request=SendEmailSerializerByApplicationId,
        responses={
            200: {
                'description': 'Email sent successfully',
                'type': 'object',
                'properties': {
                    'message': {'type': 'string', 'example': 'Email sent successfully.'}
                }
            },
            400: {
                'description': 'Validation Error',
                'type': 'object',
                'properties': {
                    'error': {'type': 'string', 'example': 'All fields are required.'}
                }
            }
        }
    ),
    send_email_to_recipients=extend_schema(
        summary='Send an Email',
        description='Sends an email using the provided sender, list of recipients, subject, and message. Returns a confirmation message on success.',
        tags=['communications'],
        request=SendEmailToRecipientsSerializer,
        responses={
            200: {
                'description': 'Email sent successfully',
                'type': 'object',
                'properties': {
                    'message': {'type': 'string', 'example': 'Email sent successfully.'}
                }
            },
            400: {
                'description': 'Validation Error',
                'type': 'object',
                'properties': {
                    'error': {'type': 'string', 'example': 'All fields are required.'}
                }
            }
        }
    ),
)
class SendEmailViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    A ViewSet for sending emails and listing all email logs.
    """
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]
    serializer_class = EmailLogSerializer  # Default serializer for the viewset
    queryset = EmailLog.objects.all()  # Queryset for listing email logs

    def list(self, request, *args, **kwargs):
        """
        Override the list method to fetch emails before returning the list of logs.
        """
        # Call the email fetching function
        fetch_emails()

        # After fetching, update the queryset to include new emails
        self.queryset = EmailLog.objects.all().order_by('-created_at')

        # Return the list of email logs as usual
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def send_email_with_application(self, request):
        """
        Custom action to send an email.
        """

        serializer = SendEmailSerializerByApplicationId(data=request.data)

        if not serializer.is_valid():
            print("Error here")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract data from the serializer
        sender = serializer.validated_data['sender']
        subject = serializer.validated_data['subject']
        message = serializer.validated_data['message']
        application_id = serializer.validated_data['application_id']
        attachments = serializer.validated_data.get('attachments', [])

        try:
            # Retrieve the application based on the ID
            application = Application.objects.get(id=application_id)

            # Determine recipient email
            recipient = application.solicitor.own_email if application.solicitor and application.solicitor.own_email else application.user.email

            if not recipient:
                return Response({"error": "No recipient email found for this application."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Call the send_email function with HTML support and attachments
            send_email_f(sender, recipient, subject, message, attachments=attachments)

            return Response({"message": "Email sent successfully."}, status=status.HTTP_200_OK)

        except Application.DoesNotExist:
            return Response({"error": "Application not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], serializer_class=SendEmailToRecipientsSerializer)
    def send_email_to_recipients(self, request):
        """
        Custom action to send an email to a list of recipients.
        """
        serializer = SendEmailToRecipientsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract data from the serializer
        sender = serializer.validated_data['sender']
        subject = serializer.validated_data['subject']
        message = serializer.validated_data['message']
        recipients = serializer.validated_data['recipients']
        attachments = serializer.validated_data.get('attachments', [])

        # Send email to each recipient
        for recipient in recipients:
            send_email_f(sender, recipient, subject, message, attachments=attachments)

        return Response({"message": "Emails sent successfully."}, status=status.HTTP_200_OK)


class AttachmentDownloadView(APIView):
    """
    View to handle downloading attachments based on email ID and unique filename.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(
        summary='Download Email Attachment',
        description='Downloads the specified attachment file from an email based on the email ID and unique filename. Requires authentication.',
        parameters=[
            OpenApiParameter(name='email_id', description='The ID of the email log entry', required=True,
                             type=OpenApiTypes.INT),
            OpenApiParameter(name='filename', description='The unique filename of the attachment', required=True,
                             type=OpenApiTypes.STR),
        ],
        responses={
            200: {
                'description': 'File download successful',
                'content': {'application/octet-stream': {}},  # Response content type for file download
            },
            404: {
                'description': 'File not found or email log entry not found',
                'type': 'object',
                'properties': {
                    'error': {'type': 'string', 'example': 'Attachment not found in this email log entry.'}
                }
            }
        },
        tags=['communications']
    )
    def get(self, request, email_id, filename, *args, **kwargs):
        try:
            email_log = EmailLog.objects.get(id=email_id)

            # Locate the full file path that ends with the provided unique filename
            file_path = next((path for path in email_log.attachments if os.path.basename(path) == filename), None)
            if not file_path:
                raise Http404("Attachment not found in this email log entry.")

            # Serve the file using FileResponse
            return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=filename)

        except EmailLog.DoesNotExist:
            return Response({"error": "Email log entry not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DeleteAttachmentView(APIView):
    """
    View to delete an attachment file from the server based on unique filename.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(
        summary='Delete an Email Attachment',
        description='Deletes the specified attachment file from the server based on the email ID and unique filename. Updates the database accordingly. Requires authentication.',
        parameters=[
            OpenApiParameter(name='email_id', description='The ID of the email log entry', required=True,
                             type=OpenApiTypes.INT),
            OpenApiParameter(name='filename', description='The unique filename of the attachment to delete',
                             required=True, type=OpenApiTypes.STR),
        ],
        responses={
            200: {
                'description': 'Attachment deleted successfully',
                'type': 'object',
                'properties': {
                    'message': {'type': 'string', 'example': 'Attachment deleted successfully.'}
                }
            },
            404: {
                'description': 'Attachment not found or email log entry not found',
                'type': 'object',
                'properties': {
                    'error': {'type': 'string', 'example': 'Attachment not found in this email log entry.'}
                }
            }
        },
        tags=['communications']
    )
    def delete(self, request, email_id, filename, *args, **kwargs):
        try:
            # Fetch the email log entry by ID
            email_log = EmailLog.objects.get(id=email_id)

            # Locate the full file path that ends with the provided unique filename
            file_path = next((path for path in email_log.attachments if os.path.basename(path) == filename), None)
            if not file_path:
                raise Http404("Attachment not found in this email log entry.")

            # Validate the file path and delete the file if it exists
            if os.path.exists(file_path) and os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Attachment {filename} deleted from {file_path}.")
            else:
                raise Http404("Attachment file not found on server.")

            # Remove the file path and corresponding original filename from the EmailLog
            index = email_log.attachments.index(file_path)
            del email_log.attachments[index]
            del email_log.original_filenames[index]
            email_log.save()

            return Response({"message": "Attachment deleted successfully."}, status=status.HTTP_200_OK)

        except EmailLog.DoesNotExist:
            return Response({"error": "Email log entry not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReplyToEmailViewSet(viewsets.GenericViewSet):
    """
    A ViewSet for replying to emails.
    """
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]
    serializer_class = ReplyEmailSerializer

    @extend_schema(
        summary="Reply to an email",
        description="Reply to an existing email using its log ID. The recipient is set to the original sender, and headers are adjusted for tracking.",
        request=ReplyEmailSerializer,
        responses={200: "Reply sent successfully.", 400: "Bad request.", 404: "Original email log not found."},
        tags=['communications'],
    )
    @action(detail=False, methods=['post'])
    def reply_to_email(self, request):
        """
        Custom action to reply to an existing email.
        """
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract data from the serializer
        sender = serializer.validated_data['sender']
        message = serializer.validated_data['message']
        email_log_id = serializer.validated_data['email_log_id']
        attachments = serializer.validated_data.get('attachments', [])

        try:
            # Retrieve the original email log
            original_email = EmailLog.objects.get(id=email_log_id)

            # Use the original email's recipient as the sender for the reply
            recipient = original_email.sender
            subject = f"Re: {original_email.subject}"

            # Call the send_email function and pass the additional headers
            send_email_f(
                sender,
                recipient,
                subject,
                message,
                attachments=attachments,
            )

            return Response({"message": "Reply sent successfully."}, status=status.HTTP_200_OK)

        except EmailLog.DoesNotExist:
            return Response({"error": "Original email log not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
