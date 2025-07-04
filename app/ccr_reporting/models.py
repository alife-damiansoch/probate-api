# ccr_reporting/models.py - Enhanced with status management and error tracking
from django.db import models
from django.utils import timezone
from decimal import Decimal
from django.conf import settings


class CCRSubmission(models.Model):
    """Track monthly CCR submissions"""
    SUBMISSION_STATUS = [
        ('PENDING', 'Pending'),
        ('GENERATED', 'Generated'),
        ('UPLOADED', 'Uploaded'),
        ('ACKNOWLEDGED', 'Acknowledged by CCR'),
        ('ERROR', 'Error'),
        ('PARTIAL_ERROR', 'Partial Error'),
    ]

    reference_date = models.DateField(help_text="Month-end date being reported")
    generated_at = models.DateTimeField(auto_now_add=True)
    file_path = models.CharField(max_length=500)
    total_records = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=SUBMISSION_STATUS, default='GENERATED')

    # Status management fields
    status_updated_at = models.DateTimeField(auto_now=True)
    status_updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    # Error tracking
    error_details = models.TextField(blank=True, help_text="Details of any errors encountered")
    ccr_response_file = models.FileField(upload_to='ccr_responses/', blank=True, null=True,
                                         help_text="Response file from CCR system")

    # Test fields for date manipulation
    is_test_submission = models.BooleanField(default=False)
    test_notes = models.TextField(blank=True)

    # File modification tracking
    has_modifications = models.BooleanField(default=False, help_text="File was modified after generation")
    modification_notes = models.TextField(blank=True, help_text="Notes about modifications made")

    class Meta:
        unique_together = ['reference_date']
        ordering = ['-reference_date']

    def __str__(self):
        return f"CCR Submission {self.reference_date} ({self.total_records} records)"

    def can_update_status(self, new_status=None, force_admin=False):
        """
        Check if status can be updated

        Args:
            new_status: The status we want to change to
            force_admin: If True, allows admin override of restrictions
        """
        if force_admin:
            return True

        # Define allowed transitions
        allowed_transitions = {
            'PENDING': ['GENERATED', 'ERROR'],
            'GENERATED': ['UPLOADED', 'ERROR', 'PARTIAL_ERROR'],
            'UPLOADED': ['ACKNOWLEDGED', 'ERROR', 'PARTIAL_ERROR'],
            'ACKNOWLEDGED': ['ERROR', 'PARTIAL_ERROR'],  # Allow if errors discovered later
            'ERROR': ['GENERATED', 'UPLOADED', 'PARTIAL_ERROR'],  # Allow retry
            'PARTIAL_ERROR': ['UPLOADED', 'ACKNOWLEDGED', 'ERROR'],
        }

        if new_status:
            # Check specific transition
            return new_status in allowed_transitions.get(self.status, [])
        else:
            # General check - can this status be updated at all?
            return len(allowed_transitions.get(self.status, [])) > 0


class CCRContractRecord(models.Model):
    """Track which LoanBooks have been reported to CCR"""
    loanbook = models.OneToOneField('loanbook.LoanBook', on_delete=models.CASCADE, related_name='ccr_record')
    ccr_contract_id = models.CharField(max_length=50, help_text="Internal CCR contract reference")
    first_reported_date = models.DateField()
    last_reported_date = models.DateField()
    is_closed_in_ccr = models.BooleanField(default=False)
    closed_date = models.DateField(null=True, blank=True)

    # Track submission history
    submissions = models.ManyToManyField(CCRSubmission, through='CCRContractSubmission')

    class Meta:
        unique_together = ['ccr_contract_id']

    def __str__(self):
        return f"CCR Record for LoanBook (Loan #{self.loanbook.loan.id})"

    @property
    def should_be_reported(self):
        """Determine if this contract should be in next submission"""
        if self.is_closed_in_ccr:
            return False
        if self.loanbook.loan.is_settled:
            return False
        return True


class CCRContractSubmission(models.Model):
    """Track which contracts were included in which submissions"""
    contract_record = models.ForeignKey(CCRContractRecord, on_delete=models.CASCADE)
    submission = models.ForeignKey(CCRSubmission, on_delete=models.CASCADE)
    submission_type = models.CharField(max_length=20, choices=[
        ('NEW', 'New Contract'),
        ('UPDATE', 'Monthly Update'),
        ('SETTLEMENT', 'Final Settlement'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)


class CCRErrorRecord(models.Model):
    """Track individual record errors and their resolution"""
    ERROR_TYPES = [
        ('VALIDATION', 'Validation Error'),
        ('MISSING_DATA', 'Missing Data'),
        ('FORMAT_ERROR', 'Format Error'),
        ('DUPLICATE', 'Duplicate Record'),
        ('OTHER', 'Other'),
    ]

    RESOLUTION_STATUS = [
        ('PENDING', 'Pending Resolution'),
        ('FIXED_MANUAL', 'Fixed Manually'),
        ('FIXED_AUTO', 'Fixed Automatically'),
        ('CARRIED_FORWARD', 'Carried to Next Submission'),
        ('IGNORED', 'Ignored'),
    ]

    submission = models.ForeignKey(CCRSubmission, on_delete=models.CASCADE, related_name='error_records')
    contract_record = models.ForeignKey(CCRContractRecord, on_delete=models.CASCADE, null=True, blank=True)

    error_type = models.CharField(max_length=20, choices=ERROR_TYPES)
    error_description = models.TextField()
    line_number = models.IntegerField(null=True, blank=True, help_text="Line number in CCR file")
    original_line_content = models.TextField(blank=True, help_text="Original line that caused error")

    resolution_status = models.CharField(max_length=20, choices=RESOLUTION_STATUS, default='PENDING')
    resolution_notes = models.TextField(blank=True)
    carry_forward_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                         help_text="If carried forward, reference to next submission")

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Error in {self.submission} - {self.error_type}"


class CCRStatusHistory(models.Model):
    """Track status changes for submissions"""
    submission = models.ForeignKey(CCRSubmission, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, choices=CCRSubmission.SUBMISSION_STATUS)
    new_status = models.CharField(max_length=20, choices=CCRSubmission.SUBMISSION_STATUS)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name_plural = "CCR Status Histories"

    def __str__(self):
        return f"{self.submission} - {self.old_status} → {self.new_status}"
