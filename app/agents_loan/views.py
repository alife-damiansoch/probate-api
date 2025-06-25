"""
Views for agents_application API
"""
import os
import re

from django.utils import timezone

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.db.models import Q
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
from agents_loan.serializers import ApplicationProcessingStatusSerializer
from app import settings
from app.utils import log_event
from communications.utils import send_email_f
from core import models
from agents_loan.permissions import IsStaff
from app.pagination import CustomPageNumberPagination

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from rest_framework.exceptions import ValidationError as DRFValidationError

from core.models import Document, Application, ApplicationProcessingStatus

from django.core.files.base import ContentFile

from core.Validators.id_validators import ApplicantsValidator

from django.conf import settings
from django.core.files.storage import default_storage

import shutil
from datetime import datetime


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all solicitor applications {-Works only for non-staff users-}',
        description='Returns all solicitor applications with optional filters for status, applicant search, and application ID.',
        tags=['agent_application'],
        parameters=[
            OpenApiParameter(
                name='status',
                description=(
                        'Filter applications by their status. Options include: '
                        '`active` (applications in progress), `rejected` (applications rejected), '
                        '`approved` (applications approved but not paid out or settled), '
                        '`paid_out` (applications paid out but not settled), '
                        '`settled` (applications fully paid and settled).'
                ),
                required=False,
                type=OpenApiTypes.STR
            ),
            OpenApiParameter(
                name='search',
                description=(
                        'Search for applications by applicant details. Searches through '
                        '`first_name`, `last_name`, and `pps_number` fields of the applicants. '
                        'Partial matches are allowed.'
                ),
                required=False,
                type=OpenApiTypes.STR
            ),
            OpenApiParameter(
                name='search_id',
                description=(
                        'Filter applications by their unique application ID. Must be an integer.'
                ),
                required=False,
                type=OpenApiTypes.INT
            ),
            OpenApiParameter(
                name='search_term',
                description=(
                        'Filter applications by their applicants. Partial search by first_name, last_name and PPS number.'
                ),
                required=False,
                type=OpenApiTypes.STR
            ),
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
            OpenApiParameter(name='approved',
                             description='Filter by approval status (true/false). This is based on the application, but also commitee approval status if applicable',
                             required=False,
                             type=bool),
            OpenApiParameter(name='is_rejected',
                             description='Filter by rejection status (true/false). This is based on the application, but also commitee approval status if applicable',
                             required=False,
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

        user = self.request.user

        # Get the user's teams and filter based on the country
        country_filters = []
        if user.teams.filter(name='ie_team').exists():
            country_filters.append('IE')
        if user.teams.filter(name='uk_team').exists():
            country_filters.append('UK')

            # Check if no country filters were added
        if not country_filters:
            raise PermissionDenied("You must be assigned to at least one team to access this resource.")

        queryset = queryset.filter(user__country__in=country_filters)

        stat = self.request.query_params.get('status', None)
        assigned = self.request.query_params.get('assigned', None)

        search_term = self.request.query_params.get('search_term', None)
        search_id = self.request.query_params.get('search_id', None)

        if search_id:
            try:
                search_id = int(search_id)  # Ensure search_id is an integer
                queryset = queryset.filter(id=search_id)
                return queryset
            except ValueError:
                raise DRFValidationError({"search_id": "Invalid ID. Must be an integer."})

                # Filter by applicant search term
        if search_term:
            queryset = queryset.filter(
                Q(applicants__first_name__icontains=search_term) |
                Q(applicants__last_name__icontains=search_term) |
                Q(applicants__pps_number__icontains=search_term) |
                Q(applicants__email__icontains=search_term) |
                Q(applicants__phone_number__icontains=search_term) |
                Q(applicants__city__icontains=search_term) |
                Q(applicants__county__icontains=search_term)
            ).distinct()
            return queryset

        if assigned is not None:
            if assigned == "true":
                queryset = queryset.filter(assigned_to=self.request.user)
            if assigned == "false":
                queryset = queryset.filter(assigned_to=None)

            # Filter based on status parameter
        if stat is not None:
            if stat == 'active':
                # Applications that are not rejected or approved, or need committee approval and are pending approval
                queryset = queryset.filter(
                    Q(is_rejected=False, approved=False) |
                    Q(
                        approved=True,
                        loan__isnull=False,
                        loan__needs_committee_approval=True,
                        loan__is_committee_approved__isnull=True
                    )
                ).distinct()

            elif stat == 'rejected':
                # Applications explicitly rejected or rejected in the loan approval process
                queryset = queryset.filter(
                    Q(is_rejected=True) |
                    Q(
                        is_rejected=False,
                        approved=True,
                        loan__isnull=False,
                        loan__needs_committee_approval=True,
                        loan__is_committee_approved=False
                    )
                ).distinct()

            elif stat == 'approved':
                # Approved applications with loans that are not paid out or settled
                queryset = queryset.filter(
                    approved=True,
                    loan__isnull=False
                ).filter(
                    (Q(loan__needs_committee_approval=False) & Q(loan__is_paid_out=False) & Q(loan__is_settled=False)) |
                    (Q(loan__needs_committee_approval=True) & Q(loan__is_committee_approved=True) & Q(
                        loan__is_paid_out=False) & Q(loan__is_settled=False))
                )

            elif stat == 'paid_out':
                # Applications with loans paid out but not settled
                queryset = queryset.filter(
                    approved=True,
                    loan__isnull=False
                ).filter(
                    (Q(loan__needs_committee_approval=False) & Q(loan__is_paid_out=True) & Q(loan__is_settled=False)) |
                    (Q(loan__needs_committee_approval=True) & Q(loan__is_committee_approved=True) & Q(
                        loan__is_paid_out=True) & Q(loan__is_settled=False))
                )
                # Add maturity_date dynamically and sort
                queryset = sorted(
                    queryset,
                    key=lambda
                        app: app.loan.maturity_date if app.loan and app.loan.maturity_date else timezone.datetime.max
                )
                return queryset

            elif stat == 'settled':
                # Applications with loans that are fully paid out and settled
                queryset = queryset.filter(
                    approved=True,
                    loan__isnull=False
                ).filter(
                    (Q(loan__needs_committee_approval=False) & Q(loan__is_paid_out=True) & Q(loan__is_settled=True)) |
                    (Q(loan__needs_committee_approval=True) & Q(loan__is_committee_approved=True) & Q(
                        loan__is_paid_out=True) & Q(loan__is_settled=True))
                )

        return queryset.order_by('-id')

    @action(detail=False, methods=['get'], url_path='search-applications')
    def search_applications(self, request):
        """
        Search all applications based on any model field, supporting foreign key and date filtering.
        Returns the whole application data using AgentApplicationDetailSerializer.
        """
        queryset = self.queryset

        # automatic filtering based on what team_country is request user
        user = request.user
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
        queryset = queryset.filter(user__country__in=country_filters)

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

        # Optimize related object fetching with select_related and prefetch_related
        queryset = queryset.select_related('user', 'solicitor', 'assigned_to').order_by("-id").prefetch_related(
            'applicants')

        # Serialize the entire application data using AgentApplicationDetailSerializer
        serializer = serializers.AgentApplicationDetailSerializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

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

    # def validate_applicants(self, applicants_data):
    #     """Validate the PPS numbers of the applicants."""
    #     pps_regex = re.compile(r'^\d{7}[A-Z]{1,2}$')
    #     for applicant in applicants_data:
    #         pps_number = applicant.get('pps_number')
    #         pps_number = pps_number.upper()
    #         if not pps_regex.match(pps_number):
    #             raise DRFValidationError({
    #                 'pps_number': 'PPS Number must be 7 digits followed by 1 or 2 letters.'
    #             })

    # @transaction.atomic
    # def perform_create(self, serializer):
    #     request_body = self.request.data
    #     applicants_data = request_body.get('applicants', [])
    #     self.validate_applicants(applicants_data)
    #     """Create a new application."""
    #     try:
    #         serializer.save(user=self.request.user)
    #         log_event(self.request, request_body, serializer.instance, response_status=201)
    #     except Exception as e:  # Catch any type of exception
    #         log_event(self.request, request_body, application=serializer.instance)
    #         raise e  # Re-raise the caught exception

    @transaction.atomic
    def perform_update(self, serializer):
        """when updating an application."""
        request_body = self.request.data
        applicants_data = request_body.get('applicants', [])
        try:
            instance = self.get_object()

            # print(instance)

            ApplicantsValidator.validate(applicants_data, instance.user)

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

    def move_file_to_deleted_directory(self, document):
        """
        Move file to deletedFiles directory, handling both local and Azure storage
        """
        if not document.document:
            return

        try:
            # Get original file name/path
            original_file_name = document.document.name  # This works for both local and Azure

            if not original_file_name:
                return

            # Create deleted files path
            deleted_file_path = f"deletedFiles/{document.application.id}/{os.path.basename(original_file_name)}"

            # Handle filename conflicts by adding timestamp if file already exists
            if default_storage.exists(deleted_file_path):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name, ext = os.path.splitext(os.path.basename(original_file_name))
                deleted_file_path = f"deletedFiles/{document.application.id}/{name}_{timestamp}{ext}"

            # Check if original file exists
            if default_storage.exists(original_file_name):
                if settings.DEBUG:
                    # Local storage - use filesystem operations
                    self._move_file_local(document, deleted_file_path)
                else:
                    # Azure storage - use storage backend operations
                    self._move_file_azure(document, deleted_file_path)

                print(f"Moved document file from {original_file_name} to {deleted_file_path}")
            else:
                print(f"Original file {original_file_name} does not exist")

        except Exception as e:
            print(f"Error moving document file {original_file_name}: {e}")
            # Continue with deletion even if move fails

    def _move_file_local(self, document, deleted_file_path):
        """Handle file moving for local storage"""
        original_file_path = document.document.path
        full_deleted_path = os.path.join(settings.MEDIA_ROOT, deleted_file_path)

        # Create directory structure
        os.makedirs(os.path.dirname(full_deleted_path), exist_ok=True)

        # Move the file
        shutil.move(original_file_path, full_deleted_path)

    def _move_file_azure(self, document, deleted_file_path):
        """Handle file moving for Azure Blob Storage"""
        original_file_name = document.document.name

        # Read the original file content
        with default_storage.open(original_file_name, 'rb') as original_file:
            file_content = original_file.read()

        # Save to new location
        default_storage.save(deleted_file_path, ContentFile(file_content))

        # Delete the original file
        default_storage.delete(original_file_name)

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

            # Move file to deletedFiles directory before deleting the database record
            self.move_file_to_deleted_directory(document)

            # Delete the database record
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


class NewApplicationViewSet(viewsets.ViewSet):
    """
    A ViewSet for managing new applications.
    """

    # Add authentication and permission classes
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List IDs of new applications",
        description="Returns a list of application IDs where `is_new=True`.",
        tags=["agent_application"],
        responses={
            200: {
                "description": "A list of new application IDs.",
                "examples": {"new_application_ids": [1, 2, 3]},
            },
            403: {"description": "Forbidden - Authentication credentials not provided."},
        },
    )
    @action(detail=False, methods=['get'], url_path='list')
    def list_new(self, request):
        """
        List IDs of applications where `is_new=True`.
        """
        country_teams = self.request.user.teams.all().filter(name__endswith='_team')
        # Extract the part of the name before '_team'
        filtered_team_names = [team.name.rsplit('_team', 1)[0].upper() for team in country_teams]

        new_applications = models.Application.objects.filter(
            is_new=True
        ).values('id', 'assigned_to__email', "user__country")

        new_applications_for_agent_teams = new_applications.filter(user__country__in=filtered_team_names)
        # print(new_applications_for_agent_teams)

        return Response({"new_application_ids": list(new_applications_for_agent_teams)}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Mark an application as seen",
        description="Sets the `is_new` field to `False` for the specified application ID.",
        tags=["agent_application"],
        responses={
            200: {
                "description": "The application has been marked as seen.",
                "examples": {"message": "Application 1 marked as seen."},
            },
            404: {"description": "Application with the given ID does not exist."},
        },
    )
    @action(detail=True, methods=['patch'], url_path='mark-seen')
    def mark_seen(self, request, pk=None):
        """
        Mark an application as not new (`is_new=False`) based on the provided ID.
        """
        try:
            application = models.Application.objects.get(pk=pk)
            application.is_new = False
            application.save()
            return Response({"message": f"Application {pk} marked as seen."}, status=status.HTTP_200_OK)
        except models.Application.DoesNotExist:
            return Response({"error": f"Application with ID {pk} does not exist."}, status=status.HTTP_404_NOT_FOUND)


class ApplicationProcessingStatusCreateView(APIView):
    """
    Create ApplicationProcessingStatus for an application.
    Only allows creation - updates and deletes must be done through admin.
    """
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    def post(self, request, application_id):
        """Create processing status for an application"""
        try:
            # Get the application
            application = get_object_or_404(Application, id=application_id)

            # Check if processing status already exists
            if hasattr(application, 'processing_status'):
                return Response(
                    {
                        'error': 'Processing status already exists for this application. Updates must be done through admin.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the processing status
            processing_status = ApplicationProcessingStatus.objects.create(
                application=application,
                application_details_completed_confirmed=request.data.get('application_details_completed_confirmed',
                                                                         False),
                solicitor_preferred_aml_method=request.data.get('solicitor_preferred_aml_method'),
                last_updated_by=request.user
            )

            # Serialize and return the created object
            serializer = ApplicationProcessingStatusSerializer(processing_status)

            return Response(
                {
                    'message': 'Processing status created successfully',
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        except Application.DoesNotExist:
            return Response(
                {'error': 'Application not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get(self, request, application_id):
        """Get processing status for an application"""
        try:
            application = get_object_or_404(Application, id=application_id)

            if hasattr(application, 'processing_status'):
                serializer = ApplicationProcessingStatusSerializer(application.processing_status)
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'message': 'No processing status found for this application'},
                    status=status.HTTP_404_NOT_FOUND
                )

        except Application.DoesNotExist:
            return Response(
                {'error': 'Application not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def put(self, request, application_id):
        """Prevent updates through API"""
        return Response(
            {'error': 'Updates not allowed through API. Please use admin interface.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def patch(self, request, application_id):
        """Prevent partial updates through API"""
        return Response(
            {'error': 'Updates not allowed through API. Please use admin interface.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def delete(self, request, application_id):
        """Prevent deletes through API"""
        return Response(
            {'error': 'Deletes not allowed through API. Please use admin interface.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


# Add this class to your existing views.py file

class NotifySolicitorDocumentUploadView(APIView):
    """
    Notify solicitor that new documents have been uploaded to an application.
    """
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsStaff]

    @extend_schema(
        summary="Notify solicitor of new document upload {-Works only for staff users-}",
        description="Sends an email notification to the solicitor when new documents are uploaded to an application.",
        tags=["document_agent"],
        responses={
            200: {"description": "Email notification sent successfully"},
            404: {"description": "Application not found"},
            400: {"description": "No solicitor associated with this application or email sending failed"}
        }
    )
    def post(self, request, application_id):
        try:
            # Get the application
            application = get_object_or_404(models.Application, id=application_id)

            # Check if application has a solicitor
            if not application.solicitor or not application.user.email:
                return Response(
                    {'error': 'No solicitor email found for this application'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get the sender (current user)
            sender_email = request.user.email
            recipient_email = application.user.email

            # Create email subject
            subject = f"New Documents Added - Application #{application.id}"

            # Create email message using HTML template
            message = self._create_email_template(application, request.user)

            # Send email using the provided function
            email_result = send_email_f(
                sender=sender_email,
                recipient=recipient_email,
                subject=subject,
                message=message,
                application=application,
                solicitor_firm=application.user,
                use_info_email=True,  # Use default info email as sender

            )

            if 'error' in email_result:
                return Response(
                    {'error': f'Failed to send email: {email_result["error"]}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Log the notification event
            log_event(
                request=request,
                request_body={'action': 'solicitor_document_notification_sent'},
                application=application,
                response_status=200
            )

            return Response(
                {
                    'message': 'Email notification sent successfully to solicitor',
                    'solicitor_email': recipient_email,
                    'application_id': application.id
                },
                status=status.HTTP_200_OK
            )

        except models.Application.DoesNotExist:
            return Response(
                {'error': 'Application not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'An error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _create_email_template(self, application, sender_user):
        """
        Create a professional HTML email template for document upload notification.
        """
        # Get sender name for personalization
        sender_name = getattr(sender_user, 'name', sender_user.email).split()[0] if hasattr(sender_user,
                                                                                            'name') and sender_user.name else 'Team'

        # Get applicant names for reference
        applicant_names = []
        if hasattr(application, 'applicants') and application.applicants.exists():
            applicant_names = [f"{applicant.first_name} {applicant.last_name}" for applicant in
                               application.applicants.all()]

        applicant_text = ", ".join(applicant_names) if applicant_names else "N/A"

        # Get recent documents count (documents uploaded today)
        today = timezone.now().date()
        recent_docs_count = models.Document.objects.filter(
            application=application,
            created_at__date=today
        ).count()

        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>New Documents Added</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f4f4f4;
                }}
                .email-container {{
                    background-color: #ffffff;
                    border-radius: 8px;
                    padding: 30px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .header {{
                    background-color: #2c3e50;
                    color: white;
                    padding: 20px;
                    border-radius: 8px 8px 0 0;
                    margin: -30px -30px 20px -30px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .application-info {{
                    background-color: #ecf0f1;
                    padding: 15px;
                    border-radius: 6px;
                    margin: 20px 0;
                }}
                .info-row {{
                    margin: 8px 0;
                }}
                .label {{
                    font-weight: bold;
                    color: #2c3e50;
                }}
                .value {{
                    margin-left: 10px;
                }}
                .highlight {{
                    background-color: #e8f5e8;
                    padding: 15px;
                    border-left: 4px solid #27ae60;
                    margin: 20px 0;
                }}
                .footer {{
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #ecf0f1;
                    font-size: 14px;
                    color: #7f8c8d;
                }}
                .button {{
                    display: inline-block;
                    padding: 12px 25px;
                    background-color: #3498db;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin: 15px 0;
                }}
                .urgent {{
                    color: #e74c3c;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>📄 New Documents Added</h1>
                </div>

                <p>Dear {application.solicitor.name if hasattr(application.solicitor, 'name') and application.solicitor.name else 'Solicitor'},</p>

                <p>We wanted to inform you that new documents have been uploaded to one of your loan applications in our system.</p>

                <div class="highlight">
                    <strong>📋 Application Details:</strong>
                </div>

                <div class="application-info">
                    <div class="info-row">
                        <span class="label">Application ID:</span>
                        <span class="value">#{application.id}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Applicant(s):</span>
                        <span class="value">{applicant_text}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Loan Amount:</span>
                        <span class="value">€{application.amount:,.2f}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Application Status:</span>
                        <span class="value">{'Approved' if application.approved else 'Rejected' if application.is_rejected else 'Under Review'}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Documents Added Today:</span>
                        <span class="value urgent">{recent_docs_count} new document(s)</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Added by:</span>
                        <span class="value">{sender_name}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Date & Time:</span>
                        <span class="value">{timezone.now().strftime('%B %d, %Y at %I:%M %p')}</span>
                    </div>
                </div>

                <p><strong>📝 Next Steps:</strong></p>
                <ul>
                    <li>Please log into your portal to review the newly uploaded documents</li>
                    <li>Verify that all required documentation is now complete</li>
                    <li>Contact us if you have any questions about the uploaded materials</li>
                </ul>

                <p>If you need to review or download these documents, please access your secure portal or contact our team directly.</p>

                <div class="footer">
                    <p><strong>Important:</strong> This is an automated notification. Please do not reply to this email directly.</p>
                    <p>If you have any questions or concerns, please contact our support team.</p>
                    <p><em>This email was sent from our loan application management system on {timezone.now().strftime('%B %d, %Y')}.</em></p>
                </div>
            </div>
        </body>
        </html>
        """

        return html_template
