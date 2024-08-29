from django.db.models import ProtectedError
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from core.models import Solicitor
from .serializers import AssignedSolicitorSerializer
from drf_spectacular.utils import extend_schema_view, extend_schema


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all assigned solicitors.For staff users all, for non_staff only assigned.',
        description='Returns a list of all assigned solicitors. For staff users all, for non_staff only assigned',
        tags=['solicitors'],
    ),
    retrieve=extend_schema(
        summary='Retrieve an assigned solicitor',
        description='Returns detailed information about a specific assigned solicitor.',
        tags=['solicitors'],
    ),
    create=extend_schema(
        summary='Create a new assigned solicitor. {Non staff users only}',
        description='Creates a new assigned solicitor and returns information about the created solicitor.',
        tags=['solicitors'],
    ),
    update=extend_schema(
        summary='Update an assigned solicitor',
        description='Updates an existing assigned solicitor and returns information about the updated solicitor.',
        tags=['solicitors'],
    ),
    partial_update=extend_schema(
        summary='Partially update an assigned solicitor',
        description='Partially updates an existing assigned solicitor and returns information about the updated solicitor.',
        tags=['solicitors'],
    ),
    destroy=extend_schema(
        summary='Delete an assigned solicitor',
        description='Deletes an existing assigned solicitor and does not return any content.',
        tags=['solicitors'],
    )
)
class AssignedSolicitorViewSet(viewsets.ModelViewSet):
    """ViewSet for managing assigned solicitors"""
    serializer_class = AssignedSolicitorSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """
        Return a queryset based on the user's role.
        If the user is a staff member, return all assigned solicitors.
        If the user is not a staff member, return only the solicitors associated with the user.
        """
        if self.request.user.is_staff:
            return Solicitor.objects.all().order_by('-id')
        else:
            return Solicitor.objects.filter(user=self.request.user).order_by('-id')

    def get_object(self):
        """
        Override get_object to ensure non-staff users can only access their own solicitors.
        Staff users can access any solicitor.
        """
        queryset = self.get_queryset()

        # Get the object based on the filtered queryset
        obj = get_object_or_404(queryset, pk=self.kwargs["pk"])

        # If the user is not staff and doesn't own the object, raise a permission denied error
        if not self.request.user.is_staff and obj.user != self.request.user:
            raise PermissionDenied("You do not have permission to perform this action.")

        return obj

    def perform_create(self, serializer):
        """Staff users are not allowed to create new solicitors."""
        if self.request.user.is_staff:
            raise PermissionDenied("Staff users are not allowed to create new solicitors.")
        """Ensure the user is set to the currently authenticated user when creating a new solicitor"""
        serializer.save(user=self.request.user)

    def perform_destroy(self, instance):
        """Override perform_destroy to handle ProtectedError."""
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                {"detail": "Cannot delete this solicitor because it is referenced in existing applications."}
            )
