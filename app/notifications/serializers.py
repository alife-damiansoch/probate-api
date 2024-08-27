from rest_framework import serializers
from django.contrib.auth.models import User
from core.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()  # Use SerializerMethodField to get the email
    recipient_email = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'recipient_email', 'text', 'seen', 'timestamp', 'created_by_email', 'application']
        read_only_fields = ['id', 'recipient_email', 'text', 'timestamp', 'created_by_email', 'application']

    def get_created_by_email(self, obj):
        """Return the email of the user who created the notification."""
        if obj.created_by:
            return obj.created_by.email  # Fetch the email from the User model
        return None  # Return None if created_by is None

    def get_recipient_email(self, obj):
        if obj.recipient:
            return obj.recipient.email  # Fetch the email from the User model
        return None  # Return None if recipient is None
