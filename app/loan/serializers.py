"""
Serializers for the Loan APIs
"""
from rest_framework import serializers
from core.models import (Loan)


class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = ['id', 'amount_agreed', 'fee_agreed', 'amount_paid', 'extension_fees_total', 'current_balance',
                  'term_agreed', 'approved_date', 'is_settled', 'settled_date', 'maturity_date', 'approved_by',
                  'last_updated_by', 'application']
        read_only_fields = ['id', 'extension_fees_total', 'current_balance', 'maturity_date', 'approved_by',
                            'last_updated_by']
        extra_kwargs = {"application": {'required': True}}
