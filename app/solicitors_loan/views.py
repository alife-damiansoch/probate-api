"""
Views for solicitors_application API
"""
from django.utils import timezone

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.db.models import Q
from django.http import JsonResponse, Http404, HttpResponse, HttpResponseNotFound, HttpResponseForbidden

import os

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from rest_framework import (viewsets, status)
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app import settings
from app.pagination import CustomPageNumberPagination
from app.utils import log_event
from core.Validators.validate_file_extension import is_valid_file_extension
from core.Validators.validate_file_size import is_valid_file_size
from core.models import Document, Notification, Solicitor, Assignment
from solicitors_loan import serializers
from core import models
from core.Validators.id_validators import ApplicantsValidator
from solicitors_loan.permissions import IsNonStaff

from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from rest_framework.exceptions import ValidationError as DRFValidationError
from django.db import transaction
import re


@extend_schema_view(
    list=extend_schema(
        summary='Retrieve all solicitor applications {-Works only for non-staff users-}',
        description='Returns all solicitor applications with optional filters for status, applicant search, and application ID.',
        tags=['solicitor_application'],
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
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsNonStaff]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        queryset = self.queryset.filter(user=self.request.user).order_by('-id')

        # Extract query parameters
        stat = self.request.query_params.get('status', None)
        search_term = self.request.query_params.get('search_term', None)
        search_id = self.request.query_params.get('search_id', None)

        if search_id:
            try:
                search_id = int(search_id)  # Ensure search_id is an integer
                queryset = queryset.filter(id=search_id)
                return queryset
            except ValueError:
                raise DRFValidationError({"search_id": "Invalid ID. Must be an integer."})

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

    def get_serializer_class(self):
        """Return serializer class for the requested model."""
        if self.action == 'list':
            return serializers.SolicitorApplicationSerializer
        return self.serializer_class

    @transaction.atomic
    def perform_create(self, serializer):
        """Create a new application."""
        request_body = self.request.data

        # check and assign applicants
        applicants_data = request_body.get('applicants', [])
        user = self.request.user

        ApplicantsValidator.validate(applicants_data, user)

        try:
            serializer.save(user=self.request.user)
            log_event(self.request, request_body, serializer.instance)

            # Check for the Assignment and set the assigned_to field
            agency_user = self.request.user
            assignment = Assignment.objects.filter(agency_user=agency_user).first()

            if assignment:
                # If the user is found in the Assignment table as an agency user, set the staff_user
                serializer.instance.assigned_to = assignment.staff_user
                serializer.instance.save()

        except Exception as e:  # Catch any type of exception
            log_event(self.request, request_body, application=serializer.instance)
            raise e  # Re-raise the caught exception

            # Broadcast the notification
        assigned_to_user = serializer.instance.assigned_to

        notification = Notification.objects.create(
            recipient=assigned_to_user,
            text='Application created',
            seen=False,
            created_by=self.request.user,
            application=serializer.instance
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'broadcast',
            {
                'type': 'notification',
                'message': notification.text,
                'recipient': notification.recipient.email if notification.recipient else None,
                'notification_id': notification.id,
                'application_id': serializer.instance.id,
                'seen': notification.seen,
                'country': serializer.instance.user.country,
            }
        )

    @transaction.atomic
    def perform_update(self, serializer):
        """Update an existing application."""
        request_body = self.request.data
        applicants_data = request_body.get('applicants', [])

        # Ensure applicants_data and estates_data are lists or empty lists
        if applicants_data is None:
            applicants_data = []

        user = self.request.user
        ApplicantsValidator.validate(applicants_data, user)

        try:
            instance = self.get_object()  # Get the current instance
            original_data = instance.__dict__.copy()  # Get a copy of the original data as a dictionary

            # Get the original applicants and estates data, ensuring they're lists
            original_applicants = list(instance.applicants.all().values()) if instance.applicants.exists() else []

            # Get the original deceased and dispute objects
            original_deceased = instance.deceased
            original_dispute = instance.dispute

            if instance.approved:
                log_event(self.request, request_body, serializer.instance)
                raise DRFValidationError("This operation is not allowed on approved applications")
            elif instance.is_rejected:
                log_event(self.request, request_body, serializer.instance)
                raise ValidationError("This operation is not allowed on rejected applications")
            else:
                # Check if request data only contains `solicitor`
                if len(request_body.keys()) == 1 and 'solicitor' in request_body:
                    try:

                        solicitor_id = request_body.get('solicitor', None)
                        # Get the Solicitor instance
                        solicitor_instance = get_object_or_404(Solicitor, id=solicitor_id)
                        # Save the updated instance
                        serializer.save(last_updated_by=self.request.user,
                                        solicitor=solicitor_instance,

                                        applicants=original_applicants,
                                        )

                        log_event(self.request, request_body, serializer.instance)

                        # Broadcast the notification
                        assigned_to_user = serializer.instance.assigned_to

                        notification = Notification.objects.create(
                            recipient=assigned_to_user,
                            text=f'Application updated: Solicitor changed',
                            seen=False,
                            created_by=self.request.user,
                            application=serializer.instance
                        )

                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            'broadcast',
                            {
                                'type': 'notification',
                                'message': notification.text,
                                'recipient': notification.recipient.email if notification.recipient else None,
                                'notification_id': notification.id,
                                'application_id': serializer.instance.id,
                                'seen': notification.seen,
                                'country': serializer.instance.user.country,
                            }
                        )
                    except Exception as e:
                        log_event(self.request, request_body, application=serializer.instance)
                        raise e
                else:
                    # Save the updated instance
                    serializer.save(last_updated_by=self.request.user)
                    log_event(self.request, request_body, serializer.instance)

                    # Get updated instance data
                    updated_instance = serializer.instance
                    updated_data = updated_instance.__dict__.copy()  # Get a copy of the updated data as a dictionary

                    # Get updated applicants and estates data, ensuring they're lists
                    updated_applicants = list(
                        updated_instance.applicants.all().values()) if updated_instance.applicants.exists() else []

                    # Get the updated deceased and dispute objects
                    updated_deceased = updated_instance.deceased
                    updated_dispute = updated_instance.dispute

                    # Compare original and updated data to find changes in main fields
                    changes = []
                    for field, original_value in original_data.items():
                        if field in updated_data and field not in ['_state',
                                                                   'id']:  # Ignore non-field attributes and primary key
                            updated_value = updated_data[field]
                            if original_value != updated_value:
                                changes.append(f"{field} changed")  # Only mention the field name

                    # Compare original and updated applicants data
                    applicants_changes = self.compare_applicants(original_applicants, updated_applicants)
                    if applicants_changes:
                        changes.append("Applicant data updated")

                    # Check for changes in deceased fields
                    if original_deceased and updated_deceased:
                        deceased_changes = self.compare_deceased(original_deceased, updated_deceased)
                        if deceased_changes:
                            changes.append("Deceased data updated")

                    # Check for changes in dispute fields
                    if original_dispute and updated_dispute:
                        dispute_changes = self.compare_dispute(original_dispute, updated_dispute)
                        if dispute_changes:
                            changes.append("Dispute data updated")

                    # Create a change message only if there are actual changes
                    if changes:
                        change_message = "; ".join(changes)
                        # print(f"message: {change_message}")

                        # Broadcast the notification
                        assigned_to_user = serializer.instance.assigned_to

                        notification = Notification.objects.create(
                            recipient=assigned_to_user,
                            text=f'Application updated: {change_message}',
                            seen=False,
                            created_by=self.request.user,
                            application=serializer.instance
                        )

                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            'broadcast',
                            {
                                'type': 'notification',
                                'message': notification.text,
                                'recipient': notification.recipient.email if notification.recipient else None,
                                'notification_id': notification.id,
                                'application_id': serializer.instance.id,
                                'seen': notification.seen,
                                'changes': changes,
                                'country': serializer.instance.user.country,
                            }
                        )
        except Exception as e:
            log_event(self.request, request_body, application=serializer.instance)
            raise e

    def compare_deceased(self, original_deceased, updated_deceased):
        """
        Compare original and updated deceased data and return a list of changes.
        """
        changes = []

        if original_deceased.first_name != updated_deceased.first_name:
            changes.append(
                f"Deceased's first name changed from {original_deceased.first_name} to {updated_deceased.first_name}")

        if original_deceased.last_name != updated_deceased.last_name:
            changes.append(
                f"Deceased's last name changed from {original_deceased.last_name} to {updated_deceased.last_name}")

        return changes

    def compare_dispute(self, original_dispute, updated_dispute):
        """
        Compare original and updated dispute data and return a list of changes.
        """
        changes = []

        if original_dispute.details != updated_dispute.details:
            changes.append(f"Dispute details changed from '{original_dispute.details}' to '{updated_dispute.details}'")

        return changes

    def compare_applicants(self, original_applicants, updated_applicants):
        """
        Compare original and updated applicants data and return a list of changes.
        """
        changes = []

        # Ensure both original and updated applicants are not None
        original_applicants = original_applicants or []
        updated_applicants = updated_applicants or []

        # Convert list of dictionaries to sets for easier comparison
        original_set = set(tuple(sorted(d.items())) for d in original_applicants)
        updated_set = set(tuple(sorted(d.items())) for d in updated_applicants)

        # Detect added applicants
        added_applicants = updated_set - original_set
        for applicant in added_applicants:
            applicant_dict = dict(applicant)
            changes.append(
                f"Applicant added: {applicant_dict.get('first_name', '')} {applicant_dict.get('last_name', '')}")

        # Detect removed applicants
        removed_applicants = original_set - updated_set
        for applicant in removed_applicants:
            applicant_dict = dict(applicant)
            changes.append(
                f"Applicant removed: {applicant_dict.get('first_name', '')} {applicant_dict.get('last_name', '')}")

        # Detect modified applicants
        for original_applicant in original_applicants:
            matching_updated_applicant = next(
                (app for app in updated_applicants if app['id'] == original_applicant['id']), None)
            if matching_updated_applicant:
                # Define important fields to track for changes
                important_fields = [
                    'title', 'first_name', 'last_name', 'pps_number',
                    'address_line_1', 'address_line_2', 'city', 'county',
                    'postal_code', 'country', 'date_of_birth', 'email', 'phone_number'
                ]

                for key in important_fields:
                    if key in original_applicant and key in matching_updated_applicant:
                        if original_applicant[key] != matching_updated_applicant[key]:
                            changes.append(
                                f"Applicant {original_applicant.get('first_name', '')} {original_applicant.get('last_name', '')} field '{key}' updated"
                            )

        return changes

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        request_body = self.request.data
        instance = None

        try:
            instance = self.get_object()
            users_country = instance.user.country
            if instance.approved:
                raise DRFValidationError("This operation is not allowed on approved applications")
            elif instance.is_rejected:
                raise ValidationError("This operation is not allowed on rejected applications")
            else:
                result = super().destroy(request, *args, **kwargs)  # carry out the deletion
                log_event(request, request_body)  # log after deletion is done

                # Broadcast notification
                assigned_to_user = instance.assigned_to

                notification = Notification.objects.create(
                    recipient=assigned_to_user,
                    text=f'Application id {instance.id} deleted',
                    seen=False,
                    created_by=request.user,
                    application=None
                )

                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'broadcast',
                    {
                        'type': 'notification',
                        'message': notification.text,
                        'recipient': notification.recipient.email if notification.recipient else None,
                        'notification_id': notification.id,
                        'application_id': None,
                        'seen': notification.seen,
                        'country': users_country
                    }
                )
                return result
        except Exception as e:
            log_event(request, request_body, application=instance)
            raise e


class SolicitorDocumentUploadAndViewListForApplicationIdView(APIView):
    serializer_class = serializers.SolicitorDocumentSerializer
    authentication_classes = (JWTAuthentication,)
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
        if "document" not in request.FILES:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = request.FILES.getlist("document")
        if not uploaded_file:
            return Response({"error": "No valid file provided."}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = uploaded_file[0]

        # ✅ **Validate File Extension**
        if not is_valid_file_extension(uploaded_file.name):
            return Response(
                {"error": f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_FILE_EXTENSIONS)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Validate file size
        if not is_valid_file_size(uploaded_file):
            return Response(
                {"error": f"File is too large. Max allowed size for {uploaded_file.name.split('.')[-1]} is exceeded."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Save file
        serializer = serializers.SolicitorDocumentSerializer(data=request.data)

        if serializer.is_valid():
            # store application instance for logging purpose
            application = models.Application.objects.get(id=application_id)
            serializer.save(application=application)

            # logging the successful POST request - FIXED THIS PART
            request_body = {}
            for key, value in request.data.items():
                if not isinstance(value, (InMemoryUploadedFile, TemporaryUploadedFile)):
                    request_body[key] = value
                else:
                    request_body[key] = 'A new file was uploaded.'

            log_event(request=request, request_body=request_body, application=application)

            # Broadcast the notification
            assigned_to_user = application.assigned_to

            notification = Notification.objects.create(
                recipient=assigned_to_user,
                text='New document uploaded',
                seen=False,
                created_by=request.user,
                application=application,
            )

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'broadcast',
                {
                    'type': 'notification',
                    'message': notification.text,
                    'recipient': notification.recipient.email if notification.recipient else None,
                    'notification_id': notification.id,
                    'application_id': application.id,
                    'seen': notification.seen,
                    'country': application.user.country,
                }
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SolicitorDocumentDeleteView(APIView):
    authentication_classes = (JWTAuthentication,)
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
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsNonStaff]

    @extend_schema(
        summary="Download a document with the given filename",
        description="Allows authenticated users to download a file if they have access permissions.",
        tags=["document_solicitor"],
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
