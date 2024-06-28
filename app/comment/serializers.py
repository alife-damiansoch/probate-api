from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from core.models import Comment


class CommentSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()
    updated_by_email = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'text', 'created_by_email', 'updated_by_email', 'is_completed', 'is_important', 'application']
        read_only_fields = ['id', 'created_by_email', 'updated_by_email']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request', None)

        if request and request.method in ['PUT', 'PATCH']:
            fields['application'].read_only = True

        return fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_created_by_email(self, obj):
        return obj.created_by.email if obj.created_by else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_updated_by_email(self, obj):
        return obj.updated_by.email if obj.updated_by else None
