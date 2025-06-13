"""
Serializers for solicitors-application apis
"""
from decimal import Decimal

from django.db.models import Sum
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from core.models import (Application, Deceased, Dispute, Applicant, Document, )
from expense.serializers import ExpenseSerializer
from user.serializers import UserSerializer
from loan.serializers import LoanSerializer
from rest_framework.reverse import reverse


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
    # Override the pps_number field to accept plain text from the frontend
    pps_number = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Applicant
        fields = ['title', 'first_name', 'last_name', 'pps_number']

    def get_pps_number(self, obj):
        """Return the decrypted PPS number for GET requests."""
        return obj.decrypted_pps

    def to_representation(self, instance):
        """Decrypt PPS number when sending data to the frontend."""
        ret = super().to_representation(instance)
        ret['pps_number'] = instance.decrypted_pps
        return ret

    def create(self, validated_data):
        """Handle creating a new Applicant."""
        return Applicant.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """Handle updating an Applicant."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


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
                  'currency_sign', "is_new"]
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
    estate_summary = serializers.SerializerMethodField(read_only=True)
    documents = serializers.SerializerMethodField(read_only=True)
    signed_documents = serializers.SerializerMethodField(read_only=True)
    expenses = ExpenseSerializer(many=True, read_only=True)
    value_of_the_estate_after_expenses = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta(AgentApplicationSerializer.Meta):
        fields = AgentApplicationSerializer.Meta.fields + ['deceased', 'applicants', 'estate_summary', 'expenses',
                                                           'value_of_the_estate_after_expenses',
                                                           'dispute', 'documents',
                                                           'signed_documents', 'was_will_prepared_by_solicitor', ]

    def get_estate_summary(self, obj):
        request = self.context.get('request')
        relative_url = reverse('estates-by-application', args=[obj.id])

        if request:
            absolute_url = request.build_absolute_uri(relative_url)

            # Check common proxy headers that indicate original HTTPS request
            is_secure = (
                    request.is_secure() or  # Direct HTTPS
                    request.META.get('HTTP_X_FORWARDED_PROTO') == 'https' or  # Most common
                    request.META.get('HTTP_X_FORWARDED_SSL') == 'on' or
                    request.META.get('HTTP_X_SCHEME') == 'https'
            )

            if is_secure and absolute_url.startswith('http://'):
                absolute_url = absolute_url.replace('http://', 'https://')

            return absolute_url

        return relative_url

    def create(self, validated_data):
        deceased_data = validated_data.pop('deceased', None)
        dispute_data = validated_data.pop('dispute', None)
        applicants_data = validated_data.pop('applicants', [])

        if deceased_data:
            deceased = AgentDeceasedSerializer.create(AgentDeceasedSerializer(), validated_data=deceased_data)
        if dispute_data:
            dispute = AgentDisputeSerializer.create(AgentDisputeSerializer(), validated_data=dispute_data)

        application = Application.objects.create(deceased=deceased if deceased_data else None,
                                                 dispute=dispute if dispute_data else None, **validated_data)
        for applicant_data in applicants_data:
            Applicant.objects.create(application=application, **applicant_data)

        return application

    def update(self, instance, validated_data):
        deceased_data = validated_data.pop('deceased', None)
        dispute_data = validated_data.pop('dispute', None)
        applicants_data = validated_data.pop('applicants', [])

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

        # Create new Applicant and Estate instances
        for applicant_data in applicants_data:
            Applicant.objects.create(application=instance, **applicant_data)

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
