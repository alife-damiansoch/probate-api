"""
Serializers for solicitors-application apis
"""
from cryptography.fernet import Fernet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from app import settings
from core.models import (Application, Deceased, Dispute, Applicant, Document, ApplicationProcessingStatus, )
from expense.serializers import ExpenseSerializer
from loan.serializers import LoanSerializer
from rest_framework.reverse import reverse


class SolicitorDocumentSerializer(serializers.ModelSerializer):
    """Serializer for uploading document files"""
    document_type_requirement = serializers.IntegerField(required=False, write_only=True)

    # Add the email-related properties
    is_emailed = serializers.ReadOnlyField()
    email_count = serializers.ReadOnlyField()
    last_emailed_date = serializers.ReadOnlyField()
    emailed_to_recipients = serializers.ReadOnlyField()

    class Meta:
        model = Document
        fields = [
            'id', 'application', 'document', 'original_name', 'is_signed',
            'is_undertaking', 'is_loan_agreement', 'signature_required',
            'who_needs_to_sign', 'document_type_requirement', 'is_terms_of_business', 'is_secci',
            # Add the new email properties
            'is_emailed', 'email_count', 'last_emailed_date', 'emailed_to_recipients'
        ]
        read_only_fields = (
            'id', 'application', 'is_signed', 'is_undertaking', 'is_loan_agreement', 'is_terms_of_business', 'is_secci')
        extra_kwargs = {'document': {'required': True}}

    def create(self, validated_data):
        # Extract the requirement ID (if provided)
        requirement_id = validated_data.pop('document_type_requirement', None)

        # Create the document first
        document = super().create(validated_data)

        # Handle requirement linking if provided
        if requirement_id:
            try:
                from document_requirements.models import ApplicationDocumentRequirement
                requirement = ApplicationDocumentRequirement.objects.get(
                    id=requirement_id,
                    application=document.application
                )

                # Link the document to the requirement
                document.document_type_requirement = requirement

                # Auto-set signature requirements based on DocumentType
                if requirement.document_type.signature_required:
                    document.signature_required = True
                    document.who_needs_to_sign = requirement.document_type.who_needs_to_sign
                else:
                    document.signature_required = False

                # Check if this is a Solicitor Letter of Undertaking
                if "Solicitor Letter of Undertaking" in requirement.document_type.name:
                    document.is_undertaking = True

                # Save with the new fields
                document.save()

            except ApplicationDocumentRequirement.DoesNotExist:
                # If requirement doesn't exist, continue without linking
                pass

        return document


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
    pps_number = serializers.CharField(required=True, allow_blank=False)

    # Add computed fields for convenience
    full_name = serializers.ReadOnlyField()
    full_address = serializers.ReadOnlyField()

    # Custom field for date of birth with proper format - now required
    date_of_birth = serializers.DateField(
        required=True,
        allow_null=False,
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'],
        format='%Y-%m-%d'
    )

    # Make other fields explicitly required
    title = serializers.ChoiceField(choices=Applicant.TITLE_CHOICES, required=True)
    first_name = serializers.CharField(max_length=255, required=True, allow_blank=False)
    last_name = serializers.CharField(max_length=255, required=True, allow_blank=False)
    address_line_1 = serializers.CharField(max_length=255, required=True, allow_blank=False)
    address_line_2 = serializers.CharField(max_length=255, required=False, allow_blank=True)  # Keep optional
    city = serializers.CharField(max_length=100, required=True, allow_blank=False)
    county = serializers.CharField(max_length=100, required=True, allow_blank=False)
    postal_code = serializers.CharField(max_length=20, required=True, allow_blank=False)
    country = serializers.CharField(max_length=100, required=True, allow_blank=False)
    email = serializers.EmailField(max_length=254, required=True, allow_blank=False)
    phone_number = serializers.CharField(max_length=17, required=True, allow_blank=False)

    class Meta:
        model = Applicant
        fields = [
            'id',
            'title',
            'first_name',
            'last_name',
            'pps_number',
            'address_line_1',
            'address_line_2',
            'city',
            'county',
            'postal_code',
            'country',
            'date_of_birth',
            'email',
            'phone_number',
            'full_name',
            'full_address',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'full_name', 'full_address', 'created_at', 'updated_at']

    def get_pps_number(self, obj):
        """Return the decrypted PPS number for GET requests."""
        return obj.decrypted_pps

    def to_representation(self, instance):
        """Decrypt PPS number when sending data to the frontend."""
        ret = super().to_representation(instance)
        ret['pps_number'] = instance.decrypted_pps
        return ret

    def validate(self, data):
        """Additional validation for required fields."""
        required_fields = [
            'title', 'first_name', 'last_name', 'pps_number',
            'address_line_1', 'city', 'county', 'postal_code',
            'date_of_birth', 'email', 'phone_number', 'country'
        ]

        errors = {}
        for field in required_fields:
            value = data.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                field_name = field.replace('_', ' ').title()
                errors[field] = f"{field_name} is required and cannot be empty."

        if errors:
            raise serializers.ValidationError(errors)

        return data

    def create(self, validated_data):
        """Handle creating a new Applicant."""
        return Applicant.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """Handle updating an Applicant."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ApplicationProcessingStatusSerializer(serializers.ModelSerializer):
    last_updated_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ApplicationProcessingStatus
        fields = [
            'application_details_completed_confirmed',
            'solicitor_preferred_aml_method',
            'last_updated_by',
            'date_updated'
        ]
        read_only_fields = ['last_updated_by', 'date_updated']


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
    processing_status = ApplicationProcessingStatusSerializer(read_only=True)

    class Meta(SolicitorApplicationSerializer.Meta):
        fields = SolicitorApplicationSerializer.Meta.fields + [
            'deceased', 'dispute', 'applicants', 'documents', 'signed_documents',
            'expenses', 'was_will_prepared_by_solicitor', 'estate_summary', 'processing_status'
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

        # Fetch current applicants related to this application
        current_applicants = Applicant.objects.filter(application=instance)

        # Create dictionaries for easier lookup
        current_applicants_by_id = {applicant.id: applicant for applicant in current_applicants}
        current_applicants_by_key = {
            (applicant.first_name, applicant.last_name, applicant.decrypted_pps): applicant
            for applicant in current_applicants
        }

        # Track applicants to keep
        applicants_to_keep = []

        # Update or create applicants
        for applicant_data in applicants_data:
            applicant_id = applicant_data.get('id')
            applicant_instance = None

            if applicant_id:
                # If ID is provided, try to find by ID first
                applicant_instance = current_applicants_by_id.get(applicant_id)

            if not applicant_instance:
                # If not found by ID, try to find by key combination
                key = (
                    applicant_data.get('first_name'),
                    applicant_data.get('last_name'),
                    applicant_data.get('pps_number')
                )
                applicant_instance = current_applicants_by_key.get(key)

            if applicant_instance:
                # Update existing applicant
                for attr, value in applicant_data.items():
                    if attr != 'id':  # Don't update the ID
                        setattr(applicant_instance, attr, value)
                applicant_instance.save()
                applicants_to_keep.append(applicant_instance)
            else:
                # Create new applicant if no match found
                # Remove 'id' from applicant_data if present to avoid conflicts
                create_data = {k: v for k, v in applicant_data.items() if k != 'id'}
                new_applicant = Applicant.objects.create(application=instance, **create_data)
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
