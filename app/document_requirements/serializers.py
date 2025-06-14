from rest_framework import serializers
from .models import DocumentType, ApplicationDocumentRequirement
from core.models import Document


class DocumentTypeSerializer(serializers.ModelSerializer):
    usage_count = serializers.SerializerMethodField()

    class Meta:
        model = DocumentType
        fields = [
            'id',
            'name',
            'description',
            'signature_required',
            'who_needs_to_sign',
            'order',
            'usage_count'
        ]

    def get_usage_count(self, obj):
        """Return how many applications use this document type"""
        return ApplicationDocumentRequirement.objects.filter(document_type=obj).count()


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

    class Meta:
        model = ApplicationDocumentRequirement
        fields = [
            'id',
            'document_type',
            'document_type_id',
            'is_uploaded',
            'uploaded_document',
            'created_at',
            'created_by_name'
        ]

    def get_created_by_name(self, obj):
        """Get the user's email as display name"""
        if obj.created_by and obj.created_by.email:
            return obj.created_by.email
        return "System"

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
