from rest_framework import mixins, viewsets, status
from rest_framework.exceptions import NotFound

from core.models import Comment, Application
from .serializers import CommentSerializer
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .permissions import IsStaff

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes

from rest_framework.response import Response


@extend_schema_view(
    list=extend_schema(
        summary='List all comments',
        description='Returns a list of all comments in the system.',
        parameters=[
            OpenApiParameter('application', OpenApiTypes.STR,
                             description="Id of the application to filter on (optional)")
        ],
        tags=['comments']
    ),

    retrieve=extend_schema(
        summary='Retrieve a comment',
        description='Returns detailed information about a comment.',
        tags=['comments']
    ),

    create=extend_schema(
        summary='Create a new comment',
        description='Creates a new comment and returns information about the created comment.',
        tags=['comments']
    ),

    update=extend_schema(
        summary='Update a comment',
        description='Updates an existing comment and returns information about the updated comment.',
        tags=['comments']
    ),

    partial_update=extend_schema(
        summary='Partially update a comment',
        description='Partially updates an existing comment and returns information about the updated comment.',
        tags=['comments']
    ),

    destroy=extend_schema(
        summary='Delete a comment',
        description='Deletes an existing comment and does not return any content.',
        tags=['comments']
    )
)
class CommentListViewSet(mixins.ListModelMixin,
                         mixins.CreateModelMixin,
                         mixins.UpdateModelMixin,
                         mixins.RetrieveModelMixin,
                         mixins.DestroyModelMixin,
                         viewsets.GenericViewSet):
    """
    A viewset that provides the standard list action.
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]

    def _param_to_int(self, param):
        """Converts a parameter to a numeric value."""
        return int(param)

    def get_queryset(self):
        application_id_string = self.request.query_params.get('application', None)
        queryset = self.queryset
        if application_id_string is not None:
            application_id = self._param_to_int(application_id_string)
            # Check if the application exists
            if not Application.objects.filter(id=application_id).exists():
                raise NotFound(detail=f'Application with id {application_id} not found.')
            queryset = queryset.filter(application_id=application_id)

        return queryset.order_by('-id')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
