"""
Views for solicitors_application API
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import JsonResponse, Http404, HttpResponse, HttpResponseNotFound, HttpResponseForbidden

import os

from django.shortcuts import get_object_or_404
from rest_framework import (viewsets, status)
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app import settings
from app.pagination import CustomPageNumberPagination
from app.utils import log_event
from core.models import Document, Notification, Solicitor
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
    authentication_classes = (JWTAuthentication,)
    permission_classes = [IsAuthenticated, IsNonStaff]
    pagination_class = CustomPageNumberPagination

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
            pps_number = pps_number.upper()
            if not pps_regex.match(pps_number):
                raise DRFValidationError({
                    'pps_number': 'PPS Number must be 7 digits followed by 1 or 2 letters.'
                })

    @transaction.atomic
    def perform_create(self, serializer):
        """Create a new application."""
        request_body = self.request.data

        # check and assign applicants
        applicants_data = request_body.get('applicants', [])

        self.validate_applicants(applicants_data)

        try:
            serializer.save(user=self.request.user)
            log_event(self.request, request_body, serializer.instance)
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
            }
        )

    @transaction.atomic
    def perform_update(self, serializer):
        """Update an existing application."""
        request_body = self.request.data
        applicants_data = request_body.get('applicants', [])
        estates_data = request_body.get('estates', [])

        # Ensure applicants_data and estates_data are lists or empty lists
        if applicants_data is None:
            applicants_data = []
        if estates_data is None:
            estates_data = []

        self.validate_applicants(applicants_data)

        try:
            instance = self.get_object()  # Get the current instance
            original_data = instance.__dict__.copy()  # Get a copy of the original data as a dictionary

            # Get the original applicants and estates data, ensuring they're lists
            original_applicants = list(instance.applicants.all().values()) if instance.applicants.exists() else []
            original_estates = list(instance.estates.all().values()) if instance.estates.exists() else []

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
                                        estates=original_estates,
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
                    updated_estates = list(
                        updated_instance.estates.all().values()) if updated_instance.estates.exists() else []

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
                                changes.append(f"{field} changed from {original_value} to {updated_value}")

                    # Compare original and updated applicants data
                    applicants_changes = self.compare_applicants(original_applicants, updated_applicants)
                    changes.extend(applicants_changes)

                    # Compare original and updated estates data
                    estates_changes = self.compare_estates(original_estates, updated_estates)
                    changes.extend(estates_changes)

                    # Check for changes in deceased fields
                    if original_deceased and updated_deceased:
                        deceased_changes = self.compare_deceased(original_deceased, updated_deceased)
                        changes.extend(deceased_changes)

                    # Check for changes in dispute fields
                    if original_dispute and updated_dispute:
                        dispute_changes = self.compare_dispute(original_dispute, updated_dispute)
                        changes.extend(dispute_changes)

                    # Create a change message only if there are actual changes
                    if changes:
                        change_message = "; ".join(changes)

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
                                'changes': changes
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
            changes.append(f"Applicant added: {dict(applicant)}")

        # Detect removed applicants
        removed_applicants = original_set - updated_set
        for applicant in removed_applicants:
            changes.append(f"Applicant removed: {dict(applicant)}")

        # Detect modified applicants
        for original_applicant in original_applicants:
            matching_updated_applicant = next(
                (app for app in updated_applicants if app['id'] == original_applicant['id']), None)
            if matching_updated_applicant:
                for key in original_applicant:
                    if original_applicant[key] != matching_updated_applicant[key]:
                        changes.append(
                            f"Applicant {original_applicant['id']} field '{key}' changed from {original_applicant[key]} to {matching_updated_applicant[key]}"
                        )

        return changes

    def compare_estates(self, original_estates, updated_estates):
        """
        Compare original and updated estates data and return a list of changes.
        """
        changes = []

        # Ensure both original and updated estates are not None
        original_estates = original_estates or []
        updated_estates = updated_estates or []

        # Convert list of dictionaries to sets for easier comparison
        original_set = set(tuple(sorted(d.items())) for d in original_estates)
        updated_set = set(tuple(sorted(d.items())) for d in updated_estates)

        # Detect added estates
        added_estates = updated_set - original_set
        for estate in added_estates:
            changes.append(f"Estate added: {dict(estate)}")

        # Detect removed estates
        removed_estates = original_set - updated_set
        for estate in removed_estates:
            changes.append(f"Estate removed: {dict(estate)}")

        # Detect modified estates
        for original_estate in original_estates:
            matching_updated_estate = next(
                (est for est in updated_estates if est['id'] == original_estate['id']), None)
            if matching_updated_estate:
                for key in original_estate:
                    if original_estate[key] != matching_updated_estate[key]:
                        changes.append(
                            f"Estate {original_estate['id']} field '{key}' changed from {original_estate[key]} to {matching_updated_estate[key]}"
                        )

        return changes

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        request_body = self.request.data
        instance = None
        try:
            instance = self.get_object()
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
