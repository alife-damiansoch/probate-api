"""
Serializers for the Loan APIs
"""
from rest_framework import serializers
from core.models import (Loan, Transaction, LoanExtension)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'loan', 'amount', 'transaction_date', 'created_by', 'description']
        read_only_fields = ['id', 'created_by', 'transaction_date']

    def update(self, instance, validated_data):
        """
        You can either remove 'loan' from the validated data
        or throw a validation error if 'loan' is in the data
        """
        if 'loan' in validated_data:
            raise serializers.ValidationError({"loan": "Cannot update loan for a transaction"})

        return super().update(instance, validated_data)


class LoanExtensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanExtension
        fields = ['id', 'loan', 'extension_term_months', 'extension_fee', 'description', 'created_by', 'created_date']
        read_only_fields = ['id', 'created_by', 'created_date']

    def update(self, instance, validated_data):
        """
        You can either remove 'loan' from the validated data
        or throw a validation error if 'loan' is in the data
        """
        if 'loan' in validated_data:
            raise serializers.ValidationError({"loan": "Cannot update loan for a transaction"})

        return super().update(instance, validated_data)


class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = ['id', 'amount_agreed', 'fee_agreed', 'amount_paid', 'extension_fees_total', 'current_balance',
                  'term_agreed', 'approved_date', 'is_settled', 'settled_date', 'maturity_date', 'approved_by',
                  'last_updated_by', 'application']
        read_only_fields = ['id', 'extension_fees_total', 'current_balance', 'maturity_date', 'approved_by',
                            'last_updated_by']
        extra_kwargs = {"application": {'required': True}}
