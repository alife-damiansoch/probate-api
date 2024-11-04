from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from app import settings
from core.models import User, Notification


def check_committee_approval(loan, request_user):
    committee_members = User.objects.filter(teams__name='committee_members')
    total_members = committee_members.count()
    required_approvals = settings.COMMITTEE_MEMBERS_COUNT_REQUIRED_FOR_APPROVAL

    approvals = loan.committee_approvals.filter(approved=True).count()
    rejections = loan.committee_approvals.filter(approved=False).count()

    # only do ti if all members approved or rejected
    if total_members == approvals + rejections:
        # Update approval status based on majority
        if approvals >= required_approvals:
            loan.is_committee_approved = True
            loan.save(update_fields=['is_committee_approved'])
            notify_loan_approved(loan, request_user)
        else:
            loan.is_committee_approved = False
            loan.save(update_fields=['is_committee_approved'])
            notify_loan_rejected(loan, request_user)


def notify_loan_approved(loan, request_user):
    # send notification to users
    notification = Notification.objects.create(
        recipient=loan.application.assigned_to,
        text=f'Advancement: {loan.id} has been approved by committee members',
        seen=False,
        created_by=request_user,
        application=loan.application
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'broadcast',
        {
            'type': 'notification',
            'message': notification.text,
            'recipient': notification.recipient.email if notification.recipient else None,
            'notification_id': notification.id,
            'application_id': loan.application.id,
            'seen': notification.seen,
        }
    )


def notify_loan_rejected(loan, request_user):
    # send notification to users
    notification = Notification.objects.create(
        recipient=loan.application.assigned_to,
        text=f'Advancement: {loan.id} has been rejected by committee members',
        seen=False,
        created_by=request_user,
        application=loan.application
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'broadcast',
        {
            'type': 'notification',
            'message': notification.text,
            'recipient': notification.recipient.email if notification.recipient else None,
            'notification_id': notification.id,
            'application_id': loan.application.id,
            'seen': notification.seen,
        }
    )
