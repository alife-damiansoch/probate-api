from rest_framework import serializers
from core.models import Document, SignedDocumentLog


class SignedDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'


class SignedDocumentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignedDocumentLog
        fields = '__all__'
