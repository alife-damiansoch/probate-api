# communications/serializers.py
from rest_framework import serializers
from core.models import EmailLog, Application


class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = '__all__'


# The SendEmailSerializer is also defined here
class SendEmailSerializer(serializers.Serializer):
    sender = serializers.EmailField()
    application_id = serializers.IntegerField()
    subject = serializers.CharField(max_length=255)
    message = serializers.CharField()
    attachments = serializers.ListField(
        child=serializers.FileField(allow_empty_file=True, use_url=False),
        required=False,
        allow_null=True,
    )

    def validate_application_id(self, value):
        try:
            Application.objects.get(id=value)
        except Application.DoesNotExist:
            raise serializers.ValidationError("Invalid application ID.")
        return value


class DownloadAttachmentSerializer(serializers.Serializer):
    email_id = serializers.IntegerField(required=True)
    filename = serializers.CharField(required=True)
