"""
Views for agents_application API
"""
import os
import re

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.http import JsonResponse, Http404, HttpResponseForbidden, HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes

from rest_framework import (viewsets, status)
from rest_framework.decorators import action
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from agents_loan import serializers
from app import settings
from app.utils import log_event
from core import models
from agents_loan.permissions import IsStaff
from app.pagination import CustomPageNumberPagination

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from rest_framework.exceptions import ValidationError as DRFValidationError

from core.models import Document


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all applications {-Works only for staff users-}',
        description='Returns  all applications.',
        tags=['agent_application'],
        parameters=[
            OpenApiParameter(name='status',
                             description='Filter by application status - optional (active,rejected,approved)',
                             required=False, type=str),
        ]
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
    ),
    all_application_ids=extend_schema(
        summary='Retrieve all application IDs {-Works only for staff users-}',
        description='Returns a list of all application IDs.',
        tags=['agent_application']
    ),
    application_ids_by_user=extend_schema(
        summary='Retrieve application IDs for a specific user {-Works only for staff users-}',
        description='Returns a list of application IDs filtered by user.',
        tags=['agent_application'],
        parameters=[
            OpenApiParameter(name='user_id',
                             description='The ID of the user whose applications you want to retrieve.',
                             required=True, type=int)
        ]
    ),
    search_applications=extend_schema(
        summary='Search applications based on any field {-Works only for staff users-}',
        description='Search applications by passing any property from the model. Supports date range for date fields and foreign key filters. Excludes loans.',
        tags=['agent_application'],
        parameters=[
            # Application ID and term range
            OpenApiParameter(name='id', description='Filter by application ID', required=False, type=int),
            OpenApiParameter(name='from_term', description='Filter by minimum term in months (From term)',
                             required=False, type=int),
            OpenApiParameter(name='to_term', description='Filter by maximum term in months (To term)', required=False,
                             type=int),

            # Amount range (grouped together)
            OpenApiParameter(name='from_amount', description='Filter by minimum amount (From amount)', required=False,
                             type=float),
            OpenApiParameter(name='to_amount', description='Filter by maximum amount (To amount)', required=False,
                             type=float),

            # Date range for date_submitted (grouped together)
            OpenApiParameter(name='from_date_submitted', description='Start date range for date_submitted (From date)',
                             required=False, type=OpenApiTypes.DATE),
            OpenApiParameter(name='to_date_submitted', description='End date range for date_submitted (To date)',
                             required=False, type=OpenApiTypes.DATE),

            # Boolean filters
            OpenApiParameter(name='approved', description='Filter by approval status (true/false)', required=False,
                             type=bool),
            OpenApiParameter(name='is_rejected', description='Filter by rejection status (true/false)', required=False,
                             type=bool),

            # Foreign key filters
            OpenApiParameter(name='user_id', description='Filter by user ID', required=False, type=int),
            OpenApiParameter(name='applicant_id', description='Filter by applicant ID', required=False, type=int),
            OpenApiParameter(name='solicitor_id', description='Filter by solicitor ID', required=False, type=int),
            OpenApiParameter(name='assigned_to_id', description='Filter by assigned to user ID', required=False,
                             type=int),
        ]
    )

)
class AgentApplicationViewSet(viewsets.ModelViewSet):
    """Viewset for applications"""
    serializer_class = serializers.AgentApplicationDetailSerializer
    queryset = models.Application.objects.all()
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        queryset = self.queryset

        stat = self.request.query_params.get('status', None)
        assigned = self.request.query_params.get('assigned', None)
        old_to_new = self.request.query_params.get('old_to_new', None)

        if assigned is not None:
            if assigned == "true":
                queryset = queryset.filter(assigned_to=self.request.user)
            if assigned == "false":
                queryset = queryset.filter(assigned_to=None)

        if stat is not None:
            if stat == 'active':
                queryset = queryset.filter(is_rejected=False, approved=False)
            elif stat == 'rejected':
                queryset = queryset.filter(is_rejected=True)
            elif stat == 'approved':
                queryset = queryset.filter(approved=True)

        if old_to_new is not None:
            if old_to_new == "true":
                return queryset.order_by('id')
        else:
            return queryset.order_by('-id')

    @action(detail=False, methods=['get'], url_path='search-applications')
    def search_applications(self, request):
        """
        Search all applications based on any model field, supporting foreign key and date filtering.
        Returns application IDs, user information, and amount ordered by ID in descending order.
        """
        queryset = self.queryset

        # Filtering by application fields
        filter_params = {
            'id': request.query_params.get('id'),
            'approved': (request.query_params.get('approved').lower() == 'true') if request.query_params.get(
                'approved') else None,
            'is_rejected': (request.query_params.get('is_rejected').lower() == 'true') if request.query_params.get(
                'is_rejected') else None,
        }

        # Term filtering: from_term and to_term
        from_term = request.query_params.get('from_term')
        to_term = request.query_params.get('to_term')
        if from_term and to_term:
            queryset = queryset.filter(term__gte=from_term, term__lte=to_term)

        # Date filtering: from and to for 'date_submitted'
        date_from = request.query_params.get('from_date_submitted')
        date_to = request.query_params.get('to_date_submitted')
        if date_from and date_to:
            queryset = queryset.filter(date_submitted__range=[date_from, date_to])

        # Amount filtering: from_amount and to_amount
        from_amount = request.query_params.get('from_amount')
        to_amount = request.query_params.get('to_amount')
        if from_amount and to_amount:
            queryset = queryset.filter(amount__gte=from_amount, amount__lte=to_amount)

        # Foreign key filtering
        user_id = request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        solicitor_id = request.query_params.get('solicitor_id')
        if solicitor_id:
            queryset = queryset.filter(solicitor_id=solicitor_id)

        assigned_to_id = request.query_params.get('assigned_to_id')
        if assigned_to_id:
            queryset = queryset.filter(assigned_to_id=assigned_to_id)

        # Applicant filtering: applicant_id
        applicant_id = request.query_params.get('applicant_id')
        if applicant_id:
            queryset = queryset.filter(applicants__id=applicant_id)

        # Apply additional filters from the filter_params dictionary
        for key, value in filter_params.items():
            if value is not None:
                queryset = queryset.filter(**{key: value})

        # Select application ID, amount, and related user info, ordered by ID in descending order
        application_data = queryset.order_by('-id').values('id', 'amount', 'user__id', 'user__email', 'user__name')

        return Response(application_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def all_application_ids(self, request):
        """Returns a list of all application IDs"""
        application_ids = self.queryset.values_list('id', flat=True)
        return Response(application_ids, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def application_ids_by_user(self, request):
        """Returns a list of application IDs for a specific user"""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'detail': 'User ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        application_ids = self.queryset.filter(user_id=user_id).values_list('id', flat=True)
        return Response(application_ids, status=status.HTTP_200_OK)

    def get_serializer_class(self):
        """Return serializer class for the requested model."""
        if self.action == 'list':
            return serializers.AgentApplicationSerializer
        return self.serializer_class

    def validate_applicants(self, applicants_data):
        """Validate the PPS numbers of the applicants."""
        pps_regex = re.compile(r'^\d{7}[A-Z]{1,2}$')
        for applicant in applicants_data:
            pps_number = applicant.get('pps_number')
            pps_number = pps_number.upper()
            if not pps_regex.match(pps_number):
                raise DRFValidationError({
                    'pps_number': 'PPS Number must be 7 digits followed by 1 or 2 letters.'
                })

    @transaction.atomic
    def perform_create(self, serializer):
        request_body = self.request.data
        applicants_data = request_body.get('applicants', [])
        self.validate_applicants(applicants_data)
        """Create a new application."""
        try:
            serializer.save(user=self.request.user)
            log_event(self.request, request_body, serializer.instance, response_status=201)
        except Exception as e:  # Catch any type of exception
            log_event(self.request, request_body, application=serializer.instance)
            raise e  # Re-raise the caught exception

    @transaction.atomic
    def perform_update(self, serializer):
        """when updating an application."""
        request_body = self.request.data
        applicants_data = request_body.get('applicants', [])
        self.validate_applicants(applicants_data)

        try:
            instance = self.get_object()

            # Check if the only key in the request data is 'assigned_to'
            if len(request_body) == 1 and 'assigned_to' in request_body:

                assigned_user_id = request_body['assigned_to']
                assigned_user = get_object_or_404(models.User, pk=assigned_user_id)

                instance.assigned_to = assigned_user
                instance.last_updated_by = self.request.user
                instance.save(update_fields=['assigned_to', 'last_updated_by'])
                log_event(self.request, request_body, serializer.instance, response_status=201)
            else:
                if instance.approved:
                    log_event(self.request, request_body, serializer.instance)
                    raise ValidationError("This operation is not allowed on approved applications")
                elif instance.is_rejected:
                    log_event(self.request, request_body, serializer.instance)
                    raise ValidationError("This operation is not allowed on rejected applications")
                else:
                    serializer.save(last_updated_by=self.request.user)
                    log_event(self.request, request_body, serializer.instance, response_status=201)
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
                raise ValidationError("This operation is not allowed on approved applications")
            elif instance.is_rejected:
                raise ValidationError("This operation is not allowed on rejected applications")
            else:
                result = super().destroy(request, *args, **kwargs)  # carry out the deletion
                log_event(request, request_body, response_status=204)  # log after deletion is done
                return result
        except Exception as e:
            log_event(request, request_body, application=instance)
            raise e


class AgentDocumentUploadAndViewListForApplicationIdView(APIView):
    serializer_class = serializers.AgentDocumentSerializer
    authentication_classes = (JWTAuthentication,)
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
        serializer = serializers.AgentDocumentSerializer(data=request.data)

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


class AgentDocumentDeleteView(APIView):
    serializer_class = serializers.AgentDocumentSerializer
    authentication_classes = (JWTAuthentication,)
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


class AgentDocumentPatchView(APIView):
    serializer_class = serializers.AgentDocumentSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    def get_document(self, document_id):
        try:
            return models.Document.objects.get(id=document_id)
        except models.Document.DoesNotExist:
            raise Http404

    @extend_schema(
        summary="Updates a document with the given ID. {-Works only for staff users-}",
        description="Updates a document",
        tags=["document_agent"],
    )
    def patch(self, request, document_id, format=None):
        document = self.get_document(document_id)
        serializer = serializers.AgentDocumentSerializer(
            document, data=request.data, partial=True)
        # set partial=True to update a data partially

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DownloadFileView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(
        summary="Download a document with the given filename",
        description="Allows authenticated users to download a file if they have access permissions.",
        tags=["document_agent"],
        responses={
            200: {
                "content": {"application/pdf": {}},
                "description": "A PDF file."
            },
            403: {"description": "Forbidden - You do not have permission to access this file."},
            404: {"description": "File not found."}
        },
    )
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
