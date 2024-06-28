"""
Serializers for solicitors-application apis
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from core.models import (Application, Deceased, Dispute, Applicant, Estate, Document, )
from expense.serializers import ExpenseSerializer


class SolicitorDocumentSerializer(serializers.ModelSerializer):
    """Serializer for uploading document files"""

    class Meta:
        model = Document
        fields = ['id', 'application', 'document', 'original_name', 'is_signed', 'is_undertaking', 'is_loan_agreement']
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
    class Meta:
        model = Applicant
        fields = ['title', 'first_name', 'last_name', 'pps_number']


class SolicitorEstateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estate
        fields = ['description', 'value']


class SolicitorApplicationSerializer(serializers.ModelSerializer):
    """serializer for application list"""

    class Meta:
        model = Application
        fields = ['id', 'amount', 'term', 'approved', 'is_rejected', 'rejected_date', 'rejected_reason',
                  'date_submitted', 'undertaking_ready',
                  'loan_agreement_ready']
        read_only_fields = ('id', 'approved', 'last_updated_by', 'date_submitted', 'assigned_to', 'undertaking_ready',
                            'loan_agreement_ready', 'is_rejected', 'rejected_date', 'rejected_reason')


class SolicitorApplicationDetailSerializer(SolicitorApplicationSerializer):
    """serializer for applicant details"""
    deceased = SolicitorDeceasedSerializer(required=True)  # Serializer for the Deceased model
    dispute = SolicitorDisputeSerializer(required=True)  # Serializer for the Dispute model
    applicants = SolicitorApplicantSerializer(
        many=True, required=True)
    estates = SolicitorEstateSerializer(
        many=True, required=True)
    documents = serializers.SerializerMethodField(read_only=True)
    signed_documents = serializers.SerializerMethodField(read_only=True)
    expenses = ExpenseSerializer(many=True, read_only=True)

    class Meta(SolicitorApplicationSerializer.Meta):
        fields = SolicitorApplicationSerializer.Meta.fields + ['deceased', 'dispute', 'applicants', 'estates',
                                                               'documents',
                                                               'signed_documents', 'expenses']

    def create(self, validated_data):
        deceased_data = validated_data.pop('deceased', None)
        dispute_data = validated_data.pop('dispute', None)
        applicants_data = validated_data.pop('applicants', [])
        estates_data = validated_data.pop('estates', [])

        if deceased_data:
            deceased = SolicitorDeceasedSerializer.create(SolicitorDeceasedSerializer(), validated_data=deceased_data)
        if dispute_data:
            dispute = SolicitorDisputeSerializer.create(SolicitorDisputeSerializer(), validated_data=dispute_data)

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
            deceased_serializer = SolicitorDeceasedSerializer(instance=instance.deceased, data=deceased_data,
                                                              partial=True)
            deceased_serializer.is_valid(raise_exception=True)
            deceased_serializer.save()

        if dispute_data is not None:
            dispute_serializer = SolicitorDisputeSerializer(instance=instance.dispute, data=dispute_data, partial=True)
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
        return SolicitorDocumentSerializer(unsigned_documents, many=True).data

    @extend_schema_field(OpenApiTypes.STR)
    def get_signed_documents(self, application):
        # Filtration of documents which are signed
        signed_documents = application.documents.filter(is_signed=True)
        return SolicitorDocumentSerializer(signed_documents, many=True).data

        return instance
