# esignature/serializers.py
from rest_framework import serializers

from core.models import Document
from .models import SignatureDocument, DocumentSigner, SignatureField


class SignatureFieldSerializer(serializers.ModelSerializer):
    """Serializer for signature fields - matches your frontend field structure"""

    class Meta:
        model = SignatureField
        fields = [
            'id', 'field_type', 'required', 'placeholder', 'is_auto_fill',
            'page_number', 'x_position', 'y_position', 'width', 'height',
            'is_signed', 'signed_value', 'signed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_signed', 'signed_value', 'signed_at', 'created_at', 'updated_at']


class DocumentSignerSerializer(serializers.ModelSerializer):
    """Serializer for document signers - includes all signer types"""
    signature_fields = SignatureFieldSerializer(many=True, read_only=True)
    signing_progress = serializers.ReadOnlyField()

    class Meta:
        model = DocumentSigner
        fields = [
            'id', 'name', 'email', 'signer_type', 'access_method',
            'applicant_id', 'solicitor_id', 'solicitor_email', 'role',
            'color', 'has_signed', 'signed_at', 'signing_order',
            'signature_fields', 'signing_progress', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'has_signed', 'signed_at', 'created_at', 'updated_at']


class SignatureDocumentSerializer(serializers.ModelSerializer):
    """Main serializer for signature documents"""
    signers = DocumentSignerSerializer(many=True, read_only=True)
    signature_fields = SignatureFieldSerializer(many=True, read_only=True)
    is_fully_signed = serializers.ReadOnlyField()
    signing_progress = serializers.ReadOnlyField()

    # Source document info
    source_document_url = serializers.SerializerMethodField()
    source_document_name = serializers.SerializerMethodField()

    class Meta:
        model = SignatureDocument
        fields = [
            'id', 'document_name', 'application_id', 'total_pages', 'pdf_scale',
            'status', 'created_at', 'updated_at', 'completed_at',
            'signers', 'signature_fields', 'is_fully_signed', 'signing_progress',
            'source_document_url', 'source_document_name'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']

    def get_source_document_url(self, obj):
        if obj.source_document and obj.source_document.document:
            return obj.source_document.document.url
        return None

    def get_source_document_name(self, obj):
        if obj.source_document:
            return obj.source_document.original_name or "Document"
        return "Document"


# Create/Update Serializers for specific operations

class CreateSignatureFieldSerializer(serializers.ModelSerializer):
    """Serializer for creating signature fields"""
    signer_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = SignatureField
        fields = [
            'field_type', 'required', 'placeholder', 'is_auto_fill',
            'page_number', 'x_position', 'y_position', 'width', 'height',
            'signer_id'
        ]

    def create(self, validated_data):
        signer_id = validated_data.pop('signer_id')
        signer = DocumentSigner.objects.get(id=signer_id)

        field = SignatureField.objects.create(
            signature_document=signer.signature_document,
            signer=signer,
            **validated_data
        )

        return field


class CreateDocumentSignerSerializer(serializers.ModelSerializer):
    """Serializer for creating document signers"""

    class Meta:
        model = DocumentSigner
        fields = [
            'name', 'email', 'signer_type', 'access_method',
            'applicant_id', 'solicitor_id', 'solicitor_email', 'role',
            'color', 'signing_order'
        ]

    def validate(self, data):
        """Validate signer data based on type"""
        signer_type = data.get('signer_type')

        if signer_type == 'applicant' and not data.get('applicant_id'):
            raise serializers.ValidationError("Applicant ID is required for applicant signers")

        if signer_type == 'solicitor' and not data.get('solicitor_id'):
            raise serializers.ValidationError("Solicitor ID is required for solicitor signers")

        if signer_type == 'custom':
            if not data.get('role'):
                raise serializers.ValidationError("Role is required for custom signers")
            if not data.get('name'):
                raise serializers.ValidationError("Name is required for custom signers")

        return data


class SignatureDocumentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating signature documents with full setup from your frontend"""
    signers_data = CreateDocumentSignerSerializer(many=True, write_only=True)
    fields_data = CreateSignatureFieldSerializer(many=True, write_only=True)
    source_document_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = SignatureDocument
        fields = [
            'document_name', 'application_id', 'total_pages', 'pdf_scale',
            'source_document_id', 'signers_data', 'fields_data'
        ]

    def create(self, validated_data):
        signers_data = validated_data.pop('signers_data', [])
        fields_data = validated_data.pop('fields_data', [])
        source_document_id = validated_data.pop('source_document_id')

        # Get the request user
        user = self.context['request'].user

        # Get source document (adjust the import path as needed)

        source_document = Document.objects.get(id=source_document_id)

        # Create the signature document
        signature_doc = SignatureDocument.objects.create(
            source_document=source_document,
            created_by=user,
            **validated_data
        )

        # Create signers and map them for field creation
        signers_map = {}
        for i, signer_data in enumerate(signers_data):
            signer = DocumentSigner.objects.create(
                signature_document=signature_doc,
                signing_order=i + 1,
                **signer_data
            )
            # Map by the temporary ID from frontend if it exists
            temp_id = signer_data.get('temp_id', str(signer.id))
            signers_map[temp_id] = signer

        # Create fields
        for field_data in fields_data:
            signer_id = field_data.pop('signer_id')

            # Find the signer by temp_id or actual ID
            signer = None
            if str(signer_id) in signers_map:
                signer = signers_map[str(signer_id)]
            else:
                try:
                    signer = signature_doc.signers.get(id=signer_id)
                except DocumentSigner.DoesNotExist:
                    continue

            if signer:
                SignatureField.objects.create(
                    signature_document=signature_doc,
                    signer=signer,
                    **field_data
                )

        return signature_doc


class SignFieldSerializer(serializers.Serializer):
    """Serializer for signing individual fields"""
    field_id = serializers.UUIDField()
    signed_value = serializers.CharField(allow_blank=True)
    signature_data = serializers.CharField(required=False, allow_blank=True)

    def validate_field_id(self, value):
        try:
            field = SignatureField.objects.get(id=value)
            if field.is_signed:
                raise serializers.ValidationError("This field has already been signed")
            return value
        except SignatureField.DoesNotExist:
            raise serializers.ValidationError("Invalid field ID")


class BulkSignFieldsSerializer(serializers.Serializer):
    """Serializer for signing multiple fields at once - matches your frontend"""
    signer_id = serializers.UUIDField()
    fields = SignFieldSerializer(many=True)
    session_metadata = serializers.JSONField(required=False, default=dict)

    def validate_signer_id(self, value):
        try:
            signer = DocumentSigner.objects.get(id=value)
            return value
        except DocumentSigner.DoesNotExist:
            raise serializers.ValidationError("Invalid signer ID")

    def validate(self, data):
        signer_id = data['signer_id']
        fields_data = data['fields']

        # Verify all fields belong to the signer
        field_ids = [f['field_id'] for f in fields_data]
        signer_field_ids = list(
            SignatureField.objects.filter(
                signer_id=signer_id
            ).values_list('id', flat=True)
        )

        for field_id in field_ids:
            if field_id not in signer_field_ids:
                raise serializers.ValidationError(
                    f"Field {field_id} does not belong to signer {signer_id}"
                )

        return data
