from django.shortcuts import render

# Create your views here.
# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from agents_loan.permissions import IsStaff  # Adjust import path
from .models import (
    Loan, FinanceChecklistItem, LoanChecklistSubmission,
    LoanChecklistItemCheck, ChecklistConfiguration
)


# from .serializers import (
#     LoanChecklistSerializer, ChecklistItemSerializer,
#     LoanChecklistSubmissionSerializer
# )


class LoanChecklistView(APIView):
    """View for staff to see and complete checklist for a loan"""
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    def get(self, request, loan_id):
        """Get checklist status for a loan"""
        loan = get_object_or_404(Loan, id=loan_id)
        config = ChecklistConfiguration.objects.filter(is_active=True).first()

        if not config:
            return Response({
                'error': 'Checklist configuration not found. Please contact admin.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get all active checklist items
        checklist_items = FinanceChecklistItem.objects.filter(is_active=True).order_by('order', 'title')

        # Get current user's submission if exists
        user_submission = LoanChecklistSubmission.objects.filter(
            loan=loan,
            submitted_by=request.user
        ).first()

        # Get all submissions for this loan
        all_submissions = loan.checklist_submissions.all().select_related('submitted_by')

        # Prepare checklist data
        checklist_data = []
        for item in checklist_items:
            # Check if current user has checked this item
            user_checked = False
            user_notes = ""

            if user_submission:
                user_check = user_submission.item_checks.filter(checklist_item=item).first()
                if user_check:
                    user_checked = user_check.is_checked
                    user_notes = user_check.notes

            # Count how many users have checked this item
            users_checked_count = LoanChecklistItemCheck.objects.filter(
                submission__loan=loan,
                checklist_item=item,
                is_checked=True
            ).values('submission__submitted_by').distinct().count()

            checklist_data.append({
                'id': item.id,
                'title': item.title,
                'description': item.description,
                'order': item.order,
                'user_checked': user_checked,
                'user_notes': user_notes,
                'users_checked_count': users_checked_count,
                'required_count': config.required_approvers,
                'is_complete': users_checked_count >= config.required_approvers,
            })

        # Prepare submissions summary
        submissions_summary = []
        for submission in all_submissions:
            checked_count = submission.item_checks.filter(is_checked=True).count()
            total_items = checklist_items.count()

            submissions_summary.append({
                'user': submission.submitted_by.email,
                'submitted_at': submission.submitted_at,
                'checked_items': checked_count,
                'total_items': total_items,
                'notes': submission.notes,
                'items_checked': list(submission.item_checks.filter(
                    is_checked=True
                ).values_list('checklist_item__title', flat=True))
            })

        return Response({
            'loan_id': loan.id,
            'loan_amount': str(loan.amount_agreed),
            'applicant': loan.first_applicant(),
            'is_paid_out': loan.is_paid_out,
            'checklist_complete': loan.finance_checklist_complete,
            'config': {
                'required_approvers': config.required_approvers,
            },
            'checklist_items': checklist_data,
            'submissions': submissions_summary,
            'user_has_submitted': user_submission is not None,
            'can_mark_paid_out': loan.finance_checklist_complete and not loan.is_paid_out,
        })


class SubmitLoanChecklistView(APIView):
    """Submit checklist for a loan"""
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    def post(self, request, loan_id):
        """Submit checklist items for a loan"""
        loan = get_object_or_404(Loan, id=loan_id)

        # Check if loan is already paid out
        if loan.is_paid_out:
            return Response({
                'error': 'Cannot submit checklist for a loan that is already marked as paid out.'
            }, status=status.HTTP_400_BAD_REQUEST)

        checklist_data = request.data.get('checklist_items', [])
        notes = request.data.get('notes', '')

        if not checklist_data:
            return Response({
                'error': 'No checklist items provided.'
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Create or update submission
            submission, created = LoanChecklistSubmission.objects.get_or_create(
                loan=loan,
                submitted_by=request.user,
                defaults={'notes': notes}
            )

            if not created:
                # Update existing submission
                submission.notes = notes
                submission.submitted_at = timezone.now()
                submission.save()
                # Clear existing checks
                submission.item_checks.all().delete()

            # Process each checklist item
            for item_data in checklist_data:
                item_id = item_data.get('item_id')
                is_checked = item_data.get('is_checked', False)
                item_notes = item_data.get('notes', '')

                try:
                    checklist_item = FinanceChecklistItem.objects.get(
                        id=item_id,
                        is_active=True
                    )

                    # Create item check record
                    LoanChecklistItemCheck.objects.create(
                        submission=submission,
                        checklist_item=checklist_item,
                        is_checked=is_checked,
                        notes=item_notes
                    )

                except FinanceChecklistItem.DoesNotExist:
                    return Response({
                        'error': f'Invalid checklist item ID: {item_id}'
                    }, status=status.HTTP_400_BAD_REQUEST)

            # Check if this submission completes the checklist
            checklist_now_complete = loan.finance_checklist_complete

            # If checklist is now complete, mark loan as ready for payout
            if checklist_now_complete and not loan.is_paid_out:
                loan.is_paid_out = True
                # Note: We don't set paid_out_date or pay_out_reference_number
                # These will be set later when actual payout happens
                loan.save(update_fields=['is_paid_out'])

                return Response({
                    'message': 'Checklist submitted successfully. Loan is now marked as ready for payout!',
                    'checklist_complete': True,
                    'loan_marked_for_payout': True,
                    'submission_id': submission.id
                })
            else:
                return Response({
                    'message': 'Checklist submitted successfully.',
                    'checklist_complete': checklist_now_complete,
                    'loan_marked_for_payout': False,
                    'submission_id': submission.id
                })


class LoanChecklistStatusView(APIView):
    """Get quick status of loan checklist"""
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    def get(self, request, loan_id):
        """Get quick checklist status"""
        loan = get_object_or_404(Loan, id=loan_id)
        config = ChecklistConfiguration.objects.filter(is_active=True).first()

        submissions_count = loan.checklist_submissions.count()
        required_count = config.required_approvers if config else 1

        return Response({
            'loan_id': loan.id,
            'is_paid_out': loan.is_paid_out,
            'checklist_complete': loan.finance_checklist_complete,
            'submissions_count': submissions_count,
            'required_submissions': required_count,
            'user_has_submitted': loan.checklist_submissions.filter(
                submitted_by=request.user
            ).exists(),
        })


class ChecklistConfigurationView(APIView):
    """Get current checklist configuration"""
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    def get(self, request):
        """Get active configuration"""
        config = ChecklistConfiguration.objects.filter(is_active=True).first()

        if not config:
            return Response({
                'error': 'No active checklist configuration found.'
            }, status=status.HTTP_404_NOT_FOUND)

        active_items = FinanceChecklistItem.objects.filter(
            is_active=True
        ).order_by('order', 'title')

        items_data = [{
            'id': item.id,
            'title': item.title,
            'description': item.description,
            'order': item.order,
        } for item in active_items]

        return Response({
            'required_approvers': config.required_approvers,
            'active_items_count': active_items.count(),
            'active_items': items_data,
        })


class LoansRequiringChecklistView(APIView):
    """Get list of loans that need checklist completion"""
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    def get(self, request):
        """Get loans that need checklist completion"""
        # Get loans that are approved but not paid out
        loans = Loan.objects.filter(
            is_paid_out=False
        ).select_related('application').prefetch_related('checklist_submissions')

        config = ChecklistConfiguration.objects.filter(is_active=True).first()
        required_approvers = config.required_approvers if config else 1

        loans_data = []
        for loan in loans:
            submissions_count = loan.checklist_submissions.count()
            user_submitted = loan.checklist_submissions.filter(
                submitted_by=request.user
            ).exists()

            loans_data.append({
                'id': loan.id,
                'amount': str(loan.amount_agreed),
                'applicant': loan.first_applicant(),
                'approved_date': loan.approved_date,
                'submissions_count': submissions_count,
                'required_submissions': required_approvers,
                'checklist_complete': loan.finance_checklist_complete,
                'user_has_submitted': user_submitted,
                'can_submit': not user_submitted,
            })

        return Response({
            'loans': loans_data,
            'required_approvers': required_approvers,
        })
