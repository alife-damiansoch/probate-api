# document_requirements/serializers.py - Complete serializers file

from rest_framework import serializers
from .models import DocumentType, ApplicationDocumentRequirement
from core.models import Document


class DocumentTypeSerializer(serializers.ModelSerializer):
    usage_count = serializers.SerializerMethodField()
    can_generate_template = serializers.SerializerMethodField()

    class Meta:
        model = DocumentType
        fields = [
            'id',
            'name',
            'description',
            'signature_required',
            'who_needs_to_sign',
            'order',
            'has_template',
            'usage_count',
            'can_generate_template'
        ]

    def get_usage_count(self, obj):
        """Return how many applications use this document type"""
        return ApplicationDocumentRequirement.objects.filter(document_type=obj).count()

    def get_can_generate_template(self, obj):
        """Check if this document type can generate templates"""
        from .services import DocumentTemplateService
        return DocumentTemplateService.can_generate_template(obj)


class SimpleDocumentSerializer(serializers.ModelSerializer):
    """Simplified document serializer for nested use"""

    class Meta:
        model = Document
        fields = [
            'id',
            'original_name',
            'is_signed',
            'created_at'
        ]


class ApplicationDocumentRequirementSerializer(serializers.ModelSerializer):
    document_type = DocumentTypeSerializer(read_only=True)
    document_type_id = serializers.IntegerField(write_only=True)
    is_uploaded = serializers.ReadOnlyField()
    uploaded_document = SimpleDocumentSerializer(read_only=True)
    created_by_name = serializers.SerializerMethodField()

    # Template-related fields
    template_available = serializers.SerializerMethodField()
    template_download_url = serializers.SerializerMethodField()
    template_filename = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationDocumentRequirement
        fields = [
            'id',
            'document_type',
            'document_type_id',
            'is_uploaded',
            'uploaded_document',
            'created_at',
            'created_by_name',
            'template_available',
            'template_download_url',
            'template_filename'
        ]

    def get_created_by_name(self, obj):
        """Get the user's email as display name"""
        if obj.created_by and obj.created_by.email:
            return obj.created_by.email
        return "System"

    def get_template_available(self, obj):
        """Check if template can be generated for this requirement"""
        from .services import DocumentTemplateService
        return DocumentTemplateService.can_generate_template(obj.document_type)

    def get_template_download_url(self, obj):
        """Get template download URL if template is available"""
        from .services import DocumentTemplateService
        if DocumentTemplateService.can_generate_template(obj.document_type):
            return f'/api/applications/{obj.application.id}/document-requirements/{obj.id}/download-template/'
        return None

    def get_template_filename(self, obj):
        """Get template filename if template is available"""
        from .services import DocumentTemplateService
        if DocumentTemplateService.can_generate_template(obj.document_type):
            return DocumentTemplateService.get_filename(obj)
        return None

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class RequirementStatusSerializer(serializers.Serializer):
    """Serializer for requirement status summary"""
    application_id = serializers.IntegerField()
    total_requirements = serializers.IntegerField()
    uploaded_count = serializers.IntegerField()
    missing_count = serializers.IntegerField()
    completion_percentage = serializers.FloatField()
    requirements = ApplicationDocumentRequirementSerializer(many=True)

    # Breakdown by signature requirement
    signature_required_count = serializers.IntegerField()
    signature_uploaded_count = serializers.IntegerField()

    # Recent activity
    last_requirement_added = serializers.DateTimeField(allow_null=True)
    last_document_uploaded = serializers.DateTimeField(allow_null=True)

    # Template availability summary
    templates_available_count = serializers.SerializerMethodField()

    def get_templates_available_count(self, obj):
        """Count how many requirements have templates available"""
        from .services import DocumentTemplateService
        requirements = obj.get('requirements', [])
        if isinstance(requirements, list) and requirements:
            # If requirements is already serialized data
            return sum(1 for req in requirements if req.get('template_available', False))
        else:
            # If requirements is queryset, we need to check each one
            count = 0
            for req_data in requirements:
                if hasattr(req_data, 'document_type'):
                    if DocumentTemplateService.can_generate_template(req_data.document_type):
                        count += 1
            return count
