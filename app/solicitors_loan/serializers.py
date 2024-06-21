"""
Serializers for application apis
"""
from rest_framework import serializers
from core.models import (Application, Deceased, Dispute, Applicant, Estate, Document, )


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for uploading document files"""

    class Meta:
        model = Document
        fields = ['id', 'application', 'document', 'original_name', 'is_signed', 'is_undertaking', 'is_loan_agreement']
        read_only_fields = ('id', 'application', 'is_signed', 'is_undertaking', 'is_loan_agreement')
        extra_kwargs = {'document': {'required': True}}


class DeceasedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deceased
        fields = ['first_name', 'last_name']


class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = ['details']


class ApplicantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Applicant
        fields = ['title', 'first_name', 'last_name', 'pps_number']


class EstateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estate
        fields = ['description', 'value']


class ApplicationSerializer(serializers.ModelSerializer):
    """serializer for application list"""

    class Meta:
        model = Application
        fields = ['id', 'amount', 'term', 'approved', 'date_submitted', 'undertaking_ready',
                  'loan_agreement_ready']
        read_only_fields = ('id', 'approved', 'last_updated_by', 'date_submitted', 'assigned_to', 'undertaking_ready',
                            'loan_agreement_ready')


class ApplicationDetailSerializer(ApplicationSerializer):
    """serializer for applicant details"""
    deceased = DeceasedSerializer(required=True)  # Serializer for the Deceased model
    dispute = DisputeSerializer(required=True)  # Serializer for the Dispute model
    applicants = ApplicantSerializer(
        many=True, required=True)
    estates = EstateSerializer(
        many=True, required=True)
    documents = serializers.SerializerMethodField(read_only=True)
    signed_documents = serializers.SerializerMethodField(read_only=True)

    class Meta(ApplicationSerializer.Meta):
        fields = ApplicationSerializer.Meta.fields + ['deceased', 'dispute', 'applicants', 'estates', 'documents',
                                                      'signed_documents']

    def create(self, validated_data):
        deceased_data = validated_data.pop('deceased', None)
        dispute_data = validated_data.pop('dispute', None)
        applicants_data = validated_data.pop('applicants', [])
        estates_data = validated_data.pop('estates', [])

        if deceased_data:
            deceased = DeceasedSerializer.create(DeceasedSerializer(), validated_data=deceased_data)
        if dispute_data:
            dispute = DisputeSerializer.create(DisputeSerializer(), validated_data=dispute_data)

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
            deceased_serializer = DeceasedSerializer(instance=instance.deceased, data=deceased_data, partial=True)
            deceased_serializer.is_valid(raise_exception=True)
            deceased_serializer.save()

        if dispute_data is not None:
            dispute_serializer = DisputeSerializer(instance=instance.dispute, data=dispute_data, partial=True)
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

    def get_documents(self, application):
        # Filtration of documents which aren't signed
        unsigned_documents = application.documents.filter(is_signed=False)
        return DocumentSerializer(unsigned_documents, many=True).data

    def get_signed_documents(self, application):
        # Filtration of documents which are signed
        signed_documents = application.documents.filter(is_signed=True)
        return DocumentSerializer(signed_documents, many=True).data

        return instance
