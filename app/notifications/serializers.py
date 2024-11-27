from rest_framework import serializers
from core.models import Notification

from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes


class NotificationSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()  # Use SerializerMethodField to get the email
    recipient_email = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()  # Add a new SerializerMethodField for country

    class Meta:
        model = Notification
        fields = ['id', 'recipient_email', 'text', 'seen', 'timestamp', 'created_by_email', 'application', 'country']
        read_only_fields = ['id', 'recipient_email', 'text', 'timestamp', 'created_by_email', 'application', 'country']

    @extend_schema_field(OpenApiTypes.STR)
    def get_created_by_email(self, obj):
        """Return the email of the user who created the notification."""
        if obj.created_by:
            return obj.created_by.email  # Fetch the email from the User model
        return None  # Return None if created_by is None

    @extend_schema_field(OpenApiTypes.STR)
    def get_recipient_email(self, obj):
        """Return the email of the recipient."""
        if obj.recipient:
            return obj.recipient.email  # Fetch the email from the User model
        return None  # Return None if recipient is None

    @extend_schema_field(OpenApiTypes.STR)
    def get_country(self, obj):
        """Return the country from application.user."""
        if obj.application and obj.application.user:
            return obj.application.user.country  # Fetch the country from application.user
        return None  # Return None if application or user is None
