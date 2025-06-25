# document_emails/services.py
import os
import logging
from typing import Dict, List, Optional
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import EmailCommunication, EmailDocument, EmailDeliveryLog
from communications.utils import send_email_f

logger = logging.getLogger(__name__)


class EmailService:
    """Service class to handle email sending functionality using existing send_email_f function"""

    def __init__(self):
        self.from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@yourcompany.com')

    def send_email_communication(
            self,
            email_communication: EmailCommunication,
            send_immediately: bool = True,
            schedule_for: Optional[timezone.datetime] = None
    ) -> Dict:
        """
        Send an email communication with attachments using your existing send_email_f function

        Returns:
            Dict with 'success' boolean and optional 'message_id' or 'error'
        """
        try:
            if schedule_for and not send_immediately:
                logger.info(f"Email {email_communication.id} scheduled for {schedule_for}")
                return {
                    'success': True,
                    'message': 'Email scheduled successfully',
                    'scheduled_for': schedule_for
                }

            # Prepare email content - message is already processed in serializer
            subject = email_communication.subject
            message = email_communication.message  # Already contains rendered template
            recipient_email = email_communication.recipient_email

            # Determine sender email (use sent_by user's email if available)
            sender_email = self.from_email
            if email_communication.sent_by and email_communication.sent_by.email:
                sender_email = email_communication.sent_by.email

            # Prepare attachments for your existing function
            attachments = self._prepare_attachments_for_send_email_f(email_communication)

            # Use your existing send_email_f function
            result = send_email_f(
                sender="noreply@alife.ie",
                recipient=recipient_email,
                subject=subject,
                message=message,  # This already contains the rendered template
                attachments=attachments,
                application=email_communication.application,
                solicitor_firm=getattr(email_communication.application, 'solicitor_firm', None),
                use_info_email=True,
                save_in_email_log=False
            )

            if result.get('success'):
                self._log_email_event(email_communication, 'sent')

                logger.info(
                    f"Email sent successfully to {recipient_email} for application {email_communication.application.id}")

                return {
                    'success': True,
                    'message_id': self._generate_message_id(email_communication),
                    'attachments_count': len(attachments)
                }
            else:
                logger.error(f"Failed to send email to {recipient_email}: {result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Email sending failed')
                }

        except Exception as e:
            logger.error(f"Error sending email communication {email_communication.id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _prepare_attachments_for_send_email_f(self, email_communication: EmailCommunication) -> List:
        """
        Prepare attachments in the format expected by send_email_f function
        Returns list of file-like objects that send_email_f can process
        """
        attachments = []

        for email_doc in email_communication.email_documents.all():
            try:
                if email_doc.document and os.path.exists(email_doc.document.path):
                    # Create a file-like object that mimics Django's UploadedFile
                    with open(email_doc.document.path, 'rb') as file:
                        file_content = file.read()

                    # Create ContentFile with proper attributes
                    content_file = ContentFile(file_content)
                    content_file.name = email_doc.original_name
                    content_file.content_type = email_doc.mime_type or 'application/octet-stream'

                    attachments.append(content_file)
                    logger.info(f"Prepared attachment: {email_doc.original_name}")
                else:
                    logger.warning(f"Document file not found: {email_doc.original_name}")

            except Exception as e:
                logger.error(f"Error preparing attachment {email_doc.id}: {e}")

        return attachments

    def _generate_message_id(self, email_communication: EmailCommunication) -> str:
        """Generate a unique message ID for tracking"""
        return f"email_{email_communication.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"

    def _log_email_event(self, email_communication: EmailCommunication, event_type: str):
        """Log email events for tracking"""
        EmailDeliveryLog.objects.create(
            email_communication=email_communication,
            event_type=event_type,
            timestamp=timezone.now()
        )


class EmailTemplateService:
    """Service for managing email templates"""

    @staticmethod
    def get_available_templates() -> List[Dict]:
        """Get list of available email templates"""
        return [
            {
                'name': 'application_documents',
                'display_name': 'Application Documents',
                'description': 'Standard template for sending application documents'
            },
            # {
            #     'name': 'loan_agreement',
            #     'display_name': 'Loan Agreement',
            #     'description': 'Template for sending loan agreement documents'
            # },
            # {
            #     'name': 'solicitor_undertaking',
            #     'display_name': 'Solicitor Undertaking',
            #     'description': 'Template for sending solicitor undertaking documents'
            # },
            # {
            #     'name': 'document_request',
            #     'display_name': 'Document Request',
            #     'description': 'Template for requesting additional documents'
            # }
        ]
