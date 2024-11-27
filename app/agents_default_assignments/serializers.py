from rest_framework import serializers

from core.models import Assignment, User
from user.serializers import TeamSerializer


class SimpleUserSerializer(serializers.ModelSerializer):
    """Serializer to handle user ID and read-only email."""
    teams = TeamSerializer(many=True, read_only=True)  # Use the TeamSerializer

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'is_active', 'country', 'teams']
        read_only_fields = ['email']  # Ensure email is read-only


class AssignmentSerializer(serializers.ModelSerializer):
    """Serializer for the Assignment model."""
    staff_user = SimpleUserSerializer(read_only=False)
    agency_user = SimpleUserSerializer(read_only=False)

    class Meta:
        model = Assignment
        fields = ['id', 'staff_user', 'agency_user']


class CreateAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating Assignments."""
    staff_user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_staff=True), source='staff_user',
                                                       write_only=True)
    agency_user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_staff=False),
                                                        source='agency_user', write_only=True)

    class Meta:
        model = Assignment
        fields = ['id', 'staff_user_id', 'agency_user_id']
