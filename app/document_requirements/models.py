from django.db import models
from django.core.exceptions import ValidationError
from core.models import Application, User, Document


class DocumentType(models.Model):
    """Pre-defined document types (managed in admin only)"""
    SIGNER_CHOICES = [
        ('solicitor', 'Solicitor'),
        ('applicant', 'Applicant'),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, help_text="Description shown to users")
    signature_required = models.BooleanField(default=False)
    who_needs_to_sign = models.CharField(
        max_length=20,
        choices=SIGNER_CHOICES,
        blank=True,
        help_text="Who needs to sign this document (if signature required)"
    )
    order = models.IntegerField(default=0, help_text="Display order")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Document Type"
        verbose_name_plural = "Document Types"

    def __str__(self):
        return self.name

    def clean(self):
        if self.signature_required and not self.who_needs_to_sign:
            raise ValidationError("If signature is required, must specify who needs to sign")


class ApplicationDocumentRequirement(models.Model):
    """Which documents are required for specific application"""
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='document_requirements'
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who added this requirement"
    )

    class Meta:
        unique_together = ['application', 'document_type']
        verbose_name = "Application Document Requirement"
        verbose_name_plural = "Application Document Requirements"
        ordering = ['document_type__order', 'document_type__name']

    def __str__(self):
        return f"{self.application.id} - {self.document_type.name}"

    @property
    def is_uploaded(self):
        """Check if this requirement has been fulfilled"""
        return self.application.documents.filter(
            document_type_requirement=self
        ).exists()

    @property
    def uploaded_document(self):
        """Get the uploaded document for this requirement"""
        try:
            return self.application.documents.get(document_type_requirement=self)
        except Document.DoesNotExist:
            return None
