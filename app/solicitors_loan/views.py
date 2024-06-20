"""
Views for application API
"""

from django.http import JsonResponse

from rest_framework import viewsets, mixins
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from solicitors_loan import serializers
from core import models
from solicitors_loan.permissions import IsNonStaff

from drf_spectacular.utils import extend_schema


class ApplicationViewSet(viewsets.ModelViewSet):
    """Viewset for applications"""
    serializer_class = serializers.ApplicationDetailSerializer
    queryset = models.Application.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsNonStaff]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-id')

    def get_serializer_class(self):
        """Return serializer class for the requested model."""
        if self.action == 'list':
            return serializers.ApplicationSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        """Create a new application."""
        serializer.save(user=self.request.user)

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PATCH', detail='PATCH method is not allowed')

    @property
    def allowed_methods(self):
        return [m for m in super().allowed_methods if m != 'PATCH']
