from rest_framework import serializers
from core.models import InternalFile


class InternalFileSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.StringRelatedField(read_only=True)
    application_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = InternalFile
        fields = ['id', 'title', 'description', 'file', 'application', 'application_id',
                  'uploaded_by', 'created_at', 'updated_at', 'is_ccr', 'is_pep_check']
        read_only_fields = ['id', 'application', 'uploaded_by', 'created_at', 'updated_at', 'is_active']

    def create(self, validated_data):
        application_id = validated_data.pop('application_id')
        validated_data['application_id'] = application_id
        return super().create(validated_data)
