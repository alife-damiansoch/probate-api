# communications/views.py
import os
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
from core.models import EmailLog
from .serializers import SendEmailSerializer, EmailLogSerializer
from .utils import send_email_f


# Custom ViewSet with only the 'list' and 'send_email' actions
@extend_schema_view(
    list=extend_schema(
        summary='List all Emails',
        description='Returns a list of all sent and received emails, including metadata like sender, recipient, subject, and message content.',
        tags=['communications'],
    ),
    send_email=extend_schema(
        summary='Send an Email',
        description='Sends an email using the provided sender, recipient, subject, and message. Returns a confirmation message on success.',
        tags=['communications'],
        request=SendEmailSerializer,
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

    @action(detail=False, methods=['post'], serializer_class=SendEmailSerializer)
    def send_email(self, request):
        """
        Custom action to send an email.
        """
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Extract data from the serializer
        sender = serializer.validated_data['sender']
        recipient = serializer.validated_data['recipient']
        subject = serializer.validated_data['subject']
        message = serializer.validated_data['message']
        attachments = serializer.validated_data.get('attachments', [])

        # Call the send_email function with HTML support and attachments
        send_email_f(sender, recipient, subject, message, attachments=attachments)

        return Response({"message": "Email sent successfully."}, status=status.HTTP_200_OK)


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
