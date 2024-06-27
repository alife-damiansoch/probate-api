from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets, mixins, permissions
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from core.models import Event
from event.permissions import IsStaff
from event.serializers import EventSerializer


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all events {-Works only for staff users-}',
        description='Returns  all events.',
        tags=['events'],
    ),

)
class EventViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    A viewset for listing all events
    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all events for given application. {-Works only for staff users-}',
        description='Returns  all events for given application.',
        tags=['events'],
    ),

)
class EventByApplicationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    A viewset for listing events by application
    """
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]

    def get_queryset(self):
        """
        Restricts the returned events to a given user by filtering against a `application_id` URL argument.
        """
        queryset = Event.objects.all()
        application_id = self.kwargs['application_id']
        queryset = queryset.filter(application__id=application_id)
        return queryset
