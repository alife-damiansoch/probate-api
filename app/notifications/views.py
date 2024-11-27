from django.db.models import Q
from rest_framework import viewsets, mixins
from rest_framework.exceptions import PermissionDenied
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
        country_filters = []

        # Determine the countries the user has access to
        if user.teams.filter(name='ie_team').exists():
            country_filters.append('IE')
        if user.teams.filter(name='uk_team').exists():
            country_filters.append('UK')

        # If no country filters were added, raise an error
        if not country_filters:
            raise PermissionDenied("You must be assigned to at least one team to access this resource.")

        # Filter applications based on the COUNTRY of the related user
        # or applications is None, this is for deleted applications,
        # they will be added for all users
        queryset = self.queryset.filter(
            Q(application__isnull=True) | Q(application__user__country__in=country_filters)
        )
        return queryset.order_by('-id')
