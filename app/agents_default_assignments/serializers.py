from django.db.models import Q
from rest_framework import serializers

from core.models import Assignment, User, Application, Loan
from user.serializers import TeamSerializer


class SimpleUserSerializer(serializers.ModelSerializer):
    """Serializer to handle user ID and read-only email."""
    teams = TeamSerializer(many=True, read_only=True)  # Use the TeamSerializer
    applications_owed_len = serializers.SerializerMethodField()
    advancements_owed_len = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'is_active', 'country', 'teams', 'applications_owed_len',
                  'advancements_owed_len']
        read_only_fields = ['email']  # Ensure email is read-only

    def get_applications_owed_len(self, obj):
        # Replace `user_field` with the actual field name that links the Application model to the User model.

        return Application.objects.filter(user=obj, is_rejected=False, approved=False).count()

    def get_advancements_owed_len(self, obj):
        return Loan.objects.filter(
            application__user=obj,
            is_settled=False,
            is_paid_out=False
        ).filter(
            Q(is_committee_approved=True) | Q(is_committee_approved__isnull=True)
        ).count()


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
