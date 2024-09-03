from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from agents_loan.permissions import IsStaff
from app.pagination import CustomPageNumberPagination
from core.models import Notification
from .serializers import NotificationSerializer
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all notifications {-Works only for staff users-}',
        description='Returns all notifications for the authenticated user.',
        tags=['notification'],
    ),
    update=extend_schema(
        summary='Update a notification {-Works only for staff users-}',
        description='Updates an existing notification to mark it as seen or not.',
        tags=['notification'],
        parameters=[
            OpenApiParameter(name='id', description='ID of the notification to update', required=True, type=int),
        ]
    ),
    partial_update=extend_schema(
        summary='Partially update a notification {-Works only for staff users-}',
        description='Partially updates an existing notification to mark it as seen or not.',
        tags=['notification'],
        parameters=[
            OpenApiParameter(name='id', description='ID of the notification to partially update', required=True,
                             type=int),
        ]
    ),
)
class NotificationViewSet(mixins.UpdateModelMixin,
                          mixins.ListModelMixin,
                          viewsets.GenericViewSet):
    """ViewSet for updating the 'seen' field of Notification objects."""
    queryset = Notification.objects.all()
    authentication_classes = (JWTAuthentication,)
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsStaff]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        """Restrict notifications to the authenticated user."""
        user = self.request.user
        return self.queryset.order_by('-id')
