"""
Views for solicitors_application API
"""
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import JsonResponse, Http404, HttpResponse, HttpResponseNotFound, HttpResponseForbidden

import os

from rest_framework import (viewsets, status)
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app import settings
from app.utils import log_event
from core.models import Document
from solicitors_loan import serializers
from core import models
from solicitors_loan.permissions import IsNonStaff

from drf_spectacular.utils import extend_schema, extend_schema_view

from rest_framework.exceptions import ValidationError as DRFValidationError
from django.db import transaction
import re


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all solicitor_applications {-Works only for non staff users-}',
        description='Returns  all solicitor_applications.',
        tags=['solicitor_application'],
    ),
    retrieve=extend_schema(
        summary='Retrieve a solicitor_application {-Works only for non staff users-}',
        description='Returns detailed information about a solicitor_application.',
        tags=['solicitor_application'],
    ),

    create=extend_schema(
        summary='Create a new solicitor_application {-Works only for non staff users-}',
        description='Creates a new solicitor_application and returns information about the created solicitor_application.',
        tags=['solicitor_application']
    ),

    update=extend_schema(
        summary='Update a solicitor_application {-Works only for non staff users-}',
        description='Updates an existing solicitor_application and returns information about the updated solicitor_application.',
        tags=['solicitor_application']
    ),

    partial_update=extend_schema(
        summary='Partially update a solicitor_application {-Works only for non staff users-}',
        description='Partially updates an existing solicitor_application and returns information about the updated solicitor_application.',
        tags=['solicitor_application']
    ),

    destroy=extend_schema(
        summary='Delete a solicitor_application {-Works only for non staff users-}',
        description='Deletes an existing solicitor_application and does not return any content.',
        tags=['solicitor_application']
    )
)
class SolicitorApplicationViewSet(viewsets.ModelViewSet):
    """Viewset for applications"""
    serializer_class = serializers.SolicitorApplicationDetailSerializer
    queryset = models.Application.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsNonStaff]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).order_by('-id')

    def get_serializer_class(self):
        """Return serializer class for the requested model."""
        if self.action == 'list':
            return serializers.SolicitorApplicationSerializer
        return self.serializer_class

    def validate_applicants(self, applicants_data):
        """Validate the PPS numbers of the applicants."""
        pps_regex = re.compile(r'^\d{7}[A-Z]{1,2}$')
        for applicant in applicants_data:
            pps_number = applicant.get('pps_number')
            if not pps_regex.match(pps_number):
                raise DRFValidationError({
                    'pps_number': 'PPS Number must be 7 digits followed by 1 or 2 letters.'
                })

    @transaction.atomic
    def perform_create(self, serializer):
        """Create a new application."""
        request_body = self.request.data
        applicants_data = request_body.get('applicants', [])
        self.validate_applicants(applicants_data)

        try:
            serializer.save(user=self.request.user)
            log_event(self.request, request_body, serializer.instance)
        except Exception as e:  # Catch any type of exception
            log_event(self.request, request_body, application=serializer.instance)
            raise e  # Re-raise the caught exception

    @transaction.atomic
    def perform_update(self, serializer):
        """Update an existing application."""
        request_body = self.request.data
        applicants_data = request_body.get('applicants', [])
        self.validate_applicants(applicants_data)

        try:
            instance = self.get_object()
            if instance.approved:
                raise DRFValidationError("This operation is not allowed on approved applications")
            else:
                serializer.save(last_updated_by=self.request.user)
                log_event(self.request, request_body, serializer.instance)
        except Exception as e:
            log_event(self.request, request_body, application=serializer.instance)
            raise e

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        request_body = self.request.data
        instance = None
        try:
            instance = self.get_object()
            if instance.approved:
                raise DRFValidationError("This operation is not allowed on approved applications")
            else:
                result = super().destroy(request, *args, **kwargs)  # carry out the deletion
                log_event(request, request_body)  # log after deletion is done
                return result
        except Exception as e:
            log_event(request, request_body, application=instance)
            raise e


class SolicitorDocumentUploadAndViewListForApplicationIdView(APIView):
    serializer_class = serializers.SolicitorDocumentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsNonStaff]

    def get_queryset(self):

        return models.Application.objects.all()

    def get_object(self, application_id):
        try:
            return models.Application.objects.get(id=application_id)
        except models.Application.DoesNotExist:
            raise Http404

    @extend_schema(
        summary="Retrieve the documents for a specific application {-Works only for non staff users-}",
        description="View to retrieve list of documents for an application with given ID.",
        tags=["document_solicitor"],
    )
    def get(self, request, application_id):
        application = self.get_object(application_id)
        documents = models.Document.objects.filter(application=application)
        serializer = self.serializer_class(documents, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Upload a new document for a specific application {-Works only for non staff users-}",
        description="View to upload a document for an application with given ID.",
        tags=["document_solicitor"],
    )
    def post(self, request, application_id):
        serializer = serializers.SolicitorDocumentSerializer(data=request.data)

        if serializer.is_valid():
            # store application instance for logging purpose
            application = models.Application.objects.get(id=application_id)
            serializer.save(application=application)

            # logging the successful POST request
            request_body = {}
            for key, value in request.data.items():
                if not isinstance(value, InMemoryUploadedFile):
                    request_body[key] = value
                else:
                    request_body[key] = 'A new file was uploaded.'

            log_event(request=request, request_body=request_body, application=application)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SolicitorDocumentDeleteView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsNonStaff]
    serializer_class = serializers.SolicitorDocumentSerializer

    def get_document(self, document_id):
        try:
            return models.Document.objects.get(id=document_id)
        except models.Document.DoesNotExist:
            raise Http404

    @extend_schema(
        summary="Deletes a document with the given ID. {-Works only for non staff users-}",
        description="Deletes a document with the given ID.",
        tags=["document_solicitor"],
    )
    def delete(self, request, document_id):
        try:
            document = self.get_document(document_id)
            if document.application.user != request.user:
                raise PermissionDenied("You do not have permission to delete this document")
            if document.application.approved:
                raise ValidationError("This operation is not allowed on approved applications")
            document.delete()
            log_event(request=request, request_body={'message': 'A document was deleted.'}, application=None)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except models.Document.DoesNotExist:
            raise NotFound("Document with given id does not exist")


class DownloadFileView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, filename):
        try:
            document = Document.objects.get(document__endswith=filename)
            application = document.application

            # Check if the user is not staff and does not own the application
            if not request.user.is_staff and application.user != request.user:
                return HttpResponseForbidden("You do not have permission to access this file.")

            file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'application', filename)

            if os.path.exists(file_path):
                with open(file_path, 'rb') as file:
                    response = HttpResponse(file.read(), content_type='application/pdf')
                    response['Content-Disposition'] = f'attachment; filename="{filename}"'
                    return response
            else:
                return HttpResponseNotFound("File not found.")

        except Document.DoesNotExist:
            return HttpResponseNotFound("File not found.")
