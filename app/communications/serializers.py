# communications/serializers.py
from rest_framework import serializers
from core.models import EmailLog


class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = '__all__'


# The SendEmailSerializer is also defined here
class SendEmailSerializer(serializers.Serializer):
    sender = serializers.EmailField()
    recipient = serializers.EmailField()
    subject = serializers.CharField(max_length=255)
    message = serializers.CharField()


class DownloadAttachmentSerializer(serializers.Serializer):
    email_id = serializers.IntegerField(required=True)
    filename = serializers.CharField(required=True)
