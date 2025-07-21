# document_emails/serializers.py
from rest_framework import serializers
from .models import EmailCommunication, EmailDocument, EmailDeliveryLog
from django.template.loader import render_to_string
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailDocumentSerializer(serializers.ModelSerializer):
    """Serializer for email documents"""

    class Meta:
        model = EmailDocument
        fields = [
            'id', 'document', 'original_name', 'file_size',
            'mime_type', 'source_document', 'created_at'
        ]
        read_only_fields = ['id', 'file_size', 'mime_type', 'created_at']


class EmailDeliveryLogSerializer(serializers.ModelSerializer):
    """Serializer for delivery logs"""

    class Meta:
        model = EmailDeliveryLog
        fields = ['id', 'event_type', 'timestamp', 'service_data', 'created_at']
        read_only_fields = ['id', 'created_at']


class EmailCommunicationListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing emails"""

    document_count = serializers.SerializerMethodField()

    class Meta:
        model = EmailCommunication
        fields = [
            'id', 'application', 'recipient_email', 'recipient_name',
            'subject', 'status', 'sent_by', 'created_at', 'sent_at',
            'document_count'
        ]
        read_only_fields = ['id', 'created_at']

    def get_document_count(self, obj):
        return obj.email_documents.count()


class EmailCommunicationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer with nested documents and logs"""

    email_documents = EmailDocumentSerializer(many=True, read_only=True)
    delivery_logs = EmailDeliveryLogSerializer(many=True, read_only=True)
    sent_by_name = serializers.CharField(source='sent_by.get_full_name', read_only=True)

    class Meta:
        model = EmailCommunication
        fields = [
            'id', 'application', 'recipient_email', 'recipient_name',
            'subject', 'message', 'status', 'sent_by', 'sent_by_name',
            'created_at', 'sent_at', 'delivered_at', 'email_service_id',
            'email_template', 'email_documents', 'delivery_logs'
        ]
        read_only_fields = [
            'id', 'status', 'sent_by', 'created_at', 'sent_at',
            'delivered_at', 'email_service_id'
        ]


class EmailCommunicationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating email communications"""

    document_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of document IDs to attach to this email"
    )

    # Override message field to make it not required
    message = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = EmailCommunication
        fields = [
            'application', 'recipient_email', 'recipient_name',
            'subject', 'message', 'email_template', 'document_ids'
        ]

    def validate(self, data):
        """Custom validation"""
        email_template = data.get('email_template')
        message = data.get('message', '').strip()

        # If no template and no message, require message
        if not email_template and not message:
            raise serializers.ValidationError({
                'message': 'This field is required when no template is selected.'
            })

        return data

    def validate_document_ids(self, value):
        """Validate that all document IDs exist and belong to the application"""
        if not value:
            return value

        application_id = self.initial_data.get('application')
        if not application_id:
            raise serializers.ValidationError("Application is required when attaching documents")

        # Check if documents exist and belong to the application
        from core.models import Document  # Adjust import
        documents = Document.objects.filter(
            id__in=value,
            application_id=application_id
        )

        if len(documents) != len(value):
            raise serializers.ValidationError("Some documents do not exist or don't belong to this application")

        return value

    def create(self, validated_data):
        document_ids = validated_data.pop('document_ids', [])
        email_template = validated_data.get('email_template')
        message = validated_data.get('message', '').strip()

        # If template is provided and no message, generate from template
        if email_template and not message:
            application = validated_data.get('application')
            try:
                # Get application for template context

                # Create a proper mock email_communication object for template context
                from datetime import datetime
                from django.conf import settings

                mock_email_communication = type('MockEmailComm', (), {
                    'created_at': timezone.now(),
                    'application': application,
                    'recipient_name': validated_data.get('recipient_name', ''),
                })()

                # Build the application URL
                base_url = getattr(settings, 'SOLICITORS_WEBSITE', 'http://localhost:4000/applications/')
                # Ensure the base URL ends with a slash
                if not base_url.endswith('/'):
                    base_url += '/'

                application_url = f"{base_url}{application.id}" if application else base_url

                # Render template to get message content
                template_path = f'email_templates/{email_template}.html'

                print(f"=== TEMPLATE DEBUG ===")
                print(f"Template path: {template_path}")
                print(f"Application ID: {application.id if application else 'None'}")
                print(f"Recipient: {validated_data.get('recipient_name', '')}")
                print(f"Application URL: {application_url}")

                rendered_message = render_to_string(template_path, {
                    'application': application,
                    'recipient_name': validated_data.get('recipient_name', ''),
                    'message': '',  # Keep empty since we're generating full content
                    'email_communication': mock_email_communication,
                    'application_url': application_url,  # Add the application URL to context
                })

                print(f"Rendered message length: {len(rendered_message)}")
                print(f"Rendered message preview: {rendered_message[:200]}...")
                print("=====================")

                # Set the rendered message
                validated_data['message'] = rendered_message
                logger.info(f"Generated message from template: {email_template}")

            except Exception as e:
                print(f"=== TEMPLATE ERROR ===")
                print(f"Error: {str(e)}")
                print(f"Template path attempted: email_templates/{email_template}.html")
                print("=====================")

                logger.error(f"Failed to render template {email_template}: {e}")

                # Fallback message with application link
                base_url = getattr(settings, 'SOLICITORS_WEBSITE', 'http://localhost:4000/applications/')
                if not base_url.endswith('/'):
                    base_url += '/'
                application_url = f"{base_url}{application.id}" if application else base_url

                validated_data['message'] = f"""
                <div style="font-family: Arial, sans-serif; padding: 20px;">
                    <h2>Application Documents</h2>
                    <p>Dear {validated_data.get('recipient_name', '')},</p>
                    <p>Please find attached the documents for your application #{application.id if application else 'N/A'}.</p>

                    <div style="text-align: center; margin: 20px 0; padding: 15px; background-color: #f1f3f4; border-radius: 5px;">
                        <p><strong>Quick Access to Your Application:</strong></p>
                        <a href="{application_url}" style="background-color: #007bff; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                            View Application #{application.id if application else 'N/A'}
                        </a>
                    </div>

                    <p>Best regards,<br>The Application Team</p>
                </div>
                """

        # Create the email communication
        email_communication = EmailCommunication.objects.create(**validated_data)

        # Copy documents to email documents
        if document_ids:
            self._copy_documents_to_email(email_communication, document_ids)

        return email_communication

    def _copy_documents_to_email(self, email_communication, document_ids):
        """Copy original documents to email documents directory"""
        import shutil
        import os
        import mimetypes
        from django.core.files import File
        from core.models import Document

        documents = Document.objects.filter(id__in=document_ids)

        for doc in documents:
            if doc.document and os.path.exists(doc.document.path):
                try:
                    # Get proper filename with extension
                    source_path = doc.document.path
                    original_name = doc.original_name or os.path.basename(source_path)

                    # Ensure filename has extension
                    if not os.path.splitext(original_name)[1]:
                        # Get extension from source file
                        source_ext = os.path.splitext(source_path)[1]
                        if source_ext:
                            original_name += source_ext

                    # Create EmailDocument instance
                    email_doc = EmailDocument(
                        email_communication=email_communication,
                        source_document=doc,
                        original_name=original_name,
                        mime_type=mimetypes.guess_type(original_name)[0] or 'application/octet-stream'
                    )

                    # Copy file
                    with open(source_path, 'rb') as original_file:
                        email_doc.document.save(
                            original_name,
                            File(original_file),
                            save=False
                        )

                    email_doc.save()
                    print(f"Copied: {original_name} -> {email_doc.document.name}")

                except Exception as e:
                    print(f"Error copying document {doc.id}: {e}")


class SendEmailSerializer(serializers.Serializer):
    """Serializer for sending emails"""

    send_immediately = serializers.BooleanField(default=True)
    schedule_for = serializers.DateTimeField(required=False)

    def validate(self, data):
        if not data.get('send_immediately') and not data.get('schedule_for'):
            raise serializers.ValidationError(
                "Must either send immediately or provide schedule_for datetime"
            )
        return data
