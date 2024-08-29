from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets, mixins
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from core.models import Expense, Notification, Application
from expense.serializers import ExpenseSerializer


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all expenses',
        description='Returns  all expenses.',
        tags=['expenses'],
    ),
    # retrieve=extend_schema(
    #     summary='Retrieve an expense ',
    #     description='Returns detailed information about an expenses.',
    #     tags=['expenses'],
    # ),

    create=extend_schema(
        summary='Create an new expense',
        description='Creates a new expense and returns information about the created expense.',
        tags=['expenses']
    ),

    update=extend_schema(
        summary='Update an expense ',
        description='Updates an existing expense and returns information about the updated expense.',
        tags=['expenses']
    ),

    partial_update=extend_schema(
        summary='Partially update an expense ',
        description='Partially updates an existing expense and returns information about the updated expense.',
        tags=['expenses']
    ),

    destroy=extend_schema(
        summary='Delete an expense ',
        description='Deletes an existing expense and does not return any content.',
        tags=['expenses']
    )
)
class ExpenseViewSet(mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     viewsets.GenericViewSet):
    """ViewSet for viewing and modifying Expense objects."""
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return self.queryset.order_by('-id')

    def create(self, request, *args, **kwargs):
        """Handle creating a new Expense with notification."""
        response = super().create(request, *args, **kwargs)
        expense = self.queryset.get(pk=response.data['id'])  # Fetch the newly created expense instance

        # Serialize the newly created expense
        serialized_expense = ExpenseSerializer(expense).data

        self._send_notification(expense, 'New expense created', serialized_expense)
        return response

    def update(self, request, *args, **kwargs):
        """Handle updating an existing Expense with notification."""
        response = super().update(request, *args, **kwargs)
        expense = self.get_object()  # Get the updated expense instance

        # Serialize the updated expense
        serialized_expense = ExpenseSerializer(expense).data

        self._send_notification(expense, 'Expense updated', serialized_expense)
        return response

    def destroy(self, request, *args, **kwargs):
        """Handle deleting an Expense with notification."""
        expense = self.get_object()  # Get the instance before it is deleted

        # Serialize the expense before deletion
        serialized_expense = ExpenseSerializer(expense).data

        self._send_notification(expense, 'Expense deleted', serialized_expense)
        response = super().destroy(request, *args, **kwargs)
        return response

    def _send_notification(self, expense, message, serialized_expense):
        """Send a notification to the assigned user when an expense is created, updated, or deleted."""

        # Get the application ID from the serialized expense data
        application_id = serialized_expense.get(
            'application')  # Assuming 'application' is the field name in the serializer

        if application_id:
            # Fetch the Application instance using the application_id
            application = Application.objects.get(id=application_id)
            assigned_to_user = application.assigned_to  # Get the assigned user from the application

            notification = Notification.objects.create(
                recipient=assigned_to_user,
                text=message,
                seen=False,
                created_by=self.request.user,
                application=application,
            )

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'broadcast',
                {
                    'type': 'notification',
                    'message': notification.text,
                    'recipient': notification.recipient.email if notification.recipient else None,
                    'notification_id': notification.id,
                    'application_id': application_id,
                    'seen': notification.seen,
                }
            )

    def list(self, request, *args, **kwargs):
        """Handle listing expenses. You may or may not want to send notifications here."""
        # Optionally, add logic here to send a notification when expenses are listed
        return super().list(request, *args, **kwargs)
