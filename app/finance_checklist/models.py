from auditlog.registry import auditlog
from django.db import models
from django.core.validators import MinValueValidator

from app import settings
from core.models import User, Loan  # Import directly from core app


class FinanceChecklistItem(models.Model):
    """Master list of checklist items managed through admin"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = "Finance Checklist Item"
        verbose_name_plural = "Finance Checklist Items"

    def __str__(self):
        return self.title


class ChecklistConfiguration(models.Model):
    """Global configuration for checklist requirements"""
    required_approvers = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1)],
        help_text="Number of different staff users required to complete the checklist"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Checklist Configuration"
        verbose_name_plural = "Checklist Configuration"

    def __str__(self):
        return f"Requires {self.required_approvers} approver(s)"

    def save(self, *args, **kwargs):
        # Ensure only one active configuration exists
        if self.is_active:
            ChecklistConfiguration.objects.filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)


class LoanChecklistSubmission(models.Model):
    """Records each checklist submission by staff users"""
    loan = models.ForeignKey('core.Loan', on_delete=models.CASCADE, related_name='checklist_submissions')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    # Store the checklist items that were checked at time of submission
    checked_items = models.ManyToManyField(FinanceChecklistItem, blank=True)

    class Meta:
        unique_together = ['loan', 'submitted_by']
        verbose_name = "Loan Checklist Submission"
        verbose_name_plural = "Loan Checklist Submissions"
        ordering = ['-submitted_at']

    def __str__(self):
        return f"Checklist for Loan {self.loan.id} by {self.submitted_by.name} at {self.submitted_at}"

    @property
    def checked_items_list(self):
        """Return list of checked item titles"""
        return list(self.checked_items.values_list('title', flat=True))


class LoanChecklistItemCheck(models.Model):
    """Individual checklist item checks for each loan submission"""
    submission = models.ForeignKey(LoanChecklistSubmission, on_delete=models.CASCADE, related_name='item_checks')
    checklist_item = models.ForeignKey(FinanceChecklistItem, on_delete=models.CASCADE)
    is_checked = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['submission', 'checklist_item']
        verbose_name = "Loan Checklist Item Check"
        verbose_name_plural = "Loan Checklist Item Checks"

    def __str__(self):
        status = "✓" if self.is_checked else "✗"
        return f"{status} {self.checklist_item.title} - Loan {self.submission.loan.id}"


auditlog.register(
    LoanChecklistSubmission,
    serialize_data=True,
    # No include_fields/exclude_fields = audit ALL fields including:
    # - loan (which loan)
    # - submitted_by (who submitted)
    # - submitted_at (when submitted)
    # - notes (any notes)
    # - checked_items (which items were checked)
)
