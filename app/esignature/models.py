# esignature/models.py
from django.db import models

from django.core.validators import MaxValueValidator, MinValueValidator
import uuid

from core.models import Document, User


class SignatureDocument(models.Model):
    """
    Main document that has been configured for e-signature.
    Links to your existing Document model without modifying it.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('ready_for_signing', 'Ready for Signing'),
        ('partially_signed', 'Partially Signed'),
        ('fully_signed', 'Fully Signed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Link to your existing Document model (adjust the path as needed)
    source_document = models.OneToOneField(
        Document,  # Update this path to match your Document model
        on_delete=models.CASCADE,
        related_name='signature_document'
    )

    # Basic document info
    document_name = models.CharField(max_length=255)
    application_id = models.CharField(max_length=100)

    # PDF settings from your frontend
    total_pages = models.PositiveIntegerField()
    pdf_scale = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(5.0)]
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Who created this signature document
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_signature_documents'
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Signature Document"
        verbose_name_plural = "Signature Documents"

    def __str__(self):
        return f"{self.document_name} - {self.application_id}"

    @property
    def is_fully_signed(self):
        """Check if all required fields are signed"""
        total_required = self.signature_fields.filter(required=True).count()
        signed_required = self.signature_fields.filter(
            required=True,
            is_signed=True
        ).count()
        return total_required > 0 and total_required == signed_required

    @property
    def signing_progress(self):
        """Return signing progress as percentage"""
        total_required = self.signature_fields.filter(required=True).count()
        if total_required == 0:
            return 100
        signed_required = self.signature_fields.filter(
            required=True,
            is_signed=True
        ).count()
        return int((signed_required / total_required) * 100)


class DocumentSigner(models.Model):
    """
    Person who needs to sign the document.
    Handles applicants, solicitors, and custom signers from your frontend.
    """
    SIGNER_TYPE_CHOICES = [
        ('applicant', 'Applicant'),
        ('solicitor', 'Solicitor'),
        ('custom', 'Custom Signer'),
    ]

    ACCESS_METHOD_CHOICES = [
        ('portal', 'Portal Access'),
        ('email', 'Email Link'),
        ('in_person', 'In-Person Signing'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signature_document = models.ForeignKey(
        SignatureDocument,
        on_delete=models.CASCADE,
        related_name='signers'
    )

    # Basic signer info
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    signer_type = models.CharField(max_length=20, choices=SIGNER_TYPE_CHOICES)
    access_method = models.CharField(max_length=20, choices=ACCESS_METHOD_CHOICES)

    # Links to your existing models (stored as strings for flexibility)
    applicant_id = models.CharField(max_length=100, blank=True, null=True)
    solicitor_id = models.CharField(max_length=100, blank=True, null=True)
    solicitor_email = models.EmailField(blank=True, null=True)

    # Custom signer specific
    role = models.CharField(max_length=255, blank=True, null=True)  # "Witness 1", etc.

    # Visual settings from your frontend
    color = models.CharField(max_length=7, default='#6366f1')  # Hex color

    # Signing status
    has_signed = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)
    signing_order = models.PositiveIntegerField(default=1)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['signing_order', 'name']
        verbose_name = "Document Signer"
        verbose_name_plural = "Document Signers"

    def __str__(self):
        return f"{self.name} ({self.get_signer_type_display()}) - {self.signature_document.document_name}"

    @property
    def signing_progress(self):
        """Return this signer's progress as percentage"""
        total = self.signature_fields.count()
        if total == 0:
            return 100
        completed = self.signature_fields.filter(is_signed=True).count()
        return int((completed / total) * 100)


class SignatureField(models.Model):
    """
    Individual signature field placed on the document.
    Stores all the position and type data from your frontend.
    """
    FIELD_TYPE_CHOICES = [
        ('signature', 'Signature'),
        ('initials', 'Initials'),
        ('name', 'Name'),
        ('textfield', 'Text Field'),
        ('dateSigned', 'Date Signed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signature_document = models.ForeignKey(
        SignatureDocument,
        on_delete=models.CASCADE,
        related_name='signature_fields'
    )
    signer = models.ForeignKey(
        DocumentSigner,
        on_delete=models.CASCADE,
        related_name='signature_fields'
    )

    # Field configuration from your frontend
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    required = models.BooleanField(default=True)
    placeholder = models.CharField(max_length=255, blank=True)
    is_auto_fill = models.BooleanField(default=False)  # For date fields, etc.

    # Position and size on PDF (exactly like your frontend)
    page_number = models.PositiveIntegerField()
    x_position = models.FloatField()  # X coordinate
    y_position = models.FloatField()  # Y coordinate
    width = models.FloatField()
    height = models.FloatField()

    # Signing data
    is_signed = models.BooleanField(default=False)
    signed_value = models.TextField(blank=True, null=True)
    signed_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['page_number', 'y_position', 'x_position']
        verbose_name = "Signature Field"
        verbose_name_plural = "Signature Fields"

    def __str__(self):
        return f"{self.get_field_type_display()} - {self.signer.name} (Page {self.page_number})"
