# communications/serializers.py
from rest_framework import serializers
from core.models import EmailLog, Application, UserEmailLog


class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = '__all__'


# The SendEmailSerializer is also defined here
class SendEmailSerializerByApplicationId(serializers.Serializer):
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


class SendEmailToRecipientsSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=255)
    message = serializers.CharField()
    recipients = serializers.ListField(
        child=serializers.EmailField(), allow_empty=False
    )  # List of recipient email addresses
    attachments = serializers.ListField(
        child=serializers.FileField(), required=False, allow_empty=True
    )


class DownloadAttachmentSerializer(serializers.Serializer):
    email_id = serializers.IntegerField(required=True)
    filename = serializers.CharField(required=True)


class ReplyEmailSerializer(serializers.Serializer):
    email_log_id = serializers.IntegerField()  # The ID of the original email log to reply to
    message = serializers.CharField()
    attachments = serializers.ListField(
        child=serializers.FileField(allow_empty_file=True, use_url=False),
        required=False,
        allow_null=True,
    )

    def validate_email_log_id(self, value):
        try:
            EmailLog.objects.get(id=value)
        except EmailLog.DoesNotExist:
            raise serializers.ValidationError("Invalid email log ID.")
        return value


class ReplyUserEmailSerializer(serializers.Serializer):
    email_log_id = serializers.IntegerField()  # The ID of the original user email log to reply to
    message = serializers.CharField()
    attachments = serializers.ListField(
        child=serializers.FileField(allow_empty_file=True, use_url=False),
        required=False,
        allow_null=True,
    )

    def validate_email_log_id(self, value):
        try:
            UserEmailLog.objects.get(id=value)
        except UserEmailLog.DoesNotExist:
            raise serializers.ValidationError("Invalid user email log ID.")
        return value


class UpdateEmailLogApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = ['application']  # Only allow updating the application field

    def validate_application(self, value):
        # Ensure the application exists
        if not Application.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Application not found.")
        return value


class UpdateEmailLogSeenSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = ['seen']
