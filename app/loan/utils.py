from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from app import settings
from core.models import User, Notification


def check_committee_approval(loan, request_user):
    """
       Checks the approval status of a loan based on committee member votes and updates the loan status if a decision is reached.

       This function:
       1. Retrieves all committee members and calculates the total number of members.
       2. Counts the approvals and rejections for the loan from committee members.
       3. If all committee members have either approved or rejected, it updates the loan’s approval status based on whether the required number of approvals is met.
       4. Sends notifications upon approval or rejection.

       Parameters:
       - loan (Loan): The loan object being evaluated for committee approval.
       - request_user (User): The user who initiated the request, used for notification purposes.

       Process:
       - The required approvals count is defined in `settings.COMMITTEE_MEMBERS_COUNT_REQUIRED_FOR_APPROVAL`.
       - If the total number of committee members equals the combined count of approvals and rejections:
         - If approvals meet or exceed the required number, `is_committee_approved` is set to True, and an approval notification is sent.
         - Otherwise, `is_committee_approved` is set to False, and a rejection notification is sent.

       Returns:
       - None. The function updates the loan’s status and sends notifications without returning a value.

       Example:
       - If a loan requires 2 approvals and receives 2 approvals and 1 rejection, it will be approved if 2 out of 3 members have approved.

       Notes:
       - Requires `notify_loan_approved` and `notify_loan_rejected` functions to handle notifications.
       - Assumes `is_committee_approved` is a field on the loan model.
       """
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
            loan.notify_committee_members(
                message="The advancement has been successfully approved by the required members of the committee. The status of the advancement has now been updated to APPROVED.",
                subject="Advancement Approval Notification")
        else:
            loan.is_committee_approved = False
            loan.save(update_fields=['is_committee_approved'])
            notify_loan_rejected(loan, request_user)
            loan.notify_committee_members(
                message="The advancement has been rejected by the committee. The status of the advancement has now been updated to REJECTED.",
                subject="Advancement Rejection Notification"
            )


def notify_loan_approved(loan, request_user):
    """
      Sends a notification to inform users that a loan has been approved by committee members.

      This function:
      1. Creates a `Notification` entry in the database for the user assigned to the loan application.
      2. Broadcasts the notification asynchronously to a WebSocket channel layer group for real-time updates.

      Parameters:
      - loan (Loan): The loan that has been approved.
      - request_user (User): The user initiating the notification, typically the user performing the approval check.

      Process:
      - Creates a notification with details including the loan ID and sets the recipient to the user assigned to the loan application.
      - Uses `channels` to send the notification to the `broadcast` group, allowing real-time notification delivery.

      Returns:
      - None. This function creates a notification and broadcasts it without returning a value.

      Example Notification Message:
      - "Advancement: <loan_id> has been approved by committee members"

      Notes:
      - Assumes the existence of a `Notification` model with fields `recipient`, `text`, `seen`, `created_by`, and `application`.
      - Requires a configured channel layer for broadcasting WebSocket messages.
      """

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
            'country': loan.application.user.country,
        }
    )


def notify_loan_rejected(loan, request_user):
    """
        Sends a notification to inform users that a loan has been rejected by committee members.

        This function:
        1. Creates a `Notification` entry in the database for the user assigned to the loan application, indicating that the loan was rejected.
        2. Broadcasts the notification asynchronously to a WebSocket channel layer group for real-time updates.

        Parameters:
        - loan (Loan): The loan that has been rejected.
        - request_user (User): The user initiating the notification, typically the user performing the approval check.

        Process:
        - Creates a notification with details including the loan ID and sets the recipient to the user assigned to the loan application.
        - Uses `channels` to send the notification to the `broadcast` group, enabling real-time notification delivery.

        Returns:
        - None. This function creates a notification and broadcasts it without returning a value.

        Example Notification Message:
        - "Advancement: <loan_id> has been rejected by committee members"

        Notes:
        - Assumes the existence of a `Notification` model with fields `recipient`, `text`, `seen`, `created_by`, and `application`.
        - Requires a configured channel layer for broadcasting WebSocket messages.
        """
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
            'country': loan.application.user.country,
        }
    )


def notify_application_referred_back_to_agent(application, request_user, comment):
    """
        Sends a notification to inform users that a application has been referred_back to agent assigned by committee member.

        This function:
        1. Creates a `Notification` entry in the database for the user assigned to the application, indicating that the referred_back to agent.
        2. Broadcasts the notification asynchronously to a WebSocket channel layer group for real-time updates.

        Parameters:
        - application (Application): The application that has been rejected. {I had to use application, not loan because loan does't exist anymore at this stage}
        - request_user (User): The user initiating the notification, typically the user performing the approval check.

        Process:
        - Creates a notification with details including the application ID and sets the recipient to the user assigned to the application.
        - Uses `channels` to send the notification to the `broadcast` group, enabling real-time notification delivery.

        Returns:
        - None. This function creates a notification and broadcasts it without returning a value.

        Example Notification Message:
        - "Advancement: <loan_id> has been referred back to agent by committee member"

        Notes:
        - Assumes the existence of a `Notification` model with fields `recipient`, `text`, `seen`, `created_by`, and `application`.
        - Requires a configured channel layer for broadcasting WebSocket messages.
        """
    # send notification to users
    notification = Notification.objects.create(
        recipient=application.assigned_to,
        text=f'Application: {application.id} has been referred_back_to_agent by committee member. Reason: {comment}. User: {request_user}',
        seen=False,
        created_by=request_user,
        application=application
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'broadcast',
        {
            'type': 'notification',
            'message': notification.text,
            'recipient': notification.recipient.email if notification.recipient else None,
            'notification_id': notification.id,
            'application_id': application.id,
            'seen': notification.seen,
            'country': application.user.country,
        }
    )
