from rest_framework import serializers
from core.models import Expense


class ExpenseSerializer(serializers.ModelSerializer):
    """Serializer for the Expense model."""

    class Meta:
        model = Expense
        fields = ('id', 'description', 'value', 'application',)
        read_only_fields = ('id',)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request', None)

        if request and request.method in ['PUT', 'PATCH']:
            fields['application'].read_only = True

        return fields

    def update(self, instance, validated_data):
        validated_data.pop('application', None)  # Ignore application if passed in update request
        return super().update(instance, validated_data)
