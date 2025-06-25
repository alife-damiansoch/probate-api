# document_emails/models.py
from django.db import models
from django.contrib.auth import get_user_model
from core.models import Application  # Adjust import path as needed

User = get_user_model()


def get_email_document_file_path(instance, filename):
    """Generate file path for email documents to keep them separate"""
    return f'email_documents/{instance.email_communication.application.id}/{filename}'


class EmailCommunication(models.Model):
    """Parent model to handle email communications with multiple documents"""

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
    ]

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='email_communications'
    )
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=500)
    message = models.TextField()

    # Email status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    # Tracking fields
    sent_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_emails'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Email service tracking
    email_service_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID from email service provider"
    )

    # Optional: Template used
    email_template = models.CharField(
        max_length=100,
        blank=True,
        help_text="Template name used for this email"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Email Communication"
        verbose_name_plural = "Email Communications"

    def __str__(self):
        return f"Email to {self.recipient_email} - App {self.application.id}"


class EmailDocument(models.Model):
    """Documents attached to email communications - separate from main Document model"""

    email_communication = models.ForeignKey(
        EmailCommunication,
        on_delete=models.CASCADE,
        related_name='email_documents'
    )

    # Reference to original document (optional)
    source_document = models.ForeignKey(
        'core.Document',  # Adjust app name as needed
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Original document this email document was copied from"
    )

    # File storage (separate directory)
    document = models.FileField(upload_to=get_email_document_file_path)
    original_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-populate file info
        if self.document and not self.file_size:
            self.file_size = self.document.size

        # Set original name from source document if available
        if self.source_document and not self.original_name:
            self.original_name = self.source_document.original_name
        elif self.document and not self.original_name:
            self.original_name = self.document.name

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Clean up file when deleting
        if self.document:
            self.document.delete()
        super().delete(*args, **kwargs)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Email Document"
        verbose_name_plural = "Email Documents"

    def __str__(self):
        return f"{self.original_name} (Email: {self.email_communication.id})"


class EmailDeliveryLog(models.Model):
    """Track email delivery events"""

    EVENT_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('bounced', 'Bounced'),
        ('spam', 'Marked as Spam'),
        ('unsubscribed', 'Unsubscribed'),
    ]

    email_communication = models.ForeignKey(
        EmailCommunication,
        on_delete=models.CASCADE,
        related_name='delivery_logs'
    )

    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    timestamp = models.DateTimeField()

    # Additional data from email service
    service_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw data from email service webhook"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Email Delivery Log"
        verbose_name_plural = "Email Delivery Logs"
