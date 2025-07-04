# ccr_reporting/models.py
from django.db import models
from django.utils import timezone
from decimal import Decimal


class CCRSubmission(models.Model):
    """Track monthly CCR submissions"""
    SUBMISSION_STATUS = [
        ('PENDING', 'Pending'),
        ('GENERATED', 'Generated'),
        ('UPLOADED', 'Uploaded'),
        ('ACKNOWLEDGED', 'Acknowledged by CCR'),
        ('ERROR', 'Error'),
    ]

    reference_date = models.DateField(help_text="Month-end date being reported")
    generated_at = models.DateTimeField(auto_now_add=True)
    file_path = models.CharField(max_length=500)
    total_records = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=SUBMISSION_STATUS, default='PENDING')
    error_message = models.TextField(blank=True)

    # Test fields for date manipulation
    is_test_submission = models.BooleanField(default=False)
    test_notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['reference_date']
        ordering = ['-reference_date']

    def __str__(self):
        return f"CCR Submission {self.reference_date} ({self.total_records} records)"


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
        return f"CCR Record for LoanBook (Loan #{self.loanbook.loan.id})"  # Updated this line

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
