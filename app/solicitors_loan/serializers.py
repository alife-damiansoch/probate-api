"""
Serializers for solicitors-application apis
"""
from cryptography.fernet import Fernet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from app import settings
from core.models import (Application, Deceased, Dispute, Applicant, Document, )
from expense.serializers import ExpenseSerializer
from loan.serializers import LoanSerializer
from rest_framework.reverse import reverse


class SolicitorDocumentSerializer(serializers.ModelSerializer):
    """Serializer for uploading document files"""

    class Meta:
        model = Document
        fields = ['id', 'application', 'document', 'original_name', 'is_signed', 'is_undertaking', 'is_loan_agreement',
                  'signature_required', 'who_needs_to_sign']
        read_only_fields = ('id', 'application', 'is_signed', 'is_undertaking', 'is_loan_agreement')
        extra_kwargs = {'document': {'required': True}}


class SolicitorDeceasedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deceased
        fields = ['first_name', 'last_name']


class SolicitorDisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = ['details']


class SolicitorApplicantSerializer(serializers.ModelSerializer):
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


class SolicitorApplicationSerializer(serializers.ModelSerializer):
    """serializer for application list"""
    applicants = SolicitorApplicantSerializer(
        many=True, required=True)
    loan = LoanSerializer(read_only=True)

    class Meta:
        model = Application
        fields = ['id', 'amount', 'term', 'approved', 'is_rejected', 'rejected_date', 'rejected_reason',
                  'date_submitted', 'undertaking_ready', 'applicants',
                  'loan_agreement_ready', 'solicitor', 'loan']
        read_only_fields = ('id', 'approved', 'last_updated_by', 'date_submitted', 'undertaking_ready',
                            'loan_agreement_ready', 'is_rejected', 'rejected_date', 'rejected_reason', 'applicants',
                            'loan')


class SolicitorApplicationDetailSerializer(SolicitorApplicationSerializer):
    """serializer for applicant details"""
    deceased = SolicitorDeceasedSerializer(required=True)  # Serializer for the Deceased model
    dispute = SolicitorDisputeSerializer(required=True)  # Serializer for the Dispute model
    applicants = SolicitorApplicantSerializer(
        many=True, required=True)
    estate_summary = serializers.SerializerMethodField(read_only=True)
    documents = serializers.SerializerMethodField(read_only=True)
    signed_documents = serializers.SerializerMethodField(read_only=True)
    expenses = ExpenseSerializer(many=True, read_only=True)

    class Meta(SolicitorApplicationSerializer.Meta):
        fields = SolicitorApplicationSerializer.Meta.fields + [
            'deceased', 'dispute', 'applicants', 'documents', 'signed_documents',
            'expenses', 'was_will_prepared_by_solicitor', 'estate_summary'
        ]

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
            deceased = SolicitorDeceasedSerializer.create(SolicitorDeceasedSerializer(), validated_data=deceased_data)
        if dispute_data:
            dispute = SolicitorDisputeSerializer.create(SolicitorDisputeSerializer(), validated_data=dispute_data)

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
            deceased_serializer = SolicitorDeceasedSerializer(instance=instance.deceased, data=deceased_data,
                                                              partial=True)
            deceased_serializer.is_valid(raise_exception=True)
            deceased_serializer.save()

        if dispute_data is not None:
            dispute_serializer = SolicitorDisputeSerializer(instance=instance.dispute, data=dispute_data, partial=True)
            dispute_serializer.is_valid(raise_exception=True)
            dispute_serializer.save()

        # Fetch current applicants and estates related to this application
        current_applicants = Applicant.objects.filter(application=instance)

        # Convert current applicants and estates to a dictionary keyed by a unique combination of fields
        current_applicants_dict = {
            (applicant.first_name, applicant.last_name, applicant.pps_number): applicant
            for applicant in current_applicants
        }

        # Track applicants and estates to keep
        applicants_to_keep = []
        estates_to_keep = []

        # Update or create applicants
        for applicant_data in applicants_data:
            key = (applicant_data.get('first_name'), applicant_data.get('last_name'), applicant_data.get('pps_number'))
            applicant_instance = current_applicants_dict.get(key)

            if applicant_instance:
                # Update existing applicant
                for attr, value in applicant_data.items():
                    setattr(applicant_instance, attr, value)
                applicant_instance.save()
                applicants_to_keep.append(applicant_instance)
            else:
                # Create new applicant if no match found
                new_applicant = Applicant.objects.create(application=instance, **applicant_data)
                applicants_to_keep.append(new_applicant)

        # Remove applicants not in the new data set
        for applicant in current_applicants:
            if applicant not in applicants_to_keep:
                applicant.delete()

        return instance

    @extend_schema_field(OpenApiTypes.STR)
    def get_documents(self, application):
        # Filtration of documents which aren't signed
        unsigned_documents = application.documents.filter(is_signed=False)
        return SolicitorDocumentSerializer(unsigned_documents, many=True).data

    @extend_schema_field(OpenApiTypes.STR)
    def get_signed_documents(self, application):
        # Filtration of documents which are signed
        signed_documents = application.documents.filter(is_signed=True)
        return SolicitorDocumentSerializer(signed_documents, many=True).data

        return instance
