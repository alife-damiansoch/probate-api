# esignature/views.py
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from .models import SignatureDocument, DocumentSigner, SignatureField
from .serializers import (
    SignatureDocumentSerializer, SignatureDocumentCreateSerializer,
    DocumentSignerSerializer, CreateDocumentSignerSerializer,
    SignatureFieldSerializer, CreateSignatureFieldSerializer,
    BulkSignFieldsSerializer
)


class SignatureDocumentListCreateView(generics.ListCreateAPIView):
    """
    List all signature documents or create a new one
    GET: List documents created by the user
    POST: Create new signature document from your frontend data
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SignatureDocument.objects.filter(
            created_by=self.request.user
        ).select_related('source_document').prefetch_related(
            'signers__signature_fields', 'signature_fields'
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SignatureDocumentCreateSerializer
        return SignatureDocumentSerializer


class SignatureDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update or delete a specific signature document
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SignatureDocumentSerializer

    def get_queryset(self):
        return SignatureDocument.objects.filter(
            created_by=self.request.user
        ).select_related('source_document').prefetch_related(
            'signers__signature_fields', 'signature_fields'
        )


class DocumentSignerListCreateView(generics.ListCreateAPIView):
    """
    List signers for a document or add a new signer
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        document_id = self.kwargs['document_id']
        return DocumentSigner.objects.filter(
            signature_document_id=document_id,
            signature_document__created_by=self.request.user
        ).prefetch_related('signature_fields')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateDocumentSignerSerializer
        return DocumentSignerSerializer

    def perform_create(self, serializer):
        document_id = self.kwargs['document_id']
        signature_document = get_object_or_404(
            SignatureDocument,
            id=document_id,
            created_by=self.request.user
        )
        serializer.save(signature_document=signature_document)


class DocumentSignerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update or delete a specific signer
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DocumentSignerSerializer

    def get_queryset(self):
        return DocumentSigner.objects.filter(
            signature_document__created_by=self.request.user
        ).prefetch_related('signature_fields')


class SignatureFieldListCreateView(generics.ListCreateAPIView):
    """
    List signature fields for a document or add a new field
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        document_id = self.kwargs['document_id']
        return SignatureField.objects.filter(
            signature_document_id=document_id,
            signature_document__created_by=self.request.user
        ).select_related('signer')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateSignatureFieldSerializer
        return SignatureFieldSerializer


class SignatureFieldDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Get, update or delete a specific signature field
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SignatureFieldSerializer

    def get_queryset(self):
        return SignatureField.objects.filter(
            signature_document__created_by=self.request.user
        ).select_related('signer', 'signature_document')


class StartSigningProcessView(APIView):
    """
    Start the signing process for a document
    Changes status from 'draft' to 'ready_for_signing'
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, document_id):
        try:
            signature_document = get_object_or_404(
                SignatureDocument,
                id=document_id,
                created_by=request.user
            )

            if signature_document.status != 'draft':
                return Response(
                    {'error': 'Document is not in draft status'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if document has signers and fields
            if not signature_document.signers.exists():
                return Response(
                    {'error': 'Document must have at least one signer'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not signature_document.signature_fields.exists():
                return Response(
                    {'error': 'Document must have at least one signature field'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update document status
            signature_document.status = 'ready_for_signing'
            signature_document.save()

            return Response({
                'success': True,
                'message': 'Signing process started',
                'document_id': str(signature_document.id),
                'status': signature_document.status
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BulkSignFieldsView(APIView):
    """
    Sign multiple fields at once for a signer
    This matches your frontend's bulk signing functionality
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BulkSignFieldsSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    signer_id = serializer.validated_data['signer_id']
                    fields_data = serializer.validated_data['fields']

                    signer = DocumentSigner.objects.get(id=signer_id)
                    signed_fields = []

                    # Sign all fields
                    for field_data in fields_data:
                        field = SignatureField.objects.get(id=field_data['field_id'])

                        field.signed_value = field_data['signed_value']
                        field.is_signed = True
                        field.signed_at = timezone.now()
                        field.save()

                        signed_fields.append(field)

                    # Update signer status
                    signer_incomplete_fields = signer.signature_fields.filter(is_signed=False)
                    if not signer_incomplete_fields.exists():
                        signer.has_signed = True
                        signer.signed_at = timezone.now()
                        signer.save()

                    # Check document completion
                    document = signer.signature_document
                    if document.is_fully_signed:
                        document.status = 'fully_signed'
                        document.completed_at = timezone.now()
                        document.save()
                    elif document.status == 'draft':
                        document.status = 'partially_signed'
                        document.save()

                return Response({
                    'success': True,
                    'message': f'Successfully signed {len(signed_fields)} fields',
                    'signed_fields_count': len(signed_fields),
                    'signer_completed': signer.has_signed,
                    'document_completed': document.is_fully_signed,
                    'document_status': document.status
                })

            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DocumentSigningStatusView(APIView):
    """
    Get comprehensive signing status for a document
    Returns detailed progress information
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, document_id):
        try:
            signature_document = get_object_or_404(
                SignatureDocument,
                id=document_id,
                created_by=request.user
            )

            # Get signing status for each signer
            signers_status = []
            for signer in signature_document.signers.all():
                fields_status = []
                for field in signer.signature_fields.all():
                    fields_status.append({
                        'id': str(field.id),
                        'type': field.field_type,
                        'page': field.page_number,
                        'is_signed': field.is_signed,
                        'signed_at': field.signed_at,
                        'required': field.required
                    })

                signers_status.append({
                    'id': str(signer.id),
                    'name': signer.name,
                    'type': signer.signer_type,
                    'has_signed': signer.has_signed,
                    'signed_at': signer.signed_at,
                    'progress': signer.signing_progress,
                    'fields': fields_status
                })

            return Response({
                'document_id': str(signature_document.id),
                'document_name': signature_document.document_name,
                'status': signature_document.status,
                'is_fully_signed': signature_document.is_fully_signed,
                'signing_progress': signature_document.signing_progress,
                'completed_at': signature_document.completed_at,
                'signers': signers_status
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelDocumentSigningView(APIView):
    """
    Cancel the signing process for a document
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, document_id):
        try:
            signature_document = get_object_or_404(
                SignatureDocument,
                id=document_id,
                created_by=request.user
            )

            if signature_document.status in ['fully_signed', 'cancelled']:
                return Response(
                    {'error': f'Cannot cancel document with status: {signature_document.status}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Update document status
            signature_document.status = 'cancelled'
            signature_document.save()

            return Response({
                'success': True,
                'message': 'Document signing cancelled',
                'document_id': str(signature_document.id),
                'status': signature_document.status
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Simple function-based view for checking access (you can customize this)
from rest_framework.decorators import api_view, permission_classes


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_signing_access(request, document_id, signer_id):
    """
    Check if current user can access signing for a specific signer
    You can customize the access logic here
    """
    try:
        signature_document = get_object_or_404(SignatureDocument, id=document_id)
        signer = get_object_or_404(DocumentSigner, id=signer_id, signature_document=signature_document)

        # Basic access check - customize this logic
        can_access = True  # Implement your access control logic here

        return Response({
            'can_access': can_access,
            'signer': {
                'id': str(signer.id),
                'name': signer.name,
                'type': signer.signer_type,
                'has_signed': signer.has_signed
            },
            'document': {
                'id': str(signature_document.id),
                'name': signature_document.document_name,
                'status': signature_document.status
            }
        })

    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
