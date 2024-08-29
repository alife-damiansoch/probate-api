from rest_framework import serializers
from core.models import Solicitor


class AssignedSolicitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Solicitor
        fields = ['id', 'user', 'title', 'first_name', 'last_name', 'own_email', 'own_phone_number']
        read_only_fields = ['id', 'user']
