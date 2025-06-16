from rest_framework import status, permissions
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from django.db.models import Max
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
from .models import DocumentType, ApplicationDocumentRequirement
from .serializers import (
    DocumentTypeSerializer,
    ApplicationDocumentRequirementSerializer,
    RequirementStatusSerializer
)
from core.models import Application


@extend_schema(
    summary="List all available document types",
    description="Returns all active document types that can be added as requirements to applications",
    tags=["document-requirements"],
    responses={200: DocumentTypeSerializer(many=True)}
)
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([permissions.IsAuthenticated])
def list_document_types(request):
    """List all available document types"""
    document_types = DocumentType.objects.filter(is_active=True).order_by('order', 'name')
    serializer = DocumentTypeSerializer(document_types, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Get application document requirements",
    description="Returns all document requirements for a specific application with upload status",
    tags=["document-requirements"],
    parameters=[
        OpenApiParameter(
            name="application_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Application ID"
        )
    ],
    responses={200: ApplicationDocumentRequirementSerializer(many=True)}
)
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_application_requirements(request, application_id):
    """Get all document requirements for an application"""
    application = get_object_or_404(Application, id=application_id)
    requirements = application.document_requirements.select_related(
        'document_type', 'created_by'
    ).prefetch_related('application__documents')

    serializer = ApplicationDocumentRequirementSerializer(requirements, many=True)
    return Response(serializer.data)


@extend_schema(
    summary="Add document requirement to application",
    description="Adds a document type as a requirement for the specified application",
    tags=["document-requirements"],
    parameters=[
        OpenApiParameter(
            name="application_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Application ID"
        )
    ],
    request=OpenApiTypes.OBJECT,
    examples=[
        OpenApiExample(
            name="Add Document Requirement",
            value={"document_type_id": 1},
            request_only=True
        )
    ],
    responses={
        201: ApplicationDocumentRequirementSerializer,
        400: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT
    }
)
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([permissions.IsAuthenticated])
def add_document_requirement(request, application_id):
    """Add a document requirement to an application"""
    application = get_object_or_404(Application, id=application_id)

    try:
        document_type_id = request.data.get('document_type_id')
        if not document_type_id:
            return Response(
                {'error': 'document_type_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        document_type = get_object_or_404(DocumentType, id=document_type_id, is_active=True)

        # Create requirement
        requirement = ApplicationDocumentRequirement.objects.create(
            application=application,
            document_type=document_type,
            created_by=request.user
        )

        serializer = ApplicationDocumentRequirementSerializer(requirement)
        return Response({
            'message': f'Document requirement "{document_type.name}" added successfully',
            'requirement': serializer.data
        }, status=status.HTTP_201_CREATED)

    except IntegrityError:
        return Response(
            {'error': 'Document requirement already exists for this application'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="Remove document requirement from application",
    description="Removes a document type requirement from the specified application",
    tags=["document-requirements"],
    parameters=[
        OpenApiParameter(
            name="application_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Application ID"
        ),
        OpenApiParameter(
            name="document_type_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Document Type ID"
        )
    ],
    responses={
        200: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT
    }
)
@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([permissions.IsAuthenticated])
def remove_document_requirement(request, application_id, document_type_id):
    """Remove a document requirement from an application"""
    application = get_object_or_404(Application, id=application_id)

    try:
        requirement = ApplicationDocumentRequirement.objects.get(
            application=application,
            document_type_id=document_type_id
        )

        document_type_name = requirement.document_type.name
        requirement.delete()

        return Response({
            'message': f'Document requirement "{document_type_name}" removed successfully'
        }, status=status.HTTP_200_OK)

    except ApplicationDocumentRequirement.DoesNotExist:
        return Response(
            {'error': 'Document requirement not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'An error occurred: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="Get application requirement status",
    description="Returns comprehensive summary of document requirements and upload status for an application",
    tags=["document-requirements"],
    parameters=[
        OpenApiParameter(
            name="application_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Application ID"
        )
    ],
    responses={200: RequirementStatusSerializer}
)
@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([permissions.IsAuthenticated])
def get_requirement_status(request, application_id):
    """Get comprehensive summary of document requirements and upload status"""
    application = get_object_or_404(Application, id=application_id)

    requirements = application.document_requirements.select_related(
        'document_type', 'created_by'
    ).prefetch_related('application__documents')

    total_requirements = requirements.count()
    uploaded_count = sum(1 for req in requirements if req.is_uploaded)
    missing_count = total_requirements - uploaded_count

    # Signature-specific stats
    signature_requirements = requirements.filter(document_type__signature_required=True)
    signature_required_count = signature_requirements.count()
    signature_uploaded_count = sum(1 for req in signature_requirements if req.is_uploaded)

    # Recent activity
    last_requirement_added = requirements.aggregate(
        last_added=Max('created_at')
    )['last_added']

    last_document_uploaded = None
    if application.documents.exists():
        last_document_uploaded = application.documents.aggregate(
            last_uploaded=Max('created_at')
        )['last_uploaded']

    response_data = {
        'application_id': application_id,
        'total_requirements': total_requirements,
        'uploaded_count': uploaded_count,
        'missing_count': missing_count,
        'completion_percentage': (uploaded_count / total_requirements * 100) if total_requirements > 0 else 0,
        'signature_required_count': signature_required_count,
        'signature_uploaded_count': signature_uploaded_count,
        'last_requirement_added': last_requirement_added,
        'last_document_uploaded': last_document_uploaded,
        'requirements': ApplicationDocumentRequirementSerializer(requirements, many=True).data
    }

    return Response(response_data)


@extend_schema(
    summary="Bulk add document requirements",
    description="Add multiple document requirements to an application at once",
    tags=["document-requirements"],
    parameters=[
        OpenApiParameter(
            name="application_id",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="Application ID"
        )
    ],
    request=OpenApiTypes.OBJECT,
    examples=[
        OpenApiExample(
            name="Bulk Add Requirements",
            value={"document_type_ids": [1, 2, 3]},
            request_only=True
        )
    ],
    responses={
        201: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT
    }
)
@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([permissions.IsAuthenticated])
def bulk_add_requirements(request, application_id):
    """Add multiple document requirements to an application"""
    application = get_object_or_404(Application, id=application_id)

    document_type_ids = request.data.get('document_type_ids', [])
    if not document_type_ids or not isinstance(document_type_ids, list):
        return Response(
            {'error': 'document_type_ids must be a non-empty list'},
            status=status.HTTP_400_BAD_REQUEST
        )

    added_requirements = []
    skipped_requirements = []
    errors = []

    for doc_type_id in document_type_ids:
        try:
            document_type = DocumentType.objects.get(id=doc_type_id, is_active=True)
            requirement, created = ApplicationDocumentRequirement.objects.get_or_create(
                application=application,
                document_type=document_type,
                defaults={'created_by': request.user}
            )

            if created:
                added_requirements.append(document_type.name)
            else:
                skipped_requirements.append(document_type.name)

        except DocumentType.DoesNotExist:
            errors.append(f'Document type with ID {doc_type_id} not found')
        except Exception as e:
            errors.append(f'Error adding document type {doc_type_id}: {str(e)}')

    return Response({
        'message': f'Bulk operation completed',
        'added': added_requirements,
        'skipped': skipped_requirements,
        'errors': errors,
        'summary': {
            'added_count': len(added_requirements),
            'skipped_count': len(skipped_requirements),
            'error_count': len(errors)
        }
    }, status=status.HTTP_201_CREATED)
