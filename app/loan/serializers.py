"""
Serializers for the Loan APIs
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from core.models import (Loan, Transaction, LoanExtension, User)
from loanbook.models import LoanBook
from loanbook.serializers import LoanBookSerializer


class TransactionSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = ['id', 'loan', 'amount', 'transaction_date', 'created_by_email', 'description']
        read_only_fields = ['id', 'created_by_email', 'transaction_date']

    @extend_schema_field(serializers.CharField)
    def get_created_by_email(self, obj):
        return obj.created_by.email

    def update(self, instance, validated_data):
        """
        You can either remove 'loan' from the validated data
        or throw a validation error if 'loan' is in the data
        """
        if 'loan' in validated_data:
            raise serializers.ValidationError({"loan": "Cannot update loan for a transaction"})

        return super().update(instance, validated_data)


class LoanExtensionSerializer(serializers.ModelSerializer):
    created_by_email = serializers.SerializerMethodField()

    class Meta:
        model = LoanExtension
        fields = ['id', 'loan', 'extension_term_months', 'extension_fee', 'description', 'created_by_email',
                  'created_date']
        read_only_fields = ['id', 'created_by_email', 'created_date']

    @extend_schema_field(serializers.CharField)
    def get_created_by_email(self, obj):
        return obj.created_by.email

    def update(self, instance, validated_data):
        """
        You can either remove 'loan' from the validated data
        or throw a validation error if 'loan' is in the data
        """
        if 'loan' in validated_data:
            raise serializers.ValidationError({"loan": "Cannot update loan for the extension"})

        return super().update(instance, validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User  # Replace `User` with the correct model name if different
        fields = ['id', 'email']  #


class LoanSerializer(serializers.ModelSerializer):
    amount_paid = serializers.SerializerMethodField()
    extension_fees_total = serializers.SerializerMethodField()
    current_balance = serializers.SerializerMethodField()
    maturity_date = serializers.SerializerMethodField()
    last_updated_by_email = serializers.SerializerMethodField()
    approved_by_email = serializers.SerializerMethodField()
    assigned_to_email = serializers.SerializerMethodField()
    committee_approvements_status = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    currency_sign = serializers.SerializerMethodField()
    loanbook_data = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = [
            'id', 'amount_agreed', 'fee_agreed', 'amount_paid', 'extension_fees_total', 'current_balance',
            'term_agreed', 'approved_date', 'is_settled', 'settled_date', 'maturity_date', 'approved_by_email',
            'last_updated_by_email', 'application', 'assigned_to_email', 'is_paid_out', 'paid_out_date',
            'pay_out_reference_number',
            'committee_approvements_status', 'needs_committee_approval', 'is_committee_approved', 'country',
            'currency_sign', 'loanbook_data'
            # New fields added here
        ]
        read_only_fields = [
            'id', 'extension_fees_total', 'current_balance', 'maturity_date', 'approved_by_email',
            'last_updated_by_email', 'committee_approvements_status', 'needs_committee_approval',
            'is_committee_approved', 'country', 'currency_sign'
        ]
        extra_kwargs = {"application": {'required': True}}

    def get_loanbook_data(self, obj):
        try:
            return LoanBookSerializer(obj.loanbook).data
        except LoanBook.DoesNotExist:
            return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_currency_sign(self, obj):
        """Returns the currency symbol based on the application's user country."""
        currency_mapping = {
            "IE": "€",  # Euro for Ireland
            "UK": "£",  # Pound for United Kingdom
            # Add more countries and their currency symbols here
        }

        # Ensure application and user exist, then get the country
        if obj.application and obj.application.user:
            country = obj.application.user.country
            return currency_mapping.get(country, "€")  # Default to Euro if country not found
        return "€"

    @extend_schema_field(OpenApiTypes.STR)
    def get_country(self, obj):
        """Retrieve the country of the loan's associated application user."""
        if obj.application and obj.application.user:
            return obj.application.user.country
        return None  # Return None if the application or user is not available

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_amount_paid(self, obj):
        return obj.amount_paid

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_extension_fees_total(self, obj):
        return obj.extension_fees_total

    @extend_schema_field(OpenApiTypes.NUMBER)
    def get_current_balance(self, obj):
        return obj.current_balance

    @extend_schema_field(OpenApiTypes.DATE)
    def get_maturity_date(self, obj):
        return obj.maturity_date

    @extend_schema_field(OpenApiTypes.STR)
    def get_last_updated_by_email(self, obj):
        return obj.last_updated_by.email if obj.last_updated_by else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_approved_by_email(self, obj):
        return obj.approved_by.email if obj.approved_by else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_assigned_to_email(self, obj):
        return obj.application.assigned_to.email if obj.application and obj.application.assigned_to else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_committee_approvements_status(self, obj):
        return obj.committee_approvements_status
