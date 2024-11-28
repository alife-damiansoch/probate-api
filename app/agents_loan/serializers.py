"""
Serializers for solicitors-application apis
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from core.models import (Application, Deceased, Dispute, Applicant, Estate, Document, )
from expense.serializers import ExpenseSerializer
from user.serializers import UserSerializer
from loan.serializers import LoanSerializer


class AgentDocumentSerializer(serializers.ModelSerializer):
    """Serializer for uploading document files"""

    class Meta:
        model = Document
        fields = ['id', 'application', 'document', 'original_name', 'is_signed', 'is_undertaking', 'is_loan_agreement']
        read_only_fields = ('id', 'application',)
        extra_kwargs = {'document': {'required': True}}


class AgentDeceasedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deceased
        fields = ['first_name', 'last_name']


class AgentDisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = ['details']


class AgentApplicantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Applicant
        fields = ['title', 'first_name', 'last_name', 'pps_number']


class AgentEstateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estate
        fields = ['description', 'value']


class AgentApplicationSerializer(serializers.ModelSerializer):
    """serializer for application list"""

    user = UserSerializer(read_only=True)
    assigned_to_email = serializers.SerializerMethodField()
    loan = LoanSerializer(read_only=True)
    last_updated_by_email = serializers.SerializerMethodField()
    applicants = AgentApplicantSerializer(
        many=True, required=True)
    currency_sign = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ['id', 'amount', 'term', 'approved', 'is_rejected', 'rejected_date', 'rejected_reason',
                  'date_submitted', 'undertaking_ready', 'last_updated_by', 'applicants', 'solicitor',
                  'loan_agreement_ready', 'user', 'assigned_to', 'assigned_to_email', 'loan', 'last_updated_by_email',
                  'currency_sign']
        read_only_fields = (
            'id', 'last_updated_by_email', 'date_submitted', 'user', 'assigned_to_email', 'loan', 'last_updated_by',
            'applicants', 'solicitor', 'currency_sign')

    @extend_schema_field(serializers.CharField)
    def get_assigned_to_email(self, obj):
        if obj.assigned_to:
            return obj.assigned_to.email
        return None

    @extend_schema_field(serializers.CharField)
    def get_last_updated_by_email(self, obj):
        """Returns the email of the user who last updated the application."""
        if obj.last_updated_by:
            return obj.last_updated_by.email
        return None

    @extend_schema_field(serializers.CharField)
    def get_currency_sign(self, obj):
        """Returns the currency symbol based on the user's country."""
        currency_mapping = {
            "IE": "€",  # Euro for Ireland
            "UK": "£",  # Pound for United Kingdom
            # Add more countries and their currency symbols here
        }

        # Default to Euro if the country is not listed
        if obj.user and obj.user.country:
            return currency_mapping.get(obj.user.country, "€")
        return "€"


class AgentApplicationDetailSerializer(AgentApplicationSerializer):
    """serializer for applicant details"""
    deceased = AgentDeceasedSerializer(required=True)  # Serializer for the Deceased model
    dispute = AgentDisputeSerializer(required=True)  # Serializer for the Dispute model
    applicants = AgentApplicantSerializer(
        many=True, required=True)
    estates = AgentEstateSerializer(
        many=True, required=True)
    documents = serializers.SerializerMethodField(read_only=True)
    signed_documents = serializers.SerializerMethodField(read_only=True)
    expenses = ExpenseSerializer(many=True, read_only=True)
    value_of_the_estate_after_expenses = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta(AgentApplicationSerializer.Meta):
        fields = AgentApplicationSerializer.Meta.fields + ['deceased', 'applicants', 'estates', 'expenses',
                                                           'value_of_the_estate_after_expenses',
                                                           'dispute', 'documents',
                                                           'signed_documents']

    def get_value_of_the_estate_after_expenses(self, obj):
        return obj.value_of_the_estate_after_expenses()

    def create(self, validated_data):
        deceased_data = validated_data.pop('deceased', None)
        dispute_data = validated_data.pop('dispute', None)
        applicants_data = validated_data.pop('applicants', [])
        estates_data = validated_data.pop('estates', [])

        if deceased_data:
            deceased = AgentDeceasedSerializer.create(AgentDeceasedSerializer(), validated_data=deceased_data)
        if dispute_data:
            dispute = AgentDisputeSerializer.create(AgentDisputeSerializer(), validated_data=dispute_data)

        application = Application.objects.create(deceased=deceased if deceased_data else None,
                                                 dispute=dispute if dispute_data else None, **validated_data)
        for applicant_data in applicants_data:
            Applicant.objects.create(application=application, **applicant_data)
        for estate_data in estates_data:
            Estate.objects.create(application=application, **estate_data)
        return application

    def update(self, instance, validated_data):
        deceased_data = validated_data.pop('deceased', None)
        dispute_data = validated_data.pop('dispute', None)
        applicants_data = validated_data.pop('applicants', [])
        estates_data = validated_data.pop('estates', [])

        # Update direct attributes of the Application instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update Deceased, Dispute instances related to application
        if deceased_data is not None:
            deceased_serializer = AgentDeceasedSerializer(instance=instance.deceased, data=deceased_data, partial=True)
            deceased_serializer.is_valid(raise_exception=True)
            deceased_serializer.save()

        if dispute_data is not None:
            dispute_serializer = AgentDisputeSerializer(instance=instance.dispute, data=dispute_data, partial=True)
            dispute_serializer.is_valid(raise_exception=True)
            dispute_serializer.save()

        # Delete old Applicant and Estate instances
        Applicant.objects.filter(application=instance.id).delete()
        Estate.objects.filter(application=instance.id).delete()

        # Create new Applicant and Estate instances
        for applicant_data in applicants_data:
            Applicant.objects.create(application=instance, **applicant_data)
        for estate_data in estates_data:
            Estate.objects.create(application=instance, **estate_data)

        return instance

    @extend_schema_field(OpenApiTypes.STR)
    def get_documents(self, application):
        # Filtration of documents which aren't signed
        unsigned_documents = application.documents.filter(is_signed=False)
        return AgentDocumentSerializer(unsigned_documents, many=True).data

    @extend_schema_field(OpenApiTypes.STR)
    def get_signed_documents(self, application):
        # Filtration of documents which are signed
        signed_documents = application.documents.filter(is_signed=True)
        return AgentDocumentSerializer(signed_documents, many=True).data

        return instance
