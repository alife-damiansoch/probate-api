"""
Views for agents_application API
"""
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import JsonResponse, Http404

from rest_framework import (viewsets, status)
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from agents_loan import serializers
from app.utils import log_event
from core import models
from agents_loan.permissions import IsStaff

from drf_spectacular.utils import extend_schema, extend_schema_view


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all applications {-Works only for staff users-}',
        description='Returns  all applications.',
        tags=['agent_application'],
    ),
    retrieve=extend_schema(
        summary='Retrieve an application {-Works only for staff users-}',
        description='Returns detailed information about an application.',
        tags=['agent_application'],
    ),

    create=extend_schema(
        summary='Create an new application {-Works only for staff users-}',
        description='Creates a new application and returns information about the created application.',
        tags=['agent_application']
    ),

    update=extend_schema(
        summary='Update an application {-Works only for staff users-}',
        description='Updates an existing application and returns information about the updated application.',
        tags=['agent_application']
    ),

    partial_update=extend_schema(
        summary='Partially update an application {-Works only for staff users-}',
        description='Partially updates an existing application and returns information about the updated application.',
        tags=['agent_application']
    ),

    destroy=extend_schema(
        summary='Delete an application {-Works only for staff users-}',
        description='Deletes an existing application and does not return any content.',
        tags=['agent_application']
    )
)
class ApplicationViewSet(viewsets.ModelViewSet):
    """Viewset for applications"""
    serializer_class = serializers.ApplicationDetailSerializer
    queryset = models.Application.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]

    def get_queryset(self):
        return self.queryset.order_by('-id')

    def get_serializer_class(self):
        """Return serializer class for the requested model."""
        if self.action == 'list':
            return serializers.ApplicationSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        request_body = self.request.data
        """Create a new application."""
        try:
            serializer.save(user=self.request.user)
            log_event(self.request, request_body, serializer.instance, response_status=201)
        except Exception as e:  # Catch any type of exception
            log_event(self.request, request_body, application=serializer.instance)
            raise e  # Re-raise the caught exception

    def perform_update(self, serializer):
        """when updating an application."""
        request_body = self.request.data
        try:
            instance = self.get_object()
            if instance.approved:
                raise ValidationError("This operation is not allowed on approved applications")
            else:
                serializer.save(last_updated_by=self.request.user)
                log_event(self.request, request_body, serializer.instance, response_status=201)
        except Exception as e:
            log_event(self.request, request_body, application=serializer.instance)
            raise e

    def destroy(self, request, *args, **kwargs):
        request_body = self.request.data
        instance = None
        try:
            instance = self.get_object()
            if instance.approved:
                raise ValidationError("This operation is not allowed on approved applications")
            else:
                result = super().destroy(request, *args, **kwargs)  # carry out the deletion
                log_event(request, request_body, response_status=204)  # log after deletion is done
                return result
        except Exception as e:
            log_event(request, request_body, application=instance)
            raise e

    @extend_schema(exclude=True)
    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed('PATCH', detail='PATCH method is not allowed')

    @property
    def allowed_methods(self):
        return [m for m in super().allowed_methods if m != 'PATCH']


class DocumentUploadAndViewListForApplicationIdView(APIView):
    serializer_class = serializers.DocumentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]

    def get_queryset(self):

        return models.Application.objects.all()

    def get_object(self, application_id):
        try:
            return models.Application.objects.get(id=application_id)
        except models.Application.DoesNotExist:
            raise Http404

    @extend_schema(
        summary="Retrieve the documents for a specific application {-Works only for staff users-}",
        description="View to retrieve list of documents for an application with given ID.",
        tags=["document_agent"],
    )
    def get(self, request, application_id):
        application = self.get_object(application_id)
        documents = models.Document.objects.filter(application=application)
        serializer = self.serializer_class(documents, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Upload a new document for a specific application {-Works only for staff users-}",
        description="View to upload a document for an application with given ID.",
        tags=["document_agent"],
    )
    def post(self, request, application_id):
        serializer = serializers.DocumentSerializer(data=request.data)

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

            log_event(request=request, request_body=request_body, application=application, response_status=201)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DocumentDeleteView(APIView):
    serializer_class = serializers.DocumentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaff]

    def get_document(self, document_id):
        try:
            return models.Document.objects.get(id=document_id)
        except models.Document.DoesNotExist:
            raise Http404

    @extend_schema(
        summary="Deletes a document with the given ID. {-Works only for staff users-}",
        description="Deletes a document with the given ID.",
        tags=["document_agent"],
    )
    def delete(self, request, document_id):
        try:
            document = self.get_document(document_id)
            if document.application.approved:
                raise ValidationError("This operation is not allowed on approved applications")
            document.delete()
            log_event(request=request, request_body={'message': 'A document was deleted.'}, application=None,
                      response_status=204)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except models.Document.DoesNotExist:
            raise NotFound("Document with given id does not exist")
