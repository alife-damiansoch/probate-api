"""
Views for application API
"""

from django.http import JsonResponse, Http404

from rest_framework import (viewsets, status)
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

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

    def perform_update(self, serializer):
        """when updating an application."""
        instance = self.get_object()
        if instance.approved:
            raise ValidationError("This operation is not allowed on approved applications")
        else:
            serializer.save(last_updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.approved:
            raise ValidationError("This operation is not allowed on approved applications")
        return super().destroy(request, *args, **kwargs)

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PATCH', detail='PATCH method is not allowed')

    @property
    def allowed_methods(self):
        return [m for m in super().allowed_methods if m != 'PATCH']


class DocumentUploadAndViewListForApplicationIdView(APIView):
    serializer_class = serializers.DocumentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsNonStaff]

    def get_queryset(self):

        return models.Application.objects.all()

    def get_object(self, application_id):
        try:
            return models.Application.objects.get(id=application_id)
        except models.Application.DoesNotExist:
            raise Http404

    def get(self, request, application_id):
        application = self.get_object(application_id)
        documents = models.Document.objects.filter(application=application)
        serializer = self.serializer_class(documents, many=True)
        return Response(serializer.data)

    def post(self, request, application_id):
        serializer = serializers.DocumentSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(application=models.Application.objects.get(id=application_id))
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DocumentDeleteView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsNonStaff]

    def get_document(self, document_id):
        try:
            return models.Document.objects.get(id=document_id)
        except models.Document.DoesNotExist:
            raise Http404

    def delete(self, request, document_id):
        try:
            document = self.get_document(document_id)
            if document.application.user != request.user:
                raise PermissionDenied("You do not have permission to delete this document")
            if document.application.approved:
                raise ValidationError("This operation is not allowed on approved applications")
            document.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except models.Document.DoesNotExist:
            raise NotFound("Document with given id does not exist")
